import json
import base64
import os
import re
import datetime
from html import unescape

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from bs4 import BeautifulSoup
import torch
from transformers import (
    BertForSequenceClassification, 
    BertTokenizerFast,
    AutoModelForTokenClassification,
    AutoTokenizer
)
import logging

from backend.workflow_pipeline.database import SessionLocal, TokenStore
from backend.workflow_pipeline.auth import save_token_to_db
from fastapi import APIRouter, HTTPException

router = APIRouter()

# ========== SETUP LOGGING ==========
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ========== BERT CLASSIFIER LOADING ==========
CLASSIFIER_MODEL_ID = "ashahrour/email-classifier"

tokenizer = BertTokenizerFast.from_pretrained(CLASSIFIER_MODEL_ID)
model = BertForSequenceClassification.from_pretrained(CLASSIFIER_MODEL_ID)
model.eval()


# ========== REJECTION PATTERNS ==========
REJECTION_PATTERNS = re.compile(
    r'\b('
    r'rejection|declined|not selected|unfortunately|'
    r'unable to proceed|regret to inform|move forward|'
    r'other (qualified )?candidates|position (has been )?filled|'
    r'rejected|not moving forward|candidate pool|'
    r"we('ve| have) decided|after careful consideration|"
    r'although we were impressed|pursue other candidates|'
    r'wish you (luck|success) in your (job )?search|'
    r'(does not|not) align (with|to) our needs'
    r')\b',
    flags=re.IGNORECASE
)

CLEANING_CONFIG = {
    "truncate_length": 1000,
    "clean_patterns": [
        r'http\S+',                # URLs
        r'\S+@\S+',                # Email addresses
        r'(?<!\w)[^\w\s,.!?:;()\[\]"\'`](?!\w)',  # Special chars
        r'\s+',
    ]
}

# ========== GET GMAIL SERVICE ==========
def get_gmail_service(user_email: str):
    db = SessionLocal()
    token_entry = db.query(TokenStore).filter(TokenStore.user_id == user_email).first()
    db.close()
    
    if not token_entry:
        raise Exception(f"No stored token found for {user_email}. Please re-authenticate.")
    
    creds = Credentials(
        token=token_entry.token,
        refresh_token=token_entry.refresh_token,
        token_uri=token_entry.token_uri,
        client_id=token_entry.client_id,
        client_secret=token_entry.client_secret,
        scopes=token_entry.scopes.split(","),
    )
    
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_token_to_db(creds, user_email)
    
    return build("gmail", "v1", credentials=creds)

# ========== CLEAN HTML CONTENT ==========
def clean_html_content(content: str) -> str:
    if not content:
        return ""

    soup = BeautifulSoup(content, "html.parser")

    # Preserve link text before removing link tags
    for link in soup.find_all('a'):
        link_text = link.get_text(strip=True)
        if link_text:
            link.replace_with(f"{link_text} ")

    # Remove unwanted elements
    for tag in soup(["script", "style", "head", "meta", "link", "img", "button"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    text = unescape(text)

    # Apply cleaning patterns
    for pattern in CLEANING_CONFIG["clean_patterns"]:
        text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)

    # Final cleanup
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:CLEANING_CONFIG["truncate_length"]]

# ========== EXTRACT BODY FROM PARTS ==========
def extract_body_from_parts(parts):
    body_content = []
    html_content = []

    def process_part(part):
        mime_type = part.get("mimeType", "")
        data = part.get("body", {}).get("data", "")

        if data:
            try:
                decoded = base64.urlsafe_b64decode(data).decode("utf-8")
                if mime_type == "text/plain":
                    body_content.append(decoded)
                elif mime_type == "text/html":
                    html_content.append(decoded)
            except Exception:
                pass

        for subpart in part.get("parts", []):
            process_part(subpart)

    for part in parts:
        process_part(part)

    if body_content:
        return clean_html_content(" ".join(body_content))
    elif html_content:
        return clean_html_content(" ".join(html_content))
    else:
        return ""

# ========== CHECK IF REJECTION ==========
def is_rejection(subject: str, body: str) -> bool:
    """Use single regex scan across subject+body to detect rejections."""
    content = f"{subject} {body}".lower()
    return bool(REJECTION_PATTERNS.search(content))

# ========== CLASSIFY EMAIL FUNCTION ==========
def classify_email(text):
    """Returns 'confirmation' or 'unrelated'."""
    inputs = tokenizer(
        text, 
        truncation=True, 
        padding="max_length", 
        max_length=512,  # Must match training
        return_tensors="pt"
    )
    with torch.no_grad():
        outputs = model(**inputs)
    probs = torch.nn.functional.softmax(outputs.logits, dim=1)
    # Argmax: 0 => unrelated, 1 => confirmation
    return "confirmation" if probs.argmax().item() == 1 else "unrelated"

# ========== ENTITY EXTRACTOR CLASS (NER MODEL) ==========
class EntityExtractor:
    """
    Loads a token classification model (e.g., fine-tuned on 'COMPANY' and 'POSITION')
    and extracts these entities from text.
    """
    def __init__(self, model_dir_or_name: str):
        self.device = torch.device("cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir_or_name)
        self.model = AutoModelForTokenClassification.from_pretrained(model_dir_or_name)
        self.model.eval()
        self.model.to(self.device)

    def predict(self, text, max_length=256):
        """
        Returns: {
          "companies": [list of distinct company strings],
          "positions": [list of distinct position strings],
        }
        """
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=max_length,
            return_offsets_mapping=True
        )
        offset_mapping = inputs.pop("offset_mapping")
        inputs = inputs.to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)

        predictions = torch.argmax(outputs.logits, dim=-1)[0].cpu().numpy()
        offset_mapping = offset_mapping[0].numpy()

        companies = self._extract_entities(text, offset_mapping, predictions, "COMPANY")
        positions = self._extract_entities(text, offset_mapping, predictions, "POSITION")

        return {
            "companies": companies,
            "positions": positions
        }

    def _extract_entities(self, text, offset_mapping, preds, entity_type):
        entities = []
        current_entity = []
        current_offsets = []

        id2label = self.model.config.id2label  # e.g., {0: 'O', 1: 'B-COMPANY', ...}

        for idx, (pred, (start, end)) in enumerate(zip(preds, offset_mapping)):
            # Skip special tokens where start==end
            if start == end:
                continue

            label = id2label[pred]

            # B-<ENTITY>
            if label == f"B-{entity_type}":
                # If we were already building something, close it off
                if current_entity:
                    entities.append(self._get_text(text, current_offsets))
                current_entity = [text[start:end]]
                current_offsets = [(start, end)]

            # I-<ENTITY>
            elif label == f"I-{entity_type}" and current_entity:
                current_entity.append(text[start:end])
                current_offsets.append((start, end))

            else:
                # If we encounter a label that's outside the current entity
                if current_entity:
                    entities.append(self._get_text(text, current_offsets))
                    current_entity = []
                    current_offsets = []

        # If ended while still building an entity
        if current_entity:
            entities.append(self._get_text(text, current_offsets))

        return entities

    def _get_text(self, text, offsets):
        if not offsets:
            return ""
        start = offsets[0][0]
        end = offsets[-1][1]
        return text[start:end]

# ========== FETCH AND CLASSIFY EMAILS ==========
def fetch_and_classify_emails(service):
    """
    Fetch new emails (per your query),
    skip rejection emails,
    classify them (confirmation/unrelated),
    and if 'confirmation' => run the EntityExtractor to get company + position.
    """
    query = "newer_than:2d"  # Adjust as needed
    try:
        response = service.users().messages().list(
            userId="me", 
            q=query, 
            maxResults=50
        ).execute()
        messages = response.get("messages", [])
    except Exception as e:
        logger.error(f"Error fetching emails: {str(e)}")
        return

    # -- Load NER extractor model once --
    # Change this path to the folder containing: config.json, model.safetensors, tokenizer.json, merges.txt, etc.
    extractor_model_id = "ashahrour/email-extractor"
    extractor = EntityExtractor(extractor_model_id)

    confirmations = []
    non_job_emails = []

    for msg in messages:
        try:
            msg_data = service.users().messages().get(
                userId="me", 
                id=msg["id"], 
                format='full',
                metadataHeaders=['Subject', 'From', 'Date']
            ).execute()
            
            payload = msg_data.get("payload", {})
            headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
            subject = headers.get("Subject", "No Subject")

            # Extract body
            if 'parts' in payload:
                body = extract_body_from_parts(payload['parts'])
            else:
                data = payload.get("body", {}).get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            cleaned_body = clean_html_content(body)

            # Combine subject + body
            final_text = f"{subject} {cleaned_body}"

            # Skip any rejection
            if is_rejection(subject, cleaned_body):
                continue

            # Classify
            prediction = classify_email(final_text)
            if prediction == "confirmation":
                # Run NER extraction
                result = extractor.predict(final_text)
                companies_found = result["companies"][0] if result["companies"] else None
                positions_found = result["positions"][0] if result["positions"] else None

                confirmations.append((subject, companies_found, positions_found))
            else:
                non_job_emails.append(subject)

        except Exception as e:
            logger.error(f"Error processing email {msg['id']}: {str(e)}")

# ========== MAIN ENTRY POINT ==========
if __name__ == "__main__":
    user_email = "ashahrourr@gmail.com"
    service = get_gmail_service(user_email)
    fetch_and_classify_emails(service)

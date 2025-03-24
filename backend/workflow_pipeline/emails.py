# emails.py
import json
import base64
import os
import re
import asyncio
import datetime
from html import unescape
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource
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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.workflow_pipeline.database import async_session, TokenStore
from backend.workflow_pipeline.auth import save_token_to_db
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()

# ========== GLOBAL CONFIG ==========
CLASSIFIER_MODEL_ID = "ashahrour/email-classifier"
EXTRACTOR_MODEL_ID = "ashahrour/email-extractor"
CLEANING_CONFIG = {
    "truncate_length": 1000,
    "clean_patterns": [
        r'http\S+', r'\S+@\S+',
        r'(?<!\w)[^\w\s,.!?:;()\[\]"\'`](?!\w)', r'\s+',
    ]
}
REJECTION_PATTERNS = re.compile(
    r'\b(rejection|declined|not selected|unfortunately|unable to proceed|'
    r'regret to inform|move forward|other (qualified )?candidates|'
    r'position (has been )?filled|rejected|not moving forward|candidate pool|'
    r"we('ve| have) decided|after careful consideration|"
    r'although we were impressed|pursue other candidates|'
    r'wish you (luck|success) in your (job )?search|'
    r'(does not|not) align (with|to) our needs)\b', 
    flags=re.IGNORECASE
)

# ========== PRELOAD MODELS ==========
logger.info("Loading ML models...")
CLASSIFIER_MODEL = BertForSequenceClassification.from_pretrained(CLASSIFIER_MODEL_ID)
CLASSIFIER_MODEL.eval()
TOKENIZER = BertTokenizerFast.from_pretrained(CLASSIFIER_MODEL_ID)

# Thread pool for CPU-intensive tasks
executor = ThreadPoolExecutor(max_workers=4)

# ========== ENTITY EXTRACTOR CLASS ==========
class EntityExtractor:
    """NER model for extracting companies and positions from text"""
    def __init__(self, model_name: str):
        self.device = torch.device("cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForTokenClassification.from_pretrained(model_name)
        self.model.eval()
        self.model.to(self.device)
        self.id2label = self.model.config.id2label

    def predict(self, text: str, max_length: int = 256) -> dict:
        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True,
            max_length=max_length, return_offsets_mapping=True
        )
        offset_mapping = inputs.pop("offset_mapping")[0].numpy()
        inputs = inputs.to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            
        preds = torch.argmax(outputs.logits, dim=-1)[0].cpu().numpy()
        return {
            "companies": self._extract_entities(text, offset_mapping, preds, "COMPANY"),
            "positions": self._extract_entities(text, offset_mapping, preds, "POSITION")
        }

    def _extract_entities(self, text: str, offsets: list, preds: list, entity_type: str) -> list:
        entities = []
        current_entity = []
        current_offsets = []

        for pred, (start, end) in zip(preds, offsets):
            if start == end:
                continue  # Skip special tokens

            label = self.id2label[pred]
            if label == f"B-{entity_type}":
                if current_entity:
                    entities.append(self._get_text(text, current_offsets))
                current_entity = [text[start:end]]
                current_offsets = [(start, end)]
            elif label == f"I-{entity_type}" and current_entity:
                current_entity.append(text[start:end])
                current_offsets.append((start, end))
            elif current_entity:
                entities.append(self._get_text(text, current_offsets))
                current_entity = []
                current_offsets = []

        if current_entity:
            entities.append(self._get_text(text, current_offsets))
        return entities

    @staticmethod
    def _get_text(text: str, offsets: list) -> str:
        return text[offsets[0][0]:offsets[-1][1]]

# Initialize extractor once
EXTRACTOR = EntityExtractor(EXTRACTOR_MODEL_ID)

# ========== CORE FUNCTIONALITY ==========
async def get_gmail_service(user_email: str) -> Resource:
    """Get authenticated Gmail service with token refresh"""
    async with async_session() as db:
        result = await db.execute(select(TokenStore).where(TokenStore.user_id == user_email))
        token_entry = result.scalar_one_or_none()

    if not token_entry:
        raise ValueError(f"No Gmail token found for {user_email}")

    creds = Credentials(
        token=token_entry.token,
        refresh_token=token_entry.refresh_token,
        token_uri=token_entry.token_uri,
        client_id=token_entry.client_id,
        client_secret=token_entry.client_secret,
        scopes=token_entry.scopes.split(","),
    )

    if creds.expired:
        await asyncio.to_thread(creds.refresh, Request())
        await save_token_to_db(creds, user_email)

    return build("gmail", "v1", credentials=creds)

@lru_cache(maxsize=1000)
def clean_html_content(content: str) -> str:
    """Clean and normalize email HTML content with caching"""
    if not content:
        return ""

    soup = BeautifulSoup(content, "html.parser")
    for link in soup.find_all('a'):
        if link_text := link.get_text(strip=True):
            link.replace_with(f"{link_text} ")
    for tag in soup(["script", "style", "head", "meta", "link", "img", "button"]):
        tag.decompose()

    text = unescape(soup.get_text(separator=" "))
    for pattern in CLEANING_CONFIG["clean_patterns"]:
        text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', text).strip()[:CLEANING_CONFIG["truncate_length"]]

def extract_body_from_payload(payload: dict) -> str:
    """Extract email body from Gmail API payload"""
    def process_part(part):
        if 'parts' in part:
            return ''.join(process_part(p) for p in part['parts'])
        if data := part.get('body', {}).get('data'):
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        return ''

    body = process_part(payload)
    return clean_html_content(body)

async def fetch_and_classify_emails(service: Resource) -> List[Dict]:
    """Fetch and process emails concurrently"""
    try:
        messages = await asyncio.get_event_loop().run_in_executor(
            None, lambda: service.users().messages().list(
                userId="me", q="newer_than:24h", maxResults=50
            ).execute().get('messages', [])
        )
    except Exception as e:
        logger.error(f"Gmail API error: {e}")
        return []

    return await asyncio.gather(*[
        _process_email(service, msg['id']) for msg in messages
    ])

async def _process_email(service: Resource, msg_id: str) -> Optional[Dict]:
    """Process individual email with error handling"""
    try:
        msg_data = await asyncio.get_event_loop().run_in_executor(
            None, lambda: service.users().messages().get(
                userId="me", id=msg_id, format='full'
            ).execute()
        )

        payload = msg_data.get('payload', {})
        headers = {h['name']: h['value'] for h in payload.get('headers', [])}
        subject = headers.get('Subject', 'No Subject')
        body = extract_body_from_payload(payload)

        if is_rejection(subject, body):
            return None

        # Parallel processing of heavy ML tasks
        prediction, entities = await asyncio.gather(
            asyncio.get_event_loop().run_in_executor(
                executor, lambda: _classify_email(f"{subject} {body}")
            ),
            asyncio.get_event_loop().run_in_executor(
                executor, lambda: EXTRACTOR.predict(f"{subject} {body}")
            ),
        )

        if prediction == "confirmation":
            return {
                "subject": subject,
                "company": entities["companies"][0] if entities["companies"] else None,
                "position": entities["positions"][0] if entities["positions"] else None
            }
        return None
    except Exception as e:
        logger.error(f"Error processing email: {e}")
        return None

def _classify_email(text: str) -> str:
    """Classify email text using pre-loaded model"""
    inputs = TOKENIZER(
        text, truncation=True, padding="max_length",
        max_length=512, return_tensors="pt"
    )
    with torch.no_grad():
        outputs = CLASSIFIER_MODEL(**inputs)
    return "confirmation" if outputs.logits.argmax() == 1 else "unrelated"

def is_rejection(subject: str, body: str) -> bool:
    """Check if email is a rejection using regex patterns"""
    return bool(REJECTION_PATTERNS.search(f"{subject} {body}".lower()))

# ========== MAIN EXECUTION ==========
if __name__ == "__main__":
    async def main():
        service = await get_gmail_service("ashahrourr@gmail.com")
        results = await fetch_and_classify_emails(service)
        print(f"Processed {len([r for r in results if r])} emails")
    
    asyncio.run(main())
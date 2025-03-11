import re
import json
import base64
from html import unescape
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from fastapi import APIRouter, HTTPException
from google.auth.transport.requests import Request
from backend.database import SessionLocal, TokenStore
import datetime
from datetime import datetime, timedelta
import pytz
from backend.auth import save_token_to_db
import time
import logging
import pickle
import os

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Load the trained email classifier model ---
MODEL_FILENAME = os.path.join(os.path.dirname(__file__), "email_classifier_v1741655564.pkl")
email_classifier_model = None

try:
    with open(MODEL_FILENAME, "rb") as f:
        email_classifier_model = pickle.load(f)
    logger.info("ML model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load ML model: {str(e)}")
    raise RuntimeError("Email classifier model failed to initialize")

def get_gmail_service(user_email: str):
    """Retrieve Gmail API credentials for a specific user"""
    db = SessionLocal()
    token_entry = db.query(TokenStore).filter(TokenStore.user_id == user_email).first()
    db.close()

    if not token_entry:
        raise HTTPException(status_code=401, detail="User not authenticated")

    creds = Credentials(
        token=token_entry.token,
        refresh_token=token_entry.refresh_token,
        token_uri=token_entry.token_uri,
        client_id=token_entry.client_id,
        client_secret=token_entry.client_secret,
        scopes=token_entry.scopes.split(","),
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_token_to_db(creds, user_email)
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise HTTPException(status_code=401, detail="Token refresh failed")

    return build("gmail", "v1", credentials=creds)

def clean_html_content(content):
    """
    Clean HTML email content while preserving link text.
    
    - Extracts link text so that if the entity (e.g. "Software Engineer") is displayed as a link,
      the text is preserved.
    - Removes unwanted tags, URLs, emails, punctuation, and numbers.
    """
    soup = BeautifulSoup(content, "html.parser")
    
    # Preserve link text: replace <a> tags with their inner text
    for link in soup.find_all('a'):
        link_text = link.get_text(strip=True)
        if link_text:
            link.replace_with(f"{link_text} ")
    
    # Remove unwanted tags (script, style, head, meta, link)
    for tag in soup(["script", "style", "head", "meta", "link"]):
        tag.decompose()
    
    text = soup.get_text(separator=" ")
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Additional cleaning: remove any leftover URLs, email addresses, punctuation, and numbers.
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'\S+@\S+', '', text)
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\d+', '', text)
    return text

def extract_body_from_parts(parts):
    """Recursively extract email body content from multipart messages."""
    body_content = []
    html_content = []

    def process_part(part):
        nonlocal body_content, html_content
        mime_type = part.get("mimeType", "")
        data = part.get("body", {}).get("data", "")
        
        if data:
            try:
                decoded = base64.urlsafe_b64decode(data).decode("utf-8")
                if mime_type == "text/plain":
                    body_content.append(clean_html_content(decoded))
                elif mime_type == "text/html" and not body_content:
                    html_content.append(decoded)
            except Exception as e:
                logger.error(f"Error decoding part: {str(e)}")

        for subpart in part.get("parts", []):
            process_part(subpart)

    for part in parts:
        process_part(part)

    if body_content:
        return " ".join(body_content)
    if html_content:
        return clean_html_content(" ".join(html_content))
    return ""

def classify_job_email(subject, body):
    """Classify email using the ML classifier model.
       Matches the training format: subject + space + body.
    """
    if not email_classifier_model:
        logger.error("Classifier model not available")
        return "not_job"

    try:
        email_text = f"{subject} {body}"
        prediction = email_classifier_model.predict([email_text])[0]
        return prediction
    except Exception as e:
        logger.error(f"Classification error: {str(e)}")
        return "not_job"

def fetch_and_classify_emails(service):
    """Fetch emails via the Gmail API and classify each email using the ML model."""
    confirmations = []
    rejections = []

    # Date range setup for today's emails in EST
    est = pytz.timezone("America/New_York")
    utc = pytz.utc
    now_est = datetime.now(est)
    today_est = now_est.date()
    
    start_time = est.localize(datetime.combine(today_est, datetime.min.time()))
    end_time = est.localize(datetime.combine(today_est, datetime.max.time()))
    
    query = f"after:{int(start_time.astimezone(utc).timestamp())} " \
            f"before:{int(end_time.astimezone(utc).timestamp())}"

    try:
        messages = []
        page_token = None
        
        while True:
            result = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=500,
                pageToken=page_token
            ).execute()
            
            messages.extend(result.get("messages", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break

        for msg in messages:
            try:
                msg_data = service.users().messages().get(
                    userId="me", 
                    id=msg["id"],
                    format="full"
                ).execute()
                
                payload = msg_data.get("payload", {})
                headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
                subject = headers.get("Subject", "No Subject")
                
                # Extract body content from multipart or single-part messages
                if "parts" in payload:
                    body = extract_body_from_parts(payload["parts"])
                else:
                    data = payload.get("body", {}).get("data", "")
                    body = clean_html_content(
                        base64.urlsafe_b64decode(data).decode("utf-8")
                    ) if data else ""
                
                classification = classify_job_email(subject, body)
                entry = {
                    "id": msg["id"],
                    "subject": subject,
                    "snippet": msg_data.get("snippet", ""),
                    "body": body[:200]  # Truncated for storage
                }

                if classification == "confirmation":
                    confirmations.append(entry)
                elif classification == "rejection":
                    rejections.append(entry)

            except Exception as e:
                logger.error(f"Error processing message {msg['id']}: {str(e)}")

    except Exception as e:
        logger.error(f"Gmail API error: {str(e)}")
        raise

    return confirmations, rejections

def save_classified_emails(confirmations, rejections):
    """Save the classified confirmation and rejection emails to JSON files."""
    try:
        if confirmations:
            with open("job_confirmations.json", "w") as f:
                json.dump({
                    "emails": [{
                        "subject": e["subject"],
                        "body": e["body"],
                        "company": "",
                        "position": ""
                    } for e in confirmations]
                }, f, indent=2)

        if rejections:
            with open("job_rejections.json", "w") as f:
                json.dump({
                    "emails": [{
                        "subject": e["subject"],
                        "body": e["body"]
                    } for e in rejections]
                }, f, indent=2)
                
    except Exception as e:
        logger.error(f"File save error: {str(e)}")

if __name__ == "__main__":
    try:
        # Replace with the actual user email
        user_email = "ashahrourr@gmail.com"  
        service = get_gmail_service(user_email)
        confirmations, rejections = fetch_and_classify_emails(service)
        save_classified_emails(confirmations, rejections)
        
        print(f"Found {len(confirmations)} confirmations and {len(rejections)} rejections")
        print("Results saved to job_confirmations.json and job_rejections.json")
        
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
        exit(1)

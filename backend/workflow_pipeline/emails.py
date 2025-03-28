# emails.py (Production-Ready Version)
import json
import base64
import os
import re
import asyncio
import time
import logging
from functools import lru_cache
from typing import List, Dict, Optional, Tuple
from html import unescape
from concurrent.futures import ThreadPoolExecutor

import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource
from google.auth.transport.requests import Request
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter
from dotenv import load_dotenv

from backend.workflow_pipeline.database import async_session, TokenStore
from backend.workflow_pipeline.auth import save_token_to_db

load_dotenv(dotenv_path="../.env")

logger = logging.getLogger(__name__)
router = APIRouter()

# ========== PRODUCTION CONFIG ==========
CLASSIFIER_API_URL = "https://api-inference.huggingface.co/models/ashahrour/email-classifier"
EXTRACTOR_API_URL = "https://api-inference.huggingface.co/models/ashahrour/email-extractor"
API_HEADERS = {"Authorization": f"Bearer {os.getenv('HF_API_TOKEN')}"}

PROD_CONFIG = {
    "truncate_length": 1000,
    "max_batch_size": 5,
    "max_email_length": 450,
    "min_entity_confidence": 0.85,
    "clean_patterns": [
        r'http\S+', r'\S+@\S+',
        r'(?<!\w)[^\w\s,.!?:;()\[\]"\'`](?!\w)', r'\s+',
    ],
    "api_retries": 5,
    "retry_delay": 10,
    "rate_limit_delay": 1.5,
}

REJECTION_PATTERNS = re.compile(
    r'\b(rejection|declined|not selected|unfortunately|unable to proceed|'
    r'regret to inform|move forward|other (qualified )?candidates|'
    r'position (has been )?filled|rejected|not moving forward|candidate pool|'
    r"we('ve| have) decided|after careful consideration"
    r'although we were impressed|pursue other candidates|'
    r'wish you (luck|success) in your (job )?search|'
    r'(does not|not) align (with|to) our needs)\b', 
    flags=re.IGNORECASE
)

# ========== CORE FUNCTIONALITY ==========
async def get_gmail_service(user_email: str) -> Resource:
    """Authenticate with Gmail API with token refresh and validation"""
    async with async_session() as db:
        result = await db.execute(select(TokenStore).where(TokenStore.user_id == user_email))
        token_entry = result.scalar_one_or_none()

    if not token_entry:
        logger.error(f"No Gmail token found for {user_email}")
        raise ValueError(f"Authentication required for {user_email}")

    creds = Credentials(
        token=token_entry.token,
        refresh_token=token_entry.refresh_token,
        token_uri=token_entry.token_uri,
        client_id=token_entry.client_id,
        client_secret=token_entry.client_secret,
        scopes=token_entry.scopes.split(","),
    )

    if creds.expired and creds.refresh_token:
        logger.info(f"Refreshing token for {user_email}")
        await asyncio.to_thread(creds.refresh, Request())
        await save_token_to_db(creds, user_email)

    return build("gmail", "v1", credentials=creds)

@lru_cache(maxsize=2000)
def clean_html_content(content: str) -> str:
    """Sanitize and normalize email content with caching"""
    if not content:
        return ""

    try:
        soup = BeautifulSoup(content, "html.parser")
        # Preserve text links
        for link in soup.find_all('a'):
            if link_text := link.get_text(strip=True):
                link.replace_with(f"{link_text} ")
        # Remove non-content elements
        for tag in soup(["script", "style", "head", "meta", "link", "img", "button"]):
            tag.decompose()

        text = unescape(soup.get_text(separator=" "))
        # Aggressive cleaning
        for pattern in PROD_CONFIG["clean_patterns"]:
            text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', text).strip()[:PROD_CONFIG["truncate_length"]]
    except Exception as e:
        logger.error(f"Content cleaning failed: {str(e)}")
        return ""

async def fetch_and_classify_emails(service: Resource) -> List[Dict]:
    """Main processing pipeline with production safeguards"""
    try:
        messages = await asyncio.get_event_loop().run_in_executor(
            None, lambda: service.users().messages().list(
                userId="me", q="newer_than:24h", maxResults=50
            ).execute().get('messages', [])
        )
    except Exception as e:
        logger.error(f"Gmail API error: {str(e)}")
        return []

    # Phase 1: Email collection and preprocessing
    valid_emails = []
    for msg in messages:
        try:
            msg_data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: service.users().messages().get(
                    userId="me", id=msg['id'], format='full'
                ).execute()
            )
            payload = msg_data.get('payload', {})
            headers = {h['name']: h['value'] for h in payload.get('headers', [])}
            subject = headers.get('Subject', 'No Subject')
            body = extract_body_from_payload(payload)

            if not body or is_rejection(subject, body):
                continue

            email_text = f"{subject} {body}"[:PROD_CONFIG["max_email_length"]]
            valid_emails.append(email_text)
        except Exception as e:
            logger.warning(f"Skipping email {msg.get('id')}: {str(e)}")
            continue

    # Phase 2: Batch classification
    batches = [
        valid_emails[i:i+PROD_CONFIG["max_batch_size"]] 
        for i in range(0, len(valid_emails), PROD_CONFIG["max_batch_size"])
    ]
    
    confirmed_emails = []
    for batch in batches:
        classifications = _classify_email_batch(batch)
        confirmed_emails.extend([
            email for email, label in zip(batch, classifications)
            if label == "confirmation"
        ])
        time.sleep(PROD_CONFIG["rate_limit_delay"])  # Rate limiting

    # Phase 3: Entity extraction
    results = []
    entity_batches = _call_extractor_api_batch(confirmed_emails)
    
    for text, entities in zip(confirmed_emails, entity_batches):
        company = next((
            e['word'] for e in entities
            if e.get('entity_group') == 'COMPANY'
            and e.get('score', 0) >= PROD_CONFIG["min_entity_confidence"]
        ), None)
        
        position = next((
            e['word'] for e in entities
            if e.get('entity_group') == 'POSITION'
            and e.get('score', 0) >= PROD_CONFIG["min_entity_confidence"]
        ), "Unknown Position")

        if company:
            results.append({
                "company": company,
                "job_title": position,
                "source_snippet": text[:100] + "..."
            })

    logger.info(f"Processed {len(results)} valid job confirmations")
    return results

# ========== API HANDLERS ==========
def _classify_email_batch(email_texts: List[str]) -> List[str]:
    """Batch classification with production safeguards"""
    if not email_texts:
        return []
    
    try:
        payload = {"inputs": email_texts}
        response = _call_with_retry(CLASSIFIER_API_URL, payload)
        
        return [
            "confirmation" if any(
                p['label'] == 'LABEL_1' and p['score'] > 0.7
                for p in preds
            )
            else "unrelated"
            for preds in (response or [])
        ]
    except Exception as e:
        logger.error(f"Classification failed: {str(e)}")
        return ["unrelated"] * len(email_texts)

def _call_extractor_api_batch(texts: List[str]) -> List[List[dict]]:
    """Batch entity extraction with quality control"""
    if not texts:
        return []

    try:
        payload = {"inputs": texts}
        response = _call_with_retry(EXTRACTOR_API_URL, payload)
        return response or [[] for _ in texts]
    except Exception as e:
        logger.error(f"Entity extraction failed: {str(e)}")
        return [[] for _ in texts]

def _call_with_retry(url: str, payload, retries: int = None) -> Optional[list]:
    """Robust API caller with model loading awareness"""
    retries = retries or PROD_CONFIG["api_retries"]
    
    for attempt in range(retries):
        try:
            response = requests.post(
                url,
                headers=API_HEADERS,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code == 503:  # Model loading
                wait_time = int(response.headers.get('estimated-time', 30)) + 5
                logger.info(f"Model loading - waiting {wait_time}s")
                time.sleep(wait_time)
                continue

            logger.warning(
                f"API attempt {attempt+1} failed: {response.status_code} - {response.text[:200]}"
            )
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"API connection error: {str(e)}")

        time.sleep(PROD_CONFIG["retry_delay"] * (attempt + 1))
    
    logger.error(f"API call failed after {retries} retries")
    return None

# ========== UTILITIES ==========
def extract_body_from_payload(payload: dict) -> str:
    """Resilient email body extraction"""
    def process_part(part):
        if 'parts' in part:
            return ''.join(process_part(p) for p in part['parts'])
        if data := part.get('body', {}).get('data'):
            try:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            except Exception as e:
                logger.warning(f"Decoding error: {str(e)}")
                return ""
        return ""
    
    try:
        return clean_html_content(process_part(payload))
    except Exception as e:
        logger.error(f"Body extraction failed: {str(e)}")
        return ""

def is_rejection(subject: str, body: str) -> bool:
    """Check for rejection patterns with context awareness"""
    combined = f"{subject.lower()} {body.lower()}"
    return bool(REJECTION_PATTERNS.search(combined))

# ========== MAIN EXECUTION ==========
if __name__ == "__main__":
    async def production_main():
        """Production entry point with error handling"""
        try:
            service = await get_gmail_service("ashahrourr@gmail.com")
            results = await fetch_and_classify_emails(service)
            print(json.dumps(results, indent=2))
        except Exception as e:
            logger.critical(f"Fatal error: {str(e)}")
            raise

    asyncio.run(production_main())
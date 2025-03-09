import os
import re
import json
import base64
import pickle
from html import unescape
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from fastapi import APIRouter, HTTPException
from google.auth.transport.requests import Request
from backend.database import SessionLocal, TokenStore
import datetime
from backend.auth import save_token_to_db
import time
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Load the trained email classifier model ---
MODEL_FILENAME = os.path.join(os.path.dirname(__file__), "email_classifier.pkl")
with open(MODEL_FILENAME, "rb") as f:
    email_classifier_model = pickle.load(f)


def get_gmail_service(user_email: str):
    """
    Retrieve Gmail API credentials for a specific user and refresh if expired.
    """
    db = SessionLocal()
    token_entry = db.query(TokenStore).filter(TokenStore.user_id == user_email).first()
    db.close()

    if not token_entry:
        raise Exception(f"No stored token found for {user_email}. Please re-authenticate at /auth/login.")

    creds = Credentials(
        token=token_entry.token,
        refresh_token=token_entry.refresh_token,
        token_uri=token_entry.token_uri,
        client_id=token_entry.client_id,
        client_secret=token_entry.client_secret,
        scopes=token_entry.scopes.split(","),
    )

    # Refresh the token if it is expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save the refreshed token for the user
        save_token_to_db(creds, user_email)

    return build("gmail", "v1", credentials=creds)


def clean_html_content(content):
    """
    Given a string that might contain HTML, parse with BeautifulSoup,
    remove script/style tags, and return a nicely stripped plain-text version.
    - Normalizes extra whitespace.
    - Converts HTML entities (like &nbsp;) to normal text.
    """
    soup = BeautifulSoup(content, "html.parser")

    # Remove script and style elements
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Get the text and do a basic normalization of whitespace
    text = soup.get_text(separator=" ")
    text = unescape(text)           # Convert HTML entities
    text = " ".join(text.split())   # Remove excessive whitespace/newlines
    return text


def extract_body_from_parts(parts):
    """
    Recursively traverse the payload parts to find 'text/plain' or 'text/html'.
    If no text/plain is found, fallback to text/html, then clean the HTML.
    """
    queue = list(parts)
    html_fallback = None

    while queue:
        part = queue.pop()
        mime_type = part.get("mimeType", "")
        data = part.get("body", {}).get("data", "")

        if data:
            decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        else:
            decoded = ""

        # 1) If it's text/plain, we still want to run it through clean_html_content
        #    in case it has partial HTML or inline tags. 
        if mime_type == "text/plain" and decoded:
            return clean_html_content(decoded)

        # 2) If it's text/html, hold onto it as a fallback if we never find a plain-text part
        if mime_type == "text/html" and decoded:
            # We'll use the *first* HTML fallback encountered
            if html_fallback is None:
                html_fallback = decoded

        # 3) Check sub-parts recursively
        sub_parts = part.get("parts", [])
        if sub_parts:
            queue.extend(sub_parts)

    # If we get here and never found a "text/plain" part, but we do have HTML:
    if html_fallback:
        return clean_html_content(html_fallback)

    # If there's no text content at all, return empty
    return ""


def classify_job_email(subject, body):
    """
    Use the ML model to classify the email.
    The model expects a single string input (e.g. subject + " " + body).
    Depending on your training, your model might output labels like "confirmation",
    "rejection", or "not_job". The additional post-processing step (checking for
    rejection keywords) is optional if your model doesn't already differentiate.
    """
    text = f"{subject} {body}"
    # The model expects a list of texts as input.
    prediction = email_classifier_model.predict([text])[0]

    # Optional: If your model outputs "confirmation" but you want to further check for rejection
    if prediction == "confirmation":
        rejection_keywords = [
            "unfortunately", "we will not be moving forward", "other candidates",
            "although we were impressed", "regret to inform", "not selected",
            "position has been filled", "more qualified candidates", "not move forward",
            "not move forward with your application",
            "we have decided to pursue other candidates",
            "after careful consideration", "candidate whose experience more closely matches",
            "no longer under consideration", "not proceed with your application",
            "at this time we will not", "however, after reviewing", "difficult decision",
            "we received a large number of applications",
            "email_jobs_application_rejected_", "after careful review", "at this time", "after careful consideration"
        ]
        if any(kw in text.lower() for kw in rejection_keywords):
            return "rejection"

    return prediction


def fetch_and_classify_emails(service):
    """
    Fetch ALL messages from 'today' that appear to be job-related (based on the subject).
    Then classify them into confirmations or rejections using the ML-based classifier.
    """
    confirmations = []
    rejections = []

    # Build the query (only for "today")
    today = datetime.datetime.utcnow().date()
    query = (
    '("thank you for applying" OR "application received" OR "we received your application" '
    'OR "your application has been received" OR "your job application" '
    'OR "application submission confirmation" OR "linkedIn job application" OR "indeed application confirmation" '
    'OR "your application was sent to" OR "we are reviewing your application" '
    'OR "next steps in the hiring process") '
    f'after:{today.strftime("%Y/%m/%d")}'
    )


    # Batch settings
    batch_size = 100  # Fetch 100 emails per batch
    next_page_token = None

    while True:
        # Fetch a batch of emails
        response = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=batch_size,
            pageToken=next_page_token
        ).execute()

        messages = response.get("messages", [])
        if not messages:
            break  # No more emails

        # Process each email in the batch
        for msg in messages:
            msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
            payload = msg_data.get("payload", {})
            headers = payload.get("headers", [])

            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            snippet = msg_data.get("snippet", "")

            # Extract the body
            if "parts" in payload:
                body = extract_body_from_parts(payload["parts"])
            else:
                data = payload.get("body", {}).get("data", "")
                if data:
                    body = clean_html_content(base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore"))
                else:
                    body = clean_html_content(snippet)

            # Classify the email using the ML model
            classification = classify_job_email(subject, body)
            if classification == "confirmation":
                confirmations.append({
                    "id": msg["id"],
                    "subject": subject,
                    "snippet": snippet,
                    "body": body[:200],  # Truncate to 200 characters
                })
            elif classification == "rejection":
                rejections.append({
                    "id": msg["id"],
                    "subject": subject,
                    "snippet": snippet,
                    "body": body[:200],
                })

        # Break if no more pages
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

        # Add a delay to avoid hitting API rate limits
        time.sleep(1)

    return confirmations, rejections


def daily_email_fetch_job():
    try:
        service = get_gmail_service()
        confirmations, rejections = fetch_and_classify_emails(service)
        logger.info(f"Processed {len(confirmations)} confirmations and {len(rejections)} rejections.")
    except Exception as e:
        logger.error(f"Error in daily email fetch: {e}")


def save_confirmations_to_json(confirmations, filename="job_confirmations.json"):
    """
    Saves only the job confirmations into a JSON file with the fields:
    subject, body (500 chars), company (empty), position (empty).
    """
    data = {"emails": []}
    for email in confirmations:
        data["emails"].append({
            "subject": email["subject"],
            "body": email["body"],  # truncated to 500 chars
            "company": "",
            "position": ""
        })

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def save_rejections_to_json(rejections, filename="job_rejections.json"):
    """
    Saves only the job rejections into a JSON file with the fields:
    subject, body (500 chars).
    """
    data = {"emails": []}
    for email in rejections:
        data["emails"].append({
            "subject": email["subject"],
            "body": email["body"]
        })

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    service = get_gmail_service("your_email@example.com")  # Replace with a valid email
    confirmations, rejections = fetch_and_classify_emails(service)

    # --- Print results to console ---
    num_confirmations = len(confirmations)
    num_rejections = len(rejections)

    print(f"\n🟢 Found {num_confirmations} Confirmation Emails:")
    print(f"\n🔴 Found {num_rejections} Rejection Emails:")

    # --- Save only the confirmations to a JSON file ---
    save_confirmations_to_json(confirmations, filename="job_confirmations.json")
    print(
        f"\n✅ Saved {num_confirmations} confirmation emails to 'job_confirmations.json'. "
        "Company/position fields are left empty."
    )

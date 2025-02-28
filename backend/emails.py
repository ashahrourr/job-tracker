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
from backend.auth import save_token_to_db

router = APIRouter()

def get_gmail_service():
    """
    Retrieve Gmail API credentials from the database and refresh if expired.
    """
    db = SessionLocal()
    token_entry = db.query(TokenStore).filter(TokenStore.id == "gmail").first()
    db.close()

    if not token_entry:
        raise Exception("No stored token found. Please re-authenticate at /auth/login.")

    creds = Credentials(
        token=token_entry.token,
        refresh_token=token_entry.refresh_token,
        token_uri=token_entry.token_uri,
        client_id=token_entry.client_id,
        client_secret=token_entry.client_secret,
        scopes=token_entry.scopes.split(","),
    )

    # ✅ Refresh the token if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_token_to_db(creds)  # ✅ Save the refreshed token to the database

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
    Returns 'confirmation' if this is a job application email that doesn't appear to be a rejection,
    'rejection' if it contains job context AND rejection indicators,
    or 'not_job' if it doesn't match job context at all.
    """

    job_keywords = [
        "thank you for applying", "application received", "we received your application",
        "your recent job application", "application for", "your application to",
        "we've received your application", "job application confirmation",
        "thank you for your application", "your application was sent to",
        "indeed application", "thanks for applying"
    ]

    job_patterns = [
        r"thank you for applying to (.+)",
        r"your application to (.+) has been received",
        r"we received your application for (.+)",
        r"application for (.+) at (.+) received"
    ]

    rejection_keywords = [
        "unfortunately", "we will not be moving forward", "other candidates",
        "although we were impressed", "regret to inform", "not selected",
        "position has been filled", "more qualified candidates", "not move forward",
        "not a fit", "not move forward with your application",
        "we have decided to pursue other candidates",
        "after careful consideration", "candidate whose experience more closely matches",
        "no longer under consideration", "not proceed with your application",
        "at this time we will not", "however, after reviewing", "difficult decision",
        "we received a large number of applications",
        # LinkedIn-specific marker for rejections:
        "email_jobs_application_rejected_", "after carful review"
    ]

    subj_lower = subject.lower()
    body_lower = body.lower()

    # 1) Check if it looks like a job email
    found_job_context = any(k in subj_lower or k in body_lower for k in job_keywords)
    if not found_job_context:
        for pattern in job_patterns:
            if re.search(pattern, subj_lower) or re.search(pattern, body_lower):
                found_job_context = True
                break

    if not found_job_context:
        return "not_job"

    # 2) Check if there's a rejection phrase
    has_rejection = any(rk in subj_lower or rk in body_lower for rk in rejection_keywords)
    if has_rejection:
        return "rejection"
    else:
        return "confirmation"



def fetch_and_classify_emails(service):
    """
    Fetch ALL messages from 'today' that appear to be job-related (based on the subject).
    Then classify them into confirmations or rejections using existing logic.
    """
    confirmations = []
    rejections = []

    # 1. Build the query (only for "today")
    start_date = datetime.datetime(2025, 2, 28)
    today = datetime.datetime.utcnow().date()
    query = (
        'subject:("thank you for applying" OR "application received" OR "your application" '
        'OR "job application" OR "your application was sent to" OR "indeed application" '
        'OR "you have applied to" OR "thanks for applying") '
        f'after:{start_date.strftime("%Y/%m/%d")} '  # ✅ Start from Feb 28, 2025
        f'before:{(today + datetime.timedelta(days=1)).strftime("%Y/%m/%d")}'  # ✅ Up to today
    )

    # 2. Get ALL messages (pagination)
    all_messages = []
    next_page_token = None

    while True:
        response = service.users().messages().list(
            userId="me",
            q=query,
            pageToken=next_page_token
        ).execute()

        messages = response.get("messages", [])
        all_messages.extend(messages)

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break  # No more pages

    # 3. For each message, get details & classify
    for msg in all_messages:
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
                raw_decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                body = clean_html_content(raw_decoded)
            else:
                # Fallback to snippet
                body = clean_html_content(snippet)

        # Classify
        classification = classify_job_email(subject, body)
        if classification == "confirmation":
            confirmations.append({
                "id": msg["id"],
                "subject": subject,
                "snippet": snippet,
                "body": body[:200],  # store up to 200 chars
            })
        elif classification == "rejection":
            rejections.append({
                "id": msg["id"],
                "subject": subject,
                "snippet": snippet,
                "body": body[:200],
            })

    return confirmations, rejections


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
    Saves only the job confirmations into a JSON file with the fields:
    subject, body (500 chars), company (empty), position (empty).
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
    service = get_gmail_service()
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
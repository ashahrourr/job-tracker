import datetime
import time
import base64
from googleapiclient.discovery import build
from database import SessionLocal, TokenStore
from auth import save_token_to_db
from bs4 import BeautifulSoup
from fastapi import HTTPException
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import json

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

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_token_to_db(creds, user_email)

    return build("gmail", "v1", credentials=creds)

def clean_html_content(content):
    """
    Parse HTML content and return clean text.
    """
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return " ".join(text.split())

def extract_body_from_parts(parts):
    """
    Extract text from email payload parts.
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

        if mime_type == "text/plain" and decoded:
            return clean_html_content(decoded)

        if mime_type == "text/html" and decoded:
            if html_fallback is None:
                html_fallback = decoded

        sub_parts = part.get("parts", [])
        if sub_parts:
            queue.extend(sub_parts)

    return clean_html_content(html_fallback) if html_fallback else ""

def fetch_non_job_emails(service, user_email):
    """
    Fetch 1,000 emails that are neither job confirmations nor rejections.
    """
    non_job_emails = []

    # Query: Exclude job-related keywords
    query = (
        '-subject:("thank you for applying" OR "application received" OR "job application" '
        'OR "your application was sent to" OR "indeed application" OR "application submitted" '
        'OR "application confirmation") '
        '-body:("thank you for applying" OR "application received" OR "job application" '
        'OR "your application was sent to" OR "indeed application" OR "application submitted" '
        'OR "application confirmation") '
        '-subject:("unfortunately" OR "we regret to inform" OR "not selected" OR "position has been filled") '
        '-body:("unfortunately" OR "we regret to inform" OR "not selected" OR "position has been filled") '
    )

    batch_size = 100
    next_page_token = None

    while len(non_job_emails) < 996:
        response = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=batch_size,
            pageToken=next_page_token
        ).execute()

        messages = response.get("messages", [])
        if not messages:
            break

        for msg in messages:
            if len(non_job_emails) >= 1000:
                break

            msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
            payload = msg_data.get("payload", {})
            headers = payload.get("headers", [])

            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            snippet = msg_data.get("snippet", "")

            if "parts" in payload:
                body = extract_body_from_parts(payload["parts"])
            else:
                data = payload.get("body", {}).get("data", "")
                body = clean_html_content(base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")) if data else clean_html_content(snippet)

            non_job_emails.append({
                "id": msg["id"],
                "subject": subject,
                "snippet": snippet,
                "body": body[:500],  # Truncate to 500 characters
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

        time.sleep(1)

    return non_job_emails

def save_non_job_emails_to_json(non_job_emails, filename="non_job_emails.json"):
    """
    Saves non-job emails to a JSON file.
    """
    data = {"emails": non_job_emails}
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    user_email = "ashahrourr@gmail.com"  # Replace with the actual user email
    service = get_gmail_service(user_email)
    
    non_job_emails = fetch_non_job_emails(service, user_email)
    
    print(f"\n🟢 Found {len(non_job_emails)} Non-Job Emails.")
    
    save_non_job_emails_to_json(non_job_emails, filename="non_job_emails.json")
    
    print("\n✅ Saved to 'non_job_emails.json'.")

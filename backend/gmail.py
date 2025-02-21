import os
import re
import base64
import binascii
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Load Gmail API credentials
def get_gmail_service():
    creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/gmail.readonly"])
    return build("gmail", "v1", credentials=creds)

def safe_b64decode(data):
    """Base64 decoding with padding fixes."""
    try:
        missing_padding = len(data) % 4
        if missing_padding:
            data += "=" * (4 - missing_padding)
        return base64.urlsafe_b64decode(data)
    except (TypeError, binascii.Error):
        return b""

def get_email_body(payload):
    """Recursively extract text/plain content from email parts."""
    body = []
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                if data:
                    decoded = safe_b64decode(data).decode("utf-8", errors="ignore")
                    body.append(decoded)
            elif "multipart/" in part["mimeType"]:
                body.extend(get_email_body(part))
    else:
        if payload["mimeType"] == "text/plain":
            data = payload["body"].get("data", "")
            if data:
                decoded = safe_b64decode(data).decode("utf-8", errors="ignore")
                body.append(decoded)
    return body

def is_job_confirmation_email(subject, body):
    """Improved detection logic."""
    job_patterns = [
        r"thank(s| you) (?:for applying|for your application)",
        r"application (?:received|submitted|confirmation)",
        r"(?:we'?ve|we have) received your (?:application|resume)",
        r"your application (?:to|for) .+ (?:has been|was) received",
        r"thank you for your interest in .+",
        r"we appreciate your interest in .+",
    ]
    text = f"{subject.lower()} {body.lower()}"
    return any(re.search(pattern, text) for pattern in job_patterns)

def parse_email_details(email, headers):
    """
    Extracts Company, Position, and Date Applied details.
    Combines subject, snippet, and body for a more comprehensive search.
    """
    details = {"Company": None, "Position": None, "Date Applied": None}

    # Retrieve Date Applied from headers
    date_header = next((h["value"] for h in headers if h["name"].lower() == "date"), None)
    details["Date Applied"] = date_header if date_header else "Not Found"

    # Combine subject, snippet, and body text for comprehensive searching
    text = f"{email.get('subject', '')}\n{email.get('snippet', '')}\n{email.get('body', '')}"

    # --- Company Extraction ---
    company_patterns = [
        r"applying to\s+([^!.\n]+)",
        r"application to\s+([^!.\n]+)",
        r"at\s+([A-Z][A-Za-z0-9 &,\.-]+)",
        r"joining\s+([A-Za-z0-9 &,\.-]+?)(?=\s*[.,])",
        r"interest in joining\s+([A-Za-z0-9 &,\.-]+?)(?=\s*[.,])",
        r"interest in\s+([A-Za-z0-9 &,\.-]+?)(?=\s*[.,])"
    ]
    for pattern in company_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            details["Company"] = match.group(1).strip()
            break

    # --- Position Extraction ---
    position_patterns = [
        # For emails with an explicit "Position Applied For:" field
        r"Position Applied For:\s*(.+?)(?=\s+Thank you|\s+We appreciated|\s*$)",
        # Pattern matching phrases like "apply for our Data Engineer position"
        r"apply for(?:\s+our)?\s+(.+?)(?=\s+position)",
        # Pattern matching "position of Data Engineer" or "position applied for Data Engineer"
        r"position (?:of|applied for)\s+([^.!?\n]+)",
        # Pattern for "application for" when followed by 'shortly'
        r"application for\s+(.+?)(?=\s+shortly)"
    ]
    for pattern in position_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            details["Position"] = match.group(1).strip()
            break

    return details

def fetch_job_emails(service, max_results=10):
    """Fetch emails with robust body extraction and additional details parsing."""
    query = (
        'subject:("thank you for applying" OR "application received" '
        'OR "your application" OR "job application" OR "we received your application" '
        'OR "we appreciate your interest" OR "thanks for applying" '
        'OR "we have received your application" OR "thank you for your interest in") '
        'newer_than:30d'
    )
    
    result = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    
    emails = []
    for msg in result.get("messages", []):
        msg_data = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        payload = msg_data["payload"]
        headers = payload.get("headers", [])

        subject = next(
            (h["value"] for h in headers if h["name"].lower() == "subject"),
            "No Subject"
        )
        
        # Get the Date header if available
        date_header = next((h["value"] for h in headers if h["name"].lower() == "date"), "No Date")
        
        body_parts = get_email_body(payload)
        body = " ".join(body_parts).strip()
        
        if is_job_confirmation_email(subject, body):
            email_dict = {
                "id": msg["id"],
                "subject": subject,
                "snippet": msg_data.get("snippet", ""),
                "body": body[:1000],  # Store first 1000 characters
                "date": date_header
            }
            # Parse and add additional details
            details = parse_email_details(email_dict, headers)
            email_dict.update(details)
            emails.append(email_dict)
    
    return emails

# Run script to test fetching job emails with extra details
if __name__ == "__main__":
    service = get_gmail_service()
    emails = fetch_job_emails(service, max_results=10)
    
    print("\n📩 **Job Confirmation Emails Found:**")
    for email in emails:
        print(f"\n📌 **Subject:** {email['subject']}")
        print(f"📨 **Snippet:** {email['snippet']}")
        print(f"🏢 **Company:** {email.get('Company', 'Not Found')}")
        print(f"📝 **Position:** {email.get('Position', 'Not Found')}")
        print(f"📅 **Date Applied:** {email.get('Date Applied', 'Not Found')}")
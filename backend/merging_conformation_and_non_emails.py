import json

# File paths
JOB_CONFIRMATIONS_FILE = "job_confirmations.json"
NON_JOB_EMAILS_FILE = "non_job_emails.json"
MERGED_DATASET_FILE = "email_dataset.json"

def load_json(filename):
    """Loads JSON and extracts subject/body fields."""
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)
        emails = data.get("emails", [])
    return emails

def format_dataset(emails, label):
    """
    Convert emails to a consistent format with subject, body, and label.
    """
    formatted_data = []
    for email in emails:
        formatted_data.append({
            "subject": email.get("subject", "").strip(),
            "body": email.get("body", "").strip(),
            "label": label
        })
    return formatted_data

# Load datasets
job_confirmations = load_json(JOB_CONFIRMATIONS_FILE)
non_job_emails = load_json(NON_JOB_EMAILS_FILE)

# Format datasets
job_confirmations_formatted = format_dataset(job_confirmations, "confirmation")
non_job_emails_formatted = format_dataset(non_job_emails, "not_job")

# Merge datasets
merged_dataset = job_confirmations_formatted + non_job_emails_formatted

# Save merged dataset
with open(MERGED_DATASET_FILE, "w", encoding="utf-8") as f:
    json.dump(merged_dataset, f, ensure_ascii=False, indent=4)

print(f"✅ Merged dataset saved as '{MERGED_DATASET_FILE}' with {len(merged_dataset)} entries.")

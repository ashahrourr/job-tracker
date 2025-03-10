from emails import fetch_and_classify_emails, get_gmail_service

service = get_gmail_service("ashahrourr@gmail.com")  # Replace with your email
fetch_and_classify_emails(service)
from transformers import BertTokenizerFast, BertForSequenceClassification, AutoTokenizer, AutoModelForTokenClassification

# Download and cache models
BertTokenizerFast.from_pretrained("ashahrour/email-classifier")
BertForSequenceClassification.from_pretrained("ashahrour/email-classifier")

AutoTokenizer.from_pretrained("ashahrour/email-extractor")
AutoModelForTokenClassification.from_pretrained("ashahrour/email-extractor")

print("✅ All models preloaded and cached.")

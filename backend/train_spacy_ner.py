import spacy
from spacy.training import Example
from spacy.util import minibatch, compounding
import random
import json
import re
from bs4 import BeautifulSoup
from html import unescape
from sklearn.model_selection import train_test_split
import time

def find_all_occurrences(text, target):
    """
    Find all case-insensitive full-word matches of target in text.
    An alternative would be to use re.finditer with word boundaries.
    """
    occurrences = []
    target_escaped = re.escape(target)
    pattern = re.compile(r'\b' + target_escaped + r'\b', re.IGNORECASE)
    for match in pattern.finditer(text):
        occurrences.append((match.start(), match.end()))
    return occurrences

def add_entity(entities, start, end, label):
    """
    Add an entity to the list, skipping overlapping ones.
    """
    for s, e, _ in entities:
        if not (end <= s or start >= e):
            print(f"Skipping overlapping entity: {label} at ({start}, {end}) conflicts with ({s}, {e})")
            return
    entities.append((start, end, label))

def clean_html_content(content):
    """
    Clean HTML while preserving the link text.
    Removes unwanted tags (script, style, head, meta, link) but keeps text.
    """
    soup = BeautifulSoup(content, "html.parser")
    
    # Preserve link text by replacing <a> tags with their inner text.
    for link in soup.find_all('a'):
        link_text = link.get_text(strip=True)
        if link_text:
            link.replace_with(f"{link_text} ")
    
    # Remove unwanted tags
    for tag in soup(["script", "style", "head", "meta", "link"]):
        tag.decompose()
    
    text = soup.get_text(separator=" ")
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# --- Load Training Data ---
with open("job_confirmations.json", "r", encoding="utf-8") as f:
    data = json.load(f)

TRAIN_DATA = []
for email in data.get("emails", []):
    text = email.get("body", "")
    entities = []
    
    # Extract COMPANY entities
    company = email.get("company", "").strip()
    if company:
        for start, end in find_all_occurrences(text, company):
            add_entity(entities, start, end, "COMPANY")
    
    # Extract POSITION entities
    position = email.get("position", "").strip()
    if position:
        for start, end in find_all_occurrences(text, position):
            add_entity(entities, start, end, "POSITION")
    
    if entities:
        TRAIN_DATA.append((text, {"entities": entities}))

# --- Model Setup ---
nlp = spacy.load("en_core_web_sm")
ner = nlp.get_pipe("ner")

# Add custom labels if not already present
for label in ["COMPANY", "POSITION"]:
    ner.add_label(label)

# --- Training Setup ---
# Disable other pipes for faster training
with nlp.disable_pipes(*[p for p in nlp.pipe_names if p != "ner"]):
    optimizer = nlp.resume_training()

    # Split data into training and validation sets (with fixed random_state for reproducibility)
    train_data, val_data = train_test_split(TRAIN_DATA, test_size=0.2, random_state=42)
    
    best_fscore = 0.0  # Using F-score as a performance metric
    patience = 3
    no_improvement = 0
    epochs = 50
    
    for epoch in range(epochs):
        random.shuffle(train_data)
        losses = {}
        examples = []
        for text, annot in train_data:
            doc = nlp.make_doc(text)
            examples.append(Example.from_dict(doc, annot))
        
        # Batch training with a variable batch size
        batches = minibatch(examples, size=compounding(4.0, 32.0, 1.001))
        for batch in batches:
            nlp.update(batch, drop=0.4, losses=losses, sgd=optimizer)
        
        # --- Validation ---
        # Create validation examples and evaluate the model.
        val_examples = []
        for text, annot in val_data:
            doc = nlp.make_doc(text)
            val_examples.append(Example.from_dict(doc, annot))
        val_scores = nlp.evaluate(val_examples)
        # Use entity F-score as the metric (higher is better)
        val_fscore = val_scores.get("ents_f", 0)
        print(f"Epoch {epoch+1} - Train Loss: {losses.get('ner', 0):.2f}, Val F-score: {val_fscore:.2f}")
        
        # Early stopping: stop training if no improvement in F-score for 'patience' epochs.
        if val_fscore > best_fscore:
            best_fscore = val_fscore
            no_improvement = 0
        else:
            no_improvement += 1
            if no_improvement >= patience:
                print("Early stopping triggered")
                break

# --- Save the Trained Model ---
model_dir = f"job_extractor_model_v{int(time.time())}"
nlp.to_disk(model_dir)
print(f"Model saved to {model_dir}")

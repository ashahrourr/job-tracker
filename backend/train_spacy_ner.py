import spacy
from spacy.training import Example
from spacy.util import minibatch, compounding
import random
import json

# Load training data from the JSON file
with open("job_confirmations.json", "r", encoding="utf-8") as f:
    data = json.load(f)

TRAIN_DATA = []
for email in data.get("emails", []):
    text = email.get("body", "")
    lower_text = text.lower()
    entities = []
    
    company = email.get("company", "").strip()
    if company:
        lower_company = company.lower()
        start = lower_text.find(lower_company)
        if start != -1:
            entities.append((start, start + len(company), "COMPANY"))
        else:
            print(f"DEBUG: Company '{company}' not found in email body: {text}")
    
    position = email.get("position", "").strip()
    if position:
        lower_position = position.lower()
        start = lower_text.find(lower_position)
        if start != -1:
            entities.append((start, start + len(position), "POSITION"))
        else:
            print(f"DEBUG: Position '{position}' not found in email body: {text}")
    
    # Only add if at least one entity is found
    if entities:
        TRAIN_DATA.append((text, {"entities": entities}))

if not TRAIN_DATA:
    print("No training examples found. Check your JSON data.")
    exit()

# Create a blank English spaCy model
nlp = spacy.blank("en")

# Add the NER pipeline component (v3+ style)
if "ner" not in nlp.pipe_names:
    ner = nlp.add_pipe("ner", last=True)
else:
    ner = nlp.get_pipe("ner")

# Add labels
for _, annotations in TRAIN_DATA:
    for ent in annotations.get("entities"):
        ner.add_label(ent[2])

# Initialize the model
nlp.begin_training()

# Convert our (text, annotations) data into spaCy `Example` objects
examples = []
for text, annots in TRAIN_DATA:
    # Create a Doc from the text
    doc = nlp.make_doc(text)
    # Turn it into an Example with the dict of annotations
    example = Example.from_dict(doc, annots)
    examples.append(example)

n_iter = 20
print("Starting training...")

for itn in range(n_iter):
    random.shuffle(examples)
    losses = {}
    # Create minibatches of our training examples
    batches = minibatch(examples, size=compounding(4.0, 32.0, 1.001))
    for batch in batches:
        # Update the model with each batch of examples
        nlp.update(batch, drop=0.5, losses=losses)
    print(f"Iteration {itn+1} - Losses: {losses}")

# Save the model
model_dir = "job_extractor_model"
nlp.to_disk(model_dir)
print(f"Model saved to '{model_dir}'")

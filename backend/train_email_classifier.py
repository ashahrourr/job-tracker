import json
import pickle
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report

# Step 1: Load Dataset
DATA_FILE = "email_dataset.json"

def load_data(filename):
    """Load dataset and extract subject, body, and labels."""
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)
        texts = [f"{email['subject']} {email['body']}" for email in data]
        labels = [email["label"] for email in data]
    return texts, labels

texts, labels = load_data(DATA_FILE)

# Step 2: Split Data into Training and Test Sets
X_train, X_test, y_train, y_test = train_test_split(
    texts, labels, test_size=0.2, random_state=42, stratify=labels
)

# Step 3: Build Text Classification Pipeline
pipeline = Pipeline([
    ('tfidf', TfidfVectorizer(
        stop_words='english',
        max_df=0.95,  # Ignore very common words
        min_df=2,  # Ignore rare words
    )),
    ('clf', LogisticRegression(max_iter=1000))
])

# Step 4: Train the Model
pipeline.fit(X_train, y_train)

# Step 5: Evaluate the Model
y_pred = pipeline.predict(X_test)
print("📊 Classification Report:")
print(classification_report(y_test, y_pred))

# Step 6: Save the Model for Later Use
MODEL_FILENAME = "email_classifier.pkl"
with open(MODEL_FILENAME, "wb") as f:
    pickle.dump(pipeline, f)

print(f"✅ Model saved to '{MODEL_FILENAME}'. Ready for deployment!")

import json
import pickle
import re
import time
from html import unescape
from bs4 import BeautifulSoup
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (classification_report, 
                            confusion_matrix, 
                            ConfusionMatrixDisplay, 
                            accuracy_score,
                            make_scorer)

# Enhanced HTML cleaning with link text preservation
def clean_html_content(content):
    """Clean HTML while preserving link text content"""
    if not content:
        return ""
    
    soup = BeautifulSoup(content, "html.parser")
    
    # Preserve text from links before removing tags
    for link in soup.find_all('a'):
        link_text = link.get_text(strip=True)
        if link_text:
            link.replace_with(f"{link_text} ")
    
    # Remove unwanted elements but keep text
    for tag in soup(["script", "style", "head", "meta", "link", "img"]):
        tag.decompose()
    
    # Clean and normalize text
    text = soup.get_text(separator=" ")
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def load_data(filename):
    """Load and preprocess email data with proper error handling"""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            texts = []
            labels = []
            
            for email in data:
                # Handle missing fields
                subject = email.get("subject", "")
                body = email.get("body", "")
                label = email.get("label", "")
                
                if not label:
                    continue
                
                # Clean and combine text
                cleaned_text = f"{clean_html_content(subject)} {clean_html_content(body)}"
                texts.append(cleaned_text)
                labels.append(label)
            
            return texts, labels
    
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        raise

def main():
    # Load and validate data
    DATA_FILE = "email_dataset.json"
    try:
        texts, labels = load_data(DATA_FILE)
    except Exception as e:
        print(f"Failed to load data: {str(e)}")
        return

    if len(texts) == 0:
        print("No training data found")
        return

    # Split data with stratification
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, 
        test_size=0.2, 
        random_state=42,
        stratify=labels
    )

    # Define pipeline with proper syntax
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            stop_words='english',
            ngram_range=(1, 2),
        )),
        ('clf', LogisticRegression(
            class_weight='balanced',
            max_iter=1000)
        )
    ])

    # Hyperparameter grid
    param_grid = {
        'tfidf__max_df': [0.75, 0.85],
        'tfidf__min_df': [1, 2],
        'tfidf__max_features': [5000, 10000],
        'clf__C': [0.1, 1, 10]
    }

    # Configure grid search
    grid_search = GridSearchCV(
        estimator=pipeline,
        param_grid=param_grid,
        cv=3,
        n_jobs=-1,
        verbose=1,
        scoring=make_scorer(accuracy_score),
        error_score='raise'
    )

    print("Starting model training...")
    try:
        grid_search.fit(X_train, y_train)
    except Exception as e:
        print(f"Training failed: {str(e)}")
        return

    # Get best model
    best_model = grid_search.best_estimator_
    print(f"Best parameters: {grid_search.best_params_}")
    print(f"Best validation accuracy: {grid_search.best_score_:.3f}")

    # Evaluate on test set
    print("\nTest set evaluation:")
    y_pred = best_model.predict(X_test)
    print(classification_report(y_test, y_pred))


    # Save model with versioning
    timestamp = int(time.time())
    model_file = f"email_classifier_v{timestamp}.pkl"
    with open(model_file, "wb") as f:
        pickle.dump(best_model, f)
    
    print(f"\nModel saved to {model_file}")

if __name__ == "__main__":
    main()
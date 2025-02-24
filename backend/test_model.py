import spacy

def load_and_test_model(model_path, sample_texts):
    """
    Loads a trained spaCy model and runs entity recognition on sample texts.
    """
    print("\n🔍 Loading model from:", model_path)
    nlp = spacy.load(model_path)

    for idx, text in enumerate(sample_texts, 1):
        doc = nlp(text)
        print(f"\n📝 Test {idx}: {text}\n")
        
        if doc.ents:
            for ent in doc.ents:
                print(f"   ✅ Entity: '{ent.text}' → Label: {ent.label_}")
        else:
            print("   ❌ No entities found!")

        print("-" * 60)

if __name__ == "__main__":
    # Path to your trained model
    model_dir = "job_extractor_model"
    
    # Realistic test samples
    sample_texts = [
        "Hello Mido, Thanks for applying to Google for the Software Engineer role!",
        "Dear Ahmad, we received your application for the Data Analyst position at Microsoft.",
        "Hi Mido, Your application for the Front-End Developer position at Meta has been received!",
        "Thank you for your application! We've received your request for the Machine Learning Engineer role at OpenAI.",
        "We appreciate your interest in joining Tesla as a Robotics Engineer. Your application is under review.",
        "Your application for the Investment Banking Analyst position at Goldman Sachs has been successfully submitted.",
        "Hi Ahmad, Thanks for applying to Amazon for the Software Development Engineer role. We'll review your application and get back to you!",
        "Hello, your application to JPMorgan Chase for the Financial Analyst role has been received. Expect an update soon!",
        "Thank you for your interest in Palantir! Your application for the Data Scientist position is currently being reviewed.",
        "Dear Mido, We received your application at Adobe for the UX Designer position. Our hiring team will reach out if you are selected for an interview."
    ]
    
    load_and_test_model(model_dir, sample_texts)


from dotenv import load_dotenv
import os

# Load the .env file from the backend directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
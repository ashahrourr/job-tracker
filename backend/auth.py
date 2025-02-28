import os
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from starlette.requests import Request
from sqlalchemy.orm import Session
from backend.database import SessionLocal, TokenStore  # ✅ Import DB session & model
from dotenv import load_dotenv  # ✅ Load .env for local testing

# ✅ Load environment variables
load_dotenv()

# ✅ Load Google credentials from ENV instead of `credentials.json`
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

if not GOOGLE_CREDENTIALS_JSON:
    raise Exception("Missing Google credentials. Set GOOGLE_CREDENTIALS_JSON in Render or .env")

# ✅ Convert JSON string back to dictionary
credentials_dict = json.loads(GOOGLE_CREDENTIALS_JSON)

# ✅ Define OAuth 2.0 Flow using credentials from ENV
flow = Flow.from_client_config(
    credentials_dict,
    scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    redirect_uri=os.getenv("REDIRECT_URI")
)

router = APIRouter()

# ✅ Function to Save Token to Database
def save_token_to_db(credentials):
    """
    Save OAuth token to database or update if it already exists.
    """
    db = SessionLocal()
    token_entry = db.query(TokenStore).filter(TokenStore.id == "gmail").first()

    if token_entry:
        # Update existing token
        token_entry.token = credentials.token
        token_entry.refresh_token = credentials.refresh_token
        token_entry.token_uri = credentials.token_uri
        token_entry.client_id = credentials.client_id
        token_entry.client_secret = credentials.client_secret
        token_entry.scopes = ",".join(credentials.scopes)
    else:
        # Insert new token
        db_token = TokenStore(
            id="gmail",
            token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=credentials.token_uri,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            scopes=",".join(credentials.scopes),
        )
        db.add(db_token)

    db.commit()
    db.close()

# ✅ Step 1: Redirect User to Google OAuth Login
@router.get("/auth/login")
async def login():
    auth_url, _ = flow.authorization_url(prompt="consent")
    return RedirectResponse(auth_url)

# ✅ Step 2: Handle Google OAuth Callback & Save Token to DB
@router.get("/auth/callback")
async def callback(request: Request):
    try:
        # Get authorization code from URL
        code = request.query_params.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code missing")

        # Exchange authorization code for access token
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # ✅ Save the token in the database instead of `token.json`
        save_token_to_db(credentials)

        return {"message": "Authentication successful"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

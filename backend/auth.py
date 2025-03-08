# auth.py (modified callback endpoint)
import os
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from starlette.requests import Request
from backend.database import SessionLocal, TokenStore
from dotenv import load_dotenv

# Import the JWT functions
from backend.session import create_access_token

load_dotenv()
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
if not GOOGLE_CREDENTIALS_JSON:
    raise Exception("Missing Google credentials. Set GOOGLE_CREDENTIALS_JSON in Render or .env")
credentials_dict = json.loads(GOOGLE_CREDENTIALS_JSON)

# Updated scopes to include email and openid for user info
flow = Flow.from_client_config(
    credentials_dict,
    scopes=["openid", "https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/userinfo.email"],
    redirect_uri=os.getenv("REDIRECT_URI")
)


router = APIRouter()

def save_token_to_db(credentials, user_email: str):
    # [Token saving logic updated for multiuser, as shown previously]
    db = SessionLocal()
    token_entry = db.query(TokenStore).filter(TokenStore.user_id == user_email).first()

    if token_entry:
        token_entry.token = credentials.token
        token_entry.refresh_token = credentials.refresh_token
        token_entry.token_uri = credentials.token_uri
        token_entry.client_id = credentials.client_id
        token_entry.client_secret = credentials.client_secret
        token_entry.scopes = ",".join(credentials.scopes)
    else:
        db_token = TokenStore(
            user_id=user_email,
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

from fastapi.responses import RedirectResponse

@router.get("/auth/callback")
async def callback(request: Request):
    try:
        code = request.query_params.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code missing")
        
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Extract user's email using the ID token
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        id_info = id_token.verify_oauth2_token(
            credentials.id_token, google_requests.Request(), credentials.client_id
        )
        user_email = id_info.get("email")
        if not user_email:
            raise HTTPException(status_code=400, detail="Failed to retrieve user email from token")

        # Save user token to DB
        save_token_to_db(credentials, user_email)

        # Create JWT token for session management
        jwt_token = create_access_token(data={"sub": user_email})

        # ✅ Redirect to frontend with token in the URL
        FRONTEND_URL = "http://localhost:5173/"  # Change this if frontend URL is different
        return RedirectResponse(f"{FRONTEND_URL}?token={jwt_token}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from fastapi.responses import RedirectResponse

@router.get("/auth/login")
async def login():
    auth_url, _ = flow.authorization_url(prompt="consent")
    return RedirectResponse(auth_url)
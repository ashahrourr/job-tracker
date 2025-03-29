# auth.py
import os
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from starlette.requests import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.workflow_pipeline.database import async_session, TokenStore
from backend.workflow_pipeline.session import create_access_token
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()

# ========== GOOGLE AUTH SETUP ==========
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
if not GOOGLE_CREDENTIALS_JSON:
    raise RuntimeError("Missing Google credentials in environment")

flow = Flow.from_client_config(
    client_config=json.loads(GOOGLE_CREDENTIALS_JSON),
    scopes=["openid", "https://www.googleapis.com/auth/gmail.readonly", 
            "https://www.googleapis.com/auth/userinfo.email"],
    redirect_uri=os.getenv("REDIRECT_URI")
)

# ========== ASYNC DATABASE OPERATIONS ==========
async def save_token_to_db(credentials, user_email: str):
    """Async version of token saving with proper session handling"""
    async with async_session() as db:
        # Check for existing token
        result = await db.execute(
            select(TokenStore).where(TokenStore.user_id == user_email)
        )
        token_entry = result.scalar_one_or_none()

        if token_entry:
            # Update existing entry
            token_entry.token = credentials.token
            token_entry.refresh_token = credentials.refresh_token
            token_entry.token_uri = credentials.token_uri
            token_entry.client_id = credentials.client_id
            token_entry.client_secret = credentials.client_secret
            token_entry.scopes = ",".join(credentials.scopes)
        else:
            # Create new entry
            db.add(TokenStore(
                user_id=user_email,
                token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=",".join(credentials.scopes),
                )
            )

        await db.commit()

# ========== ROUTES ==========
@router.get("/auth/callback")
async def callback(request: Request):
    try:
        code = request.query_params.get("code")
        if not code:
            raise HTTPException(400, "Missing authorization code")

        flow.fetch_token(code=code)
        credentials = flow.credentials

        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            google_requests.Request(),
            credentials.client_id
        )

        user_email = id_info.get("email")
        if not user_email:
            raise HTTPException(400, "Failed to retrieve user email from token")

        await save_token_to_db(credentials, user_email)

        jwt_token = create_access_token(data={"sub": user_email})
        return RedirectResponse(f"{os.getenv('FRONTEND_URL')}?token={jwt_token}")

    except Exception as e:
        import traceback
        traceback.print_exc()  # 🐛 Show the full stack trace in the logs
        raise HTTPException(500, detail=f"Authentication failed: {str(e)}")

@router.get("/auth/login")
async def login():
    """Initiate OAuth flow"""
    auth_url, _ = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true"
    )
    return RedirectResponse(auth_url)

from backend.workflow_pipeline.session import create_access_token, get_user_email_from_token
from google.oauth2.credentials import Credentials
from google.auth.transport import requests as google_requests
from datetime import datetime, timedelta  # Add to imports

@router.post("/auth/refresh")
async def refresh_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(401, detail="Missing authorization header")
    
    old_token = auth_header.replace("Bearer ", "")
    user_email = get_user_email_from_token(old_token)

    if not user_email:
        raise HTTPException(401, detail="Invalid or expired token")

    async with async_session() as db:
        result = await db.execute(select(TokenStore).where(TokenStore.user_id == user_email))
        token_entry = result.scalar_one_or_none()

        if not token_entry:
            raise HTTPException(401, detail="No token found")

        # Calculate time since last refresh
        now = datetime.utcnow()
        last_refreshed = token_entry.last_refreshed or now
        needs_force_refresh = (now - last_refreshed) > timedelta(minutes=30)

        # Build credentials
        creds = Credentials(
            token=token_entry.token,
            refresh_token=token_entry.refresh_token,
            token_uri=token_entry.token_uri,
            client_id=token_entry.client_id,
            client_secret=token_entry.client_secret,
            scopes=token_entry.scopes.split(",")
        )

        try:
            # Refresh if expired OR if 30 minutes have passed since last refresh
            creds.refresh(google_requests.Request())  # 👈 Remove expiration check
            token_entry.token = creds.token
            if creds.refresh_token:  # Handle refresh token rotation
                token_entry.refresh_token = creds.refresh_token
            token_entry.last_refreshed = datetime.utcnow()
            await db.commit()

        except Exception as e:
            await db.rollback()
            raise HTTPException(401, detail=f"Google session expired: {str(e)}")

        # Return new JWT
        new_token = create_access_token(data={"sub": user_email})
        return {"access_token": new_token}
import json
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from starlette.requests import Request

# Load client credentials from credentials.json
CLIENT_SECRETS_FILE = "credentials.json"

# Define OAuth 2.0 Flow
flow = Flow.from_client_secrets_file(
    CLIENT_SECRETS_FILE,
    scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    redirect_uri=os.getenv("REDIRECT_URI")

)

router = APIRouter()

# Step 1: Redirect user to Google OAuth Login
@router.get("/auth/login")
async def login():
    auth_url, _ = flow.authorization_url(prompt="consent")
    return RedirectResponse(auth_url)

# Step 2: Handle Google OAuth Callback
@router.get("/auth/callback")
async def callback(request: Request):
    try:
        # Get authorization code from URL
        code = request.query_params.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code missing")

        # Exchange code for access token
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Save credentials for future API calls
        token_info = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }
        with open("token.json", "w") as token_file:
            json.dump(token_info, token_file)

        return {"message": "Authentication successful", "token": credentials.token}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


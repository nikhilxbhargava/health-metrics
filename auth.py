"""OAuth2 authentication flow for the Oura Ring API."""

import json
import os
import urllib.parse

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".oura_token.json")

OURA_AUTH_URL = "https://cloud.ouraring.com/oauth/authorize"
OURA_TOKEN_URL = "https://api.ouraring.com/oauth/token"

CLIENT_ID = os.getenv("OURA_CLIENT_ID")
CLIENT_SECRET = os.getenv("OURA_CLIENT_SECRET")
REDIRECT_URI = os.getenv("OURA_REDIRECT_URI", "http://localhost:8501/oauth/callback")


def get_auth_url() -> str:
    """Build the Oura OAuth2 authorization URL."""
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "daily heartrate personal spo2 session tag workout",
    }
    return f"{OURA_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(code: str) -> dict:
    """Exchange an authorization code for access + refresh tokens."""
    resp = requests.post(
        OURA_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    resp.raise_for_status()
    token_data = resp.json()
    _save_token(token_data)
    return token_data


def refresh_access_token(refresh_token: str) -> dict:
    """Use a refresh token to get a new access token."""
    resp = requests.post(
        OURA_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    resp.raise_for_status()
    token_data = resp.json()
    _save_token(token_data)
    return token_data


def get_token() -> dict | None:
    """Load the saved token from disk, if it exists."""
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE) as f:
        return json.load(f)


def _save_token(token_data: dict) -> None:
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

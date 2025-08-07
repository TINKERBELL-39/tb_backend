from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
import requests
import urllib.parse
import os

app = FastAPI()

FB_APP_ID = os.getenv('INSTAGRAM_APP_ID')
FB_APP_SECRET = os.getenv('INSTAGRAM_APP_SECRET')
REDIRECT_URI = os.getenv("FB_REDIRECT_URI", "http://localhost:8007/auth/callback")
SCOPES = "instagram_basic,instagram_manage_messages,pages_show_list"

# === 1. Instagram 로그인 URL 제공 ===
@app.get("/auth/login")
def login():
    login_url = (
        "https://www.facebook.com/v17.0/dialog/oauth?"
        f"client_id={FB_APP_ID}&redirect_uri={urllib.parse.quote(REDIRECT_URI)}&scope={SCOPES}&response_type=code"
    )
    return RedirectResponse(url=login_url)


# === 2. Callback에서 code로 Access Token 발급 ===
@app.get("/auth/callback")
def callback(request: Request, code: str = None, error: str = None):
    if error or code is None:
        raise HTTPException(status_code=400, detail="Authorization failed")

    # Step 2: code를 short-lived token으로 교환
    token_url = "https://graph.facebook.com/v17.0/oauth/access_token"
    token_params = {
        "client_id": FB_APP_ID,
        "redirect_uri": REDIRECT_URI,
        "client_secret": FB_APP_SECRET,
        "code": code,
    }
    token_res = requests.get(token_url, params=token_params)
    short_token_data = token_res.json()

    if "access_token" not in short_token_data:
        raise HTTPException(status_code=400, detail=f"Failed to get short token: {short_token_data}")

    short_token = short_token_data["access_token"]

    # Step 3: short token → long-lived token
    long_token_res = requests.get(
        "https://graph.facebook.com/v17.0/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "fb_exchange_token": short_token,
        },
    )
    long_token_data = long_token_res.json()

    if "access_token" not in long_token_data:
        raise HTTPException(status_code=400, detail=f"Failed to get long token: {long_token_data}")

    return {
        "short_lived_token": short_token,
        "long_lived_token": long_token_data["access_token"],
        "expires_in": long_token_data.get("expires_in", None)
    }


# === 3. Instagram 계정 정보 가져오기 ===
@app.get("/auth/instagram-account")
def get_instagram_account(token: str):
    # 연결된 Facebook 페이지들 조회
    pages_res = requests.get(
        "https://graph.facebook.com/me/accounts",
        params={"access_token": token}
    )
    return pages_res.json()

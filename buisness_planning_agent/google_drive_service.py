import os
import urllib.parse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from typing import Any, Dict, Optional

import urllib.parse
from typing import Dict, List, Any, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request as GoogleRequest

from task_agent.automation_task.common import (
    get_auth_manager, get_oauth_http_client, get_config_manager,
)
# queries.py의 get_user_tokens 함수 import 추가
from shared_modules.queries import get_user_tokens
from shared_modules.database import get_session_context

import logging
logger = logging.getLogger(__name__)


SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GoogleDriveService:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.auth_manager = get_auth_manager()
        self.http_client = get_oauth_http_client()
        self.config_manager = get_config_manager()
        if config:
            self.config = config.get("google_drive", {})
        else:
            self.config = self.config_manager.get_oauth_config("google_drive")
        self.platform = "google_drive"
    
    def generate_auth_url(self, user_id: str) -> Dict[str, Any]:
        try:
            state = self.auth_manager.generate_state(user_id, self.platform)
            #state = user_id
            params = {
                "client_id": self.config.get("client_id"),
                "redirect_uri": "http://localhost:8001/auth/google/callback", 
                "scope": " ".join(SCOPES),
                "response_type": "code",
                "state": state,
                "access_type": "offline",
                "prompt": "consent"
            }
            print(params)
            base_url = "https://accounts.google.com/o/oauth2/v2/auth"
            auth_url = f"{base_url}?{urllib.parse.urlencode(params)}"
            return {"success": True, "auth_url": auth_url, "state": state, "platform": self.platform}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def exchange_code_for_token(self, code: str, state: str, user_id: str = None) -> Dict[str, Any]:
        try:
            state_data = self.auth_manager.validate_state(state, user_id, self.platform)
            if not state_data:
                return {"success": False, "error": "유효하지 않은 state 파라미터"}
            
            result = await self.http_client.exchange_oauth_code(
                token_url="https://oauth2.googleapis.com/token",
                client_id=self.config.get("client_id"),
                client_secret=self.config.get("client_secret"),
                code=code,
                redirect_uri=self.config.get("redirect_uri")
            )
            if result.get("success"):
                token_data = result.get("data", {})
                target_user_id = user_id or state_data.get("user_id")
                if target_user_id:
                    self.store_token(target_user_id, token_data)
                
                print(f"tokendata: {token_data}")
                return {
                    "success": True,
                    "access_token": token_data.get("access_token"),
                    "refresh_token": token_data.get("refresh_token"),
                    "token_type": token_data.get("token_type", "Bearer"),
                    "expires_in": token_data.get("expires_in"),
                    "scope": token_data.get("scope"),
                }
               
            else:
                print("토큰교환실패", result)
                return {"success": False, "error": f"토큰 교환 실패: {result.get('error')}"}
        except Exception as e:
            print("exchange_oauth_code 실패!", result)
            return {"success": False, "error": str(e)}
    
    def store_token(self, user_id: str, token_data: Dict[str, Any]) -> bool:
        return self.auth_manager.store_token(user_id, self.platform, token_data)
    
    def get_token(self, user_id: str) -> Optional[Dict[str, Any]]:
        """queries.py의 get_user_tokens 함수를 사용하여 토큰 조회"""
        try:
            user_id_int = int(user_id)
            with get_session_context() as db:
                token_data = get_user_tokens(db, user_id_int)
                if token_data:
                    # get_user_tokens 반환 형식을 기존 형식에 맞게 변환
                    return {
                        "access_token": token_data.get("access_token"),
                        "refresh_token": token_data.get("refresh_token")
                    }
                return None
        except (ValueError, Exception) as e:
            logger.error(f"토큰 조회 실패: {e}")
            return None
    
    def get_drive_service(self, user_id: str):
        token_data = self.get_token(user_id)
        if not token_data:
            raise ValueError("유저 인증 필요 (토큰 없음)")
        
        # Ensure all required fields are present for token refresh
        credentials = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.config["client_id"],
            client_secret=self.config["client_secret"],
            scopes=SCOPES,
        )
        
        # Check if credentials are valid and refresh if needed
        if not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(GoogleRequest())
                    # Update stored token with new access token
                    new_token_data = {
                        "access_token": credentials.token,
                        "refresh_token": credentials.refresh_token
                    }
                    self.store_token(user_id, new_token_data)
                except Exception as e:
                    logger.error(f"Token refresh failed: {e}")
                    raise ValueError("토큰 갱신 실패 - 재인증이 필요합니다")
            else:
                raise ValueError("유효하지 않은 토큰 - 재인증이 필요합니다")
        
        return build("drive", "v3", credentials=credentials)

    def upload_file(self, user_id: str, server_path: str, mime_type: str = "application/octet-stream"):
        try:
            safe_name = os.path.basename(server_path)
            service = self.get_drive_service(user_id)
            media = MediaFileUpload(server_path, mimetype=mime_type)
            uploaded = service.files().create(
                body={'name': safe_name},
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            return {
                "success": True,
                "file_id": uploaded.get('id'),
                "webViewLink": uploaded.get('webViewLink')
            }
        except ValueError as ve:
            # Handle authentication errors specifically
            return {"success": False, "error": str(ve), "auth_required": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

drive_service = GoogleDriveService()

google_drive_router = APIRouter(prefix="", tags=["Google Drive"])

@google_drive_router.post("/drive/upload")
async def drive_file_upload(user_id: str = Form(...), file: UploadFile = File(...)):
    upload_dir = f"./uploads/{user_id}"
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    server_path = os.path.join(upload_dir, safe_name)
    with open(server_path, "wb") as f:
        content = await file.read()
        f.write(content)
    return {"success": True, "filename": server_path, "basename": safe_name}

@google_drive_router.post("/drive/upload/gdrive")
async def drive_upload_gdrive(data: dict):
    user_id = data["user_id"]
    filename = data["filename"]
    mime_type = data.get("mime_type", "application/octet-stream")
    # 유저 인증정보/토큰 확인: 없으면 인증 URL 반환
    token_data = drive_service.get_token(user_id)

    print("🔎 업로드API user_id:", user_id)
    print("🔎 get_token 반환:", token_data) 

    if not token_data or not token_data.get("refresh_token"):
        # 인증URL 반환
        auth_url_info = drive_service.generate_auth_url(user_id)
        return {
            "success": False,
            "error_type": "GOOGLE_OAUTH_REQUIRED",
            "message": "구글 인증이 필요합니다. 구글 계정으로 로그인 해주세요.",
            "oauth_url": auth_url_info["auth_url"]
        }
    # 토큰 있으면 파일 업로드
    upload_res = drive_service.upload_file(user_id, filename, mime_type)
    print("🔎 실제 업로드 결과:", upload_res)

    if upload_res.get("success", False):
        try:
            os.remove(filename)
            print(f"[파일삭제] {filename} 삭제 완료")
        except Exception as e:
            print(f"[파일삭제실패] {filename} 삭제 중 오류:", e)
            
    return upload_res

@google_drive_router.get("/auth/google/callback")
async def google_drive_oauth_callback(request: Request, code: str, state: str):
    # 1. state 검증 및 user_id 추출
    state_data = drive_service.auth_manager.validate_state(state, None, "google_drive")
    if not state_data:
        return RedirectResponse("http://localhost:3000/google-drive?success=false&error=invalid_state")

    user_id = state_data["user_id"]  # ← state와 플랫폼에 맞는 user_id 추출

    # 2. 토큰 교환
    token_res = await drive_service.exchange_code_for_token(code, state, user_id)
    if not token_res.get("success"):
        return RedirectResponse(f"http://localhost:3000/google-drive?success=false&error={token_res.get('error')}")
    return RedirectResponse("http://localhost:3000/google-drive?success=true")


@google_drive_router.post("/auth/google/exchange")
async def google_drive_oauth_exchange(data: dict):
    code = data.get("code")
    state= data.get("state")
    # 1. state로부터 실제 user_id 추출 (state 검증)
    state_data = drive_service.auth_manager.validate_state(state, None, "google_drive")
    if not state_data:
        return {"success": False, "error": "유효하지 않은 state 파라미터"}
    user_id = state_data["user_id"]  # 안전하게 추출
    # state = data.get("state")# user_id = state #drive_service.auth_manager.get_userid_from_state(state, "google_drive")
    token_res = await drive_service.exchange_code_for_token(code, state, user_id)
    return token_res
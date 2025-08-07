"""
OAuth 인증 및 토큰 관리 공통 모듈
"""

import json
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class AuthManager:
    """OAuth 인증 및 토큰 관리를 위한 공통 클래스"""
    
    def __init__(self):
        self.tokens_storage = {}  # 실제로는 데이터베이스 사용
    
    def generate_state(self, user_id: str, platform: str) -> str:
        """OAuth state 파라미터 생성 및 저장"""
        state = secrets.token_urlsafe(32)
        
        self.tokens_storage[f"state_{user_id}_{platform}"] = {
            "state": state,
            "platform": platform,
            "user_id": user_id,
            "created_at": datetime.now()
        }
        
        return state
    
    def validate_state(self, state: str, user_id: str = None, platform: str = None) -> Optional[Dict[str, Any]]:
        """OAuth state 검증"""
        try:
            logger.debug(f"Validate state called with: {state}, user_id={user_id}, platform={platform}")
            logger.debug(f"Current tokens_storage items: {self.tokens_storage.items()}") # 경고: 실제 토큰 정보가 노출되지 않도록 주의

            for key, data in self.tokens_storage.items():
                logger.debug(f"Checking key: {key}, data: {data}")
                if key.startswith("state_") and data.get("state") == state:
                    logger.debug(f"Matching state found for key: {key}")
                    if user_id and data.get("user_id") != user_id:
                        logger.debug(f"User ID mismatch for state {state}. Expected: {user_id}, Found: {data.get('user_id')}")
                        continue
                    if platform and data.get("platform") != platform:
                        logger.debug(f"Platform mismatch for state {state}. Expected: {platform}, Found: {data.get('platform')}")
                        continue
                    logger.debug(f"State validation successful for {state}")
                    return data
            logger.warning(f"No matching state found for {state}")
            return None
        except Exception as e:
            logger.error(f"State 검증 실패: {e}")
            return None
    
    def store_token(self, user_id: str, platform: str, token_data: Dict[str, Any]) -> bool:
        """토큰 저장"""
        try:
            key = f"token_{user_id}_{platform}"
            token_data["stored_at"] = datetime.now().isoformat()
            self.tokens_storage[key] = token_data
            
            # 토큰을 JSON 파일로도 저장 (백업용)
            try:
                token_file_path = f"./tokens/{platform}_token_{user_id}.json"
                os.makedirs(os.path.dirname(token_file_path), exist_ok=True)
                with open(token_file_path, 'w') as f:
                    json.dump(token_data, f, indent=2, default=str)
                logger.info(f"토큰 파일 저장 완료: {token_file_path}")
            except Exception as e:
                logger.warning(f"토큰 파일 저장 실패: {e}")
            
            logger.info(f"{platform} 토큰 저장 완료: user {user_id}")
            return True
        except Exception as e:
            logger.error(f"토큰 저장 실패: {e}")
            return False
    
    def get_token(self, user_id: str, platform: str) -> Optional[Dict[str, Any]]:
        """저장된 토큰 가져오기"""
        try:
            key = f"token_{user_id}_{platform}"
            token_data = self.tokens_storage.get(key)
            
            # 메모리에 없으면 파일에서 로드 시도
            if not token_data:
                token_file_path = f"./tokens/{platform}_token_{user_id}.json"
                if os.path.exists(token_file_path):
                    with open(token_file_path, 'r') as f:
                        token_data = json.load(f)
                    self.tokens_storage[key] = token_data
                    logger.info(f"토큰 파일에서 로드 완료: {token_file_path}")
            
            return token_data
        except Exception as e:
            logger.error(f"토큰 가져오기 실패: {e}")
            return None
    
    def is_token_valid(self, user_id: str, platform: str) -> bool:
        """토큰 유효성 검사"""
        try:
            token_data = self.get_token(user_id, platform)
            if not token_data:
                return False
            
            # 만료 시간 확인
            expires_in = token_data.get("expires_in")
            stored_at = token_data.get("stored_at")
            
            if expires_in and stored_at:
                stored_time = datetime.fromisoformat(stored_at)
                expiry_time = stored_time + timedelta(seconds=expires_in)
                return datetime.now() < expiry_time
            
            return True  # 만료 정보가 없으면 유효한 것으로 간주
            
        except Exception as e:
            logger.error(f"토큰 유효성 검사 실패: {e}")
            return False
    
    def update_token(self, user_id: str, platform: str, updated_data: Dict[str, Any]) -> bool:
        """토큰 업데이트"""
        try:
            existing_token = self.get_token(user_id, platform)
            if not existing_token:
                return False
            
            existing_token.update(updated_data)
            return self.store_token(user_id, platform, existing_token)
        except Exception as e:
            logger.error(f"토큰 업데이트 실패: {e}")
            return False
    
    def remove_token(self, user_id: str, platform: str) -> bool:
        """토큰 제거"""
        try:
            key = f"token_{user_id}_{platform}"
            if key in self.tokens_storage:
                del self.tokens_storage[key]
            
            # 토큰 파일 삭제
            token_file_path = f"./tokens/{platform}_token_{user_id}.json"
            if os.path.exists(token_file_path):
                os.remove(token_file_path)
            
            logger.info(f"{platform} 토큰 제거 완료: user {user_id}")
            return True
        except Exception as e:
            logger.error(f"토큰 제거 실패: {e}")
            return False
    
    def get_connection_info(self, user_id: str, platform: str) -> Dict[str, Any]:
        """연동 정보 조회"""
        token_data = self.get_token(user_id, platform)
        if token_data:
            return {
                "connected": True,
                "user_info": token_data.get("user_info", {}),
                "connected_at": token_data.get("stored_at"),
                "is_valid": self.is_token_valid(user_id, platform)
            }
        else:
            return {"connected": False}


# 전역 인스턴스
_auth_manager = None

def get_auth_manager() -> AuthManager:
    """AuthManager 싱글톤 인스턴스 반환"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager

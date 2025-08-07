"""
Instagram 자동화 실행기 v1
실제 Instagram API를 호출하는 실행기
"""

import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from datetime import datetime
import os
import sys

# 상위 디렉토리의 모듈 import를 위한 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from shared_modules.db_models import InstagramToken
from shared_modules.database import get_session_context
from sqlalchemy import desc

logger = logging.getLogger(__name__)

class InstagramExecutor:
    """Instagram 자동화 실행기 - 실제 API 호출"""
    
    def __init__(self):
        """Instagram 실행기 초기화"""
        self.supported_platforms = ["instagram"]
        self.api_base_url = os.getenv("TASK_AGENT_API_URL", "https://localhost:8005")
        
        # Instagram API 설정
        self.instagram_app_id = os.getenv("INSTAGRAM_APP_ID")
        self.instagram_app_secret = os.getenv("INSTAGRAM_APP_SECRET")
        self.redirect_uri = os.getenv("INSTAGRAM_REDIRECT_URI")
        
        logger.info("InstagramExecutor v1 초기화 완료 (실제 API 호출)")

    async def execute(self, task_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Instagram 포스팅 실행 - 실제 API 호출"""
        try:
            logger.info(f"Instagram 포스팅 실행 시작 - 사용자: {user_id}")
            
            # 필수 데이터 검증
            validation_result = self._validate_task_data(task_data)
            if not validation_result["is_valid"]:
                return {
                    "success": False,
                    "message": f"데이터 검증 실패: {', '.join(validation_result['errors'])}",
                    "details": validation_result
                }
            
            # 포스팅 데이터 추출 및 정규화
            post_data = await self._normalize_post_data(task_data)
            
            # 실제 Instagram API 호출
            result = await self._call_instagram_api(post_data, user_id)
            
            if result["success"]:
                logger.info(f"Instagram 포스팅 성공 - 포스트 ID: {result.get('post_id')}")
                return {
                    "success": True,
                    "message": f"Instagram 포스팅이 성공적으로 완료되었습니다",
                    "details": {
                        "post_id": result.get("post_id"),
                        "platform": "instagram",
                        "content": post_data["post_content"][:100] + "..." if len(post_data["post_content"]) > 100 else post_data["post_content"],
                        "hashtags": post_data.get("searched_hashtags", []),
                        "posted_at": datetime.utcnow().isoformat()
                    }
                }
            else:
                logger.error(f"Instagram 포스팅 실패: {result.get('error')}")
                return {
                    "success": False,
                    "message": f"Instagram 포스팅 실패: {result.get('error')}",
                    "details": result
                }
                
        except Exception as e:
            logger.error(f"Instagram 실행기 오류: {e}")
            return {
                "success": False,
                "message": f"Instagram 포스팅 중 오류 발생: {str(e)}",
                "details": {"error": str(e)}
            }

    async def _call_instagram_api(self, post_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """실제 Instagram API 호출"""
        try:            
            # Instagram API 데이터 형태로 변환
            api_post_data = {
                "caption": post_data["post_content"],
                "image_url": post_data.get("image_url", "")
            }
            
            # HTTP 클라이언트로 API 호출
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_base_url}/instagram/post"
                
                logger.info(f"Instagram API 호출: {url} with data: {api_post_data}")
                
                async with session.post(
                    url,
                    json={
                        "user_id": user_id,
                        "caption": api_post_data["caption"],
                        "image_url": api_post_data["image_url"]
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "success": True,
                            "post_id": result.get("id"),
                            "api_response": result
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Instagram API 호출 실패: {response.status} - {error_text}")
                        return {
                            "success": False,
                            "error": f"API 호출 실패 (HTTP {response.status}): {error_text}"
                        }
                        
        except asyncio.TimeoutError:
            logger.error("Instagram API 호출 타임아웃")
            return {"success": False, "error": "API 호출 시간 초과"}
        except aiohttp.ClientError as e:
            logger.error(f"Instagram API 클라이언트 오류: {e}")
            return {"success": False, "error": f"네트워크 오류: {str(e)}"}
        except Exception as e:
            logger.error(f"Instagram API 호출 예외: {e}")
            return {"success": False, "error": f"API 호출 실패: {str(e)}"}

    def _validate_task_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Instagram 포스팅 작업 데이터 검증"""
        errors = []
        warnings = []
        
        if not task_data.get("post_content"):
            errors.append("포스팅 내용이 필요합니다")
        else:
            content_length = len(task_data["post_content"])
            if content_length > 2200:  # Instagram 캡션 제한
                warnings.append(f"포스팅 내용이 너무 깁니다 ({content_length}자). Instagram 제한을 초과할 수 있습니다.")
        
        # 이미지 URL 검증 (선택적)
        if task_data.get("image_url"):
            image_url = task_data["image_url"]
            if not image_url.startswith(("http://", "https://")):
                errors.append("올바른 이미지 URL이 필요합니다")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    async def _normalize_post_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """포스팅 데이터 정규화"""
        try:
            post_content or content or full_content
            normalized = {
                "post_content": task_data.get("post_content", "").strip(),
                "image_url": task_data.get("image_url", "")
            }
            
            return normalized
            
        except Exception as e:
            logger.error(f"포스팅 데이터 정규화 실패: {e}")
            raise

    def is_available(self) -> bool:
        """실행기 사용 가능 여부"""
        return all([
            self.instagram_app_id,
            self.instagram_app_secret,
            self.redirect_uri
        ])

    async def test_connection(self) -> Dict[str, Any]:
        """Instagram API 연결 테스트"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_base_url}/health"
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "Instagram API 연결이 정상입니다",
                            "api_url": self.api_base_url,
                            "config_status": {
                                "app_id_configured": bool(self.instagram_app_id),
                                "app_secret_configured": bool(self.instagram_app_secret),
                                "redirect_uri_configured": bool(self.redirect_uri)
                            }
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"API 응답 오류: HTTP {response.status}"
                        }
                        
        except Exception as e:
            return {"success": False, "error": f"연결 테스트 실패: {str(e)}"}

    async def cleanup(self):
        """실행기 정리"""
        try:
            logger.info("InstagramExecutor v1 정리 완료")
        except Exception as e:
            logger.error(f"InstagramExecutor v1 정리 실패: {e}")
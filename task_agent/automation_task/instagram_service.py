from ast import main
import httpx
import logging
import os
import requests
import asyncio
import json
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class Settings:
    BACKEND_URL = "http://localhost:8080"  # 실제 값으로 바꿔주세요

settings = Settings()

class InstagramPostingService:
    """Instagram Graph API를 사용한 게시글 업로드 서비스"""

    def __init__(self):
        self.base_url = "https://graph.instagram.com/v23.0"
        self.backend_url = settings.BACKEND_URL
        # Instagram OAuth 설정
        self.instagram_app_id = os.getenv('INSTAGRAM_APP_ID')
        self.instagram_app_secret = os.getenv('INSTAGRAM_APP_SECRET')
        self.redirect_uri = os.getenv('INSTAGRAM_REDIRECT_URI', 'http://localhost:8080/auth/instagram/callback')
        # 토큰 저장 파일 경로
        self.token_file = Path("instagram_tokens.json")

    def get_instagram_auth_url(self) -> str:
        """Instagram 인증 URL 생성 (1단계) - 올바른 scope 사용"""
        if not self.instagram_app_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Instagram App ID가 설정되지 않았습니다."
            )
        
        from urllib.parse import urlencode
        
        # Instagram Basic Display API scope 사용
        params = {
            "client_id": self.instagram_app_id,
            "redirect_uri": self.redirect_uri,
            "scope": "instagram_basic",  # 또는 "instagram_business_basic"
            "response_type": "code",
            "state": "csrf_protection_string"  # CSRF 보호
        }
        
        auth_url = f"https://api.instagram.com/oauth/authorize?{urlencode(params)}"
        logger.info(f"Instagram 인증 URL: {auth_url}")
        return auth_url

    async def get_access_token(self, authorization_code: str, state: str = None) -> Dict:
        """인증 코드로 Short-lived Access Token 발급 후 Long-lived Token으로 교환 (2단계)"""
        logger.info("=== Instagram Access Token 발급 시작 ===")
        
        if not self.instagram_app_id or not self.instagram_app_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Instagram App 설정이 완료되지 않았습니다."
            )
        
        try:
            async with httpx.AsyncClient() as client:
                # Short-lived Access Token 요청
                response = await client.post(
                    "https://api.instagram.com/oauth/access_token",
                    data={
                        "client_id": self.instagram_app_id,
                        "client_secret": self.instagram_app_secret,
                        "grant_type": "authorization_code",
                        "redirect_uri": self.redirect_uri,
                        "code": authorization_code
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"토큰 발급 실패: {response.text}"
                    )
                
                token_data = response.json()
                short_lived_token = token_data.get("access_token")
                user_id = token_data.get("user_id")
                
                if not short_lived_token:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Short-lived Access Token을 받지 못했습니다."
                    )
                
                logger.info(f"Short-lived Access Token 발급 성공: {short_lived_token[:20]}...")
                
                # Long-lived Access Token으로 교환
                long_lived_data = await self.exchange_for_long_lived_token(short_lived_token)
                
                # 토큰 저장
                await self.save_tokens(user_id, long_lived_data)
                
                return {
                    "access_token": long_lived_data["access_token"],
                    "user_id": user_id,
                    "token_type": "bearer",
                    "expires_in": long_lived_data["expires_in"]
                }
                
        except Exception as e:
            logger.error(f"토큰 발급 중 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"토큰 발급 중 오류가 발생했습니다: {str(e)}"
            )

    async def exchange_for_long_lived_token(self, short_lived_token: str) -> Dict:
        """Short-lived Token을 Long-lived Token으로 교환 (3단계)"""
        logger.info("=== Long-lived Access Token 교환 시작 ===")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.instagram.com/access_token",
                    params={
                        "grant_type": "ig_exchange_token",
                        "client_secret": self.instagram_app_secret,
                        "access_token": short_lived_token
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Long-lived Token 교환 실패: {response.text}"
                    )
                
                data = response.json()
                logger.info(f"Long-lived Token 발급 성공, 유효기간: {data.get('expires_in')}초")
                
                return data
                
        except Exception as e:
            logger.error(f"Long-lived Token 교환 중 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Long-lived Token 교환 중 오류가 발생했습니다: {str(e)}"
            )

    async def refresh_long_lived_token(self, current_token: str) -> Dict:
        """Long-lived Token 갱신 (4단계)"""
        logger.info("=== Long-lived Access Token 갱신 시작 ===")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.instagram.com/refresh_access_token",
                    params={
                        "grant_type": "ig_refresh_token",
                        "access_token": current_token
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Token 갱신 실패: {response.text}"
                    )
                
                data = response.json()
                logger.info(f"Token 갱신 성공, 새로운 유효기간: {data.get('expires_in')}초")
                
                return data
                
        except Exception as e:
            logger.error(f"Token 갱신 중 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Token 갱신 중 오류가 발생했습니다: {str(e)}"
            )

    async def save_tokens(self, user_id: str, token_data: Dict) -> None:
        """토큰을 파일에 저장"""
        try:
            # 기존 토큰 데이터 로드
            tokens = {}
            if self.token_file.exists():
                with open(self.token_file, 'r', encoding='utf-8') as f:
                    tokens = json.load(f)
            
            # 새 토큰 데이터 추가
            tokens[user_id] = {
                "access_token": token_data["access_token"],
                "expires_in": token_data["expires_in"],
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + 
                              timedelta(seconds=token_data["expires_in"])).isoformat()
            }
            
            # 파일에 저장
            with open(self.token_file, 'w', encoding='utf-8') as f:
                json.dump(tokens, f, indent=2, ensure_ascii=False)
            
            logger.info(f"토큰이 성공적으로 저장되었습니다: {user_id}")
            
        except Exception as e:
            logger.error(f"토큰 저장 중 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"토큰 저장 중 오류가 발생했습니다: {str(e)}"
            )

    async def load_tokens(self, user_id: str) -> Optional[Dict]:
        """저장된 토큰 로드"""
        try:
            if not self.token_file.exists():
                return None
            
            with open(self.token_file, 'r', encoding='utf-8') as f:
                tokens = json.load(f)
            
            return tokens.get(user_id)
            
        except Exception as e:
            logger.error(f"토큰 로드 중 오류: {str(e)}")
            return None

    async def get_valid_access_token(self, user_id: str) -> Optional[str]:
        """유효한 Access Token 반환 (자동 갱신 포함)"""
        try:
            # 저장된 토큰 로드
            token_data = await self.load_tokens(user_id)
            if not token_data:
                logger.warning(f"저장된 토큰이 없습니다: {user_id}")
                return None
            
            # 토큰 만료 확인
            expires_at = datetime.fromisoformat(token_data["expires_at"])
            now = datetime.now()
            
            # 토큰이 7일 이내에 만료되면 갱신
            if (expires_at - now).days < 7:
                logger.info(f"토큰이 곧 만료됩니다. 갱신을 시도합니다: {user_id}")
                
                # 토큰 갱신
                refreshed_data = await self.refresh_long_lived_token(token_data["access_token"])
                
                # 갱신된 토큰 저장
                await self.save_tokens(user_id, refreshed_data)
                
                return refreshed_data["access_token"]
            
            return token_data["access_token"]
            
        except Exception as e:
            logger.error(f"토큰 검증 중 오류: {str(e)}")
            return None

    async def revoke_access_token(self, user_id: str) -> bool:
        """Access Token 취소"""
        try:
            token_data = await self.load_tokens(user_id)
            if not token_data:
                return False
            
            # 토큰 취소는 Instagram API에서 직접 지원하지 않음
            # 대신 저장된 토큰을 삭제
            if self.token_file.exists():
                with open(self.token_file, 'r', encoding='utf-8') as f:
                    tokens = json.load(f)
                
                if user_id in tokens:
                    del tokens[user_id]
                    
                    with open(self.token_file, 'w', encoding='utf-8') as f:
                        json.dump(tokens, f, indent=2, ensure_ascii=False)
                    
                    logger.info(f"토큰이 삭제되었습니다: {user_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"토큰 취소 중 오류: {str(e)}")
            return False

    def _validate_image_url(self, image_url: str) -> bool:
        """이미지 URL 기본 검증"""
        try:
            # 이미지 파일 확장자 확인
            if not any(
                image_url.lower().endswith(ext)
                for ext in [".jpg", ".jpeg", ".png", ".gif"]
            ):
                logger.warning(f"Unsupported image format: {image_url}")
                return False

            return True
        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            return False

    def _convert_to_public_url(self, image_url: str) -> Optional[str]:
        """이미지 URL을 공개 URL로 변환 (간단버전)"""
        logger.info(f"이미지 URL 변환 시작: {image_url}")

        if image_url.startswith("http"):
            logger.info(f"이미 공개 URL입니다: {image_url}")
            return image_url
        else:
            logger.warning(f"지원하지 않는 이미지 경로 형식: {image_url}")
            return None

    async def upload_image_to_instagram(
        self, image_url: str, access_token: str, instagram_id: str, caption: str = None
    ) -> str:
        """이미지를 Instagram에 업로드하고 media_id 반환 (캡션 포함)"""
        logger.info(f"=== 이미지 업로드 시작 ===")
        logger.info(f"입력 image_url: {image_url}")
        logger.info(f"입력 instagram_id: {instagram_id}")
        logger.info(f"입력 caption: {caption}")
        logger.info(
            f"입력 access_token 길이: {len(access_token) if access_token else 0}"
        )

        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                logger.info(f"=== 시도 {retry_count + 1}/{max_retries} ===")
                # 이미지 URL을 공개 URL로 변환
                public_image_url = self._convert_to_public_url(image_url)
                logger.info(f"Converting image URL: {image_url} -> {public_image_url}")

                # 변환 실패 체크
                if not public_image_url:
                    logger.error(f"이미지 URL 변환 실패: {image_url}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"이미지 URL을 공개 URL로 변환할 수 없습니다. S3 설정을 확인하세요. 원본 URL: {image_url}",
                    )

                # 로컬 URL인 경우 인스타그램 업로드 불가능
                if public_image_url.startswith(
                    "https://localhost"
                ) or public_image_url.startswith("http://localhost"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="로컬 이미지 URL은 인스타그램 API에서 접근할 수 없습니다. 공개 URL을 사용하거나 S3 등의 클라우드 스토리지를 사용하세요.",
                    )

                async with httpx.AsyncClient() as client:

                    # Instagram API 요청 데이터 (캡션 포함)
                    request_data = {
                        "image_url": public_image_url,
                    }

                    # 캡션이 있으면 추가
                    if caption and caption.strip():
                        # Instagram API 캡션 요구사항 확인
                        safe_caption = caption.strip()

                        # 1. 캡션 길이 제한 (2200자)
                        if len(safe_caption) > 2200:
                            safe_caption = safe_caption[:2197] + "..."

                        # 2. 특수 문자 처리 (이모지 제거) - 해시태그 #은 유지
                        import re

                        safe_caption = re.sub(
                            r"[^\w\s\.,!?\-()가-힣#]", "", safe_caption
                        )

                        # 3. 빈 캡션 방지
                        if safe_caption.strip():
                            request_data["caption"] = safe_caption
                            logger.info(
                                f"Adding caption to image upload: {safe_caption}"
                            )
                            logger.info(f"Caption length: {len(safe_caption)}")
                            logger.info(
                                f"Caption contains hashtags: {'#' in safe_caption}"
                            )

                    logger.info(f"Instagram API request data: {request_data}")
                    logger.info(
                        f"Instagram API endpoint: {self.base_url}/{instagram_id}/media"
                    )

                    logger.info(
                        f"Making Instagram API request to: {self.base_url}/{instagram_id}/media"
                    )
                    logger.info(
                        f"Request headers: Authorization=Bearer {access_token[:20]}..., Content-Type=application/json"
                    )
                    logger.info(f"Request data: {request_data}")

                    response = await client.post(
                        f"{self.base_url}/{instagram_id}/media",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json",
                        },
                        json=request_data,
                        timeout=60.0,  # 60초 타임아웃으로 증가
                    )
                    logger.info(
                        f"Instagram API response status: {response.status_code}"
                    )
                    logger.info(f"Instagram API response headers: {response.headers}")
                    logger.info(f"Instagram API response text: {response.text}")

                    try:
                        response_json = response.json()
                        logger.info(f"Instagram API response JSON: {response_json}")
                    except Exception as e:
                        logger.error(
                            f"Failed to parse Instagram API response as JSON: {e}"
                        )
                        logger.error(f"Response text: {response.text}")

                    if response.status_code != 200:
                        logger.error(
                            f"Image upload failed: {response.status_code} - {response.text}"
                        )

                        # Instagram API 오류 메시지 파싱
                        error_message = "이미지 업로드에 실패했습니다"
                        try:
                            error_data = response.json()
                            if "error" in error_data:
                                error_detail = error_data["error"]
                                if "error_user_msg" in error_detail:
                                    error_message = error_detail["error_user_msg"]
                                elif "message" in error_detail:
                                    error_message = error_detail["message"]
                        except:
                            pass

                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"{error_message}: {response.text}",
                        )

                    try:
                        data = response.json()
                    except Exception as e:
                        logger.error(f"Failed to parse response as JSON: {e}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Instagram API 응답을 파싱할 수 없습니다: {response.text}",
                        )

                    media_id = data.get("id")

                    if not media_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Media ID를 받지 못했습니다.",
                        )

                    logger.info(f"Image uploaded successfully: {media_id}")
                    return media_id

            except httpx.ReadTimeout as e:
                retry_count += 1
                logger.warning(
                    f"Instagram API timeout (attempt {retry_count}/{max_retries}): {e}"
                )
                if retry_count >= max_retries:
                    logger.error(f"Instagram API timeout after {max_retries} attempts")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Instagram API 타임아웃: {max_retries}번 시도 후 실패",
                    )
                continue
            except Exception as e:
                logger.error(f"Image upload error: {str(e)}")
                logger.error(f"Exception type: {type(e)}")
                logger.error(f"Exception args: {e.args}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"이미지 업로드 중 오류가 발생했습니다: {str(e)}",
                )

    async def publish_post_to_instagram(
        self, media_id: str, caption: str, access_token: str, instagram_id: str
    ) -> Dict:
        """Instagram에 게시글 발행"""
        logger.info(f"=== 게시글 발행 시작 ===")
        logger.info(f"입력 media_id: {media_id}")
        logger.info(f"입력 caption: {caption}")
        logger.info(f"입력 instagram_id: {instagram_id}")
        logger.info(
            f"입력 access_token 길이: {len(access_token) if access_token else 0}"
        )

        try:
            # 캡션 디버깅 로그 추가
            logger.info(f"=== Instagram Publish Debug ===")
            logger.info(f"Media ID: {media_id}")
            logger.info(f"Caption to publish: {caption}")
            logger.info(f"Caption length: {len(caption)} characters")
            logger.info(f"Instagram ID: {instagram_id}")

            async with httpx.AsyncClient() as client:
                # 캡션을 params로 전송 (Instagram API 요구사항)
                # 빈 캡션이나 None인 경우 기본 텍스트 사용
                safe_caption = (
                    caption if caption and caption.strip() else "새로운 게시글입니다."
                )

                # Instagram API 캡션 요구사항 확인
                # 1. 캡션 길이 제한 (2200자)
                if len(safe_caption) > 2200:
                    safe_caption = safe_caption[:2197] + "..."

                # 2. 특수 문자 처리 (이모지 제거)
                import re

                safe_caption = re.sub(r"[^\w\s\.,!?\-()가-힣#]", "", safe_caption)

                # 3. 빈 캡션 방지
                if not safe_caption.strip():
                    safe_caption = "새로운 게시글입니다."

                    # Instagram API 발행 파라미터 (캡션은 이미 이미지 업로드 시 포함됨)
                publish_params = {
                    "access_token": access_token,
                    "creation_id": media_id,
                }

                # 캡션은 이미 이미지 업로드 시 포함되었으므로 발행 단계에서는 제외
                logger.info(
                    "Caption already included in image upload, skipping in publish step"
                )
                logger.info(f"Publish params: {publish_params}")
                logger.info(f"Original caption: {caption}")
                logger.info(f"Safe caption: {safe_caption}")
                logger.info(f"Caption length: {len(safe_caption)}")

                # 실제 요청 URL과 파라미터 로깅
                request_url = f"{self.base_url}/{instagram_id}/media_publish"
                logger.info(f"Making Instagram publish request to: {request_url}")
                logger.info(f"Request params: {publish_params}")

                response = await client.post(
                    request_url,
                    params=publish_params,
                    timeout=60.0,
                )

                logger.info(
                    f"Instagram publish response status: {response.status_code}"
                )
                logger.info(f"Instagram publish response headers: {response.headers}")
                logger.info(f"Instagram publish response text: {response.text}")

                if response.status_code != 200:
                    logger.error(
                        f"Post publishing failed: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"게시글 발행에 실패했습니다: {response.text}",
                    )

                data = response.json()
                logger.info(f"Post published successfully: {data.get('id')}")
                logger.info(f"Full publish API response: {data}")

                # 업로드된 게시글의 캡션 확인
                if data.get("id"):
                    try:
                        post_info = await self.get_instagram_post_info(
                            data.get("id"), access_token, instagram_id
                        )
                        logger.info(f"Uploaded post info: {post_info}")
                        logger.info(f"Post caption: {post_info.get('caption')}")
                    except Exception as e:
                        logger.warning(f"Could not verify post caption: {e}")

                return data

        except Exception as e:
            logger.error(f"Post publishing error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"게시글 발행 중 오류가 발생했습니다: {str(e)}",
            )

    async def post_to_instagram(
        self, instagram_id: str, access_token: str, image_url: str, caption: str
    ) -> Dict:
        """전체 Instagram 게시글 업로드 프로세스"""
        logger.info(f"=== Instagram Post Upload 시작 ===")
        logger.info(f"instagram_id: {instagram_id}")
        logger.info(f"image_url: {image_url}")
        logger.info(f"access_token 길이: {len(access_token) if access_token else 0}")
        logger.info(
            f"access_token 미리보기: {access_token[:20]}..." if access_token else "None"
        )

        try:
            logger.info(f"Starting Instagram post upload for account: {instagram_id}")

            # Instagram 계정 상태 확인
            logger.info("=== Instagram 계정 상태 확인 ===")
            account_status = await self.verify_instagram_permissions(
                access_token, instagram_id
            )
            if not account_status:
                logger.warning("Instagram 계정 상태 확인 실패, 하지만 계속 진행합니다.")

            # 캡션 디버깅 로그 추가
            logger.info(f"=== Instagram Post Debug ===")
            logger.info(f"Caption parameter: {caption}")
            logger.info(f"Caption type: {type(caption)}")
            logger.info(f"Caption length: {len(caption) if caption else 0}")

            # 1. 이미지 업로드 (캡션 포함)
            logger.info("=== 1단계: 이미지 업로드 시작 ===")
            media_id = await self.upload_image_to_instagram(
                image_url, access_token, instagram_id, caption
            )
            logger.info(f"이미지 업로드 성공 - media_id: {media_id}")

            # 2. 게시글 발행 (캡션은 이미 이미지 업로드 시 포함됨)
            logger.info("=== 2단계: 게시글 발행 시작 ===")
            logger.info(f"발행할 media_id: {media_id}")
            result = await self.publish_post_to_instagram(
                media_id, "", access_token, instagram_id  # 빈 캡션 전달
            )
            logger.info(f"게시글 발행 성공 - result: {result}")
            logger.info(f"Instagram post completed successfully: {result.get('id')}")
            logger.info(f"Full Instagram API response: {result}")

            # 인스타그램 API 응답에서 post ID 추출 (여러 가능한 필드 확인)
            logger.info(f"Full Instagram API response: {result}")
            logger.info(f"Response keys: {list(result.keys())}")

            instagram_post_id = (
                result.get("id")
                or result.get("post_id")
                or result.get("media_id")
                or result.get("creation_id")
            )
            logger.info(f"Extracted instagram_post_id: {instagram_post_id}")
            logger.info(
                f"Available fields: id={result.get('id')}, post_id={result.get('post_id')}, media_id={result.get('media_id')}, creation_id={result.get('creation_id')}"
            )

            # post ID가 없으면 에러 발생
            if not instagram_post_id:
                logger.error(f"No post ID found in Instagram API response: {result}")
                logger.error(f"Response type: {type(result)}")
                logger.error(
                    f"Response keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="인스타그램에서 post ID를 받지 못했습니다. API 응답을 확인해주세요.",
                )

            logger.info(f"=== Instagram 업로드 최종 성공 ===")
            logger.info(f"인스타그램 포스트 ID: {instagram_post_id}")
            logger.info(f"업로드된 게시글 정보:")
            logger.info(f"  - 인스타그램 ID: {instagram_id}")
            logger.info(f"  - 이미지 URL: {image_url}")
            logger.info(f"  - 캡션 길이: {len(caption)}자")

            return {
                "success": True,
                "instagram_post_id": instagram_post_id,
                "message": "인스타그램에 성공적으로 업로드되었습니다.",
            }

        except HTTPException as he:
            logger.error(f"❌ Instagram posting HTTPException: {str(he)}")
            logger.error(f"HTTPException detail: {he.detail}")
            logger.error(f"업로드 실패 정보:")
            logger.error(f"  - 인스타그램 ID: {instagram_id}")
            logger.error(f"  - 이미지 URL: {image_url}")
            logger.error(f"  - 캡션 길이: {len(caption)}자")
            raise
        except Exception as e:
            logger.error(f"❌ Instagram posting error: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error args: {e.args}")
            logger.error(f"업로드 실패 정보:")
            logger.error(f"  - 인스타그램 ID: {instagram_id}")
            logger.error(f"  - 이미지 URL: {image_url}")
            logger.error(f"  - 캡션 길이: {len(caption)}자")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"인스타그램 업로드 중 오류가 발생했습니다: {str(e)}",
            )

    async def verify_instagram_permissions(
        self, access_token: str, instagram_id: str
    ) -> bool:
        """Instagram 권한 확인"""
        try:
            async with httpx.AsyncClient() as client:
                # 1. 기본 계정 정보 확인
                response = await client.get(
                    f"{self.base_url}/{instagram_id}",
                    params={
                        "access_token": access_token,
                        "fields": "id,username,account_type,media_count,account_status",
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(
                        f"Instagram permissions verified: {data.get('username')}"
                    )
                    logger.info(f"Account type: {data.get('account_type')}")
                    logger.info(f"Account status: {data.get('account_status')}")
                    logger.info(f"Media count: {data.get('media_count')}")

                    # 2. 권한 확인 - 캡션 권한 체크
                    permissions_response = await client.get(
                        f"{self.base_url}/{instagram_id}/permissions",
                        params={
                            "access_token": access_token,
                            
                        },
                    )

                    if permissions_response.status_code == 200:
                        permissions_data = permissions_response.json()
                        logger.info(f"Instagram permissions: {permissions_data}")

                        # 캡션 관련 권한 확인
                        has_caption_permission = any(
                            perm.get("permission")
                            in ["instagram_basic", "instagram_content_publish"]
                            for perm in permissions_data.get("data", [])
                        )

                        if not has_caption_permission:
                            logger.warning(
                                "Instagram account may not have caption publishing permission"
                            )

                    return True
                elif response.status_code == 400:
                    error_data = response.json()
                    if error_data.get("error", {}).get("code") == 190:
                        logger.error("Instagram access token is invalid or expired")
                        return False
                    else:
                        logger.error(
                            f"Instagram permissions check failed: {response.status_code}"
                        )
                        return False
                else:
                    logger.error(
                        f"Instagram permissions check failed: {response.status_code}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Instagram permissions check error: {str(e)}")
            return False

    async def get_instagram_post_info(
        self, post_id: str, access_token: str, instagram_id: str
    ) -> Dict:
        """인스타그램 게시물 정보 조회"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{post_id}",
                    params={
                        "access_token": access_token,
                        "fields": "id,media_type,media_url,thumbnail_url,permalink,timestamp,caption,like_count,comments_count",
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"게시물 정보 조회 실패: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"게시물 정보 조회에 실패했습니다: {response.text}",
                    )

                data = response.json()
                logger.info(f"게시물 정보 조회 성공: {post_id}")
                return data

        except Exception as e:
            logger.error(f"게시물 정보 조회 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"게시물 정보 조회 중 오류가 발생했습니다: {str(e)}",
            )

    async def get_user_instagram_posts(
        self, access_token: str, instagram_id: str, limit: int = 10
    ) -> Dict:
        """인스타그램 사용자의 게시물 목록 조회"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{instagram_id}/media",
                    params={
                        "access_token": access_token,
                        "fields": "id,media_type,media_url,thumbnail_url,permalink,timestamp,caption,like_count,comments_count",
                        "limit": limit,
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"게시물 목록 조회 실패: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"게시물 목록 조회에 실패했습니다: {response.text}",
                    )

                data = response.json()
                logger.info(f"게시물 목록 조회 성공: {len(data.get('data', []))}개")
                return data

        except Exception as e:
            logger.error(f"게시물 목록 조회 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"게시물 목록 조회 중 오류가 발생했습니다: {str(e)}",
            )

    async def get_instagram_post_insights(
        self, post_id: str, access_token: str, instagram_id: str
    ) -> Dict:
        """인스타그램 게시물 인사이트(통계) 조회"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{post_id}/insights",
                    params={"access_token": access_token, "metric": ""},
                )

                if response.status_code != 200:
                    logger.error(
                        f"게시물 인사이트 조회 실패: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"게시물 인사이트 조회에 실패했습니다: {response.text}",
                    )

                data = response.json()
                logger.info(f"게시물 인사이트 조회 성공: {post_id}")
                return data

        except Exception as e:
            logger.error(f"게시물 인사이트 조회 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"게시물 인사이트 조회 중 오류가 발생했습니다: {str(e)}",
            )

    async def get_instagram_post_comments(
        self, post_id: str, access_token: str, instagram_id: str, limit: int = 10
    ) -> Dict:
        """인스타그램 게시물 댓글 조회"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{post_id}/comments",
                    params={
                        "access_token": access_token,
                        "fields": "id,text,timestamp,username",
                        "limit": limit,
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"게시물 댓글 조회 실패: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"게시물 댓글 조회에 실패했습니다: {response.text}",
                    )

                data = response.json()
                logger.info(f"게시물 댓글 조회 성공: {post_id}")
                return data

        except Exception as e:
            logger.error(f"게시물 댓글 조회 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"게시물 댓글 조회 중 오류가 발생했습니다: {str(e)}",
            )

    async def get_instagram_post_info_batch(
        self, post_ids: List[str], access_token: str, instagram_id: str
    ) -> Dict[str, Dict]:
        """인스타그램 게시물 정보 배치 조회"""
        results = {}

        for post_id in post_ids:
            try:
                post_info = await self.get_instagram_post_info(
                    post_id, access_token, instagram_id
                )
                results[post_id] = post_info
            except Exception as e:
                logger.error(f"Failed to get post info for {post_id}: {str(e)}")
                results[post_id] = None

        return results

    async def get_instagram_post_insights_batch(
        self, post_ids: List[str], access_token: str, instagram_id: str
    ) -> Dict[str, Dict]:
        """인스타그램 게시물 인사이트 배치 조회"""
        results = {}

        for post_id in post_ids:
            try:
                insights = await self.get_instagram_post_insights(
                    post_id, access_token, instagram_id
                )
                results[post_id] = insights
            except Exception as e:
                logger.error(f"Failed to get insights for {post_id}: {str(e)}")
                results[post_id] = None

        return results

    # # 테스트용 값 (실제 값으로 대체 필요)
    # ACCESS_TOKEN = "IGAApvP0R9Y3tBZAE5LTWxIZADUtYnU5N1o5akt6OWgxMFZAvZAXpsNmtBeUUtX2VCVDFIQWpoWk9NSEFpZATdZAQ2x3ZA21oUlBJUmRyNExyOUJsTE5NSmJfbW5JVEw0cFVhM2JCMWxEVjdDcVBIVHRUb1d2Q29fQWUtMVVGVk5aRzl2WQZDZD"  # Instagram Graph API에서 받은 long-lived 토큰
    # INSTAGRAM_ID = "17841464558647230"  # 연결된 비즈니스 Instagram 계정 ID
    # IMAGE_URL = "https://m.health.chosun.com/site/data/img_dir/2025/04/08/2025040803041_0.jpg"  # 공개 접근 가능한 이미지 URL
    # CAPTION = "🚀 오늘도 열심히! #테스트"
    
    # async def test_post_to_instagram():
    #     service = InstagramPostingService()
    #     result = await service.post_to_instagram(
    #         instagram_id=INSTAGRAM_ID,
    #         access_token=ACCESS_TOKEN,
    #         image_url=IMAGE_URL,
    #         caption=CAPTION,
    #     )
    #     print("✅ 업로드 결과:", result)
    
    async def test_get_access_token():
        service = InstagramPostingService()
        auth_url = service.get_instagram_auth_url()
        print(f"이 URL로 이동하세요: {auth_url}")
        code = "사용자가_받은_인증_코드"
        token_info = await service.get_access_token(code)
        print(f"액세스 토큰: {token_info['access_token']}")
        
    if __name__ == "__main__":
        asyncio.run(test_get_access_token())
        
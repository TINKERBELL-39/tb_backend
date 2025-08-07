"""
HTTP 클라이언트 공통 모듈
"""

import aiohttp
import json
import base64
from typing import Dict, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)


class HttpClient:
    """HTTP 요청을 위한 공통 클래스"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
    
    async def get(self, url: str, headers: Optional[Dict[str, str]] = None, 
                  params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET 요청"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=headers, params=params) as response:
                    return await self._process_response(response)
        except Exception as e:
            logger.error(f"GET 요청 실패 ({url}): {e}")
            return {"success": False, "error": str(e)}
    
    async def post(self, url: str, data: Optional[Union[Dict, str]] = None,
                   json_data: Optional[Dict[str, Any]] = None,
                   headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """POST 요청"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                kwargs = {"headers": headers}
                
                if json_data:
                    kwargs["json"] = json_data
                elif data:
                    kwargs["data"] = data
                
                async with session.post(url, **kwargs) as response:
                    return await self._process_response(response)
        except Exception as e:
            logger.error(f"POST 요청 실패 ({url}): {e}")
            return {"success": False, "error": str(e)}
    
    async def put(self, url: str, data: Optional[Union[Dict, str]] = None,
                  json_data: Optional[Dict[str, Any]] = None,
                  headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """PUT 요청"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                kwargs = {"headers": headers}
                
                if json_data:
                    kwargs["json"] = json_data
                elif data:
                    kwargs["data"] = data
                
                async with session.put(url, **kwargs) as response:
                    return await self._process_response(response)
        except Exception as e:
            logger.error(f"PUT 요청 실패 ({url}): {e}")
            return {"success": False, "error": str(e)}
    
    async def delete(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """DELETE 요청"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.delete(url, headers=headers) as response:
                    return await self._process_response(response)
        except Exception as e:
            logger.error(f"DELETE 요청 실패 ({url}): {e}")
            return {"success": False, "error": str(e)}
    
    async def _process_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """응답 처리"""
        try:
            content_type = response.headers.get('Content-Type', '')
            
            if 'application/json' in content_type:
                data = await response.json()
            else:
                data = await response.text()
            
            if response.status >= 200 and response.status < 300:
                return {
                    "success": True,
                    "status_code": response.status,
                    "data": data,
                    "headers": dict(response.headers)
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status,
                    "error": data,
                    "headers": dict(response.headers)
                }
        except Exception as e:
            logger.error(f"응답 처리 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "status_code": response.status
            }


class OAuthHttpClient(HttpClient):
    """OAuth 인증이 포함된 HTTP 클라이언트"""
    
    def __init__(self, timeout: int = 30):
        super().__init__(timeout)
    
    async def oauth_request(self, method: str, url: str, access_token: str,
                           token_type: str = "Bearer", **kwargs) -> Dict[str, Any]:
        """OAuth 토큰을 사용한 HTTP 요청"""
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"{token_type} {access_token}"
        kwargs["headers"] = headers
        
        if method.upper() == "GET":
            return await self.get(url, **kwargs)
        elif method.upper() == "POST":
            return await self.post(url, **kwargs)
        elif method.upper() == "PUT":
            return await self.put(url, **kwargs)
        elif method.upper() == "DELETE":
            return await self.delete(url, **kwargs)
        else:
            return {"success": False, "error": f"지원하지 않는 HTTP 메서드: {method}"}
    
    async def exchange_oauth_code(self, token_url: str, client_id: str, client_secret: str,
                                 code: str, redirect_uri: str, grant_type: str = "authorization_code",
                                 additional_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """OAuth Authorization Code를 Access Token으로 교환"""
        data = {
            "grant_type": grant_type,
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        if additional_params:
            data.update(additional_params)
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        return await self.post(token_url, data=data, headers=headers)
    
    async def refresh_oauth_token(self, token_url: str, client_id: str, client_secret: str,
                                 refresh_token: str, additional_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """OAuth Refresh Token으로 Access Token 갱신"""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        if additional_params:
            data.update(additional_params)
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        return await self.post(token_url, data=data, headers=headers)
    
    def create_basic_auth_header(self, username: str, password: str) -> str:
        """Basic Authentication 헤더 생성"""
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded_credentials}"


# 전역 인스턴스
_http_client = None
_oauth_http_client = None

def get_http_client() -> HttpClient:
    """HttpClient 싱글톤 인스턴스 반환"""
    global _http_client
    if _http_client is None:
        _http_client = HttpClient()
    return _http_client

def get_oauth_http_client() -> OAuthHttpClient:
    """OAuthHttpClient 싱글톤 인스턴스 반환"""
    global _oauth_http_client
    if _oauth_http_client is None:
        _oauth_http_client = OAuthHttpClient()
    return _oauth_http_client

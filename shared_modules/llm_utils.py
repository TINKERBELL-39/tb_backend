"""
LLM 유틸리티 공통 모듈
각 에이전트에서 공통으로 사용하는 LLM 클라이언트 및 유틸리티 함수
"""

import logging
from typing import Dict, Any, List, Optional, Union
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.messages import BaseMessage

from shared_modules.env_config import get_config

logger = logging.getLogger(__name__)

class LLMManager:
    """LLM 클라이언트 관리 클래스"""
    
    def __init__(self, config=None):
        """
        LLM 매니저 초기화
        
        Args:
            config: 환경 설정 객체 (기본값: 전역 설정 사용)
        """
        self.config = config if config else get_config()
        self.models = {}
        self.current_provider = None
        self.call_count = 0  # API 호출 카운트 (로드 밸런싱용)
        
        # 출력 파서 초기화
        self.str_parser = StrOutputParser()
        self.json_parser = JsonOutputParser()
        
        self._initialize_models()
    
    def _initialize_models(self):
        """LLM 모델 초기화"""
        try:
            # OpenAI 모델 초기화
            if self.config.OPENAI_API_KEY:
                self.models["openai"] = ChatOpenAI(
                    model=self.config.DEFAULT_MODEL if "gpt" in self.config.DEFAULT_MODEL else "gpt-4o-mini",
                    api_key=self.config.OPENAI_API_KEY,
                    temperature=self.config.TEMPERATURE,
                    max_tokens=self.config.MAX_TOKENS
                )
                logger.info("OpenAI 모델 초기화 성공")
            
            # Google Gemini 모델 초기화
            if self.config.GOOGLE_API_KEY:
                self.models["gemini"] = ChatGoogleGenerativeAI(
                    model=self.config.DEFAULT_MODEL if "gemini" in self.config.DEFAULT_MODEL else "gemini-2.0-flash",
                    google_api_key=self.config.GOOGLE_API_KEY,
                    temperature=self.config.TEMPERATURE,
                    max_output_tokens=self.config.MAX_TOKENS
                )
                logger.info("Gemini 모델 초기화 성공")
            
            # 기본 모델 설정 (우선순위: Gemini > OpenAI)
            if "gemini" in self.models:
                self.current_provider = "gemini"
            elif "openai" in self.models:
                self.current_provider = "openai"
            else:
                logger.warning("사용 가능한 LLM 모델이 없습니다")
            
        except Exception as e:
            logger.error(f"LLM 모델 초기화 실패: {e}")
    
    def get_llm(self, provider: str = None, load_balance: bool = False):
        """
        LLM 모델 반환
        
        Args:
            provider: 특정 프로바이더 지정 ("openai", "gemini")
            load_balance: 로드 밸런싱 사용 여부
        
        Returns:
            LLM 모델 객체
        """
        if load_balance:
            return self._get_load_balanced_llm()
        
        if provider and provider in self.models:
            return self.models[provider]
        
        if self.current_provider and self.current_provider in self.models:
            return self.models[self.current_provider]
        
        # 사용 가능한 첫 번째 모델 반환
        if self.models:
            return list(self.models.values())[0]
        
        logger.error("사용 가능한 LLM 모델이 없습니다")
        return None
    
    def _get_load_balanced_llm(self):
        """로드 밸런싱된 LLM 반환"""
        self.call_count += 1
        
        available_models = list(self.models.keys())
        if not available_models:
            return None
        
        # 간단한 라운드 로빈 로드 밸런싱
        if len(available_models) == 1:
            return self.models[available_models[0]]
        
        # OpenAI와 Gemini 간 번갈아 사용
        if self.call_count <= 10:
            provider = "openai" if "openai" in self.models else available_models[0]
        elif self.call_count <= 20:
            provider = "gemini" if "gemini" in self.models else available_models[0]
        else:
            self.call_count = 1
            provider = "openai" if "openai" in self.models else available_models[0]
        
        return self.models[provider]
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        provider: str = None,
        output_format: str = "string",
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """
        LLM 응답 생성
        
        Args:
            messages: 메시지 리스트 [{"role": "user", "content": "..."}]
            provider: 특정 프로바이더 지정
            output_format: 출력 형식 ("string", "json")
            **kwargs: 추가 매개변수
        
        Returns:
            LLM 응답 (문자열 또는 딕셔너리)
        """
        try:
            llm = self.get_llm(provider, kwargs.get("load_balance", False))
            if not llm:
                return "죄송합니다. 현재 AI 서비스에 접속할 수 없습니다."
            
            # 프롬프트 템플릿 생성
            prompt = ChatPromptTemplate.from_messages([
                (msg["role"], msg["content"]) for msg in messages
            ])
            
            # 체인 구성
            if output_format == "json":
                chain = prompt | llm | self.json_parser
            else:
                chain = prompt | llm | self.str_parser
            
            # 응답 생성
            result = await chain.ainvoke({})
            return result
            
        except Exception as e:
            logger.error(f"LLM 응답 생성 실패: {e}")
            
            # 폴백 시도
            if provider and provider != self.current_provider:
                try:
                    return await self.generate_response(
                        messages, 
                        provider=self.current_provider,
                        output_format=output_format,
                        **kwargs
                    )
                except Exception as fallback_error:
                    logger.error(f"폴백 응답 생성도 실패: {fallback_error}")
            
            return "죄송합니다. 응답을 생성할 수 없습니다."
    
    def generate_response_sync(
        self,
        messages: List[Dict[str, str]],
        provider: str = None,
        output_format: str = "string",
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """
        LLM 응답 생성 (동기 버전)
        
        Args:
            messages: 메시지 리스트
            provider: 특정 프로바이더 지정
            output_format: 출력 형식
            **kwargs: 추가 매개변수
        
        Returns:
            LLM 응답
        """
        try:
            llm = self.get_llm(provider, kwargs.get("load_balance", False))
            if not llm:
                return "죄송합니다. 현재 AI 서비스에 접속할 수 없습니다."
            
            # 프롬프트 템플릿 생성
            prompt = ChatPromptTemplate.from_messages([
                (msg["role"], msg["content"]) for msg in messages
            ])
            
            # 체인 구성
            if output_format == "json":
                chain = prompt | llm | self.json_parser
            else:
                chain = prompt | llm | self.str_parser
            
            # 응답 생성
            result = chain.invoke({})
            return result
            
        except Exception as e:
            logger.error(f"LLM 응답 생성 실패: {e}")
            
            # 폴백 시도
            if provider and provider != self.current_provider:
                try:
                    return self.generate_response_sync(
                        messages,
                        provider=self.current_provider,
                        output_format=output_format,
                        **kwargs
                    )
                except Exception as fallback_error:
                    logger.error(f"폴백 응답 생성도 실패: {fallback_error}")
            
            return "죄송합니다. 응답을 생성할 수 없습니다."
    
    def get_available_models(self) -> List[str]:
        """사용 가능한 모델 목록 반환"""
        return list(self.models.keys())
    
    def get_status(self) -> Dict[str, Any]:
        """LLM 매니저 상태 반환"""
        return {
            "available_models": self.get_available_models(),
            "current_provider": self.current_provider,
            "call_count": self.call_count,
            "config": {
                "default_model": self.config.DEFAULT_MODEL,
                "max_tokens": self.config.MAX_TOKENS,
                "temperature": self.config.TEMPERATURE
            }
        }
    
    def test_connection(self) -> Dict[str, bool]:
        """모든 모델 연결 테스트"""
        results = {}
        
        for provider, model in self.models.items():
            try:
                # 간단한 테스트 메시지
                test_messages = [
                    {"role": "user", "content": "안녕하세요! 간단한 인사를 해주세요."}
                ]
                
                response = self.generate_response_sync(test_messages, provider=provider)
                results[provider] = bool(response and "죄송합니다" not in response)
                
            except Exception as e:
                logger.error(f"{provider} 연결 테스트 실패: {e}")
                results[provider] = False
        
        return results


# 전역 LLM 매니저 인스턴스
_global_llm_manager = None

def get_llm_manager(config=None) -> LLMManager:
    """
    전역 LLM 매니저 인스턴스 반환 (싱글톤)
    
    Args:
        config: 환경 설정 객체
    
    Returns:
        LLMManager: LLM 매니저 인스턴스
    """
    global _global_llm_manager
    if _global_llm_manager is None:
        _global_llm_manager = LLMManager(config)
    return _global_llm_manager

def reload_llm_manager(config=None) -> LLMManager:
    """
    LLM 매니저 재로드
    
    Args:
        config: 환경 설정 객체
    
    Returns:
        LLMManager: 새로운 LLM 매니저 인스턴스
    """
    global _global_llm_manager
    _global_llm_manager = LLMManager(config)
    return _global_llm_manager

# 편의 함수들
def get_llm(provider: str = None, load_balance: bool = False):
    """LLM 모델 반환"""
    return get_llm_manager().get_llm(provider, load_balance)

async def generate_response(messages: List[Dict[str, str]], **kwargs) -> Union[str, Dict[str, Any]]:
    """LLM 응답 생성 (비동기)"""
    return await get_llm_manager().generate_response(messages, **kwargs)

def generate_response_sync(messages: List[Dict[str, str]], **kwargs) -> Union[str, Dict[str, Any]]:
    """LLM 응답 생성 (동기)"""
    return get_llm_manager().generate_response_sync(messages, **kwargs)

def call_llm(prompt: str, model: str = None, temperature: float = None) -> str:
    """
    간단한 LLM 호출 함수 (기존 코드 호환성용)
    
    Args:
        prompt: 프롬프트 텍스트
        model: 모델 이름 (무시됨, 설정에서 관리)
        temperature: 온도 (무시됨, 설정에서 관리)
    
    Returns:
        str: LLM 응답
    """
    messages = [{"role": "user", "content": prompt}]
    return generate_response_sync(messages)

def test_llm_connection() -> bool:
    """LLM 연결 테스트"""
    results = get_llm_manager().test_connection()
    return any(results.values())

# 기존 코드와의 호환성을 위한 LLM 인스턴스들
llm_openai = get_llm("openai")
llm_gemini = get_llm("gemini")
llm = get_llm()  # 기본 LLM

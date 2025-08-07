"""
Task Agent 유틸리티 함수들 v4
공통 모듈의 utils를 활용하여 유틸리티 제공
"""

import sys
import os
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from functools import lru_cache

# 공통 모듈 경로 추가
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared_modules.utils import (
    get_current_timestamp,
    ensure_directory_exists,
    truncate_text,
    merge_dicts,
    validate_email,
    create_error_response,
    create_success_response,
    PromptTemplate
)
from shared_modules.logging_utils import setup_logging

# ===== Task Agent 전용 유틸리티 =====

def generate_task_id(prefix: str = "task") -> str:
    """작업 ID 생성"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}_{timestamp}_{unique_id}"

def generate_conversation_id(user_id: str = None) -> str:
    """대화 ID 생성"""
    if user_id:
        return f"conv_{user_id}_{uuid.uuid4().hex[:12]}"
    return f"conv_{uuid.uuid4().hex[:16]}"

class TaskAgentLogger:
    """Task Agent 전용 로깅 유틸리티"""
    
    @staticmethod
    def setup(level: str = "INFO", log_file: str = None):
        """Task Agent 로깅 설정"""
        if log_file is None:
            log_dir = os.path.join(os.path.dirname(__file__), "logs")
            ensure_directory_exists(log_dir)
            log_file = os.path.join(log_dir, f"task_agent_{get_current_timestamp()}.log")
        
        return setup_logging(
            name="task_agent",
            level=level,
            log_file=log_file,
            format_string='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
    
    @staticmethod
    def log_user_interaction(user_id: str, action: str, details: str = None):
        """사용자 상호작용 로깅"""
        logger = logging.getLogger("task_agent")
        log_message = f"사용자 상호작용 - ID: {user_id}, 액션: {action}"
        if details:
            log_message += f", 세부사항: {details}"
        logger.info(log_message)
    
    @staticmethod
    def log_automation_task(task_id: str, task_type: str, status: str, details: str = None):
        """자동화 작업 로깅"""
        logger = logging.getLogger("task_agent")
        log_message = f"자동화 작업 - ID: {task_id}, 타입: {task_type}, 상태: {status}"
        if details:
            log_message += f", 세부사항: {details}"
        logger.info(log_message)

class TaskAgentResponseFormatter:
    """Task Agent 전용 응답 포맷터"""
    
    @staticmethod
    def query_response(
        response: str,
        conversation_id: str,
        intent: str,
        urgency: str = "medium",
        confidence: float = 0.5,
        actions: List[Dict[str, Any]] = None,
        sources: List[str] = None
    ) -> Dict[str, Any]:
        """쿼리 응답 포맷"""
        return {
            "status": "success",
            "response": response,
            "conversation_id": conversation_id,
            "intent": intent,
            "urgency": urgency,
            "confidence": confidence,
            "actions": actions or [],
            "sources": sources or [],
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def automation_response(
        task_id: int,
        status: str,
        message: str,
        scheduled_time: datetime = None
    ) -> Dict[str, Any]:
        """자동화 작업 응답 포맷"""
        response = {
            "task_id": task_id,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if scheduled_time:
            response["scheduled_time"] = scheduled_time.isoformat()
        
        return response
    
    @staticmethod
    def error_response(error_message: str, error_code: str = None, conversation_id: str = None) -> Dict[str, Any]:
        """에러 응답 포맷"""
        response = create_error_response(error_message, error_code)
        
        if conversation_id:
            response["conversation_id"] = conversation_id
        
        return response

class TaskAgentCacheManager:
    """Task Agent 전용 캐시 매니저"""
    
    def __init__(self, ttl: int = 1800):
        self._cache = {}
        self._conversation_cache = {}
        self._ttl = ttl
    
    def get_conversation_context(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """대화 컨텍스트 조회"""
        return self._get_cached_item(self._conversation_cache, conversation_id)
    
    def set_conversation_context(self, conversation_id: str, context: Dict[str, Any]):
        """대화 컨텍스트 저장"""
        self._set_cached_item(self._conversation_cache, conversation_id, context)
    
    def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """사용자 선호도 조회"""
        return self._get_cached_item(self._cache, f"user_prefs_{user_id}")
    
    def set_user_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """사용자 선호도 저장"""
        self._set_cached_item(self._cache, f"user_prefs_{user_id}", preferences)
    
    def get_intent_cache(self, message_hash: str) -> Optional[Dict[str, Any]]:
        """의도 분석 캐시 조회"""
        return self._get_cached_item(self._cache, f"intent_{message_hash}")
    
    def set_intent_cache(self, message_hash: str, intent_result: Dict[str, Any]):
        """의도 분석 캐시 저장"""
        self._set_cached_item(self._cache, f"intent_{message_hash}", intent_result)
    
    def _get_cached_item(self, cache_dict: Dict, key: str) -> Optional[Any]:
        """캐시에서 항목 조회"""
        if key in cache_dict:
            value, timestamp = cache_dict[key]
            if (datetime.now() - timestamp).seconds < self._ttl:
                return value
            else:
                del cache_dict[key]
        return None
    
    def _set_cached_item(self, cache_dict: Dict, key: str, value: Any):
        """캐시에 항목 저장"""
        cache_dict[key] = (value, datetime.now())
    
    def cleanup_expired(self) -> int:
        """만료된 캐시 정리"""
        now = datetime.now()
        expired_count = 0
        
        # 일반 캐시 정리
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items()
            if (now - timestamp).seconds >= self._ttl
        ]
        for key in expired_keys:
            del self._cache[key]
            expired_count += 1
        
        # 대화 캐시 정리
        expired_conv_keys = [
            key for key, (_, timestamp) in self._conversation_cache.items()
            if (now - timestamp).seconds >= self._ttl
        ]
        for key in expired_conv_keys:
            del self._conversation_cache[key]
            expired_count += 1
        
        return expired_count
    
    def clear_all(self):
        """모든 캐시 클리어"""
        self._cache.clear()
        self._conversation_cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        return {
            "general_cache_size": len(self._cache),
            "conversation_cache_size": len(self._conversation_cache),
            "ttl_seconds": self._ttl,
            "last_cleanup": datetime.now().isoformat()
        }

# ===== Task Agent 전용 텍스트 처리 =====

@lru_cache(maxsize=256)
def extract_task_keywords(text: str, max_keywords: int = 8) -> List[str]:
    """작업 관련 키워드 추출"""
    task_related_words = [
        "자동화", "스케줄", "일정", "예약", "알림", "미팅", "회의", "이메일", 
        "메시지", "SNS", "포스팅", "업로드", "다운로드", "백업", "정리"
    ]
    
    words = text.split()
    keywords = []
    
    # 작업 관련 단어 우선 추출
    for word in words:
        if word in task_related_words:
            keywords.append(word)
    
    # 일반 키워드 추가
    general_keywords = [word for word in words if len(word) > 2 and word not in task_related_words]
    keywords.extend(general_keywords[:max_keywords - len(keywords)])
    
    return keywords[:max_keywords]

def parse_time_expression(text: str) -> Optional[datetime]:
    """자연어 시간 표현 파싱 (간단한 버전)"""
    import re
    from datetime import datetime, timedelta
    
    now = datetime.now()
    text_lower = text.lower()
    
    # 오늘/내일/모레 패턴
    if "오늘" in text_lower:
        return now.replace(hour=14, minute=0, second=0, microsecond=0)  # 기본 오후 2시
    elif "내일" in text_lower:
        return (now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
    elif "모레" in text_lower:
        return (now + timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)
    
    # 시간 패턴 (예: "오후 3시", "15시", "3시 30분")
    time_patterns = [
        r'(\d{1,2})시\s*(\d{1,2})분',  # "3시 30분"
        r'(\d{1,2})시',  # "3시"
        r'오후\s*(\d{1,2})시',  # "오후 3시"
        r'오전\s*(\d{1,2})시',  # "오전 9시"
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                hour = int(match.group(1))
                minute = int(match.group(2)) if len(match.groups()) > 1 else 0
                
                # 오후 처리
                if "오후" in text_lower and hour < 12:
                    hour += 12
                
                return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            except (ValueError, IndexError):
                continue
    
    return None

def format_task_summary(task_data: Dict[str, Any]) -> str:
    """작업 데이터 요약 포맷"""
    task_type = task_data.get("task_type", "알 수 없음")
    title = task_data.get("title", "제목 없음")
    
    summary = f"[{task_type}] {title}"
    
    if "scheduled_at" in task_data:
        scheduled_time = task_data["scheduled_at"]
        if isinstance(scheduled_time, str):
            summary += f" (예정: {scheduled_time})"
        elif hasattr(scheduled_time, "strftime"):
            summary += f" (예정: {scheduled_time.strftime('%Y-%m-%d %H:%M')})"
    
    return summary

# ===== 전역 인스턴스 =====

# Task Agent 전용 캐시 매니저
task_cache = TaskAgentCacheManager()

# Task Agent 전용 로거 설정
task_logger = TaskAgentLogger.setup()


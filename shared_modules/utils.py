"""
공통 유틸리티 모듈
각 에이전트에서 공통으로 사용하는 유틸리티 함수들
"""

import logging
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
# import pytz
from shared_modules import (
    create_conversation,
    get_conversation_by_id,
    get_session_context
)
from shared_modules.db_models import TemplateMessage

def get_or_create_conversation_session(user_id: int, conversation_id: int = None) -> Dict[str, Any]:
    """통일된 대화 세션 조회 또는 생성 로직"""
    try:
        with get_session_context() as db:
            if conversation_id:
                conversation = get_conversation_by_id(db, conversation_id)
                if conversation and conversation.user_id == user_id:
                    print(f"🔄 기존 대화 세션 사용: {conversation_id}")
                    return {
                        "conversation_id": conversation.conversation_id,
                        "is_new": False
                    }
            
            # 새 대화 세션 생성
            conversation = create_conversation(db, user_id)
            if not conversation:
                print(f"❌ 대화 세션 생성 실패 - user_id: {user_id}")
                raise Exception("대화 세션 생성에 실패했습니다")
            
            print(f"🆕 새 대화 세션 생성: {conversation.conversation_id}")
            return {
                "conversation_id": conversation.conversation_id,
                "is_new": True
            }
    except Exception as e:
        print(f"❌ 대화 세션 처리 실패: {e}")
        raise


def load_prompt_from_file(file_path: str, encoding: str = 'utf-8') -> str:
    """
    파일에서 프롬프트 텍스트 로드
    
    Args:
        file_path: 프롬프트 파일 경로
        encoding: 파일 인코딩
    
    Returns:
        str: 프롬프트 텍스트
    """
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            return f.read().strip()
    except Exception as e:
        logging.error(f"프롬프트 파일 로드 실패 ({file_path}): {e}")
        return ""

def save_prompt_to_file(prompt: str, file_path: str, encoding: str = 'utf-8') -> bool:
    """
    프롬프트 텍스트를 파일에 저장
    
    Args:
        prompt: 저장할 프롬프트 텍스트
        file_path: 저장할 파일 경로
        encoding: 파일 인코딩
    
    Returns:
        bool: 성공 여부
    """
    try:
        # 디렉토리 생성
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(prompt)
        
        return True
    except Exception as e:
        logging.error(f"프롬프트 파일 저장 실패 ({file_path}): {e}")
        return False

def load_json_file(file_path: str, default: Any = None) -> Any:
    """
    JSON 파일 로드
    
    Args:
        file_path: JSON 파일 경로
        default: 로드 실패 시 기본값
    
    Returns:
        Any: JSON 데이터 또는 기본값
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"JSON 파일 로드 실패 ({file_path}): {e}")
        return default

def save_json_file(data: Any, file_path: str, indent: int = 2) -> bool:
    """
    JSON 파일 저장
    
    Args:
        data: 저장할 데이터
        file_path: 저장할 파일 경로
        indent: JSON 들여쓰기
    
    Returns:
        bool: 성공 여부
    """
    try:
        # 디렉토리 생성
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        
        return True
    except Exception as e:
        logging.error(f"JSON 파일 저장 실패 ({file_path}): {e}")
        return False

def format_conversation_history(
    conversation_history: List[Dict[str, str]], 
    max_messages: int = 10,
    format_template: str = None
) -> str:
    """
    대화 히스토리 포맷팅
    
    Args:
        conversation_history: 대화 히스토리 리스트
        max_messages: 최대 메시지 수
        format_template: 포맷 템플릿 ("role: content" 형식)
    
    Returns:
        str: 포맷팅된 대화 히스토리
    """
    if not conversation_history:
        return ""
    
    # 최근 메시지만 사용
    recent_messages = conversation_history[-max_messages:] if max_messages > 0 else conversation_history
    
    formatted_messages = []
    for msg in recent_messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        
        # 역할 한글화
        role_map = {
            "user": "사용자",
            "assistant": "에이전트",
            "system": "시스템"
        }
        role_kr = role_map.get(role, role)
        
        if format_template:
            formatted = format_template.format(role=role_kr, content=content)
        else:
            formatted = f"{role_kr}: {content}"
        
        formatted_messages.append(formatted)
    
    return "\n".join(formatted_messages)

def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    파일명 정리 (특수문자 제거, 길이 제한)
    
    Args:
        filename: 원본 파일명
        max_length: 최대 길이
    
    Returns:
        str: 정리된 파일명
    """
    import re
    
    # 특수문자 제거 및 공백을 언더스코어로 변경
    cleaned = re.sub(r'[<>:"/\\|?*]', '', filename)
    cleaned = re.sub(r'\s+', '_', cleaned)
    
    # 길이 제한
    if len(cleaned) > max_length:
        name, ext = os.path.splitext(cleaned)
        cleaned = name[:max_length - len(ext)] + ext
    
    return cleaned

def get_current_timestamp(format_string: str = "%Y%m%d_%H%M%S") -> str:
    """
    현재 시간 문자열 반환
    
    Args:
        format_string: 시간 포맷 문자열
    
    Returns:
        str: 포맷팅된 시간 문자열
    """
    return datetime.now().strftime(format_string)

def ensure_directory_exists(directory_path: str) -> bool:
    """
    디렉토리 존재 확인 및 생성
    
    Args:
        directory_path: 디렉토리 경로
    
    Returns:
        bool: 성공 여부
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"디렉토리 생성 실패 ({directory_path}): {e}")
        return False

def get_file_size_mb(file_path: str) -> float:
    """
    파일 크기를 MB 단위로 반환
    
    Args:
        file_path: 파일 경로
    
    Returns:
        float: 파일 크기 (MB)
    """
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except Exception:
        return 0.0

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    텍스트 길이 제한
    
    Args:
        text: 원본 텍스트
        max_length: 최대 길이
        suffix: 생략 표시
    
    Returns:
        str: 제한된 텍스트
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    여러 딕셔너리 병합 (나중 값이 우선)
    
    Args:
        *dicts: 병합할 딕셔너리들
    
    Returns:
        Dict[str, Any]: 병합된 딕셔너리
    """
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result

def validate_email(email: str) -> bool:
    """
    이메일 주소 유효성 검사
    
    Args:
        email: 이메일 주소
    
    Returns:
        bool: 유효성 여부
    """
    import re
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def extract_domain_from_url(url: str) -> str:
    """
    URL에서 도메인 추출
    
    Args:
        url: URL 문자열
    
    Returns:
        str: 도메인
    """
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ""

def parse_duration_string(duration_str: str) -> int:
    """
    기간 문자열을 초 단위로 변환 (예: "1h 30m" -> 5400)
    
    Args:
        duration_str: 기간 문자열 (예: "1h", "30m", "1h 30m")
    
    Returns:
        int: 초 단위 시간
    """
    import re
    
    total_seconds = 0
    
    # 시간 단위 패턴
    patterns = {
        r'(\d+)h': 3600,  # 시간
        r'(\d+)m': 60,    # 분
        r'(\d+)s': 1      # 초
    }
    
    for pattern, multiplier in patterns.items():
        matches = re.findall(pattern, duration_str.lower())
        for match in matches:
            total_seconds += int(match) * multiplier
    
    return total_seconds

def create_error_response(error_message: str, error_code: str = None) -> Dict[str, Any]:
    """
    표준 에러 응답 생성
    
    Args:
        error_message: 에러 메시지
        error_code: 에러 코드
    
    Returns:
        Dict[str, Any]: 에러 응답 딕셔너리
    """
    response = {
        "success": False,
        "error": error_message,
        "timestamp": datetime.now().isoformat()
    }
    
    if error_code:
        response["error_code"] = error_code
    
    return response

def create_success_response(data: Any = None, message: str = None) -> Dict[str, Any]:
    """
    표준 성공 응답 생성
    
    Args:
        data: 응답 데이터
        message: 성공 메시지
    
    Returns:
        Dict[str, Any]: 성공 응답 딕셔너리
    """
    response = {
        "success": True,
        "timestamp": datetime.now().isoformat()
    }
    
    if data is not None:
        response["data"] = data
    
    if message:
        response["message"] = message
    
    return response

class PromptTemplate:
    """간단한 프롬프트 템플릿 클래스"""
    
    def __init__(self, template: str, variables: List[str] = None):
        """
        프롬프트 템플릿 초기화
        
        Args:
            template: 템플릿 문자열 (중괄호 변수 포함)
            variables: 변수 목록
        """
        self.template = template
        self.variables = variables or []
    
    def format(self, **kwargs) -> str:
        """
        템플릿에 변수 값 적용
        
        Args:
            **kwargs: 변수 값들
        
        Returns:
            str: 포맷팅된 프롬프트
        """
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            logging.error(f"프롬프트 템플릿 변수 오류: {e}")
            return self.template
    
    def get_variables(self) -> List[str]:
        """템플릿에서 사용된 변수 목록 반환"""
        import re
        variables = re.findall(r'\{(\w+)\}', self.template)
        return list(set(variables))
    
    def update_template_message(db, template_id, **update_data):
    # 템플릿 찾기
        template = db.query(TemplateMessage).filter_by(template_id=template_id).first()
        if not template:
            return False  # 템플릿이 없으면 실패

        # 수정 가능한 필드만 업데이트
        allowed_fields = [
            "template_type", "channel_type", "title",
            "content", "content_type"
        ]
        for key in allowed_fields:
            if key in update_data and update_data[key] is not None:
                setattr(template, key, update_data[key])
        db.commit()
        return True

# def utc_to_kst(utc_dt: datetime) -> datetime:
#     if utc_dt.tzinfo is None:
#         # UTC 정보가 없는 naive datetime이면 UTC로 간주
#         utc_dt = utc_dt.replace(tzinfo=timezone.utc)
#     kst = timezone(timedelta(hours=9))
#     return utc_dt.astimezone(kst)
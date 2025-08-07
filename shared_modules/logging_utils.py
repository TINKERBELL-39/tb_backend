import logging
from typing import Optional
import os

def setup_logging(
    name: str = None,
    level: str = "INFO",
    log_file: str = None,
    format_string: str = None
) -> logging.Logger:
    """
    로깅 설정
    
    Args:
        name: 로거 이름 (기본값: 호출한 모듈 이름)
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 로그 파일 경로 (선택사항)
        format_string: 로그 포맷 문자열
    
    Returns:
        logging.Logger: 설정된 로거
    """
    if name is None:
        name = __name__
    
    logger = logging.getLogger(name)
    
    # 이미 핸들러가 있으면 중복 설정 방지
    if logger.handlers:
        return logger
    
    # 로그 레벨 설정
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # 기본 포맷
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    formatter = logging.Formatter(format_string)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 (선택사항)
    if log_file:
        # 로그 디렉토리 생성
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
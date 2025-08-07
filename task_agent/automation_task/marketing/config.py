"""마케팅 자동화 설정 모듈"""

from typing import List

# CORS 설정
CORS_SETTINGS = {
    "allow_origins": [
        "http://localhost:3000",  # Next.js 개발 서버
        "http://localhost:8080",  # FastAPI 서버
    ],
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}

# 데이터베이스 설정
DATABASE_URL = "sqlite:///./marketing_automation.db"

# 로깅 설정
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 스케줄러 설정
SCHEDULER_TIMEZONE = "Asia/Seoul"

# API 설정
API_VERSION = "1.0.0"
API_TITLE = "마케팅 자동화 API"
API_DESCRIPTION = "네이버 블로그 검색 키워드 통계 기반 컨텐츠 제작 및 인스타그램 포스팅 자동화"

NAVER_API_CONFIG = {
    'datalab': {
        'client_id': 'dtQJrVVMFjKH9sz_gmd_',
        'client_secret': 'XPZ_QPRD_N'
    },
    'search_ad': {
        'api_key': '01000000004b5fae8ed5d4a9bce22c02db3cc56780a9703f57282bf575ddc2b765e5f455f5',
        'secret_key': 'AQAAAABLX66O1dSpvOIsAts8xWeAY9zcCvrKr2dS+bn92wg+gg==',
        'customer_id': '3519183'
    }
}
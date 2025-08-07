"""
마케팅 분석 도구 API 패키지
"""

__version__ = "1.0.0"
__author__ = "SKN11-FINAL-5Team"
__description__ = "네이버 트렌드 분석과 인스타그램 해시태그 분석을 통한 마케팅 콘텐츠 자동 생성 API"

# app 대신 router를 import
from .marketing_api import router

__all__ = ["router"]

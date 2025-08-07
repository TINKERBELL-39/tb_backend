"""마케팅 자동화 API 메인 모듈"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import logging
import os
import sys

# 상위 디렉토리의 모듈들을 import하기 위한 경로 설정
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from task_agent.automation_task.marketing.api import keyword_api, blog_content_api, blog_publish_api
from task_agent.automation_task.common.db_helper import AutomationDatabaseHelper
from task_agent.automation_task.marketing.utils.scheduler import AutomationScheduler
from task_agent.automation_task.marketing.utils.logger import setup_logger
from task_agent.automation_task.marketing.config import CORS_SETTINGS, API_TITLE, API_DESCRIPTION, API_VERSION

# 로깅 설정
logger = setup_logger(__name__)

# FastAPI 앱 초기화
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    **CORS_SETTINGS
)

# 전역 변수
db_manager = AutomationDatabaseHelper()
scheduler = AutomationScheduler()

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작시 초기화"""
    logger.info("마케팅 자동화 API 시작")
    await db_manager.initialize()
    await scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료시 정리"""
    logger.info("마케팅 자동화 API 종료")
    await scheduler.stop()
    await db_manager.close()

@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "message": "마케팅 자동화 API",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

# API 라우터 등록
app.include_router(keyword_api.router)
app.include_router(blog_content_api.router)
app.include_router(blog_publish_api.router)

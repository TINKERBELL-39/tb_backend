"""블로그 컨텐츠 생성 API 모듈"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
import logging

from task_agent.automation_task.marketing.blog.naver_blog_automation import NaverBlogAutomation
from task_agent.automation_task.marketing.models.schemas import ContentGenerationRequest, BlogContentResponse
from task_agent.automation_task.common.db_helper import AutomationDatabaseHelper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 라우터 초기화
router = APIRouter(prefix="/blog/content", tags=["blog_content"])

# 전역 변수
blog_automation = NaverBlogAutomation()
db_manager = AutomationDatabaseHelper()

@router.post("/generate", response_model=BlogContentResponse)
async def generate_content(request: ContentGenerationRequest):
    """블로그 컨텐츠 생성"""
    try:
        # 컨텐츠 생성
        content = await blog_automation.generate_content(
            keyword=request.keyword,
            keyword_data=request.keyword_data,
            template=request.template
        )
        
        # DB에 생성된 컨텐츠 저장
        await db_manager.save_blog_content(
            keyword=request.keyword,
            content=content,
            template=request.template
        )
        
        logger.info(f"블로그 컨텐츠 생성 완료: {request.keyword}")
        return {"success": True, "data": content}
    except Exception as e:
        logger.error(f"블로그 컨텐츠 생성 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_content_history(
    page: int = 1,
    limit: int = 10,
    keyword: Optional[str] = None,
    status: Optional[str] = None
):
    """생성된 컨텐츠 히스토리 조회"""
    try:
        history = await db_manager.get_content_history(
            page=page,
            limit=limit,
            keyword=keyword,
            status=status
        )
        return {"success": True, "data": history}
    except Exception as e:
        logger.error(f"컨텐츠 히스토리 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{content_id}")
async def get_content_detail(content_id: str):
    """특정 컨텐츠 상세 조회"""
    try:
        content = await db_manager.get_content_detail(content_id)
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        return {"success": True, "data": content}
    except Exception as e:
        logger.error(f"컨텐츠 상세 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
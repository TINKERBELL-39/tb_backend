"""블로그 발행 API 모듈"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional, List
import logging

from task_agent.automation_task.marketing.blog.naver_blog_automation import NaverBlogAutomation
from task_agent.automation_task.marketing.models.schemas import BlogPublishRequest, BlogPublishResponse, BlogPost
from task_agent.automation_task.common.db_helper import AutomationDatabaseHelper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 라우터 초기화
router = APIRouter(prefix="/blog/publish", tags=["blog_publish"])

# 전역 변수
blog_automation = NaverBlogAutomation()
db_manager = AutomationDatabaseHelper()

@router.post("/", response_model=BlogPublishResponse)
async def publish_blog(
    request: BlogPublishRequest,
    background_tasks: BackgroundTasks
):
    """블로그 포스트 발행"""
    try:
        # 컨텐츠 유효성 검사
        content = await db_manager.get_content_detail(request.content_id)
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        
        # 발행 상태 업데이트
        await db_manager.update_content_status(
            content_id=request.content_id,
            status="publishing"
        )
        
        # 백그라운드에서 블로그 발행 처리
        background_tasks.add_task(
            blog_automation.upload_to_naver_blog,
            content,
            request.blog_config
        )
        
        logger.info(f"블로그 발행 요청 완료: {request.content_id}")
        return {"success": True, "message": "Blog publishing started"}
    except Exception as e:
        logger.error(f"블로그 발행 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{content_id}")
async def get_publish_status(content_id: str):
    """블로그 발행 상태 조회"""
    try:
        status = await blog_automation.get_publish_status(content_id)
        return {"success": True, "data": status}
    except Exception as e:
        logger.error(f"발행 상태 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/posts", response_model=List[BlogPost])
async def get_published_posts(
    page: int = 1,
    limit: int = 10,
    keyword: Optional[str] = None
):
    """발행된 블로그 포스트 목록 조회"""
    try:
        posts = await blog_automation.get_posts(
            page=page,
            limit=limit,
            keyword=keyword,
            status="published"
        )
        return {"success": True, "data": posts}
    except Exception as e:
        logger.error(f"발행된 포스트 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{content_id}")
async def cancel_publish(content_id: str):
    """블로그 발행 취소"""
    try:
        # 발행 상태 확인
        status = await blog_automation.get_publish_status(content_id)
        if status.get("status") == "completed":
            raise HTTPException(status_code=400, detail="Cannot cancel completed publication")
            
        # 발행 취소 처리
        await blog_automation.cancel_publish(content_id)
        
        # 상태 업데이트
        await db_manager.update_content_status(
            content_id=content_id,
            status="cancelled"
        )
        
        logger.info(f"블로그 발행 취소 완료: {content_id}")
        return {"success": True, "message": "Publication cancelled successfully"}
    except Exception as e:
        logger.error(f"발행 취소 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
"""키워드 추천 API 모듈"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
import logging

from task_agent.automation_task.marketing.blog.keyword import NaverKeywordRecommender
from task_agent.automation_task.marketing.models.schemas import KeywordAnalysisRequest, KeywordAnalysisResponse
from task_agent.automation_task.marketing.config import NAVER_API_CONFIG
from task_agent.automation_task.common.db_helper import get_automation_db_helper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 라우터 초기화
router = APIRouter(prefix="/keywords", tags=["keywords"])

# 전역 변수
keyword_recommender = NaverKeywordRecommender(NAVER_API_CONFIG)
db_helper = get_automation_db_helper()

@router.post("/recommend", response_model=KeywordAnalysisResponse)
async def recommend_keywords(
    request: KeywordAnalysisRequest,
    filters: Optional[Dict[str, Any]] = None
):
    """키워드 분석 및 추천"""
    try:
        # 기본 필터 설정
        if not filters:
            filters = {
                'search_volume_range': {'min': 1000, 'max': 100000},
                'category': 'IT'
            }

        # 키워드 추천 수행
        result = keyword_recommender.recommend_keywords(
            base_keyword=request.keyword,
            filters=filters,
            count=30
        )

        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', '키워드 추천 실패'))

        # DB에 분석 결과 저장
        save_result = await db_helper.save_keyword_analysis(
            user_id=request.user_id,
            keyword=request.keyword,
            platform='naver',  # 현재는 네이버만 지원
            analysis_data=result
        )

        if not save_result:
            logger.warning(f"키워드 분석 결과 저장 실패: {request.keyword}")

        logger.info(f"키워드 분석 완료: {request.keyword}")
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"키워드 분석 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/expand")
async def expand_keywords(
    keyword: str,
    max_results: int = 100
):
    """키워드 확장"""
    try:
        expanded = keyword_recommender.expand_keywords([keyword], max_results)
        return {"success": True, "data": expanded}
    except Exception as e:
        logger.error(f"키워드 확장 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics")
async def get_keyword_metrics(
    keyword: str
):
    """키워드 메트릭스 조회"""
    try:
        metrics = keyword_recommender.get_keyword_metrics([keyword])
        return {"success": True, "data": metrics}
    except Exception as e:
        logger.error(f"키워드 메트릭스 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/demographics")
async def get_keyword_demographics(
    keyword: str
):
    """키워드 인구통계 정보 조회"""
    try:
        demographics = keyword_recommender.get_keyword_demographics([keyword])
        return {"success": True, "data": demographics}
    except Exception as e:
        logger.error(f"키워드 인구통계 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_keyword_history(
    page: int = 1,
    limit: int = 10,
    keyword: Optional[str] = None
):
    """키워드 분석 히스토리 조회"""
    try:
        history = await db_helper.get_keyword_history(
            page=page,
            limit=limit,
            keyword=keyword
        )
        return {"success": True, "data": history}
    except Exception as e:
        logger.error(f"키워드 히스토리 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
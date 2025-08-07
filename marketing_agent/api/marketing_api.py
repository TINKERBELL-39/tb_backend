from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import asyncio
import sys
import os
import logging
from datetime import datetime

# 모듈 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔥 Enhanced Marketing Agent 로드 시도
try:
    from enhanced_marketing_agent import enhanced_marketing_agent
    ENHANCED_AGENT_AVAILABLE = True
    logger.info("✅ Enhanced Marketing Agent v2.0 로드됨")
except ImportError:
    try:
        from marketing_agent import marketing_agent as enhanced_marketing_agent
        ENHANCED_AGENT_AVAILABLE = False
        logger.info("⚠️ 기존 Marketing Agent 사용")
    except ImportError:
        enhanced_marketing_agent = None
        ENHANCED_AGENT_AVAILABLE = False
        logger.warning("❌ Marketing Agent 로드 실패")

# APIRouter 생성 (FastAPI 앱 대신)
router = APIRouter()

# 기존 요청/응답 모델들
class KeywordRequest(BaseModel):
    keyword: str = Field(..., description="분석할 기본 키워드", example="스킨케어")
    description: Optional[str] = Field(None, description="키워드에 대한 추가 설명", example="여성 타겟 스킨케어 제품")

class TrendAnalysisRequest(BaseModel):
    keywords: List[str] = Field(..., description="분석할 키워드 리스트", example=["스킨케어", "화장품", "뷰티"])
    start_date: Optional[str] = Field(None, description="시작 날짜 (YYYY-MM-DD)", example="2024-01-01")
    end_date: Optional[str] = Field(None, description="종료 날짜 (YYYY-MM-DD)", example="2024-12-31")

class HashtagAnalysisRequest(BaseModel):
    question: str = Field(..., description="해시태그 분석 질문", example="스킨케어 마케팅")
    hashtags: Optional[List[str]] = Field(None, description="사용자 해시태그", example=["#skincare", "#beauty"])

class BlogContentResponse(BaseModel):
    success: bool
    base_keyword: Optional[str] = None
    related_keywords: Optional[List[str]] = None
    top_keywords: Optional[List[str]] = None
    trend_analysis: Optional[Dict[str, Any]] = None
    blog_content: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None

class InstagramContentResponse(BaseModel):
    success: bool
    base_keyword: Optional[str] = None
    related_keywords: Optional[List[str]] = None
    hashtag_analysis: Optional[Dict[str, Any]] = None
    template_result: Optional[Dict[str, Any]] = None
    instagram_content: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None

class TrendResponse(BaseModel):
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    period: Optional[str] = None
    keywords: Optional[List[str]] = None
    error: Optional[str] = None

class HashtagResponse(BaseModel):
    success: bool
    searched_hashtags: Optional[List[str]] = None
    popular_hashtags: Optional[List[str]] = None
    total_posts: Optional[int] = None
    error: Optional[str] = None

# 🔥 Enhanced Agent 요청/응답 모델들
class EnhancedChatRequest(BaseModel):
    message: str = Field(..., description="사용자 메시지", example="카페를 운영하고 있어요")
    user_id: int = Field(..., description="사용자 ID", example=123)
    conversation_id: Optional[int] = Field(None, description="대화 ID (생략시 자동 생성)")

class EnhancedChatResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ConversationStatusResponse(BaseModel):
    conversation_id: int
    status: Dict[str, Any]

# 블로그 콘텐츠 생성 워크플로우
@router.post("/api/v1/content/blog", response_model=BlogContentResponse)
async def create_blog_content(request: KeywordRequest):
    """
    블로그 콘텐츠 생성 전체 워크플로우
    
    워크플로우:
    1. 키워드 입력 
    2. LLM 기반으로 관련 키워드 10개 추천 
    3. 네이버 검색어 트렌드 분석을 통해 트렌드 수치 반환 
    4. 상위 5개 키워드 + 추천 마케팅 템플릿 활용해서 LLM 기반으로 블로그 콘텐츠 작성
    """
    start_time = datetime.now()
    
    try:
        # 마케팅 분석 도구 가져오기
        from general_marketing_tools import get_marketing_analysis_tools
        tools = get_marketing_analysis_tools()
        
        logger.info(f"블로그 콘텐츠 생성 시작: {request.keyword}")
        
        # 워크플로우 실행
        result = await tools.create_blog_content_workflow(request.keyword)
        
        # 처리 시간 계산
        processing_time = (datetime.now() - start_time).total_seconds()
        result["processing_time"] = processing_time
        
        logger.info(f"블로그 콘텐츠 생성 완료: {request.keyword}, 처리시간: {processing_time:.2f}초")
        
        return BlogContentResponse(**result)
        
    except Exception as e:
        logger.error(f"블로그 콘텐츠 생성 API 오류: {e}")
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return BlogContentResponse(
            success=False,
            error=f"블로그 콘텐츠 생성 중 오류가 발생했습니다: {str(e)}",
            processing_time=processing_time
        )

# 인스타그램 콘텐츠 생성 워크플로우
@router.post("/api/v1/content/instagram", response_model=InstagramContentResponse)
async def create_instagram_content(request: KeywordRequest):
    """
    인스타그램 콘텐츠 생성 전체 워크플로우
    
    워크플로우:
    1. 키워드 입력
    2. LLM 기반으로 관련 키워드 10개 추천
    3. 관련 인스타 해시태그 추천
    4. 해시태그 기반 + 추천 마케팅 템플릿 활용해서 LLM 기반으로 인스타 콘텐츠 작성
    """
    start_time = datetime.now()
    
    try:
        # 마케팅 분석 도구 가져오기
        from general_marketing_tools import get_marketing_analysis_tools
        tools = get_marketing_analysis_tools()
        
        logger.info(f"인스타그램 콘텐츠 생성 시작: {request.keyword}")
        
        # 워크플로우 실행
        result = await tools.create_instagram_content_workflow(request.keyword)
        
        # 처리 시간 계산
        processing_time = (datetime.now() - start_time).total_seconds()
        result["processing_time"] = processing_time
        
        logger.info(f"인스타그램 콘텐츠 생성 완료: {request.keyword}, 처리시간: {processing_time:.2f}초")
        
        return InstagramContentResponse(**result)
        
    except Exception as e:
        logger.error(f"인스타그램 콘텐츠 생성 API 오류: {e}")
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return InstagramContentResponse(
            success=False,
            error=f"인스타그램 콘텐츠 생성 중 오류가 발생했습니다: {str(e)}",
            processing_time=processing_time
        )

# 네이버 트렌드 분석 (개별 기능)
@router.post("/api/v1/analysis/naver-trends", response_model=TrendResponse)
async def analyze_naver_trends(request: TrendAnalysisRequest):
    """네이버 검색어 트렌드 분석"""
    try:
        from general_marketing_tools import get_marketing_analysis_tools
        tools = get_marketing_analysis_tools()
        
        logger.info(f"네이버 트렌드 분석 시작: {request.keywords}")
        
        result = await tools.analyze_naver_trends(
            keywords=request.keywords,
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        logger.info(f"네이버 트렌드 분석 완료: {len(request.keywords)}개 키워드")
        
        return TrendResponse(**result)
        
    except Exception as e:
        logger.error(f"네이버 트렌드 분석 API 오류: {e}")
        return TrendResponse(
            success=False,
            error=f"네이버 트렌드 분석 중 오류가 발생했습니다: {str(e)}"
        )

# 인스타그램 해시태그 분석 (개별 기능)
@router.post("/api/v1/analysis/instagram-hashtags", response_model=HashtagResponse)
async def analyze_instagram_hashtags(request: HashtagAnalysisRequest):
    """인스타그램 해시태그 트렌드 분석"""
    try:
        from general_marketing_tools import get_marketing_analysis_tools
        tools = get_marketing_analysis_tools()
        
        logger.info(f"인스타그램 해시태그 분석 시작: {request.question}")
        
        result = await tools.analyze_instagram_hashtags(
            question=request.question,
            user_hashtags=request.hashtags
        )
        
        logger.info(f"인스타그램 해시태그 분석 완료: {result.get('total_posts', 0)}개 게시물 분석")
        
        return HashtagResponse(**result)
        
    except Exception as e:
        logger.error(f"인스타그램 해시태그 분석 API 오류: {e}")
        return HashtagResponse(
            success=False,
            error=f"인스타그램 해시태그 분석 중 오류가 발생했습니다: {str(e)}"
        )

# 관련 키워드 생성 (개별 기능)
@router.post("/api/v1/keywords/generate")
async def generate_related_keywords(request: KeywordRequest):
    """LLM 기반 관련 키워드 생성"""
    try:
        from general_marketing_tools import get_marketing_analysis_tools
        tools = get_marketing_analysis_tools()
        
        logger.info(f"관련 키워드 생성 시작: {request.keyword}")
        
        keywords = await tools.generate_related_keywords(request.keyword, 10)
        
        logger.info(f"관련 키워드 생성 완료: {len(keywords)}개 키워드")
        
        return {
            "success": True,
            "base_keyword": request.keyword,
            "related_keywords": keywords,
            "count": len(keywords)
        }
        
    except Exception as e:
        logger.error(f"관련 키워드 생성 API 오류: {e}")
        return {
            "success": False,
            "error": f"관련 키워드 생성 중 오류가 발생했습니다: {str(e)}"
        }

# 인스타그램 마케팅 템플릿 가져오기 (개별 기능)
@router.get("/api/v1/templates/instagram")
async def get_instagram_templates():
    """인스타그램 마케팅 콘텐츠 템플릿 가져오기"""
    try:
        from general_marketing_tools import get_marketing_analysis_tools
        tools = get_marketing_analysis_tools()
        
        logger.info("인스타그램 템플릿 가져오기 시작")
        
        result = await tools.generate_instagram_content()
        
        logger.info("인스타그램 템플릿 가져오기 완료")
        
        return result
        
    except Exception as e:
        logger.error(f"인스타그램 템플릿 API 오류: {e}")
        return {
            "success": False,
            "error": f"인스타그램 템플릿 가져오기 중 오류가 발생했습니다: {str(e)}"
        }

# 🔥 통합 기능 엔드포인트들

@router.post("/api/v2/integrated/consultation-and-content")
async def integrated_consultation_and_content(request: EnhancedChatRequest):
    """
    🔥 통합 기능: 대화형 상담 + 트렌드 분석 + 콘텐츠 생성
    
    사용자와 대화를 통해 정보를 수집하고, 필요시 트렌드 분석과 콘텐츠 생성을 자동으로 수행
    """
    if not enhanced_marketing_agent:
        raise HTTPException(status_code=503, detail="Enhanced Marketing Agent가 로드되지 않았습니다.")
    
    try:
        # 1. 대화형 상담 먼저 수행
        chat_result = await enhanced_marketing_agent.process_message(
            user_input=request.message,
            user_id=request.user_id,
            conversation_id=request.conversation_id
        )
        
        # 2. 대화 상태 확인
        conversation_id = chat_result["data"]["conversation_id"]
        status = enhanced_marketing_agent.get_conversation_status(conversation_id)
        
        # 3. 충분한 정보가 수집되었고 콘텐츠 생성이 요청된 경우
        collected_info = status.get("collected_info", {})
        
        additional_content = {}
        
        # 키워드가 있고 콘텐츠 생성이 요청된 경우 트렌드 분석 수행
        if ("product" in collected_info or "business_type" in collected_info) and \
           any(keyword in request.message.lower() for keyword in ["포스트", "콘텐츠", "블로그", "인스타"]):
            
            try:
                from general_marketing_tools import get_marketing_analysis_tools
                tools = get_marketing_analysis_tools()
                
                # 키워드 결정
                keyword = collected_info.get("product", collected_info.get("business_type", "마케팅"))
                
                # 인스타그램 콘텐츠 생성 (해시태그 분석 포함)
                instagram_result = await tools.create_instagram_content_workflow(keyword)
                additional_content["instagram_analysis"] = instagram_result
                
                logger.info(f"통합 기능: 트렌드 분석 및 콘텐츠 생성 완료 - {keyword}")
                
            except Exception as e:
                logger.warning(f"통합 기능 중 트렌드 분석 실패: {e}")
                additional_content["analysis_error"] = str(e)
        
        # 4. 결과 통합
        result = chat_result
        if additional_content:
            result["data"]["additional_content"] = additional_content
            result["data"]["integrated_features"] = True
        
        return result
        
    except Exception as e:
        logger.error(f"통합 기능 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# API 문서용 예시 엔드포인트들
@router.get("/api/v1/examples/blog-request")
async def get_blog_request_example():
    """블로그 콘텐츠 생성 요청 예시"""
    return {
        "example": {
            "keyword": "스킨케어",
            "description": "여성 타겟 스킨케어 제품 마케팅"
        }
    }

# 배치 처리 엔드포인트
@router.post("/api/v1/batch/content-generation")
async def batch_content_generation(keywords: List[str], background_tasks: BackgroundTasks):
    """배치로 여러 키워드에 대한 콘텐츠 생성"""
    if len(keywords) > 5:  # 과부하 방지
        raise HTTPException(status_code=400, detail="최대 5개 키워드까지만 배치 처리 가능합니다.")
    
    task_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # 백그라운드에서 처리
    background_tasks.add_task(process_batch_content, keywords, task_id)
    
    return {
        "success": True,
        "task_id": task_id,
        "keywords": keywords,
        "status": "processing",
        "message": "배치 처리가 시작되었습니다. 결과는 별도로 확인해주세요."
    }

async def process_batch_content(keywords: List[str], task_id: str):
    """배치 콘텐츠 생성 처리 함수"""
    logger.info(f"배치 처리 시작: {task_id}, 키워드: {keywords}")
    
    try:
        from general_marketing_tools import get_marketing_analysis_tools
        tools = get_marketing_analysis_tools()
        
        results = []
        for keyword in keywords:
            try:
                # 블로그와 인스타그램 콘텐츠를 모두 생성
                blog_result = await tools.create_blog_content_workflow(keyword)
                instagram_result = await tools.create_instagram_content_workflow(keyword)
                
                results.append({
                    "keyword": keyword,
                    "blog_content": blog_result,
                    "instagram_content": instagram_result
                })
                
                # 과부하 방지를 위한 딜레이
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"키워드 '{keyword}' 처리 중 오류: {e}")
                results.append({
                    "keyword": keyword,
                    "error": str(e)
                })
        
        # 결과 저장 (실제로는 데이터베이스나 파일에 저장)
        logger.info(f"배치 처리 완료: {task_id}, 결과: {len(results)}개")
        
    except Exception as e:
        logger.error(f"배치 처리 오류: {task_id}, 오류: {e}")

# 메인 실행
if __name__ == "__main__":
    import uvicorn
    
    print("🚀 통합 마케팅 API 시작")
    if ENHANCED_AGENT_AVAILABLE:
        print("✅ Enhanced v2.0 모드 - 트렌드 분석 + 개선된 대화형 상담")
    else:
        print("⚠️ 기본 모드 - 트렌드 분석만 사용 가능")
    
    # 개발 환경 설정
    uvicorn.run(
        "marketing_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

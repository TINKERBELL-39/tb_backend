"""
Mental Health Agent - 리팩토링된 메인 진입점
마케팅 에이전트의 구조를 참고하여 멀티턴 대화 시스템으로 업그레이드
"""

import logging
import time
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi import Body
import httpx
import asyncio

# 공통 모듈 임포트
from shared_modules import (
    get_config,
    setup_logging,
    create_success_response,
    create_error_response,
    get_current_timestamp
)

# 새로운 정신건강 매니저 임포트
from mental_agent.core.mental_health_manager import MentalHealthAgentManager

# 로깅 설정
logger = setup_logging("mental_health_v3", log_file="logs/mental_health.log")

# 설정 로드
config = get_config()

# FastAPI 초기화
app = FastAPI(
    title="Mental Health Agent v3.0",
    description="멀티턴 대화 기반 정신건강 전문 상담 에이전트",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정신건강 매니저 인스턴스 
mental_health_manager = MentalHealthAgentManager()

# 요청 모델
class UserQuery(BaseModel):
    """사용자 쿼리 요청"""
    user_id: int = Field(..., description="사용자 ID")
    conversation_id: Optional[int] = Field(None, description="대화 ID (멀티턴)")
    message: str = Field(..., description="사용자 메시지")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "conversation_id": 456,
                "message": "요즘 우울하고 의욕이 없어요",
            }
        }

class PHQ9Request(BaseModel):
    """PHQ-9 설문 요청"""
    user_id: int = Field(..., description="사용자 ID")
    responses: List[int] = Field(..., description="PHQ-9 응답 (0-3, 9개 문항)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "responses": [1, 2, 1, 3, 2, 1, 2, 0, 0]
            }
        }

# API 엔드포인트
@app.post("/agent/query")
async def process_user_query(request: UserQuery):
    """멀티턴 대화 기반 사용자 쿼리 처리"""
    try:
        start_time = time.time()
        logger.info(f"멀티턴 쿼리 처리 시작 - user_id: {request.user_id}, message: {request.message[:50]}...")
        
        # 정신건강 매니저로 처리
        result = mental_health_manager.process_user_query(
            
            user_input=request.message,
            user_id=request.user_id,
            conversation_id=request.conversation_id
        )
        
        # 처리 시간 추가
        result["processing_time"] = time.time() - start_time
        
        logger.info(f"멀티턴 쿼리 처리 완료 - 시간: {result['processing_time']:.2f}초")
        return result
        
    except Exception as e:
        logger.error(f"멀티턴 쿼리 처리 중 오류 발생: {e}")
        return create_error_response(
            error_message=f"쿼리 처리 중 오류가 발생했습니다: {str(e)}",
            error_code="MULTITURN_QUERY_ERROR"
        )

@app.get("/agent/status")
def get_agent_status():
    """에이전트 상태 조회"""
    try:
        status = mental_health_manager.get_agent_status()
        return create_success_response(status)
        
    except Exception as e:
        logger.error(f"상태 조회 실패: {e}")
        return create_error_response(f"상태 조회 실패: {str(e)}", "STATUS_ERROR")

@app.get("/conversation/{conversation_id}/status")
def get_conversation_status(conversation_id: int):
    """특정 대화 상태 조회"""
    try:
        if conversation_id in mental_health_manager.conversation_states:
            state = mental_health_manager.conversation_states[conversation_id]
            status = {
                "conversation_id": conversation_id,
                "stage": state.stage.value,
                "completion_rate": state.get_completion_rate(),
                "risk_level": state.assessment_results.get("risk_level", "low"),
                "suicide_risk": state.assessment_results.get("suicide_risk", False),
                "phq9_active": state.phq9_state["is_active"],
                "phq9_completed": state.phq9_state["completed"],
                "phq9_score": state.phq9_state.get("score"),
                "immediate_intervention_needed": state.assessment_results.get("immediate_intervention_needed", False),
                "total_counseling_sessions": len(state.counseling_sessions),
                "total_safety_plans": len(state.safety_plans),
                "is_completed": state.stage.name == "COMPLETED",
                "last_updated": state.updated_at.isoformat()
            }
            return create_success_response(status)
        else:
            return create_error_response("대화를 찾을 수 없습니다", "CONVERSATION_NOT_FOUND")
        
    except Exception as e:
        logger.error(f"대화 상태 조회 실패: {e}")
        return create_error_response(f"대화 상태 조회 실패: {str(e)}", "CONVERSATION_STATUS_ERROR")

@app.delete("/conversation/{conversation_id}")
def reset_conversation(conversation_id: int):
    """대화 초기화"""
    try:
        if conversation_id in mental_health_manager.conversation_states:
            # 위기 상황 체크
            state = mental_health_manager.conversation_states[conversation_id]
            if state.assessment_results.get("immediate_intervention_needed", False):
                return create_error_response(
                    "위기 상황 대화는 초기화할 수 없습니다. 전문가와 상담하세요.", 
                    "CRISIS_CONVERSATION_PROTECTED"
                )
            
            del mental_health_manager.conversation_states[conversation_id]
            return create_success_response({
                "message": "대화가 초기화되었습니다", 
                "conversation_id": conversation_id
            })
        else:
            return create_error_response("대화를 찾을 수 없습니다", "CONVERSATION_NOT_FOUND")
        
    except Exception as e:
        logger.error(f"대화 초기화 실패: {e}")
        return create_error_response(f"대화 초기화 실패: {str(e)}", "CONVERSATION_RESET_ERROR")

@app.post("/phq9/submit")
def submit_phq9(request: PHQ9Request):
    """PHQ-9 설문 결과 제출"""
    try:
        from mental_agent.utils.mental_health_utils import calculate_phq9_score
        
        # PHQ-9 점수 계산
        result = calculate_phq9_score(request.responses)
        
        # DB 저장 시도 (선택적)
        try:
            from shared_modules.queries import save_or_update_phq9_result
            from shared_modules import get_session_context
            
            with get_session_context() as db:
                # PHQ9 점수를 레벨로 변환 (0-4: 1, 5-9: 2, 10-14: 3, 15-19: 4, 20-27: 5)
                level = 1
                total_score = result.get("total_score", 0)
                if total_score >= 20:
                    level = 5
                elif total_score >= 15:
                    level = 4
                elif total_score >= 10:
                    level = 3
                elif total_score >= 5:
                    level = 2
                
                save_or_update_phq9_result(
                    db, request.user_id, 
                    total_score,
                    level
                )
                request.responses
        except Exception as e:
            logger.warning(f"PHQ-9 결과 DB 저장 실패: {e}")
        
        return create_success_response({
            "phq9_result": result,
            "user_id": request.user_id,
            "submission_time": get_current_timestamp()
        })
        
    except Exception as e:
        logger.error(f"PHQ-9 제출 처리 실패: {e}")
        return create_error_response(f"PHQ-9 제출 처리 실패: {str(e)}", "PHQ9_SUBMISSION_ERROR")

@app.get("/phq9/questions")
def get_phq9_questions():
    """PHQ-9 설문 문항 조회"""
    try:
        from mental_agent.utils.mental_health_utils import PHQ9_QUESTIONS
        
        return create_success_response({
            "questions": PHQ9_QUESTIONS,
            "instructions": {
                "title": "PHQ-9 우울증 자가진단 설문",
                "description": "지난 2주 동안의 경험을 바탕으로 답변해주세요",
                "options": {
                    "0": "전혀 그렇지 않다",
                    "1": "며칠 정도 그렇다",
                    "2": "일주일 이상 그렇다", 
                    "3": "거의 매일 그렇다"
                }
            }
        })
        
    except Exception as e:
        logger.error(f"PHQ-9 문항 조회 실패: {e}")
        return create_error_response(f"PHQ-9 문항 조회 실패: {str(e)}", "PHQ9_QUESTIONS_ERROR")

@app.get("/crisis/resources")
def get_crisis_resources():
    """위기 상황 자원 조회"""
    try:
        crisis_resources = {
            "immediate": {
                "title": "즉시 연락",
                "contacts": [
                    {"name": "응급실", "number": "119", "description": "생명이 위험한 응급상황"},
                    {"name": "생명의전화", "number": "1393", "description": "24시간 자살예방상담"},
                    {"name": "정신건강위기상담", "number": "1577-0199", "description": "24시간 정신건강 위기상담"}
                ]
            },
            "professional": {
                "title": "전문가 도움",
                "contacts": [
                    {"name": "정신건강의학과", "description": "전문의 진료 및 치료"},
                    {"name": "정신건강상담센터", "description": "지역별 상담센터"},
                    {"name": "청소년상담복지센터", "number": "1388", "description": "청소년 전용 상담"}
                ]
            },
            "online": {
                "title": "온라인 자원",
                "resources": [
                    {"name": "마음건강센터", "url": "https://www.blutouch.net", "description": "온라인 정신건강 정보"},
                    {"name": "생명의전화 온라인상담", "url": "https://www.lifeline.or.kr", "description": "온라인 상담 서비스"}
                ]
            }
        }
        
        return create_success_response(crisis_resources)
        
    except Exception as e:
        logger.error(f"위기 자원 조회 실패: {e}")
        return create_error_response(f"위기 자원 조회 실패: {str(e)}", "CRISIS_RESOURCES_ERROR")

@app.get("/health")
def health_check():
    """상태 확인 엔드포인트"""
    try:
        health_data = {
            "service": "mental_health_agent_v3",
            "status": "healthy",
            "timestamp": get_current_timestamp(),
            "version": "3.0.0",
            "features": [
                "멀티턴 상담",
                "PHQ-9 설문",
                "위기 상황 감지",
                "감정 상태 분석",
                "안전 계획 수립",
                "전문가 페르소나",
                "실시간 위험도 평가"
            ],
            "safety_protocols": [
                "자살 위험 감지",
                "즉시 개입 시스템",
                "응급 연락처 제공",
                "전문가 연계"
            ]
        }
        
        return create_success_response(health_data)
        
    except Exception as e:
        logger.error(f"헬스체크 실패: {e}")
        return create_error_response(f"헬스체크 실패: {str(e)}", "HEALTH_CHECK_ERROR")
    
# main.py의 PHQ-9 관련 엔드포인트들 수정

@app.get("/conversation/{conversation_id}/phq9/status")
def get_phq9_status_endpoint(conversation_id: int):
    """PHQ-9 설문 상태 조회"""
    try:
        result = mental_health_manager.get_phq9_status(conversation_id)
        return create_success_response(result)
    except Exception as e:
        logger.error(f"PHQ-9 상태 조회 실패: {e}")
        return create_error_response(str(e), "PHQ9_STATUS_ERROR")

@app.post("/conversation/{conversation_id}/phq9/response")
def submit_phq9_button_response_endpoint(conversation_id: int, data: dict = Body(...)):
    """PHQ-9 버튼 응답 제출 - 프론트엔드 응답 형식에 맞춤"""
    try:
        user_id = data.get("user_id")
        response_value = data.get("response_value")
        
        if user_id is None:
            return create_error_response("사용자 ID가 필요합니다", "MISSING_USER_ID")
        
        if response_value is None:
            return create_error_response("응답값이 필요합니다", "MISSING_RESPONSE")
        
        result = mental_health_manager.submit_phq9_button_response(
            conversation_id, user_id, response_value
        )
        
        if result.get("success"):
            # 프론트엔드가 기대하는 형식으로 응답 구성
            response_data = {
                "completed": result.get("completed", False),
                "response": result.get("response", ""),  # 메시지 내용
            }
            
            if result.get("completed"):
                response_data["result"] = result.get("result", {})
                response_data["next_stage"] = result.get("next_stage", "")
            else:
                response_data["next_question"] = result.get("next_question", {})
            
            return create_success_response(response_data)
        else:
            return create_error_response(result.get("error", "알 수 없는 오류"), "PHQ9_SUBMIT_ERROR")
            
    except Exception as e:
        logger.error(f"PHQ-9 버튼 응답 제출 실패: {e}")
        return create_error_response(str(e), "PHQ9_SUBMIT_ERROR")

@app.post("/conversation/{conversation_id}/phq9/start")
def start_phq9_survey_endpoint(conversation_id: int, data: dict = Body(...)):
    """PHQ-9 설문 시작 - 프론트엔드 응답 형식에 맞춤"""
    try:
        user_id = data.get("user_id")
        
        if user_id is None:
            return create_error_response("사용자 ID가 필요합니다", "MISSING_USER_ID")
        
        result = mental_health_manager.start_phq9_survey(conversation_id, user_id)
        
        if result.get("success"):
            # 프론트엔드가 기대하는 형식으로 응답 구성
            response_data = {
                "response": result.get("response", ""),  # PHQ9_BUTTON을 포함한 메시지
                "first_question": result.get("first_question", {})
            }
            return create_success_response(response_data)
        else:
            return create_error_response(result.get("error", "알 수 없는 오류"), "PHQ9_START_ERROR")
            
    except Exception as e: 
        logger.error(f"PHQ-9 시작 실패: {e}")
        return create_error_response(str(e), "PHQ9_START_ERROR")

# 메인 실행
if __name__ == "__main__":
    import uvicorn
    
    logger.info("=== Mental Health Agent v3.0 시작 ===")
    logger.info("✅ 마케팅 에이전트 구조 기반 리팩토링 완료")
    logger.info("✅ 멀티턴 대화 시스템 적용")
    logger.info("✅ PHQ-9 설문 통합")
    logger.info("✅ 위기 상황 감지 및 대응")
    logger.info("✅ 공감적 AI 상담 시스템")
    
    uvicorn.run(
        app, 
        host=config.HOST, 
        port=getattr(config, 'MENTAL_HEALTH_PORT', 8004),
        log_level=config.LOG_LEVEL.lower()
    )

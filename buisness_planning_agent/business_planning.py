"""
Business Planning Agent - 공통 모듈 최대 활용 버전
모든 shared_modules 기능을 최대한 활용하여 리팩토링
"""

import sys
import os
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
import re

# 텔레메트리 비활성화 (ChromaDB 오류 방지)
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
os.environ['CHROMA_TELEMETRY'] = 'False' 
os.environ['DO_NOT_TRACK'] = '1'

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from shared_modules.utils import get_or_create_conversation_session
# 공통 모듈에서 모든 필요한 것들 import (이제 __init__.py에서 export됨)
from shared_modules import (
    get_config, 
    get_llm_manager,
    get_vector_manager, 
    get_db_manager,
    get_session_context,
    setup_logging,
    create_conversation, 
    create_message, 
    get_conversation_by_id, 
    get_recent_messages,
    get_template_by_title,

    create_report,
    get_db_dependency,
    get_user_reports,
    get_report_by_id,

    insert_message_raw,
    load_prompt_from_file,
    create_success_response,
    create_error_response,
    format_conversation_history,
    sanitize_filename,
    get_current_timestamp,
    create_business_response,  # 표준 응답 생성 함수 추가
)

# 🔥 프로젝트 자동 저장 기능 추가
from shared_modules.project_utils import (
    save_business_plan_as_project,
    check_project_completion,
    auto_save_completed_project
)

sys.path.append(os.path.join(os.path.dirname(__file__), '../unified_agent_system'))
from core.models import UnifiedResponse, RoutingDecision, AgentType

from langchain.prompts import ChatPromptTemplate, PromptTemplate
from langchain.chains import RetrievalQA
from langchain_core.output_parsers import StrOutputParser
from fastapi import FastAPI, Body, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# 로깅 설정 - 공통 모듈 활용
logger = setup_logging("business_planning", log_file="logs/business_planning.log")

# 설정 로드 - 공통 모듈 활용
config = get_config()

# LLM, Vector, DB 매니저 - 공통 모듈 활용
llm_manager = get_llm_manager()
vector_manager = get_vector_manager()
db_manager = get_db_manager()

# FastAPI 초기화
app = FastAPI(
    title="Business Planning Agent",
    description="1인 창업 전문 컨설팅 에이전트",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from google_drive_service import google_drive_router
from draft import draft_router

app.include_router(google_drive_router)
app.include_router(draft_router)

# 프롬프트 설정 - 공통 모듈의 유틸리티 활용
try:
    from config.prompts_config import PROMPT_META
except ImportError:
    logger.warning("prompts_config.py를 찾을 수 없습니다. 기본 설정을 사용합니다.")
    PROMPT_META = {}

from idea_market import get_persona_trend, get_market_analysis
from multi_turn import MultiTurnManager

class BusinessPlanningService:
    """비즈니스 기획 서비스 클래스 - 공통 모듈 최대 활용"""

    def __init__(self):
        """서비스 초기화"""
        self.llm_manager = llm_manager
        self.multi_turn = MultiTurnManager(self.llm_manager)
        self.vector_manager = vector_manager
        self.db_manager = db_manager
        
        # 토픽 분류 시스템 프롬프트
        self.topic_classify_prompt = self._load_classification_prompt()
        
        logger.info("BusinessPlanningService 초기화 완료")
    
    def get_next_stage(self, current_stage: str) -> Optional[str]:
        try:
            idx = self.STAGES.index(current_stage)
            return self.STAGES[idx + 1] if idx + 1 < len(self.STAGES) else None
        except ValueError:
            return None
    
    async def is_single_question(self, user_input: str) -> bool:
        """
        싱글턴(single)인지 멀티턴(multi)인지 LLM으로 판별.
        - LLM이 '단계 주제'와 관련 있는지 판단해 multi 여부를 결정
        - 관련성이 있으면 무조건 multi, 아니면 single/multi 판단
        """
        try:
            judge_prompt = f"""
            다음 질문이 아래 단계 주제와 관련이 있으면 무조건 multi를 출력하세요.
            - 단계 주제: "아이디어 탐색 및 추천", "시장 검증", "비즈니스 모델링", "실행 계획 수립", "성장 전략 & 리스크 관리"
            - 단계 주제와 전혀 관련이 없으면 질문 난이도를 기반으로 single 또는 multi를 출력하세요.
            - 즉답 가능한 단순 정보: "single"
            - 전략/분석/단계별 설명 필요: "multi"
            - 답변은 반드시 single 또는 multi만 출력.

            질문: "{user_input}"
            """
            messages = [
                {"role": "system", "content": "너는 single/multi만 판단하는 전문가야."},
                {"role": "user", "content": judge_prompt}
            ]

            result = await self.llm_manager.generate_response(messages=messages, provider="openai")
            result_clean = result.strip().lower()

            return "single" in result_clean and "multi" not in result_clean
        except Exception as e:
            logger.error(f"[is_single_question] 판별 실패: {e}")
            return False  # 에러 시 멀티턴 진행


    # 11. final_business_plan(사업 기획서 작성)
    # 4. market_research(시장/경쟁 분석, 시장규모)
    def _load_classification_prompt(self) -> str:
        """분류 프롬프트 로드"""
        return """
        너는 고객 질문을 분석해서 관련된 사업기획 topic을 모두 골라주는 역할이야.
        소괄호 안은 topic에 대한 부가 설명이야. 부가 설명을 참고해서

        아래의 토픽 중에서 질문과 관련된 키워드를 **복수 개까지** 골라줘.

        콤마(,)로 구분된 키만 출력하고, 설명은 하지마.

        가능한 토픽:
        0. startup_preparation(창업 준비, 체크리스트)
        1. idea_recommendation(창업 아이템, 트렌드, 아이디어 추천)
        2. idea_validation(아이디어 검증, 시장성 분석, 시장규모, 타겟 분석)
        3. business_model(린캔버스, 수익 구조)
        5. mvp_development(MVP 기획, 초기 제품 설계)
        6. funding_strategy(투자유치, 정부지원, 자금 조달)
        7. business_registration(사업자등록, 면허, 신고 절차)
        8. financial_planning(예산, 매출, 세무)
        9. growth_strategy(사업 확장, 스케일업)
        10. risk_management(리스크 관리, 위기 대응)
        11. final_business_plan(사업 기획서 작성)
        
        **출력 예시**: startup_preparation, idea_validation
        """
    
    async def classify_topics(self, user_input: str) -> List[str]:
        """토픽 분류 - 공통 모듈의 LLM 매니저 활용"""
        try:
            messages = [
                {"role": "system", "content": self.topic_classify_prompt},
                {"role": "user", "content": f"사용자 질문: {user_input}"}
            ]
            
            # 공통 모듈의 LLM 매니저로 응답 생성
            result = await self.llm_manager.generate_response(
                messages=messages,
                provider="openai"  # 분류에는 OpenAI 사용
            )
            
            # 결과 파싱
            topics = [t.strip() for t in result.split(",") if t.strip() in PROMPT_META]
            logger.info(f"토픽 분류 결과: {topics}")
            return topics
            
        except Exception as e:
            logger.error(f"토픽 분류 실패: {e}")
            return []
    
    def load_prompt_texts(self, topics: List[str]) -> List[str]:
        """프롬프트 텍스트 로드 - 공통 모듈의 유틸리티 활용"""
        merged_prompts = []
        
        for topic in topics:
            if topic in PROMPT_META:
                file_path = PROMPT_META[topic]["file"]
                # 공통 모듈의 load_prompt_from_file 활용
                prompt_text = load_prompt_from_file(file_path)
                if prompt_text:
                    merged_prompts.append(prompt_text)
                    logger.info(f"프롬프트 로드 성공: {topic}")
                else:
                    logger.warning(f"프롬프트 로드 실패: {file_path}")
        
        return merged_prompts
    

    def build_agent_prompt(
        self, topics: List[str], user_input: str, persona: str, history: str,
        current_stage: str, progress: float, missing: List[str]
    ) -> PromptTemplate:
        """
        에이전트 프롬프트 구성 - LLM이 부족한 정보나 진행률을 참고하여 자연스럽게 후속 질문을 생성.
        """
        merged_prompts = self.load_prompt_texts(topics)
        role_descriptions = [PROMPT_META[topic]["role"] for topic in topics if topic in PROMPT_META]

        # 페르소나별 컨텍스트
        if persona == "common":
            system_context = f"당신은 1인 창업 전문 컨설턴트입니다. {', '.join(role_descriptions)}"
        else:
            system_context = f"당신은 {persona} 전문 1인 창업 컨설턴트입니다. {', '.join(role_descriptions)}"

        # 진행률 및 부족 정보 안내
        progress_hint = ""
        if progress >= 0.8:
            next_stage = self.multi_turn.get_next_stage(current_stage)
            if next_stage:
                progress_hint = f"\n현재 '{current_stage}' 단계를 거의 마쳤습니다. 이제 '{next_stage}' 단계로 넘어갈 준비가 되었는지 자연스럽게 제안하세요."
            else:
                progress_hint = "\n모든 단계가 완료되었습니다. 이제 최종 사업기획서를 작성할 수 있음을 자연스럽게 알리세요."

        missing_hint = ""
        if missing:
            missing_hint = (
                f"\n'{current_stage}' 단계에서 부족한 정보: {', '.join(missing)}. "
                f"이 정보를 알려줄까요? 또는 사용자에게 흥미를 유도할 질문을 만들어보세요."
            )

        template = f"""{system_context}

    다음 지침을 따라 답변하세요:
    { " | ".join(merged_prompts) }

    최근 대화:
    {history}

    참고 문서:
    {{context}}

    사용자 질문: "{user_input}"

    [응답 지침]
    **문단 구성 및 가독성:**
    - 핵심 포인트를 먼저 간단히 요약하여 시작하세요
    - 내용을 논리적인 순서로 2-4개 문단으로 나누어 구성하세요
    - 각 문단은 하나의 주제만 다루고, 문단 간 자연스러운 연결을 유지하세요
    - 중요한 키워드는 **굵게** 표시하고, 필요시 번호나 불릿 포인트를 활용하세요
    - 마지막에는 구체적인 다음 단계나 질문을 제시하세요
    
    **톤앤매너:**
    - 전문적이지만 친근한 1인 창업 컨설턴트 어조 유지
    - 복잡한 내용도 쉽게 이해할 수 있도록 설명
    - 부족한 정보가 있다면 "추가로 알아보실까요?" 같은 자연스러운 톤으로 제안
    - 진행률이 높으면 다음 단계로의 전환을 부드럽게 제안
    {progress_hint}
    {missing_hint}
    """.strip()

        return PromptTemplate(
            input_variables=["context"],
            template=template
        )


    
        
    def format_history(self, messages: List[Any]) -> str:
        """대화 히스토리 포맷팅 - 공통 모듈 활용"""
        history_data = []
        for msg in reversed(messages):  # 시간순 정렬
            history_data.append({
                "role": "user" if msg.sender_type.lower() == "user" else "assistant",
                "content": msg.content,
                "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                "agent_type": msg.agent_type
            })
        
        # 공통 모듈의 format_conversation_history 활용
        return format_conversation_history(history_data, max_messages=10)
    
    async def _handle_special_topic(
            self, topic: str, persona: str, user_input: str, prompt: PromptTemplate,
            current_stage: str, progress: float, missing: List[str],
            next_stage: Optional[str], next_question: Optional[str]
        ):
        """idea_recommendation, idea_validation 공통 처리 함수"""
        logger.info("handle_special_topic 시작")
        topic_data_funcs = {
            "idea_recommendation": get_persona_trend,
            "idea_validation": get_market_analysis,
        }
       
        get_data_func = topic_data_funcs.get(topic)
        if not get_data_func:
            raise ValueError(f"Unsupported topic for special handling: {topic}")

        logger.info(f"get_data_func type: {type(get_data_func)}, value: {get_data_func}")

        try:
            if topic == "idea_recommendation":
                logger.info(f"{get_data_func} 실행")
                result = await get_data_func(persona, user_input)
                # get_persona_trend는 튜플 (trend_data, mcp_source)를 반환
                if isinstance(result, tuple) and len(result) == 2:
                    trend_data, mcp_source = result
                else:
                    trend_data = str(result)
                    mcp_source = "smithery_ai/persona-trend"
                logger.info(f"{get_data_func} 실행완료")
            elif topic == "idea_validation":
                logger.info(f"{get_data_func} 실행")
                trend_data = await get_data_func(user_input)
                # get_market_analysis는 단일 문자열을 반환
                mcp_source = "smithery_ai/brightdata-search"
                logger.info(f"{get_data_func} 실행완료")
            else:
                raise ValueError("Unsupported topic")
        except Exception as e:
            logger.error(f"데이터 수집 중 오류: {e}")
            trend_data = "시장 데이터를 불러오지 못했습니다. 일반적인 창업 컨설팅 지식으로 답변해주세요."
            mcp_source = "fallback"
        
        logger.info(f"trend_data type: {type(trend_data)}, value: {trend_data}")

        # LLM 응답 생성 (answer)
        prompt_str = prompt.template.format(context=trend_data)
        messages = [{"role": "user", "content": prompt_str}]
        logger.info(f"1차 기본 요약 : {messages}")

        answer = await self.llm_manager.generate_response(
            messages=messages,
            provider="openai",
        )
        
        return {
            "topics": [topic],
            "answer": answer,
            "sources": mcp_source,
            "retrieval_used": False,
            "metadata": {
                "type": topic,
                "current_stage": current_stage,
                "progress": progress,
                "missing": missing,
                "next_stage": next_stage,
                "next_question": next_question
            }
        }
    
    async def run_rag_query(
        self, conversation_id: int, user_input: str, use_retriever: bool = True, persona: str = "common"
    ) -> Dict[str, Any]:
        try:
            # 1. 대화 히스토리
            with get_session_context() as db:
                messages = get_recent_messages(db, conversation_id, 10)
                history = self.format_history(messages)

            # 2. 토픽 및 단계
            topics = await self.classify_topics(user_input)
            current_stage = self.multi_turn.determine_stage(topics)
            print("topics:",topics)
            print("current_stage:",current_stage)

            # 3. 진행률 및 누락 정보
            progress_info = await self.multi_turn.check_overall_progress(conversation_id, history)
            progress = progress_info.get("current_progress", 0.0)
            missing = progress_info.get("missing", [])
            logger.info(f"progress: {progress}, missing: {missing}")
            
            # 🔥 새로운 기능: 최종 기획서 작성 감지 및 자동 저장
            if current_stage == "최종 기획서 작성" or "final_business_plan" in topics or progress >= 0.95:
                logger.info(f"[AUTO_SAVE] 최종 사업기획서 작성 단계 감지 - conversation_id: {conversation_id}, progress: {progress}")
                
                # 최종 사업기획서 생성
                business_plan_content = await self._generate_final_business_plan(conversation_id, history)
                
                # 🔥 자동 저장 실행
                auto_saved = False
                save_message = ""
                
                try:
                    # 수집된 정보 추출
                    business_info = self._extract_business_info_from_history(history)
                    # 사용자 ID 추출 (대화에서)
                    with get_session_context() as db:
                        conversation = get_conversation_by_id(db, conversation_id)
                        if conversation:
                            user_id = conversation.user_id
                            
                            # 프로젝트로 자동 저장
                            save_result = save_business_plan_as_project(
                                user_id=user_id,
                                conversation_id=conversation_id,
                                business_plan_content=business_plan_content,
                                business_info=business_info
                            )
                            
                            if save_result["success"]:
                                logger.info(f"[AUTO_SAVE] 사업기획서 자동 저장 성공: project_id={save_result['project_id']}")
                                auto_saved = True
                                
                                # 저장 완료 메시지 추가
                                save_message = f"\n\n📁 **자동 저장 완료**\n" \
                                            f"• 프로젝트 제목: {save_result['title']}\n" \
                                            f"• 파일명: {save_result['file_name']}\n" \
                                            f"• 프로젝트 ID: {save_result['project_id']}\n" \
                                            f"• 저장 시간: {get_current_timestamp()}\n\n" \
                                            f"💡 마이페이지에서 저장된 사업기획서를 확인하실 수 있습니다."
                            else:
                                logger.error(f"[AUTO_SAVE] 사업기획서 자동 저장 실패: {save_result.get('error')}")
                                save_message = f"\n\n⚠️ **저장 실패**\n저장 중 오류가 발생했습니다: {save_result.get('error', '알 수 없는 오류')}"
                        else:
                            logger.error(f"[AUTO_SAVE] 대화 정보를 찾을 수 없음: conversation_id={conversation_id}")
                            save_message = "\n\n⚠️ **저장 실패**\n대화 정보를 찾을 수 없습니다."
                                
                except Exception as save_error:
                    logger.error(f"[AUTO_SAVE] 자동 저장 중 오류: {save_error}")
                    save_message = f"\n\n⚠️ **저장 실패**\n저장 중 예외 발생: {str(save_error)}"
                
                # 최종 응답 구성
                final_content = business_plan_content + save_message
                
                return {
                    "topics": topics,
                    "answer": final_content,
                    "sources": "종합된 대화 히스토리 기반",
                    "retrieval_used": False,
                    "metadata": {
                        "type": "final_business_plan",
                        "current_stage": current_stage,
                        "progress": 1.0,  # 완료
                        "missing": [],
                        "next_stage": None,
                        "next_question": None,
                        "auto_saved": auto_saved,
                        "completion_detected": True
                    }
                }

            # 4. 프롬프트 생성
            prompt = self.build_agent_prompt(topics, user_input, persona, history, current_stage, progress, missing)

            # 🔥 특별한 토픽 처리 추가
            special_topics = ["idea_recommendation", "idea_validation"]
            if any(topic in special_topics for topic in topics):
                special_topic = next(topic for topic in topics if topic in special_topics)
                next_stage = self.multi_turn.get_next_stage(current_stage)
                
                return await self._handle_special_topic(
                    topic=special_topic,
                    persona=persona,
                    user_input=user_input,
                    prompt=prompt,
                    current_stage=current_stage,
                    progress=progress,
                    missing=missing,
                    next_stage=next_stage,
                    next_question=None
                )

            # 5. RAG or Fallback
            if use_retriever and topics:
                try:
                    topic_filter = {"$and": [{"category": "business_planning"}, {"topic": {"$in": topics}}]}
                    retriever = self.vector_manager.get_retriever(
                        collection_name="global-documents",
                        k=5,
                        search_kwargs={"filter": topic_filter}
                    )

                    if retriever:
                        llm = self.llm_manager.get_llm(load_balance=True)
                        qa_chain = RetrievalQA.from_chain_type(
                            llm=llm,
                            chain_type="stuff",
                            retriever=retriever,
                            chain_type_kwargs={"prompt": prompt},
                            return_source_documents=True
                        )

                        result = qa_chain.invoke(user_input) or {}
                        sources = self._format_source_documents(result.get("source_documents", []))

                        return {
                            "topics": topics,
                            "answer": result.get('result', "관련 답변을 찾을 수 없습니다."),
                            "sources": sources,
                            "retrieval_used": True,
                            "metadata": {
                                "type": topics[0] if topics else "general",
                                "current_stage": current_stage,
                                "progress": progress,
                                "missing": missing,
                                "next_stage": self.multi_turn.get_next_stage(current_stage),
                                "next_question": None
                            }
                        }
                    else:
                        logger.warning("Retriever 생성 실패, 폴백으로 전환")

                except Exception as e:
                    logger.warning(f"RAG 검색 중 오류 발생. 폴백으로 전환: {e}")

            # Fallback 경로
            return await self._generate_fallback_response(
                topics, user_input, prompt, current_stage, None, progress, missing
            )

        except Exception as e:
            logger.error(f"RAG 쿼리 실행 실패: {e}")
            return await self._generate_fallback_response([], user_input, self.build_agent_prompt([], user_input, persona, "", "아이디어 탐색", 0.0, []))

    async def _generate_final_business_plan(self, conversation_id: int, history: str) -> str:
        """
        최종 사업기획서를 작성하기 위해 대화 히스토리를 요약하고 문서화
        """
        try:
            messages = [
                {"role": "system", "content": "너는 1인 창업 전문가로서 사업기획서를 작성하는 전문가야."},
                {"role": "user", "content": f"""
다음 대화 히스토리를 기반으로 종합적인 사업기획서를 작성해줘:

{history}

다음 형식으로 작성해주세요:

# 📋 사업기획서

## 1. 사업 개요
- 사업 아이디어
- 사업 목표
- 핵심 가치 제안

## 2. 시장 분석
- 시장 규모 및 동향
- 타겟 고객 분석
- 경쟁사 분석

## 3. 비즈니스 모델
- 수익 모델
- 가격 전략
- 비용 구조

## 4. 실행 계획
- 개발 로드맵
- 마케팅 계획
- 운영 계획

## 5. 재무 계획
- 초기 투자비
- 매출 예상
- 손익 분석

## 6. 리스크 관리
- 주요 리스크 요인
- 대응 방안
- 백업 계획

## 7. 향후 계획
- 단기 목표 (6개월)
- 중기 목표 (1-2년)
- 장기 비전 (3-5년)

실용적이고 구체적으로 작성해주세요.
불필요한 개행 없이 자연스러운 문단 구성해주세요.
"""}
            ]
            result = await self.llm_manager.generate_response(messages=messages, provider="openai")
            return result
        except Exception as e:
            logger.error(f"[final_business_plan] 생성 실패: {e}")
            return "최종 사업기획서를 생성하지 못했습니다. 다시 시도해주세요."
    
    def _extract_business_info_from_history(self, history: str) -> Dict[str, Any]:
        """대화 히스토리에서 비즈니스 정보 추출"""
        business_info = {}
        
        try:
            # 간단한 키워드 기반 정보 추출
            history_lower = history.lower()
            
            # 업종 추출
            business_types = ["카페", "쇼핑몰", "뷰티", "교육", "IT", "식당", "서비스", "제조", "유통"]
            for bt in business_types:
                if bt in history:
                    business_info["business_type"] = bt
                    break
            
            # 목표 추출
            if "매출" in history_lower or "수익" in history_lower:
                business_info["main_goal"] = "매출 증대"
            elif "고객" in history_lower or "인지도" in history_lower:
                business_info["main_goal"] = "고객 확보"
            
            # 타겟 추출
            age_groups = ["10대", "20대", "30대", "40대", "50대"]
            for age in age_groups:
                if age in history:
                    business_info["target_audience"] = age
                    break
            
            logger.info(f"추출된 비즈니스 정보: {business_info}")
            return business_info
            
        except Exception as e:
            logger.error(f"비즈니스 정보 추출 실패: {e}")
            return {}



    def _format_source_documents(self, documents: List[Any]) -> str:
        """소스 문서 포맷팅"""
        if not documents:
            return "관련 문서를 찾지 못했습니다."
        
        sources = []
        for doc in documents:
            source_info = {
                "source": doc.metadata.get("source", "❌ 없음"),
                "metadata": doc.metadata,
                "length": len(doc.page_content),
                "snippet": doc.page_content[:300]
            }
            sources.append(f"# 문서\n{source_info['snippet']}\n")
        
        return "\n\n".join(sources)
    
    async def _generate_fallback_response(self, topics: List[str], user_input: str, prompt: PromptTemplate, current_stage: str = "아이디어 탐색", next_stage: str = "", progress: float = 0.0, missing: List[str] = []) -> Dict[str, Any]:
        """폴백 응답 생성"""
        try:
            # Gemini로 폴백 응답 생성
            llm = self.llm_manager.get_llm("gemini", load_balance=True)
            
            formatted_prompt = prompt.format(
                context="관련 문서를 찾지 못했습니다. 기본 컨설턴트 지식만으로 답변해주세요.",
                current_stage=current_stage or "아이디어 탐색",
                next_stage=next_stage or ""
            )
            
            messages = [{"role": "user", "content": formatted_prompt}]
            result = await self.llm_manager.generate_response(messages, provider="gemini")
            
            return {
                "topics": topics,
                "answer": result,
                "sources": "문서를 찾지 못했습니다. 기본 지식으로 답변합니다.",
                "retrieval_used": False,
                "metadata": {
                    "type": topics[0] if topics else "general",
                    "current_stage": current_stage,
                    "progress": progress,
                    "missing": missing,
                    "next_stage": next_stage,
                    "next_question": None
                }
            }
            
        except Exception as e:
            logger.error(f"폴백 응답 생성 실패: {e}")
            return await self._generate_error_fallback(user_input)
    
    async def _generate_error_fallback(self, user_input: str) -> Dict[str, Any]:
        """에러 폴백 응답"""
        return {
            "topics": [],
            "answer": "죄송합니다. 현재 시스템에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            "sources": "시스템 오류로 인해 문서 검색이 불가능합니다.",
            "retrieval_used": False,
            "error": True
        }
    
    def handle_lean_canvas_request(self, user_question: str) -> Dict[str, Any]:
        """린캔버스 요청 처리 - 공통 모듈의 DB 함수 활용"""
        try:
            # 기본값: Common
            template_title = "린 캔버스_common"

            # 세부 키워드에 따라 타이틀 지정
            if "네일" in user_question:
                template_title = "린 캔버스_nail"
            elif "속눈썹" in user_question:
                template_title = "린 캔버스_eyelash"
            elif "쇼핑몰" in user_question:
                template_title = "린 캔버스_ecommers"
            elif "유튜버" in user_question or "크리에이터" in user_question:
                template_title = "린 캔버스_creator"

            # 공통 모듈의 DB 함수로 템플릿 조회
            template = get_template_by_title(template_title)

            return {
                "type": "lean_canvas",
                "title": template_title,
                "content": template["content"] if template else "<p>템플릿 없음</p>"
            }
            
        except Exception as e:
            logger.error(f"린캔버스 요청 처리 실패: {e}")
            return create_error_response("린캔버스 템플릿을 로드할 수 없습니다.", "TEMPLATE_LOAD_ERROR")

# 전역 서비스 인스턴스
business_service = BusinessPlanningService()

# 요청 모델 정의
class UserQuery(BaseModel):
    """사용자 쿼리 요청"""
    user_id: Optional[int] = Field(..., description="사용자 ID")
    conversation_id: Optional[int] = Field(None, description="대화 ID")
    message: str = Field(..., description="사용자 메시지")
    persona: Optional[str] = Field(default="common", description="페르소나")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "conversation_id": 456,
                "message": "창업 아이디어를 검증하고 싶습니다",
                "persona": "common"
            }
        }

# FastAPI 엔드포인트들
@app.post("/agent/query")
async def process_user_query(request: UserQuery):
    """사용자 쿼리 처리 - 공통 모듈들 최대 활용"""
    try:
        start_time = time.time()
        logger.info(f"[START] 쿼리 처리 시작 - user_id: {request.user_id}")

        user_question = request.message
        user_id = request.user_id
        conversation_id = request.conversation_id

        # 1. 대화 세션 처리
        logger.info("[STEP 1] 대화 세션 처리 시작")
        try:
            session_info = get_or_create_conversation_session(user_id, conversation_id)
            conversation_id = session_info["conversation_id"]
            logger.info("[STEP 1] 대화 세션 처리 완료")
        except Exception as e:
            logger.error(f"[STEP 1] 대화 세션 처리 실패: {e}")
            return create_error_response("대화 세션 생성에 실패했습니다", "SESSION_CREATE_ERROR")

        # 2. 사용자 메시지 저장
        logger.info("[STEP 2] 사용자 메시지 저장 시작")
        try:
            with get_session_context() as db:
                user_message = create_message(db, conversation_id, "user", "business_planning", user_question)
                if not user_message:
                    logger.warning("[STEP 2] 사용자 메시지 저장 실패")
            logger.info("[STEP 2] 사용자 메시지 저장 완료")
        except Exception as e:
            logger.warning(f"[STEP 2] 사용자 메시지 저장 실패: {e}")

        # 3. 린캔버스 요청 분기
        logger.info("[STEP 3] 린캔버스 여부 확인")
        if "린캔버스" in user_question:
            logger.info("[STEP 3] 린캔버스 요청 분기 진입")
            lean_canvas_start = time.time()
            lean_canvas_result = business_service.handle_lean_canvas_request(user_question)
            logger.info(f"[STEP 3] 린캔버스 처리 완료 - 소요시간: {time.time() - lean_canvas_start:.2f}s")

            response_data = UnifiedResponse(
                conversation_id=conversation_id,
                agent_type=AgentType.BUSINESS_PLANNING,
                response=lean_canvas_result["content"],
                confidence=0.9,
                routing_decision=RoutingDecision(
                    agent_type=AgentType.BUSINESS_PLANNING,
                    confidence=0.9,
                    reasoning="린캔버스 템플릿 요청",
                    keywords=["린캔버스", lean_canvas_result["title"]]
                ),
                sources=None,
                metadata={
                    "type": "lean_canvas",
                    "template_title": lean_canvas_result["title"]
                },
                processing_time=time.time() - start_time
            )
            return create_success_response(response_data)

        # 4. 일반 RAG 쿼리 처리
        logger.info("[STEP 4] RAG 쿼리 요청 시작")
        rag_start = time.time()
        result = await business_service.run_rag_query(
            conversation_id,
            user_question,
            use_retriever=True,
            persona=request.persona or "common"
        )
        logger.info(f"[STEP 4] RAG 쿼리 처리 완료 - 소요시간: {time.time() - rag_start:.2f}s")

        # 5. 에이전트 응답 저장
        logger.info("[STEP 5] 에이전트 응답 저장 시작")
        try:
            content_to_save = result["answer"]

            # # 기획서 쓸 때 도움되는 트렌드/시장 데이터는 저장
            # if result.get("sources") and any(t in ["idea_validation", "idea_recommendation"] for t in result.get("topics", [])):
            #     content_to_save += "\n\n[참고문서]\n" + str(result["sources"])

            insert_message_raw(
                conversation_id=conversation_id,
                sender_type="agent",
                agent_type="business_planning",
                content=content_to_save
            )
            logger.info("[STEP 5] 에이전트 응답 저장 완료")
        except Exception as e:
            logger.warning(f"[STEP 5] 에이전트 메시지 저장 실패: {e}")

        # 6. 응답 생성
        logger.info("[STEP 6] 응답 생성 및 반환")
        # if "metadata" in result and result["metadata"]:  # metadata가 있을 경우
        #     response_data = UnifiedResponse(
        #     conversation_id=conversation_id,
        #     agent_type=AgentType.BUSINESS_PLANNING,
        #     response=result["answer"],
        #     confidence=0.85,  # 상황에 맞게 지정, 필요시 계산
        #     routing_decision=RoutingDecision(
        #         agent_type=AgentType.BUSINESS_PLANNING,
        #         confidence=0.85,
        #         reasoning="사업기획서 제공",
        #         keywords=result.get("topics", [])
        #         ),
        #     sources=result.get("sources"),
        #     metadata=result["metadata"],
        #     processing_time=time.time() - start_time
        #     )
        #     return create_success_response(response_data)
            
        
        # response_data = create_business_response(
        #     conversation_id=conversation_id,
        #     answer=result["answer"],
        #     topics=result.get("topics", []),
        #     sources=result.get("sources", "")
        # )
        # logger.info(f"응답을 create_success_response에 넣기 전 :{response_data}")
        # logger.info(f"[END] 전체 처리 완료 - 총 소요시간: {time.time() - start_time:.2f}s")

        metadata = result.get("metadata", {})

        # if metadata.get("type") == "final_business_plan":
        #     metadata = {**metadata, "content": result["answer"]}
        #     result["answer"] = "최종 사업기획서가 작성되었습니다."

        response_data = UnifiedResponse(
            conversation_id=conversation_id,
            agent_type=AgentType.BUSINESS_PLANNING,
            response=result["answer"],
            confidence=result.get("confidence", 0.8),
            routing_decision=RoutingDecision(
                agent_type=AgentType.BUSINESS_PLANNING,
                confidence=result.get("confidence", 0.8),
                reasoning="사업기획 단계별 멀티턴 진행",
                keywords=result.get("topics", [])
            ),
            sources=result.get("sources"),
            metadata=metadata,
            processing_time=time.time() - start_time
        )

        return create_success_response(response_data)

    except Exception as e:
        logger.error(f"[ERROR] 쿼리 처리 중 예외 발생: {e}")
        return create_error_response(f"쿼리 처리 중 오류가 발생했습니다: {str(e)}", "QUERY_PROCESSING_ERROR")

# @app.get("/lean_canvas/{title}")
# def preview_template(title: str):
#     """린캔버스 템플릿 미리보기 - 통합 시스템 사용 권장"""
#     return create_error_response("이 API는 통합 시스템으로 이동되었습니다. 통합 시스템의 /lean_canvas/{title}을 사용해주세요.", "API_MOVED")

@app.get("/lean_canvas/{title}")
def preview_template(title: str):
    """린캔버스 템플릿 미리보기 - 공통 모듈 활용"""
    try:
        # sanitize_filename으로 안전한 파일명 보장
        #safe_title = sanitize_filename(title)
        
        # 공통 모듈의 DB 함수로 템플릿 조회
        template = get_template_by_title(title)
        html = template["content"] if template else "<p>템플릿 없음</p>"
        
        return Response(content=html, media_type="text/html")
        
    except Exception as e:
        logger.error(f"템플릿 미리보기 실패: {e}")
        """린캔버스 템플릿 미리보기 - 통합 시스템 사용 권장"""
        return create_error_response("이 API는 통합 시스템으로 이동되었습니다. 통합 시스템의 /lean_canvas/{title}을 사용해주세요.", "API_MOVED")
    
@app.get("/health")
def health_check():
    """상태 확인 엔드포인트 - 공통 모듈들의 상태 체크"""
    try:
        # 각 매니저의 상태 확인
        config_status = config.validate_config()
        llm_status = llm_manager.get_status()
        vector_status = vector_manager.get_status()
        db_status = db_manager.test_connection()
        
        health_data = {
            "service": "business_planning_agent",
            "status": "healthy",
            "timestamp": get_current_timestamp(),
            "config": config_status,
            "llm": {
                "available_models": llm_status["available_models"],
                "current_provider": llm_status["current_provider"],
                "call_count": llm_status["call_count"]
            },
            "vector": {
                "embedding_available": vector_status["embedding_available"],
                "default_collection": vector_status["default_collection"],
                "cached_vectorstores": vector_status["cached_vectorstores"]
            },
            "database": {
                "connected": db_status,
                "engine_info": db_manager.get_engine_info()
            }
        }
        
        return create_success_response(health_data)
        
    except Exception as e:
        logger.error(f"헬스체크 실패: {e}")
        return create_error_response(f"헬스체크 실패: {str(e)}", "HEALTH_CHECK_ERROR")

@app.get("/status/detailed")
def detailed_status():
    """상세 상태 확인 - 각 공통 모듈의 상세 정보"""
    try:
        # LLM 연결 테스트
        llm_test = llm_manager.test_connection()
        
        # 벡터 스토어 정보
        vector_info = vector_manager.get_collection_info()
        
        detailed_data = {
            "service_info": {
                "name": "Business Planning Agent",
                "version": "2.0.0",
                "uptime": get_current_timestamp()
            },
            "llm_test_results": llm_test,
            "vector_collection_info": vector_info,
            "config_summary": config.to_dict(),
            "prompt_meta_available": len(PROMPT_META) > 0,
            "prompt_topics": list(PROMPT_META.keys()) if PROMPT_META else []
        }
        
        return create_success_response(detailed_data)
        
    except Exception as e:
        logger.error(f"상세 상태 확인 실패: {e}")
        return create_error_response(f"상세 상태 확인 실패: {str(e)}", "DETAILED_STATUS_ERROR")


### pdf 다운로드 추가 ###
from fpdf import FPDF
from io import BytesIO
import uuid
import tempfile
import pdfkit

def generate_pdf_from_html(html_content: str) -> bytes:
    pdf_bytes = pdfkit.from_string(html_content, False)  # False: 메모리에 저장
    return pdf_bytes


def generate_pdf(content: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, content)
    pdf_output = BytesIO()
    pdf.output(pdf_output)
    return pdf_output.getvalue()

def save_pdf_to_temp(pdf_bytes: bytes) -> str:
    file_id = str(uuid.uuid4())
    temp_path = os.path.join(tempfile.gettempdir(), f"{file_id}.pdf")
    with open(temp_path, "wb") as f:
        f.write(pdf_bytes)
    return file_id

def load_pdf_from_temp(file_id: str) -> bytes:
    temp_path = os.path.join(tempfile.gettempdir(), f"{file_id}.pdf")
    with open(temp_path, "rb") as f:
        return f.read()

### pdf 생성/다운로드 api###
from fastapi.responses import StreamingResponse, JSONResponse

# @app.post("/report/pdf/create")
# async def create_pdf_report(data: dict = Body(...)):
#     content = data.get("content", "리포트 내용이 없습니다.")
#     pdf_bytes = generate_pdf(content)
#     file_id = save_pdf_to_temp(pdf_bytes)
#     return JSONResponse({"file_id": file_id})

class PdfCreateRequest(BaseModel):
    html: str
    form_data: Optional[Dict[str, str]] = None
    user_id: int                       
    conversation_id: Optional[int] = None
    title: Optional[str] = "린 캔버스_common" 

## db에 저장
@app.post("/report/pdf/create")
async def create_pdf_from_html_api(data: PdfCreateRequest,
    db: Session = Depends(get_db_dependency),):
    html = data.html or "<p>내용 없음</p>"
    form_data = data.form_data or {}
   
    try:
        pdf_bytes = generate_pdf_from_html(html)
        file_id = save_pdf_to_temp(pdf_bytes)
        file_url = f"/report/pdf/download/{file_id}"  # 상대경로로 저장

        report = create_report(
            db=db,
            user_id=data.user_id,  
            conversation_id=data.conversation_id,
            report_type="린캔버스",
            title=data.title, # 프론트에서 주는 값 바꿔야함
            content_data=form_data,  # JSON으로 저장
            file_url=file_url,
        )
        if not report:
            raise Exception("DB 저장 실패")
        return JSONResponse({"file_id": file_id})
    except Exception as e:
        logger.error(f"PDF 생성 실패: {e}")
    raise HTTPException(status_code=500, detail="PDF 생성 중 오류 발생")

@app.get("/report/pdf/download/{file_id}")
async def download_pdf_report(file_id: str):
    pdf_bytes = load_pdf_from_temp(file_id)
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=report_{file_id}.pdf"
    })

# 리포트 조회
@app.get("/reports/{report_id}")
def get_report_detail(report_id: int, db: Session = Depends(get_db_dependency)):
    """
    리포트 상세 조회 API
    """
    report = get_report_by_id(db, report_id)

    if not report:
        raise HTTPException(status_code=404, detail="해당 리포트를 찾을 수 없습니다")

    return {
        "success": True,
        "data": {
            "report_id": report.report_id,
            "report_type": report.report_type,
            "title": report.title,
            "status": "completed" if report.file_url else "generating",
            "content_data": report.content_data,
            "file_url": report.file_url,
            "created_at": report.created_at.isoformat()
        }
    }


@app.get("/reports")
def get_report_list(
    user_id: int = Query(...),  #  필수 파라미터
    report_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db_dependency)
):
    """
    리포트 목록 조회 API (필수: user_id, 선택: report_type, status)
    """
    try:
        reports = get_user_reports(db, user_id=user_id, report_type=report_type, limit=100)

        if status:
            if status == "completed":
                reports = [r for r in reports if r.file_url]
            elif status == "generating":
                reports = [r for r in reports if not r.file_url]

        return {
            "success": True,
            "data": [
                {
                    "report_id": r.report_id,
                    "report_type": r.report_type,
                    "title": r.title,
                    "status": "completed" if r.file_url else "generating",
                    "file_url": r.file_url,
                    "created_at": r.created_at.isoformat()
                }
                for r in reports
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리포트 조회 중 오류: {str(e)}")

# ✅ MCP 페르소나 기반 트렌드 분석 요청 모델
class McpPersonaTrendRequest(BaseModel):
    persona: str = Field(..., description="사용자 페르소나 (e_commerce, developer, creator 등)")
    query: str = Field(..., description="분석용 키워드 또는 질문")

# ✅ MCP 시장 분석 요청 모델
class McpMarketAnalysisRequest(BaseModel):
    query: str = Field(..., description="시장 규모/경쟁사 등 자유 질문")
    
# ✅ MCP 페르소나 트렌드 분석 API 엔드포인트
@app.post("/mcp/persona-trend")
async def get_mcp_persona_trend_api(request: McpPersonaTrendRequest):
    """
    MCP 기반 페르소나별 트렌드 데이터 조회
    - 예: 아마존 인기 상품, 앱스토어 신규 앱, 유튜브 트렌드 등
    """
    try:
        # 📡 idea_market.py의 MCP 함수 호출
        trend, source = await get_persona_trend(request.persona, request.query)

        return {
            "success": True,
            "trend": trend,
            "source_type": source  # ex: "smithery_ai/amazon-product-search"
        }
    except Exception as e:
        logger.error(f"[MCP PersonaTrend] 오류 발생: {e}")
        return create_error_response("페르소나 트렌드 분석 실패", "MCP_ERROR")


# ✅ MCP 시장 분석 API 엔드포인트
@app.post("/mcp/market-analysis")
async def get_mcp_market_analysis_api(request: McpMarketAnalysisRequest):
    """
    MCP 기반 시장 분석 API
    - 브라이트데이터 기반 경쟁사/시장규모 분석용
    """
    try:
        # 📡 idea_market.py의 get_market_analysis 호출
        result = await get_market_analysis(request.query)

        return {
            "success": True,
            "analysis": result,
            "source_type": "smithery_ai/brightdata-search"
        }
    except Exception as e:
        logger.error(f"[MCP MarketAnalysis] 오류 발생: {e}")
        return create_error_response("시장 분석 실패", "MCP_ERROR")

# 메인 실행
if __name__ == "__main__":
    import uvicorn
    
    logger.info("=== Business Planning Agent v2.0 시작 ===\n✅ 이제 통합 시스템과 연동됩니다.")
    logger.info("✅ 핵심 기능만 유지: /agent/query, /health, /status")
    logger.info("✅ 린캔버스 템플릿은 통합 시스템 사용")
    
    uvicorn.run(
        app, 
        host=config.HOST, 
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower()
    )

# 실행 명령어:
# uvicorn business_planning:app --reload --host 0.0.0.0 --port 8080
# http://127.0.0.1:8080/docs

# python -m uvicorn business_planning:app --reload --host 0.0.0.0 --port 8001
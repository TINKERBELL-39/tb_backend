"""
Mental Health Agent Utilities - 템플릿 변수 오류 해결 버전
정신건강 관련 유틸리티 함수들
"""

import logging
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from shared_modules.llm_utils import generate_response_sync
from shared_modules.llm_utils import get_llm_manager
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# PHQ-9 설문 문항
PHQ9_QUESTIONS = [
    "지난 2주 동안, 일을 하는데 흥미나 즐거움을 거의 느끼지 못했다",
    "지난 2주 동안, 기분이 가라앉거나, 우울하거나, 희망이 없다고 느꼈다", 
    "지난 2주 동안, 잠들기 어렵거나 자주 깨거나 혹은 너무 많이 잤다",
    "지난 2주 동안, 피곤하다고 느끼거나 기력이 거의 없었다",
    "지난 2주 동안, 식욕이 떨어지거나 과식을 했다",
    "지난 2주 동안, 자신을 부정적으로 생각하거나, 자신이 실패자라고 생각하거나, 자신 또는 가족을 실망시켰다고 생각했다",
    "지난 2주 동안, 신문을 읽거나 텔레비전 보는 것과 같은 일에 집중하는 것이 어려웠다",
    "지난 2주 동안, 다른 사람들이 눈치 챌 정도로 평소보다 말과 행동이 느려졌거나, 반대로 안절부절못하거나 들떠서 평소보다 많이 움직였다",
    "지난 2주 동안, 자신을 해치거나 죽어버리고 싶다는 생각을 했다"
]

def fix_invalid_json(response: str) -> Dict[str, Any]:
    """
    LLM이 반환한 잘못된 JSON 응답을 가능한 한 자동 보정하여 dict로 변환.
    """
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        cleaned = re.sub(r"```[a-zA-Z]*", "", response).strip()
        cleaned = cleaned.replace("'", '"')
        start, end = cleaned.find("{"), cleaned.rfind("}") + 1
        if start != -1 and end != -1:
            cleaned = cleaned[start:end]
        cleaned = re.sub(r",\s*}", "}", cleaned)
        cleaned = re.sub(r",\s*]", "]", cleaned)
        try:
            return json.loads(cleaned)
        except Exception:
            return {"error": "JSON 파싱 실패", "raw": response}

def calculate_phq9_score(responses: List[int]) -> Dict[str, Any]:
    """PHQ-9 점수 계산 및 해석 (JSON 기반)"""
    try:
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

        # 메시지 리스트 구성
        messages = [
            SystemMessage(content="당신은 정신건강 전문가입니다. PHQ-9 응답을 분석하고 반드시 JSON으로만 응답해주세요."),
            HumanMessage(content=f"""
다음 PHQ-9 응답을 분석해주세요:

응답: {responses}

다음 JSON 형식으로 응답해주세요:
{{
    "total_score": "총점",
    "severity": "심각도 (정상, 경미한 우울, 중등도 우울, 중등도 심각 우울, 심각한 우울)",
    "recommendation": "권장사항",
    "action_needed": "필요한 조치 (none, lifestyle, recommended, urgent, immediate)",
    "suicide_risk": "자살 위험 여부 (true/false)",
    "responses": "응답 배열",
    "assessment_date": "평가 일시",
    "interpretation": "상세 해석"    
}}

주의사항:
- 반드시 JSON 형식만 출력하세요.
- 설명 문장은 출력하지 마세요.
""")
        ]

        # LLM 호출
        raw_result = llm.invoke(messages)

        # JSON 파싱 (보정 포함)
        result = fix_invalid_json(str(raw_result.content))

        # 필드 검증 및 기본값 보정
        return {
            "total_score": int(result.get("total_score", 0)),
            "severity": result.get("severity", "평가 불가"),
            "recommendation": result.get("recommendation", "다시 평가해주세요."),
            "action_needed": result.get("action_needed", "none"),
            "suicide_risk": bool(result.get("suicide_risk", False)),
            "responses": responses,
            "assessment_date": datetime.now(),
            "interpretation": result.get("interpretation", "평가 결과를 확인할 수 없습니다.")
        }

    except Exception as e:
        logger.error(f"PHQ-9 점수 계산 실패: {e}")
        return {
            "error": str(e),
            "total_score": 0,
            "severity": "평가 불가",
            "recommendation": "다시 평가해주세요."
        }

def get_detailed_interpretation(score: int, suicide_risk: bool) -> Dict[str, Any]:
    """상세한 PHQ-9 해석 제공 (JSON 기반)"""
    try:
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

        # 메시지 리스트 구성
        messages = [
            SystemMessage(content="당신은 정신건강 전문가입니다. PHQ-9 점수와 자살 위험 여부를 바탕으로 상세한 해석을 제공하고 반드시 JSON으로만 응답해주세요."),
            HumanMessage(content=f"""
다음 정보를 바탕으로 상세한 해석을 제공해주세요:

총점: {score}
자살위험: {suicide_risk}

다음 JSON 형식으로 응답해주세요:
{{
    "score_interpretation": "점수 해석",
    "severity_level": "심각도 수준",
    "risk_assessment": "위험 평가",
    "recommendations": ["권장사항1", "권장사항2"],
    "warning_signs": ["주의해야 할 징후1", "주의해야 할 징후2"],
    "next_steps": ["다음 단계1", "다음 단계2"]
}}

주의사항:
- 반드시 JSON 형식만 출력하세요.
- 설명 문장은 출력하지 마세요.
""")
        ]

        # LLM 호출
        raw_result = llm.invoke(messages)

        # JSON 파싱 (보정 포함)
        result = fix_invalid_json(str(raw_result.content))

        # 필드 검증 및 기본값 보정
        return {
            "score_interpretation": result.get("score_interpretation", "해석 불가"),
            "severity_level": result.get("severity_level", "평가 불가"),
            "risk_assessment": result.get("risk_assessment", "위험 평가 불가"),
            "recommendations": result.get("recommendations", ["전문가와 상담하세요"]),
            "warning_signs": result.get("warning_signs", ["주의 징후 파악 불가"]),
            "next_steps": result.get("next_steps", ["전문가의 도움을 받으세요"])
        }

    except Exception as e:
        logger.error(f"PHQ-9 상세 해석 실패: {e}")
        return {
            "error": str(e),
            "score_interpretation": "해석 불가",
            "severity_level": "평가 불가",
            "risk_assessment": "위험 평가 불가",
            "recommendations": ["전문가와 상담하세요"],
            "warning_signs": ["주의 징후 파악 불가"],
            "next_steps": ["전문가의 도움을 받으세요"]
        }

def analyze_emotional_state(text: str) -> Dict[str, Any]:
    """
    LLM을 사용하여 텍스트에서 감정 상태 분석 (JSON 기반)
    """
    try:
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

        # 메시지 리스트 구성
        messages = [
            SystemMessage(content="당신은 정신건강 전문가입니다. 사용자의 텍스트에서 감정 상태를 분석하고 반드시 JSON으로만 응답해주세요."),
            HumanMessage(content=f"""
다음 텍스트에서 감정 상태를 분석해주세요:

"{text}"

다음 JSON 형식으로 응답해주세요:
{{
    "primary_emotion": "감정 (sad, anxious, angry, hopeless, suicidal, positive, neutral 중 하나)",
    "emotional_intensity": "감정 강도 (1-10 사이의 정수)",
    "risk_level": "위험 수준 (low, medium, high)",
    "requires_immediate_attention": "즉각적 개입 필요 여부 (true/false)",
    "detected_emotions": {{
        "감정1": "근거가 되는 표현",
        "감정2": "근거가 되는 표현"
    }}
}}

주의사항:
- 반드시 JSON 형식만 출력하세요.
- 설명 문장은 출력하지 마세요.
""")
        ]

        # LLM 호출
        raw_result = llm.invoke(messages)

        # JSON 파싱 (보정 포함)
        result = fix_invalid_json(str(raw_result.content))

        # 필드 검증 및 기본값 보정
        return {
            "primary_emotion": result.get("primary_emotion", "neutral"),
            "emotional_intensity": int(result.get("emotional_intensity", 0)),
            "risk_level": result.get("risk_level", "low"),
            "requires_immediate_attention": bool(result.get("requires_immediate_attention", False)),
            "detected_emotions": result.get("detected_emotions", {})
        }

    except Exception as e:
        return {
            "primary_emotion": "neutral",
            "emotional_intensity": 0,
            "risk_level": "low",
            "requires_immediate_attention": False,
            "detected_emotions": {},
            "error": str(e)
        }


def detect_crisis_indicators(text: str) -> Dict[str, Any]:
    """
    LLM을 사용하여 위기 상황 지표 감지 (SystemMessage + HumanMessage 기반).
    """
    try:
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

        # 메시지 리스트 작성
        messages = [
            SystemMessage(content="당신은 정신건강 위기 평가 전문가입니다. 사용자의 텍스트에서 위기 상황 지표를 분석하고 반드시 JSON으로만 응답해주세요."),
            HumanMessage(content=f"""
다음 텍스트에서 위기 상황 지표를 분석해주세요:

"{text}"

다음 JSON 형식으로 응답해주세요:
{{
    "crisis_level": "위기 수준 (none, mild, moderate, severe 중 하나)",
    "immediate_intervention": "즉각 개입 필요 여부 (true/false)",
    "suicide_risk": "자살 위험 여부 (true/false)",
    "self_harm_risk": "자해 위험 여부 (true/false)",
    "total_indicators": "감지된 위기 지표 개수 (숫자)",
    "emergency_resources_needed": "응급 자원 필요 여부 (true/false)",
    "detected_indicators": {{
        "crisis_content": "감지된 위기 관련 구체적 표현들"
    }},
    "recommended_actions": ["권장 조치1", "권장 조치2"]
}}

주의사항:
- 반드시 JSON 형식만 출력하세요.
- 설명 문장은 출력하지 마세요.
""")
        ]

        # LLM 호출
        raw_result = llm.invoke(messages)
        result = fix_invalid_json(str(raw_result.content))

        # 필드 검증 및 기본값 보정
        parsed_result = {
            "crisis_level": result.get("crisis_level", "none"),
            "immediate_intervention": bool(result.get("immediate_intervention", False)),
            "suicide_risk": bool(result.get("suicide_risk", False)),
            "self_harm_risk": bool(result.get("self_harm_risk", False)),
            "total_indicators": int(result.get("total_indicators", 0)),
            "emergency_resources_needed": bool(result.get("emergency_resources_needed", False)),
            "detected_indicators": result.get("detected_indicators", {"crisis_content": "없음"}),
            "recommended_actions": result.get("recommended_actions", [])
        }

        # 값 검증
        if parsed_result["crisis_level"] not in ["none", "mild", "moderate", "severe"]:
            parsed_result["crisis_level"] = "none"

        if parsed_result["total_indicators"] < 0:
            parsed_result["total_indicators"] = 0

        # 자살/자해 위험 시 강제 플래그 설정
        if parsed_result["suicide_risk"] or parsed_result["self_harm_risk"]:
            parsed_result["immediate_intervention"] = True
            parsed_result["emergency_resources_needed"] = True
            if not parsed_result["recommended_actions"]:
                parsed_result["recommended_actions"] = ["즉시 119 또는 1393에 연락하세요"]

        return parsed_result

    except Exception as e:
        return {
            "crisis_level": "none",
            "immediate_intervention": False,
            "suicide_risk": False,
            "self_harm_risk": False,
            "total_indicators": 0,
            "emergency_resources_needed": False,
            "detected_indicators": {"crisis_content": "없음"},
            "recommended_actions": [],
            "error": str(e)
        }

def generate_safety_plan(crisis_info: Dict[str, Any]) -> Dict[str, Any]:
    """LLM을 사용하여 위기 정보를 바탕으로 맞춤형 안전 계획 생성 (JSON 기반)"""
    try:
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

        # 메시지 리스트 구성
        messages = [
            SystemMessage(content="당신은 정신건강 위기 관리 전문가입니다. 내담자의 위기 정보를 바탕으로 맞춤형 안전 계획을 생성하고 반드시 JSON으로만 응답해주세요."),
            HumanMessage(content=f"""
다음과 같은 내담자의 위기 정보를 바탕으로, 맞춤형 안전 계획을 생성해주세요:

위기 정보: {crisis_info}

다음 JSON 형식으로 응답해주세요:
{{
    "immediate_actions": ["즉시 조치사항1", "즉시 조치사항2"],
    "coping_strategies": ["대처전략1", "대처전략2"],
    "emergency_contacts": ["긴급연락처1", "긴급연락처2"],
    "professional_resources": ["전문가자원1", "전문가자원2"],
    "safety_notes": ["안전수칙1", "안전수칙2"],
    "warning_signs": ["경고신호1", "경고신호2"]
}}

주의사항:
- 반드시 JSON 형식만 출력하세요.
- 설명 문장은 출력하지 마세요.
- 실행 가능하고 구체적인 조치를 제안하세요.
- 24시간 이용 가능한 연락처를 포함하세요.
- 안전을 최우선으로 고려하세요.
""")
        ]

        # LLM 호출
        raw_result = llm.invoke(messages)

        # JSON 파싱 (보정 포함)
        result = fix_invalid_json(str(raw_result.content))

        # 필드 검증 및 기본값 보정
        return {
            "immediate_actions": result.get("immediate_actions", ["전문가의 도움을 받으세요"]),
            "coping_strategies": result.get("coping_strategies", ["깊은 호흡을 하며 진정하세요"]),
            "emergency_contacts": result.get("emergency_contacts", ["생명의전화: 1393", "응급실: 119"]),
            "professional_resources": result.get("professional_resources", ["가까운 정신건강의학과"]),
            "safety_notes": result.get("safety_notes", ["위험한 상황이라고 판단되면 즉시 119에 연락하세요."]),
            "warning_signs": result.get("warning_signs", [])
        }

    except Exception as e:
        logger.error(f"안전 계획 생성 실패: {e}")
        return {
            "immediate_actions": ["전문가의 도움을 받으세요"],
            "coping_strategies": ["깊은 호흡을 하며 진정하세요"],
            "emergency_contacts": ["생명의전화: 1393", "응급실: 119"],
            "professional_resources": ["가까운 정신건강의학과"],
            "safety_notes": ["위험한 상황이라고 판단되면 즉시 119에 연락하세요."],
            "warning_signs": []
        }

def get_follow_up_questions(emotional_state: Dict[str, Any]) -> Dict[str, Any]:
    """LLM을 사용하여 감정 상태에 따른 맥락화된 후속 질문 생성 (JSON 기반)"""
    try:
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

        # 메시지 리스트 구성
        messages = [
            SystemMessage(content="당신은 정신건강 상담 전문가입니다. 내담자의 감정 상태를 기반으로 적절한 후속 질문을 생성하고 반드시 JSON으로만 응답해주세요."),
            HumanMessage(content=f"""
다음과 같은 내담자의 감정 상태 정보를 바탕으로, 맥락화된 후속 질문을 생성해주세요:

감정 상태: {emotional_state}

다음 JSON 형식으로 응답해주세요:
{{
    "questions": [
        "첫 번째 질문",
        "두 번째 질문",
        "세 번째 질문"
    ],
    "focus_areas": ["중점적으로 다룰 영역1", "중점적으로 다룰 영역2"],
    "safety_concerns": "안전 관련 우려사항 (있는 경우)",
    "approach_style": "상담 접근 방식 추천"
}}

주의사항:
- 반드시 JSON 형식만 출력하세요.
- 설명 문장은 출력하지 마세요.
- 내담자의 주요 감정과 강도를 고려하여 질문을 구성하세요.
- 위험 수준이 높은 경우 안전 확인 질문을 우선적으로 포함하세요.
- 개방형 질문을 사용하여 내담자가 자유롭게 표현할 수 있도록 하세요.
- 비판단적이고 공감적인 어조를 유지하세요.
""")
        ]

        # LLM 호출
        raw_result = llm.invoke(messages)

        # JSON 파싱 (보정 포함)
        result = fix_invalid_json(str(raw_result.content))

        # 필드 검증 및 기본값 보정
        return {
            "questions": result.get("questions", ["더 자세히 말씀해 주실 수 있나요?"])[:3],  # 최대 3개만 반환
            "focus_areas": result.get("focus_areas", ["감정 상태 탐색"]),
            "safety_concerns": result.get("safety_concerns", "없음"),
            "approach_style": result.get("approach_style", "공감적 경청")
        }

    except Exception as e:
        logger.error(f"후속 질문 생성 실패: {e}")
        return {
            "questions": ["더 자세히 말씀해 주실 수 있나요?"],
            "focus_areas": ["감정 상태 탐색"],
            "safety_concerns": "없음",
            "approach_style": "공감적 경청"
        }

def recommend_resources(assessment: Dict[str, Any]) -> Dict[str, Any]:
    """LLM을 사용하여 평가 결과에 따른 맞춤형 자원 추천 (JSON 기반)"""
    try:
        llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

        # 메시지 리스트 구성
        messages = [
            SystemMessage(content="당신은 정신건강 자원 추천 전문가입니다. 내담자의 평가 결과를 바탕으로 맞춤형 자원을 추천하고 반드시 JSON으로만 응답해주세요."),
            HumanMessage(content=f"""
다음과 같은 내담자의 평가 결과를 바탕으로, 맞춤형 자원을 추천해주세요:

평가 결과: {assessment}

다음 JSON 형식으로 응답해주세요:
{{
    "immediate": ["긴급 자원1", "긴급 자원2"],
    "professional": ["전문가 자원1", "전문가 자원2"],
    "self_help": ["자가 관리 자원1", "자가 관리 자원2"],
    "lifestyle": ["생활습관 자원1", "생활습관 자원2"],
    "resource_notes": "자원 관련 중요 참고사항",
    "priority_level": "우선순위 수준 (high, medium, low)",
    "follow_up_needed": "후속 조치 필요 여부 (true/false)"
}}

주의사항:
- 반드시 JSON 형식만 출력하세요.
- 설명 문장은 출력하지 마세요.
- PHQ-9 점수와 자살 위험도에 따라 자원의 우선순위를 조정하세요.
- 구체적이고 실행 가능한 자원을 추천하세요.
- 필요한 경우 24시간 이용 가능한 긴급 자원을 강조하세요.
""")
        ]

        # LLM 호출
        raw_result = llm.invoke(messages)

        # JSON 파싱 (보정 포함)
        result = fix_invalid_json(str(raw_result.content))

        # 필드 검증 및 기본값 보정
        return {
            "immediate": result.get("immediate", ["생명의전화 1393", "응급실 119"]),
            "professional": result.get("professional", ["가까운 정신건강의학과"]),
            "self_help": result.get("self_help", ["심호흡과 명상"]),
            "lifestyle": result.get("lifestyle", ["규칙적인 생활습관 유지"]),
            "resource_notes": result.get("resource_notes", "평가 결과에 따른 맞춤형 자원입니다."),
            "priority_level": result.get("priority_level", "low"),
            "follow_up_needed": bool(result.get("follow_up_needed", False))
        }

    except Exception as e:
        logger.error(f"자원 추천 실패: {e}")
        return {
            "immediate": ["생명의전화 1393", "응급실 119"],
            "professional": ["가까운 정신건강의학과"],
            "self_help": ["심호흡과 명상"],
            "lifestyle": ["규칙적인 생활습관 유지"],
            "resource_notes": "위험한 상황이라고 판단되면 즉시 전문가의 도움을 받으세요.",
            "priority_level": "low",
            "follow_up_needed": False
        }

import json
from typing import List, Dict, Any

class MultiTurnManager:
    """
    멀티턴 대화 흐름 및 단계별 정보 수집을 관리하는 매니저
    """

    STAGE_TOPIC_MAP = {
        "아이디어 탐색": ["idea_recommendation"],
        "시장 검증": ["idea_validation"],
        "비즈니스 모델링": ["business_model", "mvp_development"],
        "실행 계획 수립": ["funding_strategy", "financial_planning", "startup_preparation"],
        "성장 전략 & 리스크 관리": ["growth_strategy", "risk_management"],
        "최종 기획서 작성": ["final_business_plan"]
    }

    STAGES = list(STAGE_TOPIC_MAP.keys())

    STAGE_REQUIREMENTS = {
        "아이디어 탐색": ["창업 아이디어"],
        "시장 검증": ["시장 정보"],
        "비즈니스 모델링": ["BMC", "MVP 개발 계획"],
        "실행 계획 수립": ["자금 조달 계획", "재무 계획", "창업 준비 체크리스트"],
        "성장 전략 & 리스크 관리": ["사업 확장 전략", "리스크 관리 방안"],
        "최종 기획서 작성": []
    }

    def __init__(self, llm_manager):
        self.llm_manager = llm_manager
        self.progress_cache = {}  # {conversation_id: float}

    def determine_stage(self, topics: List[str]) -> str:
        for stage, mapped_topics in self.STAGE_TOPIC_MAP.items():
            if any(t in mapped_topics for t in topics):
                return stage
        return "아이디어 탐색"

    def get_next_stage(self, current_stage: str) -> str:
        try:
            idx = self.STAGES.index(current_stage)
            return self.STAGES[idx + 1] if idx + 1 < len(self.STAGES) else None
        except ValueError:
            return None

    async def check_overall_progress(self, conversation_id: int, history: str) -> Dict[str, Any]:
        """
        대화(conversation_id) 기준으로 진행률 캐싱 및 업데이트
        """
        all_requirements = []
        for stage, items in self.STAGE_REQUIREMENTS.items():
            if stage != "최종 기획서 작성":
                all_requirements.extend(items)

        if not all_requirements:
            return {"progress": 0.0, "missing": []}

        prompt = f"""
        다음 대화 기록에서 아래 요구 정보 항목이 얼마나 수집되었는지 평가하세요.
        전체 항목: {', '.join(all_requirements)}
        대화 기록:
        {history}

        각 항목에 대해 '있음' 또는 '없음'으로 평가하고,
        누락된 항목 목록과 진행률(0~1)을 JSON으로 출력하세요.
        예시:
        {{
            "progress": 0.6,
            "missing": ["경쟁사 분석", "타겟 시장"]
        }}
        """.replace("{", "{{").replace("}", "}}")

        try:
            messages = [
                {"role": "system", "content": "너는 전체 단계 정보 수집 현황을 JSON으로 평가하는 전문가야."},
                {"role": "user", "content": prompt}
            ]
            result = await self.llm_manager.generate_response(messages=messages, provider="openai")
            result = self._parse_progress_json(result)

            new_progress = float(result.get("progress", 0.0))
            current_progress = self.progress_cache.get(conversation_id, 0.0)

            if new_progress >= 0.999:
                self.progress_cache[conversation_id] = 0.0
                result["current_progress"] = 1.0
                result["missing"] = []
            else:
                self.progress_cache[conversation_id] = max(current_progress, new_progress)
                result["current_progress"] = self.progress_cache[conversation_id]
            return result

        except Exception as e:
            print(f"[check_overall_progress] 오류: {e}")
            return {"progress": 0.0, "missing": all_requirements}

    def _parse_progress_json(self, result: str) -> Dict[str, Any]:
        try:
            clean_result = result.strip().strip("`")
            if clean_result.startswith("json"):
                clean_result = clean_result[4:].strip()

            return json.loads(clean_result)
        except Exception as e:
            print(f"JSON 파싱 실패: {e}, 원본: {result}")
            return {"progress": 0.0, "missing": []}

"""
일정 추출 서비스
대화 히스토리에서 일정 정보를 추출하고 자동화 작업으로 등록하는 서비스
"""

import logging
import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ExtractedSchedule:
    """추출된 일정 정보"""
    title: str
    start_time: str
    end_time: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: Optional[List[str]] = None
    all_day: bool = False
    confidence: float = 0.0

class ScheduleExtractionService:
    """일정 추출 서비스"""
    
    def __init__(self, llm_service):
        """서비스 초기화"""
        self.llm_service = llm_service
        logger.info("ScheduleExtractionService 초기화 완료")

    async def extract_schedules_from_conversation(self, conversation_history: List[Dict[str, Any]]) -> List[ExtractedSchedule]:
        """대화 히스토리에서 일정 정보 추출"""
        try:
            # 최근 10개 메시지만 확인 (성능 최적화)
            recent_messages = conversation_history[-10:] if conversation_history else []
            
            schedules = []
            
            # 1. 룰 기반 추출 (빠른 처리)
            rule_based_schedules = self._extract_schedules_by_rules(recent_messages)
            schedules.extend(rule_based_schedules)
            
            # 2. LLM 기반 추출 (정확도 향상)
            if self.llm_service:
                llm_schedules = await self._extract_schedules_by_llm(recent_messages)
                schedules.extend(llm_schedules)
            
            # 3. 중복 제거 및 정리
            unique_schedules = self._remove_duplicate_schedules(schedules)
            
            logger.info(f"대화에서 {len(unique_schedules)}개의 일정을 추출했습니다")
            return unique_schedules
            
        except Exception as e:
            logger.error(f"일정 추출 실패: {e}")
            return []

    def _extract_schedules_by_rules(self, messages: List[Dict[str, Any]]) -> List[ExtractedSchedule]:
        """룰 기반 일정 추출"""
        schedules = []
        
        try:
            for message in messages:
                content = message.get('content', '')
                if not content or message.get('sender_type') != 'agent':
                    continue
                
                # 일정 패턴 매칭
                schedule_info = self._match_schedule_patterns(content)
                if schedule_info:
                    schedules.extend(schedule_info)
            
            return schedules
            
        except Exception as e:
            logger.error(f"룰 기반 일정 추출 실패: {e}")
            return []

    def _match_schedule_patterns(self, content: str) -> List[ExtractedSchedule]:
        """일정 패턴 매칭"""
        schedules = []
        
        try:
            # 시간 패턴들
            time_patterns = [
                r'(\d{1,2})시\s*(\d{1,2})?분?',  # 14시 30분
                r'(\d{1,2}):(\d{2})',             # 14:30
                r'(오전|오후)\s*(\d{1,2})시',     # 오후 2시
                r'(내일|모레|오늘)\s*(오전|오후)?\s*(\d{1,2})시',  # 내일 오후 2시
            ]
            
            # 날짜 패턴들
            date_patterns = [
                r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',  # 2024년 1월 15일
                r'(\d{1,2})월\s*(\d{1,2})일',              # 1월 15일
                r'(내일|모레|오늘)',                        # 내일
                r'(\d{1,2})/(\d{1,2})',                   # 1/15
            ]
            
            # 제목 추출 패턴
            title_patterns = [
                r'(\w+)\s*(회의|미팅|약속|일정)',
                r'(\w+)\s*만나기',
                r'(\w+)\s*시간',
                r'"([^"]+)"',  # 따옴표로 둘러싸인 텍스트
            ]
            
            # 패턴 매칭 실행
            found_times = []
            found_dates = []
            found_titles = []
            
            # 시간 매칭
            for pattern in time_patterns:
                matches = re.findall(pattern, content)
                found_times.extend(matches)
            
            # 날짜 매칭
            for pattern in date_patterns:
                matches = re.findall(pattern, content)
                found_dates.extend(matches)
            
            # 제목 매칭
            for pattern in title_patterns:
                matches = re.findall(pattern, content)
                found_titles.extend(matches)
            
            # 일정 조합 생성
            if found_times or found_dates or found_titles:
                schedule = self._combine_schedule_parts(found_times, found_dates, found_titles, content)
                if schedule:
                    schedules.append(schedule)
            
            return schedules
            
        except Exception as e:
            logger.error(f"패턴 매칭 실패: {e}")
            return []

    def _combine_schedule_parts(self, times: List, dates: List, titles: List, content: str) -> Optional[ExtractedSchedule]:
        """일정 구성 요소들을 조합"""
        try:
            # 제목 결정
            title = "일정"
            if titles:
                title = str(titles[0]) if isinstance(titles[0], tuple) else str(titles[0])
                if isinstance(titles[0], tuple):
                    title = " ".join(str(x) for x in titles[0] if x)
            
            # 시간 결정
            start_time = None
            if times:
                time_info = times[0]
                if isinstance(time_info, tuple) and len(time_info) >= 2:
                    hour = int(time_info[0])
                    minute = int(time_info[1]) if time_info[1] else 0
                    start_time = f"{hour:02d}:{minute:02d}"
            
            # 날짜 결정
            date_str = None
            if dates:
                date_info = dates[0]
                if isinstance(date_info, str):
                    if date_info in ['내일', '모레', '오늘']:
                        base_date = datetime.now()
                        if date_info == '내일':
                            base_date += timedelta(days=1)
                        elif date_info == '모레':
                            base_date += timedelta(days=2)
                        date_str = base_date.strftime('%Y-%m-%d')
            
            # start_time 조합
            if date_str and start_time:
                full_start_time = f"{date_str}T{start_time}:00"
            elif date_str:
                full_start_time = f"{date_str}T09:00:00"  # 기본 시간
            elif start_time:
                # 오늘 날짜로 설정
                today = datetime.now().strftime('%Y-%m-%d')
                full_start_time = f"{today}T{start_time}:00"
            else:
                # 기본값: 내일 오전 9시
                tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                full_start_time = f"{tomorrow}T09:00:00"
            
            return ExtractedSchedule(
                title=title,
                start_time=full_start_time,
                description=content[:200] + "..." if len(content) > 200 else content,
                confidence=0.7
            )
            
        except Exception as e:
            logger.error(f"일정 조합 실패: {e}")
            return None

    async def _extract_schedules_by_llm(self, messages: List[Dict[str, Any]]) -> List[ExtractedSchedule]:
        """LLM 기반 일정 추출"""
        try:
            # 메시지들을 하나의 컨텍스트로 결합
            context = "\n".join([
                f"{msg.get('sender_type', 'unknown')}: {msg.get('content', '')}"
                for msg in messages[-5:]  # 최근 5개 메시지만
            ])
            
            # LLM에게 일정 추출 요청
            extraction_prompt = self._create_extraction_prompt(context)
            llm_response = await self.llm_service.extract_schedules(extraction_prompt)
            
            # 응답 파싱
            schedules = self._parse_llm_response(llm_response)
            return schedules
            
        except Exception as e:
            logger.error(f"LLM 기반 일정 추출 실패: {e}")
            return []

    def _create_extraction_prompt(self, context: str) -> str:
        """일정 추출 프롬프트 생성"""
        return f"""
다음 대화에서 언급된 일정 정보를 JSON 형태로 추출해주세요.

대화 내용:
{context}

추출할 정보:
- title: 일정 제목
- start_time: 시작 시간 (ISO 8601 형식: YYYY-MM-DDTHH:MM:SS)
- end_time: 종료 시간 (선택사항)
- description: 설명
- location: 위치 (선택사항)
- attendees: 참석자 이메일 목록 (선택사항)
- all_day: 종일 일정 여부 (true/false)

응답 형식:
{{
  "schedules": [
    {{
      "title": "회의 제목",
      "start_time": "2024-01-15T14:00:00",
      "end_time": "2024-01-15T15:00:00",
      "description": "회의 설명",
      "location": "회의실 A",
      "attendees": ["user@example.com"],
      "all_day": false
    }}
  ]
}}

일정이 없다면 빈 배열을 반환하세요.
"""

    def _parse_llm_response(self, response: str) -> List[ExtractedSchedule]:
        """LLM 응답 파싱"""
        try:
            # JSON 파싱 시도
            if isinstance(response, str):
                data = json.loads(response)
            else:
                data = response
            
            schedules = []
            for schedule_data in data.get('schedules', []):
                schedule = ExtractedSchedule(
                    title=schedule_data.get('title', '일정'),
                    start_time=schedule_data.get('start_time'),
                    end_time=schedule_data.get('end_time'),
                    description=schedule_data.get('description'),
                    location=schedule_data.get('location'),
                    attendees=schedule_data.get('attendees'),
                    all_day=schedule_data.get('all_day', False),
                    confidence=0.9  # LLM 추출의 신뢰도는 높게 설정
                )
                schedules.append(schedule)
            
            return schedules
            
        except json.JSONDecodeError as e:
            logger.error(f"LLM 응답 JSON 파싱 실패: {e}")
            return []
        except Exception as e:
            logger.error(f"LLM 응답 파싱 실패: {e}")
            return []

    def _remove_duplicate_schedules(self, schedules: List[ExtractedSchedule]) -> List[ExtractedSchedule]:
        """중복 일정 제거"""
        try:
            unique_schedules = []
            seen_schedules = set()
            
            for schedule in schedules:
                # 제목과 시작시간으로 중복 체크
                key = (schedule.title, schedule.start_time)
                if key not in seen_schedules:
                    seen_schedules.add(key)
                    unique_schedules.append(schedule)
            
            # 신뢰도 기준으로 정렬
            unique_schedules.sort(key=lambda x: x.confidence, reverse=True)
            
            return unique_schedules
            
        except Exception as e:
            logger.error(f"중복 제거 실패: {e}")
            return schedules

    async def create_calendar_automation_task(self, schedule: ExtractedSchedule, user_id: int, conversation_id: int) -> Dict[str, Any]:
        """일정을 Google Calendar 자동화 작업으로 생성"""
        try:
            task_data = {
                "title": schedule.title,
                "start_time": schedule.start_time,
                "end_time": schedule.end_time,
                "description": schedule.description or f"자동 생성된 일정: {schedule.title}",
                "location": schedule.location,
                "all_day": schedule.all_day,
                "calendar_id": "primary",
                "reminders": [{"method": "popup", "minutes": 15}]
            }
            
            # 참석자가 있으면 추가
            if schedule.attendees:
                task_data["attendees"] = [{"email": email} for email in schedule.attendees]
            
            return {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "task_type": "calendar_sync",
                "title": f"일정 등록: {schedule.title}",
                "task_data": task_data,
                "scheduled_at": None,  # 즉시 실행
                "confidence": schedule.confidence
            }
            
        except Exception as e:
            logger.error(f"Calendar 자동화 작업 생성 실패: {e}")
            return None

    def format_schedules_summary(self, schedules: List[ExtractedSchedule]) -> str:
        """추출된 일정들의 요약 메시지 생성"""
        try:
            if not schedules:
                return "대화에서 일정 정보를 찾을 수 없습니다."
            
            summary = f"📅 **{len(schedules)}개의 일정을 찾았습니다:**\n\n"
            
            for i, schedule in enumerate(schedules, 1):
                summary += f"**{i}. {schedule.title}**\n"
                summary += f"• 시간: {self._format_time(schedule.start_time)}"
                if schedule.end_time:
                    summary += f" ~ {self._format_time(schedule.end_time)}"
                summary += "\n"
                
                if schedule.description:
                    summary += f"• 설명: {schedule.description[:50]}...\n"
                if schedule.location:
                    summary += f"• 위치: {schedule.location}\n"
                
                summary += f"• 신뢰도: {schedule.confidence:.1%}\n\n"
            
            return summary
            
        except Exception as e:
            logger.error(f"일정 요약 생성 실패: {e}")
            return "일정 요약을 생성할 수 없습니다."

    def _format_time(self, time_str: str) -> str:
        """시간 문자열 포맷팅"""
        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return dt.strftime('%m월 %d일 %H:%M')
        except:
            return time_str

    async def get_status(self) -> Dict[str, Any]:
        """서비스 상태 조회"""
        return {
            "service": "ScheduleExtractionService",
            "version": "1.0.0",
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }

    async def cleanup(self):
        """서비스 정리"""
        logger.info("ScheduleExtractionService 정리 완료")

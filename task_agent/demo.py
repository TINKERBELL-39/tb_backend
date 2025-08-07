#!/usr/bin/env python3
"""
Task Agent v5.0 실시간 데모
사용자가 직접 일정 추출 → 자동 등록 워크플로우를 테스트할 수 있는 스크립트
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Task Agent 모듈들
from models import UserQuery, PersonaType
from services.schedule_extraction_service import ScheduleExtractionService
from automation import AutomationManager

class TaskAgentDemo:
    """Task Agent 실시간 데모 클래스"""
    
    def __init__(self):
        print("🤖 Task Agent v5.0 실시간 데모")
        print("="*50)
        
    async def demo_schedule_extraction_workflow(self):
        """일정 추출 → 자동 등록 워크플로우 데모"""
        print("\n📅 일정 추출 → 자동 등록 워크플로우 데모")
        print("-" * 50)
        
        # Mock LLM Service
        class MockLLMService:
            async def extract_schedules(self, prompt):
                return {
                    "schedules": [
                        {
                            "title": "개발팀 주간 미팅",
                            "start_time": (datetime.now() + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0).isoformat(),
                            "end_time": (datetime.now() + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0).isoformat(),
                            "description": "주간 개발 진행 상황 점검 및 계획 수립",
                            "location": "회의실 A"
                        },
                        {
                            "title": "고객 미팅",
                            "start_time": (datetime.now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
                            "end_time": (datetime.now() + timedelta(days=2)).replace(hour=11, minute=30, second=0, microsecond=0).isoformat(),
                            "description": "Q1 프로젝트 요구사항 논의",
                            "location": "온라인 (Zoom)"
                        }
                    ]
                }
        
        try:
            # 1. 사용자 대화 시뮬레이션
            print("👤 사용자: '내일 오후 2시에 개발팀 주간 미팅이 있고, 모레 오전 10시에 고객 미팅이 예정되어 있어'")
            print("🤖 봇: '네, 두 일정을 확인했습니다...'")
            print()
            print("👤 사용자: '지금 짜준 일정 기반으로 구글 캘린더에 등록해줘'")
            print()
            
            # 2. 대화 히스토리 생성
            conversation_history = [
                {
                    "sender_type": "user",
                    "content": "내일 오후 2시에 개발팀 주간 미팅이 있고, 모레 오전 10시에 고객 미팅이 예정되어 있어"
                },
                {
                    "sender_type": "agent", 
                    "content": "네, 두 일정을 확인했습니다. 내일 오후 2시 개발팀 주간 미팅과 모레 오전 10시 고객 미팅이군요."
                }
            ]
            
            # 3. 일정 추출 서비스 실행
            print("🔍 일정 추출 중...")
            schedule_service = ScheduleExtractionService(MockLLMService())
            extracted_schedules = await schedule_service.extract_schedules_from_conversation(conversation_history)
            
            if extracted_schedules:
                print(f"✅ {len(extracted_schedules)}개 일정 추출 완료!")
                for i, schedule in enumerate(extracted_schedules, 1):
                    print(f"   {i}. {schedule.title}")
                    print(f"      📅 {schedule.start_time}")
                    if schedule.location:
                        print(f"      📍 {schedule.location}")
                print()
                
                # 4. 자동화 작업 생성
                print("⚙️ 자동화 작업 생성 중...")
                automation_manager = AutomationManager()
                
                created_tasks = []
                for schedule in extracted_schedules:
                    # 자동화 작업 데이터 생성
                    automation_data = await schedule_service.create_calendar_automation_task(
                        schedule, 2, 456
                    )
                    
                    if automation_data:
                        from models import AutomationRequest
                        automation_req = AutomationRequest(**automation_data)
                        
                        # 자동화 작업 등록
                        response = await automation_manager.create_automation_task(automation_req)
                        
                        if response.task_id > 0:
                            created_tasks.append({
                                "task_id": response.task_id,
                                "title": schedule.title,
                                "status": response.status.value
                            })
                            print(f"   ✅ {schedule.title} → 작업 ID: {response.task_id}")
                
                if created_tasks:
                    print(f"\n🎉 {len(created_tasks)}개 일정이 automation_task DB에 저장되었습니다!")
                    print("🔄 스케쥴러가 자동으로 main.py의 Google Calendar API를 호출합니다.")
                    
                    # 5. 작업 상태 확인 시뮬레이션
                    print("\n📊 작업 상태 확인:")
                    for task in created_tasks:
                        status = await automation_manager.get_task_status(task["task_id"])
                        print(f"   📋 {task['title']}: {status.get('status', '확인 중...')}")
                
                # 정리
                await automation_manager.cleanup()
                await schedule_service.cleanup()
                
            else:
                print("❌ 일정을 추출할 수 없습니다.")
                
        except Exception as e:
            print(f"❌ 데모 실행 중 오류: {e}")
    
    async def demo_direct_automation(self):
        """직접 자동화 작업 생성 데모"""
        print("\n🚀 직접 자동화 작업 생성 데모")
        print("-" * 50)
        
        try:
            print("👤 사용자: '내일 오후 3시에 프로젝트 리뷰 미팅 캘린더에 등록해줘'")
            print()
            
            # 직접 자동화 작업 생성
            from models import AutomationRequest
            
            automation_req = AutomationRequest(
                user_id=2,
                task_type="calendar_sync",
                title="프로젝트 리뷰 미팅 등록",
                task_data={
                    "title": "프로젝트 리뷰 미팅",
                    "start_time": (datetime.now() + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0).isoformat(),
                    "end_time": (datetime.now() + timedelta(days=1)).replace(hour=16, minute=0, second=0, microsecond=0).isoformat(),
                    "description": "Q1 프로젝트 진행 상황 리뷰 및 다음 단계 논의",
                    "location": "회의실 B",
                    "calendar_id": "primary",
                    "reminders": [{"method": "popup", "minutes": 15}]
                }
            )
            
            automation_manager = AutomationManager()
            response = await automation_manager.create_automation_task(automation_req)
            
            if response.task_id > 0:
                print(f"✅ 자동화 작업 생성 완료!")
                print(f"   📋 작업 ID: {response.task_id}")
                print(f"   📅 제목: 프로젝트 리뷰 미팅")
                print(f"   ⏰ 시간: {(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')} 15:00")
                print(f"   🔄 상태: {response.status.value}")
                print()
                print("🔄 CalendarExecutor가 main.py의 POST /events API를 호출하여")
                print("   실제 Google Calendar에 일정을 등록합니다.")
                
                # 작업 상태 확인
                status = await automation_manager.get_task_status(response.task_id)
                print(f"\n📊 작업 상태: {status.get('status', '확인 중...')}")
            else:
                print(f"❌ 자동화 작업 생성 실패: {response.message}")
            
            await automation_manager.cleanup()
            
        except Exception as e:
            print(f"❌ 직접 자동화 데모 실행 중 오류: {e}")
    
    async def demo_system_monitoring(self):
        """시스템 모니터링 데모"""
        print("\n📊 시스템 모니터링 데모")
        print("-" * 50)
        
        try:
            automation_manager = AutomationManager()
            
            # 시스템 통계 조회
            stats = await automation_manager.get_system_stats()
            
            print("📈 시스템 통계:")
            print(f"   📋 총 작업 수: {stats.get('total_tasks', 0)}")
            print(f"   ⏳ 대기 중: {stats.get('status_distribution', {}).get('pending', 0)}")
            print(f"   ⚙️ 처리 중: {stats.get('status_distribution', {}).get('processing', 0)}")
            print(f"   ✅ 성공: {stats.get('status_distribution', {}).get('success', 0)}")
            print(f"   ❌ 실패: {stats.get('status_distribution', {}).get('failed', 0)}")
            print(f"   🔄 스케쥴러 작업: {stats.get('scheduler_jobs', 0)}")
            
            print("\n🔧 실행기 상태:")
            executor_status = stats.get('executor_status', {})
            for task_type, available in executor_status.items():
                status_icon = "✅" if available else "❌"
                print(f"   {status_icon} {task_type}: {'사용 가능' if available else '사용 불가'}")
            
            await automation_manager.cleanup()
            
        except Exception as e:
            print(f"❌ 시스템 모니터링 데모 실행 중 오류: {e}")
    
    def show_architecture(self):
        """시스템 아키텍처 설명"""
        print("\n🏗️ Task Agent v5.0 아키텍처")
        print("-" * 50)
        print("사용자 메시지")
        print("    ↓")
        print("Agent.py (일정 추출 기능 추가)")
        print("    ↓")
        print("ScheduleExtractionService (신규)")
        print("    ↓")
        print("AutomationManager (스케쥴러)")
        print("    ↓")
        print("CalendarExecutor v2 (실제 API 호출)")
        print("    ↓")
        print("main.py POST /events")
        print("    ↓")
        print("Google Calendar 실제 등록")
        print()
        print("🔄 전체 프로세스:")
        print("1. 사용자가 일정 관련 메시지 전송")
        print("2. Agent가 ScheduleExtractionService로 일정 추출") 
        print("3. 추출된 일정을 automation_task DB에 저장")
        print("4. AutomationManager의 스케쥴러가 작업 실행")
        print("5. CalendarExecutor가 실제 main.py API 호출")
        print("6. Google Calendar에 실제 일정 등록 완료")

async def main():
    """메인 데모 실행"""
    demo = TaskAgentDemo()
    
    while True:
        print("\n" + "="*60)
        print("🤖 Task Agent v5.0 데모 메뉴")
        print("="*60)
        print("1. 일정 추출 → 자동 등록 워크플로우 데모")
        print("2. 직접 자동화 작업 생성 데모") 
        print("3. 시스템 모니터링 데모")
        print("4. 시스템 아키텍처 보기")
        print("5. 종료")
        print()
        
        try:
            choice = input("선택하세요 (1-5): ").strip()
            
            if choice == "1":
                await demo.demo_schedule_extraction_workflow()
            elif choice == "2":
                await demo.demo_direct_automation()
            elif choice == "3":
                await demo.demo_system_monitoring()
            elif choice == "4":
                demo.show_architecture()
            elif choice == "5":
                print("\n👋 Task Agent v5.0 데모를 종료합니다.")
                break
            else:
                print("❌ 잘못된 선택입니다. 1-5 중에서 선택해주세요.")
                
        except KeyboardInterrupt:
            print("\n\n👋 데모가 사용자에 의해 종료되었습니다.")
            break
        except Exception as e:
            print(f"\n❌ 데모 실행 중 오류: {e}")
        
        input("\n계속하려면 Enter를 누르세요...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 데모가 종료되었습니다.")
    except Exception as e:
        print(f"\n❌ 데모 시작 실패: {e}")

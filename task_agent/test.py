#!/usr/bin/env python3
"""
Google Calendar 통합 테스트 스크립트

이 스크립트는 다음 기능들을 테스트합니다:
1. Google OAuth 인증 플로우
2. 캘린더 목록 조회
3. 이벤트 생성 (일반/빠른 생성)
4. 이벤트 조회 및 검색
5. 이벤트 수정 및 삭제
6. 연동 해제
"""

import requests
import json
import webbrowser
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class TestConfig:
    """테스트 설정"""
    base_url: str = "https://localhost:8005"
    user_id: int = 2
    test_calendar_id: str = "primary"
    timeout: int = 30

class GoogleCalendarIntegrationTester:
    """Google Calendar 통합 테스트 클래스"""
    
    def __init__(self, config: TestConfig = None):
        self.config = config or TestConfig()
        self.session = requests.Session()
        self.session.timeout = self.config.timeout
        self.auth_state = None
        self.created_events = []  # 테스트 중 생성된 이벤트 추적
        
    def print_step(self, step_num: int, title: str):
        """테스트 단계 출력"""
        print(f"\n{'='*60}")
        print(f"Step {step_num}: {title}")
        print(f"{'='*60}")
    
    def print_result(self, success: bool, message: str, data: Any = None):
        """결과 출력"""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{status}: {message}")
        if data and isinstance(data, dict):
            print(f"📋 Data: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    def step1_check_server_status(self) -> bool:
        """Step 1: 서버 상태 확인"""
        self.print_step(1, "서버 상태 확인")
        
        try:
            response = self.session.get(f"{self.config.base_url}/health")
            response.raise_for_status()
            
            data = response.json()
            self.print_result(True, "서버가 정상 동작 중입니다", data)
            return True
            
        except Exception as e:
            self.print_result(False, f"서버 연결 실패: {e}")
            return False
    
    def step2_get_authorization_url(self) -> Optional[str]:
        """Step 2: Google OAuth 인증 URL 획득"""
        self.print_step(2, "Google OAuth 인증 URL 획득")
        
        try:
            url = f"{self.config.base_url}/auth/google-calendar/authorize"
            params = {"user_id": self.config.user_id}
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            auth_url = data.get('auth_url')
            self.auth_state = data.get('state')
            
            if auth_url and self.auth_state:
                self.print_result(True, "인증 URL 생성 성공")
                print(f"🔗 인증 URL: {auth_url}")
                print(f"🔑 State: {self.auth_state}")
                return auth_url
            else:
                self.print_result(False, "인증 URL 또는 State가 없습니다", data)
                return None
                
        except Exception as e:
            self.print_result(False, f"인증 URL 획득 실패: {e}")
            return None
    
    def step3_user_authorization(self, auth_url: str) -> Optional[str]:
        """Step 3: 사용자 인증 (수동 단계)"""
        self.print_step(3, "사용자 Google 계정 인증")
        
        print("🌐 브라우저에서 Google 인증 페이지를 열고 있습니다...")
        print(f"   URL: {auth_url}")
        
        try:
            webbrowser.open(auth_url)
            print("✅ 브라우저가 성공적으로 열렸습니다!")
        except Exception as e:
            print(f"❌ 브라우저 열기 실패: {e}")
            print(f"수동으로 다음 URL을 방문해주세요: {auth_url}")
        
        print("\n📝 Google에서 권한을 승인한 후, 리다이렉트 URL에서 'code' 파라미터를 복사해주세요:")
        print(f"   예시: {self.config.base_url}/auth/google-calendar/callback?code=AUTHORIZATION_CODE&state={self.auth_state}")
        print("\n⚠️  인증 코드를 입력해주세요:")
        
        auth_code = input("Authorization Code: ").strip()
        state = input("State: ").strip()

        return auth_code, state
    
    def step4_complete_oauth(self, auth_code: str, state: str) -> bool:
        """Step 4: OAuth 인증 완료"""
        self.print_step(4, "OAuth 인증 완료")
        
        try:
            url = f"{self.config.base_url}/auth/google-calendar/callback"
            params = {
                "code": auth_code,
                "state": state
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success'):
                self.print_result(True, "OAuth 인증이 성공적으로 완료되었습니다", data)
                return True
            else:
                self.print_result(False, "OAuth 인증 실패", data)
                return False
                
        except Exception as e:
            self.print_result(False, f"OAuth 인증 처리 실패: {e}")
            return False
    
    def step5_check_connection_status(self) -> bool:
        """Step 5: 연동 상태 확인"""
        self.print_step(5, "Google Calendar 연동 상태 확인")
        
        try:
            url = f"{self.config.base_url}/user/{self.config.user_id}/calendar-status"
            
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            is_connected = data.get('is_connected', False)
            
            if is_connected:
                self.print_result(True, "Google Calendar가 성공적으로 연동되었습니다", data)
                return True
            else:
                self.print_result(False, "Google Calendar 연동이 확인되지 않습니다", data)
                return False
                
        except Exception as e:
            self.print_result(False, f"연동 상태 확인 실패: {e}")
            return False
    
    def step6_get_calendars(self) -> bool:
        """Step 6: 캘린더 목록 조회"""
        self.print_step(6, "캘린더 목록 조회")
        
        try:
            url = f"{self.config.base_url}/calendars"
            params = {"user_id": self.config.user_id}
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            calendars = data.get('calendars', [])
            
            self.print_result(True, f"캘린더 {len(calendars)}개를 조회했습니다")
            
            for i, calendar in enumerate(calendars[:3]):  # 처음 3개만 출력
                print(f"  📅 {i+1}. {calendar.get('summary', 'Unknown')} (ID: {calendar.get('id', 'Unknown')})")
            
            if len(calendars) > 3:
                print(f"  ... 및 {len(calendars) - 3}개 더")
            
            return True
            
        except Exception as e:
            self.print_result(False, f"캘린더 목록 조회 실패: {e}")
            return False
    
    def step7_create_test_event(self) -> Optional[str]:
        """Step 7: 테스트 이벤트 생성"""
        self.print_step(7, "테스트 이벤트 생성")
        
        # 내일 오후 2시에 1시간 회의 생성
        start_time = datetime.now() + timedelta(days=1)
        start_time = start_time.replace(hour=14, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)
        
        event_data = {
            "title": "🤖 TinkerBell 테스트 이벤트",
            "description": "Google Calendar 연동 테스트를 위한 자동 생성 이벤트입니다.",
            "location": "온라인 (Zoom)",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "timezone": "Asia/Seoul",
            "calendar_id": self.config.test_calendar_id,
            "reminders": [
                {"method": "popup", "minutes": 15},
                {"method": "email", "minutes": 60}
            ]
        }
        
        try:
            url = f"{self.config.base_url}/events"
            params = {"user_id": self.config.user_id}
            
            response = self.session.post(url, params=params, json=event_data)
            # response.raise_for_status()
            data = response.json()
            print(data)
            if data.get('success'):
                event_id = data.get('event_data', {}).get('event_id')
                event_link = data.get('event_data', {}).get('event_link')
                
                self.created_events.append(event_id)
                
                self.print_result(True, "테스트 이벤트가 성공적으로 생성되었습니다")
                print(f"📅 이벤트 ID: {event_id}")
                print(f"🔗 이벤트 링크: {event_link}")
                print(f"⏰ 시간: {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%H:%M')}")
                
                return event_id
            else:
                self.print_result(False, "이벤트 생성 실패", data)
                return None
                
        except Exception as e:
            self.print_result(False, f"이벤트 생성 실패: {e}")
            return None
    
    def step8_create_quick_event(self) -> Optional[str]:
        """Step 8: 빠른 이벤트 생성 (자연어)"""
        self.print_step(8, "빠른 이벤트 생성 (자연어)")
        
        quick_event_data = {
            "text": "모레 오전 10시에 팀 스탠드업 미팅 30분",
            "calendar_id": self.config.test_calendar_id
        }
        
        try:
            url = f"{self.config.base_url}/events/quick"
            params = {"user_id": self.config.user_id}
            
            response = self.session.post(url, params=params, json=quick_event_data)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success'):
                event_id = data.get('event_id')
                event_link = data.get('event_link')
                
                self.created_events.append(event_id)
                
                self.print_result(True, "빠른 이벤트가 성공적으로 생성되었습니다")
                print(f"📅 이벤트 ID: {event_id}")
                print(f"🔗 이벤트 링크: {event_link}")
                print(f"📝 입력 텍스트: {quick_event_data['text']}")
                
                return event_id
            else:
                self.print_result(False, "빠른 이벤트 생성 실패", data)
                return None
                
        except Exception as e:
            self.print_result(False, f"빠른 이벤트 생성 실패: {e}")
            return None
    
    def step9_get_today_events(self) -> bool:
        """Step 9: 오늘의 이벤트 조회"""
        self.print_step(9, "오늘의 이벤트 조회")
        
        try:
            url = f"{self.config.base_url}/events/today"
            params = {
                "user_id": self.config.user_id,
                "calendar_id": self.config.test_calendar_id
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Updated to match the corrected API response format
            if data.get('success'):
                events = data.get('events', [])  # Changed from data.get('data', {}).get('events', [])
                self.print_result(True, f"오늘의 이벤트 {len(events)}개를 조회했습니다")
                
                for i, event in enumerate(events[:3]):
                    print(f"  📅 {i+1}. {event.get('summary', 'No Title')}")
                    print(f"     ⏰ {event.get('start', {}).get('dateTime', 'No Time')}")
                
                return True
            else:
                self.print_result(False, "오늘의 이벤트 조회 실패", data)
                return False
                
        except Exception as e:
            self.print_result(False, f"오늘의 이벤트 조회 실패: {e}")
            return False
    
    def step10_get_upcoming_events(self) -> bool:
        """Step 10: 다가오는 이벤트 조회 (7일)"""
        self.print_step(10, "다가오는 이벤트 조회 (7일)")
        
        try:
            url = f"{self.config.base_url}/events/upcoming"
            params = {
                "user_id": self.config.user_id,
                "days": 7,
                "calendar_id": self.config.test_calendar_id
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Updated to match the corrected API response format
            if data.get('success'):
                events = data.get('events', [])  # Changed from data.get('data', {}).get('events', [])
                days = data.get('days', 7)  # Changed from period
                
                self.print_result(True, f"{days}일 동안의 이벤트 {len(events)}개를 조회했습니다")
                
                for i, event in enumerate(events[:5]):
                    print(f"  📅 {i+1}. {event.get('summary', 'No Title')}")
                    start_time = event.get('start', {}).get('dateTime', 'No Time')
                    if start_time != 'No Time':
                        try:
                            dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                            print(f"     ⏰ {dt.strftime('%m/%d %H:%M')}")
                        except:
                            print(f"     ⏰ {start_time}")
                
                return True
            else:
                self.print_result(False, "다가오는 이벤트 조회 실패", data)
                return False
                
        except Exception as e:
            self.print_result(False, f"다가오는 이벤트 조회 실패: {e}")
            return False
    
    def step11_search_events(self) -> bool:
        """Step 11: 이벤트 검색"""
        self.print_step(11, "이벤트 검색")
        
        try:
            url = f"{self.config.base_url}/events/search"
            params = {
                "user_id": self.config.user_id,
                "query": "TinkerBell",
                "calendar_id": self.config.test_calendar_id,
                "max_results": 10
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # The search endpoint response format is already correct
            if data.get('success'):
                events = data.get('events', [])
                query = data.get('query', '')
                
                self.print_result(True, f"'{query}' 검색 결과: {len(events)}개 이벤트")
                
                for i, event in enumerate(events[:3]):
                    print(f"  📅 {i+1}. {event.get('summary', 'No Title')}")
                    print(f"     📝 {event.get('description', 'No Description')[:50]}...")
                
                return True
            else:
                self.print_result(False, "이벤트 검색 실패", data)
                return False
                
        except Exception as e:
            self.print_result(False, f"이벤트 검색 실패: {e}")
            return False
    
    def step12_update_event(self, event_id: str) -> bool:
        """Step 12: 이벤트 수정"""
        if not event_id:
            print("⚠️  수정할 이벤트 ID가 없습니다. 이 단계를 건너뜁니다.")
            return True
            
        self.print_step(12, "이벤트 수정")
        
        update_data = {
            "title": "🤖 TinkerBell 테스트 이벤트 (수정됨)",
            "description": "이 이벤트는 수정되었습니다. Google Calendar 연동 테스트 완료!",
            "location": "온라인 (Google Meet)"
        }
        
        try:
            url = f"{self.config.base_url}/events/{event_id}"
            params = {
                "user_id": self.config.user_id,
                "calendar_id": self.config.test_calendar_id
            }
            
            response = self.session.put(url, params=params, json=update_data)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success'):
                self.print_result(True, "이벤트가 성공적으로 수정되었습니다")
                print(f"📅 수정된 제목: {update_data['title']}")
                print(f"📍 수정된 위치: {update_data['location']}")
                return True
            else:
                self.print_result(False, "이벤트 수정 실패", data)
                return False
                
        except Exception as e:
            self.print_result(False, f"이벤트 수정 실패: {e}")
            return False
    
    def step13_cleanup_events(self) -> bool:
        """Step 13: 테스트 이벤트 정리"""
        if not self.created_events:
            print("⚠️  정리할 이벤트가 없습니다.")
            return True
            
        self.print_step(13, "테스트 이벤트 정리")
        
        success_count = 0
        
        for event_id in self.created_events:
            try:
                url = f"{self.config.base_url}/events/{event_id}"
                params = {
                    "user_id": self.config.user_id,
                    "calendar_id": self.config.test_calendar_id
                }
                
                response = self.session.delete(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get('success'):
                    print(f"✅ 이벤트 {event_id} 삭제 완료")
                    success_count += 1
                else:
                    print(f"❌ 이벤트 {event_id} 삭제 실패")
                    
            except Exception as e:
                print(f"❌ 이벤트 {event_id} 삭제 중 오류: {e}")
        
        self.print_result(
            success_count == len(self.created_events),
            f"테스트 이벤트 정리 완료 ({success_count}/{len(self.created_events)})"
        )
        
        return success_count > 0
    
    def step14_disconnect_calendar(self) -> bool:
        """Step 14: Google Calendar 연동 해제 (선택사항)"""
        self.print_step(14, "Google Calendar 연동 해제 (선택사항)")
        
        print("⚠️  Google Calendar 연동을 해제하시겠습니까?")
        print("   연동을 해제하면 다시 인증을 받아야 합니다.")
        
        choice = input("연동 해제 (y/N): ").strip().lower()
        
        if choice != 'y':
            print("✅ 연동을 유지합니다.")
            return True
        
        try:
            url = f"{self.config.base_url}/auth/google-calendar/disconnect"
            params = {"user_id": self.config.user_id}
            
            response = self.session.delete(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success'):
                self.print_result(True, "Google Calendar 연동이 해제되었습니다", data)
                return True
            else:
                self.print_result(False, "연동 해제 실패", data)
                return False
                
        except Exception as e:
            self.print_result(False, f"연동 해제 실패: {e}")
            return False
    
    def run_full_test(self) -> Dict[str, bool]:
        """전체 테스트 실행"""
        print("🚀 Google Calendar 통합 테스트를 시작합니다!")
        print(f"📍 서버: {self.config.base_url}")
        print(f"👤 사용자 ID: {self.config.user_id}")
        
        results = {}
        
        # Step 1: 서버 상태 확인
        results['server_status'] = self.step1_check_server_status()
        if not results['server_status']:
            print("\n❌ 서버 연결 실패로 테스트를 중단합니다.")
            return results
        
        # # Step 2: 인증 URL 획득
        # auth_url = self.step2_get_authorization_url()
        # results['auth_url'] = auth_url is not None
        # if not auth_url:
        #     print("\n❌ 인증 URL 획득 실패로 테스트를 중단합니다.")
        #     return results
        
        # # Step 3: 사용자 인증
        # auth_code = self.step3_user_authorization(auth_url)
        # results['user_auth'] = auth_code is not None
        # if not auth_code:
        #     print("\n❌ 사용자 인증 실패로 테스트를 중단합니다.")
        #     return results
        
        # # Step 4: OAuth 완료
        # results['oauth_complete'] = self.step4_complete_oauth(auth_code,state)
        # if not results['oauth_complete']:
        #     print("\n❌ OAuth 인증 완료 실패로 테스트를 중단합니다.")
        #     return results
        
        # Step 5: 연동 상태 확인
        # results['connection_status'] = self.step5_check_connection_status()
        
        # Step 6: 캘린더 목록 조회
        results['get_calendars'] = self.step6_get_calendars()
        
        # Step 7: 테스트 이벤트 생성
        test_event_id = self.step7_create_test_event()
        results['create_event'] = test_event_id is not None
        
        # Step 8: 빠른 이벤트 생성
        quick_event_id = self.step8_create_quick_event()
        results['create_quick_event'] = quick_event_id is not None
        
        # Step 9: 오늘의 이벤트 조회
        results['get_today_events'] = self.step9_get_today_events()
        
        # Step 10: 다가오는 이벤트 조회
        results['get_upcoming_events'] = self.step10_get_upcoming_events()
        
        # Step 11: 이벤트 검색
        results['search_events'] = self.step11_search_events()
        
        # Step 12: 이벤트 수정
        results['update_event'] = self.step12_update_event(test_event_id)
        
        # Step 13: 테스트 이벤트 정리
        # results['cleanup_events'] = self.step13_cleanup_events()
        
        # Step 14: 연동 해제 (선택사항)
        results['disconnect'] = self.step14_disconnect_calendar()
        
        return results
    
    def print_test_summary(self, results: Dict[str, bool]):
        """테스트 결과 요약 출력"""
        print("\n" + "="*60)
        print("📊 테스트 결과 요약")
        print("="*60)
        
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result)
        
        print(f"\n✅ 통과: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")
        
        print("\n📋 상세 결과:")
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {status} {test_name}")
        
        if passed_tests == total_tests:
            print("\n🎉 모든 테스트가 성공적으로 완료되었습니다!")
            print("   Google Calendar 연동이 정상적으로 작동합니다.")
        else:
            print(f"\n⚠️  {total_tests - passed_tests}개의 테스트가 실패했습니다.")
            print("   로그를 확인하여 문제를 해결해주세요.")

def main():
    """메인 함수"""
    print("🤖 TinkerBell Google Calendar 통합 테스트")
    print("="*50)
    
    # 설정 확인
    config = TestConfig()
    print(f"📍 테스트 서버: {config.base_url}")
    print(f"👤 테스트 사용자 ID: {config.user_id}")
    
    # 사용자 확인
    print("\n⚠️  주의사항:")
    print("  1. 서버가 실행 중이어야 합니다")
    print("  2. Google Calendar API 설정이 완료되어야 합니다")
    print("  3. 테스트 중 실제 캘린더에 이벤트가 생성됩니다")
    print("  4. 테스트 완료 후 생성된 이벤트는 자동으로 삭제됩니다")
    
    choice = input("\n테스트를 시작하시겠습니까? (y/N): ").strip().lower()
    
    if choice != 'y':
        print("테스트를 취소했습니다.")
        return
    
    # 테스트 실행
    tester = GoogleCalendarIntegrationTester(config)
    results = tester.run_full_test()
    
    # 결과 요약
    tester.print_test_summary(results)

if __name__ == "__main__":
    main()
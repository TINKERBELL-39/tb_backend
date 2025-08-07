"""
Customer Service Agent - 멀티턴 대화 사용 예제
마케팅 에이전트의 멀티턴 시스템을 참고한 예제
"""

import asyncio
import json
from customer_service_agent.core.customer_service_manager import CustomerServiceAgentManager

async def customer_service_multiturn_demo():
    """고객 서비스 멀티턴 대화 데모"""
    
    print("=== 고객 서비스 에이전트 멀티턴 대화 데모 ===\n")
    
    # 매니저 초기화
    manager = CustomerServiceAgentManager()
    
    # 사용자 정보
    user_id = 45
    conversation_id = 890  # 새 대화 시작
    
    # 대화 시나리오
    conversation_flow = [
        "안녕하세요, 고객 불만 처리에 대해 상담받고 싶습니다.",
        "온라인 쇼핑몰을 운영하고 있어요.",
        "최근에 배송 지연으로 인한 고객 불만이 많이 들어오고 있어서 고민입니다.",
        "주로 20-30대 직장인들이 고객이에요.",
        "고객들이 빠른 배송을 기대하는데 현실적으로 어려운 상황입니다.",
        "고객 불만을 줄이고 만족도를 높이고 싶어요.",
        "이 문제가 계속되면 매출에 영향을 줄 것 같아 꽤 시급한 상황이에요.",
        "현재 고객센터 직원 2명과 배송 업체 1곳을 이용하고 있습니다.",
        "이전에 할인 쿠폰을 드렸는데 근본적인 해결이 되지 않았어요.",
        "배송 관련 피드백이 대부분이고, 몇몇 고객은 아예 주문 취소까지 했습니다.",
        "주로 카카오톡 상담과 이메일로 고객과 소통하고 있어요.",
        "가능하면 이번 달 안에 개선 방안을 마련하고 싶습니다."
    ]
    
    print("📋 대화 시나리오:")
    for i, message in enumerate(conversation_flow, 1):
        print(f"{i}. {message}")
    print("\n" + "="*60 + "\n")
    
    # 멀티턴 대화 실행
    for step, user_message in enumerate(conversation_flow, 1):
        print(f"🗣️ [사용자 {step}]: {user_message}")
        
        try:
            # 매니저를 통한 쿼리 처리
            result = manager.process_user_query(
                user_input=user_message,
                user_id=user_id,
                conversation_id=conversation_id
            )
            
            # conversation_id 업데이트 (첫 번째 응답에서 받음)
            if conversation_id is None and result.get("conversation_id"):
                conversation_id = result["conversation_id"]
                print(f"📞 새 대화 세션 생성: {conversation_id}")
            
            # 응답 출력
            print(f"🤖 [에이전트]: {result.get('answer', '응답을 받지 못했습니다.')}")
            
            # 대화 상태 정보 출력
            if conversation_id in manager.conversation_states:
                state = manager.conversation_states[conversation_id]
                print(f"📊 [상태] 단계: {state.stage.value}, 완료율: {state.get_completion_rate():.1%}")
            
            print("-" * 60)
            
            # 단계 전환 시 잠시 대기
            if step in [1, 6, 12]:
                print("⏱️ 잠시 대기 중...\n")
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            break
    
    # 최종 대화 상태 출력
    if conversation_id and conversation_id in manager.conversation_states:
        final_state = manager.conversation_states[conversation_id]
        print("\n" + "="*60)
        print("📋 최종 대화 상태:")
        print(f"- 현재 단계: {final_state.stage.value}")
        print(f"- 정보 완료율: {final_state.get_completion_rate():.1%}")
        print(f"- 수집된 정보 개수: {len([v for v in final_state.collected_info.values() if v])}")
        print(f"- 분석 완료: {'예' if final_state.analysis_results.get('primary_topics') else '아니오'}")
        
        print("\n📝 수집된 핵심 정보:")
        for key, value in final_state.collected_info.items():
            if value:
                print(f"- {key}: {value}")

async def template_request_demo():
    """템플릿 요청 데모"""
    print("\n=== 고객 메시지 템플릿 요청 데모 ===\n")
    
    manager = CustomerServiceAgentManager()
    
    template_queries = [
        "생일 축하 메시지 템플릿을 보여주세요",
        "VIP 고객에게 보낼 맞춤 메시지가 필요해요",
        "재구매 유도 메시지를 작성하고 싶습니다",
        "리뷰 요청 메시지 템플릿이 있나요?"
    ]
    
    for i, query in enumerate(template_queries, 1):
        print(f"🗣️ [질문 {i}]: {query}")
        
        result = manager.process_user_query(
            user_input=query,
            user_id=3000 + i,
            conversation_id=None
        )
        
        print(f"🤖 [응답]: {result.get('answer', '응답 없음')[:300]}...")
        print("-" * 60)

async def single_query_demo():
    """단일 쿼리 데모"""
    print("\n=== 단일 쿼리 데모 ===\n")
    
    manager = CustomerServiceAgentManager()
    
    test_queries = [
        "고객 불만을 효과적으로 처리하는 방법을 알려주세요",
        "고객 만족도를 높이려면 어떻게 해야 하나요?",
        "고객 세분화는 어떻게 하는 것이 좋을까요?"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"🗣️ [질문 {i}]: {query}")
        
        result = manager.process_user_query(
            user_input=query,
            user_id=4000 + i,
            conversation_id=None
        )
        
        print(f"🤖 [응답]: {result.get('answer', '응답 없음')[:200]}...")
        print("-" * 60)

if __name__ == "__main__":
    print("Customer Service Agent - 멀티턴 대화 테스트")
    print("공통 모듈과 마케팅 에이전트 구조 기반")
    print("="*60)
    
    # 멀티턴 대화 데모 실행
    asyncio.run(customer_service_multiturn_demo())
    
    # 템플릿 요청 데모 실행
    asyncio.run(template_request_demo())
    
    # 단일 쿼리 데모 실행
    asyncio.run(single_query_demo())
    
    print("\n✅ 모든 테스트 완료!")

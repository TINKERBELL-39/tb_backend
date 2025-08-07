"""
Mental Health Agent - 멀티턴 대화 사용 예제
마케팅 에이전트의 멀티턴 시스템을 참고한 예제
"""

import asyncio
import json
from mental_agent.core.mental_health_manager import MentalHealthAgentManager

async def mental_health_multiturn_demo():
    """정신건강 멀티턴 대화 데모"""
    
    print("=== 정신건강 에이전트 멀티턴 대화 데모 ===\n")
    
    # 매니저 초기화
    manager = MentalHealthAgentManager()
    
    # 사용자 정보
    user_id = 6
    conversation_id = 745  # 새 대화 시작
    
    # 대화 시나리오 - 일반적인 우울 상담 사례
    conversation_flow = [
        "안녕하세요, 요즘 마음이 많이 힘들어요.",
        "최근에 우울한 기분이 계속되고 있어서 걱정이에요.",
        "아침에 일어나기 힘들고, 평소 좋아하던 일들에도 관심이 없어져요.",
        "2-3주 정도 이런 상태가 계속되고 있어요.",
        "직장에서 스트레스를 많이 받고, 혼자 사는 것도 외로운 것 같아요.",
        "예전에는 친구들과 만나거나 운동을 했는데 요즘은 그럴 에너지가 없어요.",
        "가족이나 친구들이 있긴 하지만 이런 얘기를 하기가 어려워요.",
        "병원에 가본 적은 없고, 혼자 해결하려고 했는데 잘 안되네요.",
        "설문을 해보고 싶어요.",  # PHQ-9 설문 요청
        "1",  # PHQ-9 1번 문항 응답
        "2",  # PHQ-9 2번 문항 응답  
        "2",  # PHQ-9 3번 문항 응답
        "3",  # PHQ-9 4번 문항 응답
        "1",  # PHQ-9 5번 문항 응답
        "2",  # PHQ-9 6번 문항 응답
        "2",  # PHQ-9 7번 문항 응답
        "1",  # PHQ-9 8번 문항 응답
        "0",  # PHQ-9 9번 문항 응답 (자살사고 없음)
        "결과를 보니 중등도 우울이라고 나오네요. 어떻게 해야 할까요?",
        "전문가 상담을 받아보는 것을 고려해보겠습니다. 감사합니다."
    ]
    
    print("📋 대화 시나리오:")
    for i, message in enumerate(conversation_flow, 1):
        if message.isdigit() and len(message) == 1:
            print(f"{i}. [PHQ-9 응답] {message}")
        else:
            print(f"{i}. {message}")
    print("\n" + "="*60 + "\n")
    
    # 멀티턴 대화 실행
    for step, user_message in enumerate(conversation_flow, 1):
        if user_message.isdigit() and len(user_message) == 1:
            print(f"📝 [PHQ-9 응답 {step}]: {user_message}")
        else:
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
            print(f"🤖 [상담사]: {result.get('data').get('answer')}")
            
            # 대화 상태 정보 출력
            if conversation_id in manager.conversation_states:
                state = manager.conversation_states[conversation_id]
                status_info = f"📊 [상태] 단계: {state.stage.value}"
                
                if state.assessment_results.get("risk_level"):
                    status_info += f", 위험도: {state.assessment_results['risk_level']}"
                
                if state.phq9_state["is_active"]:
                    status_info += f", PHQ-9: {len(state.phq9_state['responses'])}/9"
                elif state.phq9_state["completed"]:
                    status_info += f", PHQ-9 완료: {state.phq9_state.get('score', 0)}점"
                
                print(status_info)
            
            print("-" * 60)
            
            # 단계 전환 시 잠시 대기
            if step in [1, 8, 18, 20]:
                print("⏱️ 잠시 대기 중...\n")
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            break
    
    # 최종 대화 상태 출력
    if conversation_id and conversation_id in manager.conversation_states:
        final_state = manager.conversation_states[conversation_id]
        print("\n" + "="*60)
        print("📋 최종 상담 상태:")
        print(f"- 현재 단계: {final_state.stage.value}")
        print(f"- 위험 수준: {final_state.assessment_results.get('risk_level', 'low')}")
        print(f"- 자살 위험: {'있음' if final_state.assessment_results.get('suicide_risk', False) else '없음'}")
        print(f"- PHQ-9 점수: {final_state.phq9_state.get('score', '미완료')}")
        print(f"- 상담 세션 수: {len(final_state.counseling_sessions)}")
        print(f"- 안전 계획 수: {len(final_state.safety_plans)}")
        
        if final_state.phq9_state["completed"]:
            interpretation = final_state.phq9_state["interpretation"]
            print(f"\n📝 PHQ-9 결과:")
            print(f"- 총점: {interpretation.get('total_score', 0)}점")
            print(f"- 평가: {interpretation.get('severity', '')}")
            print(f"- 권장사항: {interpretation.get('recommendation', '')}")

async def crisis_situation_demo():
    """위기 상황 대응 데모"""
    print("\n=== 위기 상황 대응 데모 ===\n")
    
    manager = MentalHealthAgentManager()
    
    crisis_scenarios = [
        "죽고 싶은 생각이 들어요",
        "더 이상 못살겠어요. 모든 게 힘들어요",
        "자해를 하고 싶은 충동이 있어요"
    ]
    
    for i, scenario in enumerate(crisis_scenarios, 1):
        print(f"🚨 [위기 상황 {i}]: {scenario}")
        
        result = manager.process_user_query(
            user_input=scenario,
            user_id=4000 + i,
            conversation_id=None
        )
        
        print(f"🤖 [위기 상담사]: {result.get('answer', '응답 없음')[:300]}...")
        
        # 위기 상황 상태 확인
        conversation_id = result.get("conversation_id")
        if conversation_id and conversation_id in manager.conversation_states:
            state = manager.conversation_states[conversation_id]
            print(f"⚠️ [위기 상태] 즉시 개입 필요: {state.assessment_results.get('immediate_intervention_needed', False)}")
        
        print("-" * 60)

async def phq9_standalone_demo():
    """PHQ-9 독립 설문 데모"""
    print("\n=== PHQ-9 설문 독립 실행 데모 ===\n")
    
    from mental_agent.utils.mental_health_utils import calculate_phq9_score, PHQ9_QUESTIONS
    
    # 예시 응답 (중등도 우울 수준)
    sample_responses = [2, 2, 1, 3, 1, 2, 2, 1, 0]
    
    print("📋 PHQ-9 설문 문항과 응답:")
    for i, (question, response) in enumerate(zip(PHQ9_QUESTIONS, sample_responses)):
        response_text = ["전혀 그렇지 않다", "며칠 정도 그렇다", "일주일 이상 그렇다", "거의 매일 그렇다"][response]
        print(f"{i+1}. {question}")
        print(f"   응답: {response} ({response_text})")
        print()
    
    # 점수 계산
    result = calculate_phq9_score(sample_responses)
    
    print("📊 PHQ-9 결과:")
    print(f"- 총점: {result.get('total_score', 0)}점")
    print(f"- 평가: {result.get('severity', '')}")
    print(f"- 자살 위험: {'있음' if result.get('suicide_risk', False) else '없음'}")
    print(f"- 권장사항: {result.get('recommendation', '')}")
    print(f"\n{result.get('interpretation', '')}")

async def emotional_analysis_demo():
    """감정 분석 데모"""
    print("\n=== 감정 분석 데모 ===\n")
    
    from mental_agent.utils.mental_health_utils import analyze_emotional_state, detect_crisis_indicators
    
    test_texts = [
        "요즘 너무 슬프고 우울해요. 아무것도 하기 싫어요.",
        "불안하고 걱정이 많아서 밤에 잠을 못 자요.",
        "화가 나고 짜증이 계속 나요. 모든 게 다 싫어요.",
        "희망이 없는 것 같아요. 모든 게 의미없어 보여요.",
        "오늘은 기분이 좋아요. 날씨도 좋고 친구들도 만나요."
    ]
    
    for i, text in enumerate(test_texts, 1):
        print(f"💭 [텍스트 {i}]: {text}")
        
        # 감정 분석
        emotion_result = analyze_emotional_state(text)
        print(f"😊 [감정]: {emotion_result.get('primary_emotion', 'neutral')}")
        print(f"📊 [위험도]: {emotion_result.get('risk_level', 'low')}")
        
        # 위기 지표 감지
        crisis_result = detect_crisis_indicators(text)
        print(f"🚨 [위기 수준]: {crisis_result.get('crisis_level', 'none')}")
        
        if emotion_result.get('detected_emotions'):
            print(f"🔍 [감지된 감정들]: {list(emotion_result['detected_emotions'].keys())}")
        
        print("-" * 40)

if __name__ == "__main__":
    print("Mental Health Agent - 멀티턴 대화 테스트")
    print("공통 모듈과 마케팅 에이전트 구조 기반")
    print("="*60)
    
    # 멀티턴 대화 데모 실행
    asyncio.run(mental_health_multiturn_demo())
    
    # 위기 상황 데모 실행
    asyncio.run(crisis_situation_demo())
    
    # PHQ-9 독립 실행 데모
    asyncio.run(phq9_standalone_demo())
    
    # 감정 분석 데모 실행
    asyncio.run(emotional_analysis_demo())
    
    print("\n✅ 모든 테스트 완료!")
    print("\n⚠️ 주의: 이는 데모용 시스템입니다. 실제 정신건강 문제가 있으시면 전문가와 상담하세요.")
    print("📞 응급상황: 119, 생명의전화: 1393")

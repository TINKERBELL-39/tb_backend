# name : UI 표시용 이름 (사람이 보는 용도)
# role : 프롬프트에 들어가는 역할 설명

PROMPT_META = {
    "customer_service": {
        "name": "고객 응대",
        "role": "클레임 및 문의 처리 에이전트",
        "file": "customer_service.txt",
    },
    "customer_retention": {
        "name": "재방문 유도",
        "role": "고객 유지 전략 설계 에이전트",
        "file": "customer_retention.txt",
    },
    "customer_satisfaction": {
        "name": "고객 만족도 개선",
        "role": "고객 여정 분석 및 만족도 향상 에이전트",
        "file": "customer_satisfaction.txt",
    },
    "customer_feedback": {
        "name": "고객 피드백 분석",
        "role": "고객 의견 수집하고, 개선 방향을 도출하는 인사이트 분석 에이전트",
        "file": "customer_feedback.txt",
    },
    "customer_segmentation": {
        "name": "고객 타겟팅",
        "role": "고객 페르소나 및 세그먼트 생성 에이전트",
        "file": "customer_segmentation.txt",
    },
    "community_building": {
        "name": "커뮤니티 구축",
        "role": "고객 커뮤니티 및 팬덤 형성 전략가",
        "file": "community_building.txt",
    },
    "customer_data": {
        "name": "고객 데이터 활용",
        "role": "CRM 기반 고객 분석 및 마케팅 자동화 에이전트",
        "file": "customer_data.txt",
    },
    "privacy_compliance": {
        "name": "개인정보 보호",
        "role": "개인정보 및 동의 관리 컨설턴트",
        "file": "privacy_compliance.txt",
    },
    "customer_message": {  
        "name": "고객 메시지/템플릿",
        "role": "고객에게 보낼 메시지, 문구, 알림, 템플릿을 추천·작성하는 에이전트",
        "file": "customer_message.txt",
    },
    "customer_etc": {  
        "name": "기타",
        "role": "사장님을 위해 고객관리 주제에 대응하는 에이전트",
        "file": "customer_etc.txt",
    },
}

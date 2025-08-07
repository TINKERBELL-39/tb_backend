"""마케팅 자동화 패키지 초기화"""

__version__ = "1.0.0"
__author__ = "Marketing Automation Team"
__description__ = "네이버 블로그 검색 키워드 통계 기반 컨텐츠 제작 및 인스타그램 포스팅 자동화"

# 패키지 레벨에서 사용할 수 있는 주요 클래스들
__all__ = [
    "BlogAutomationConfig",
    "InstagramAutomationConfig", 
    "KeywordData",
    "HashtagData",
    "GeneratedContent",
    "BlogPost",
    "InstagramPost",
    "NaverBlogAutomation",
    "InstagramAutomation", 
    "KeywordAnalyzer",
    "DatabaseManager",
    "AutomationScheduler",
    "setup_logger"
]

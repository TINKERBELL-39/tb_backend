"""
마케팅 자동화 API용 Pydantic 모델 정의
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

class PlatformType(str, Enum):
    """플랫폼 타입"""
    NAVER_BLOG = "naver_blog"
    INSTAGRAM = "instagram"
    TISTORY = "tistory"
    MEDIUM = "medium"

class ScheduleFrequency(str, Enum):
    """스케줄 빈도"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

class PostStatus(str, Enum):
    """포스트 상태"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"

class AutomationStatus(str, Enum):
    """자동화 상태"""
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"

# ============= 스케줄 모델 =============

class Schedule(BaseModel):
    """스케줄 설정"""
    frequency: ScheduleFrequency
    time: str = Field(..., description="실행 시간 (HH:MM 형식)")
    days: Optional[List[str]] = Field(None, description="요일 (weekly일 때)")
    custom_cron: Optional[str] = Field(None, description="커스텀 크론 표현식")
    
    @validator('time')
    def validate_time(cls, v):
        try:
            datetime.strptime(v, '%H:%M')
            return v
        except ValueError:
            raise ValueError('시간은 HH:MM 형식이어야 합니다')

# ============= 블로그 자동화 모델 =============

class BlogAutomationConfig(BaseModel):
    """블로그 자동화 설정"""
    enabled: bool = False
    keywords: List[str] = Field(..., min_items=1, description="추적할 키워드 목록")
    schedule: Schedule
    template: Optional[str] = Field(None, description="컨텐츠 템플릿")
    auto_publish: bool = False
    target_platform: PlatformType = PlatformType.NAVER_BLOG
    blog_id: Optional[str] = Field(None, description="블로그 ID")
    category: Optional[str] = Field(None, description="블로그 카테고리")
    tags: Optional[List[str]] = Field(None, description="기본 태그")
    
    @validator('keywords')
    def validate_keywords(cls, v):
        if len(v) > 20:
            raise ValueError('키워드는 최대 20개까지만 설정할 수 있습니다')
        return v

class BlogPost(BaseModel):
    """블로그 포스트"""
    id: Optional[str] = None
    keyword: str
    title: str
    content: str
    excerpt: Optional[str] = None
    tags: Optional[List[str]] = None
    platform: PlatformType
    status: PostStatus = PostStatus.DRAFT
    seo_score: Optional[int] = None
    word_count: Optional[int] = None
    reading_time: Optional[int] = None
    url: Optional[str] = None
    views: Optional[int] = 0
    engagement: Optional[float] = 0.0
    created_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# ============= 인스타그램 자동화 모델 =============

class InstagramAutomationConfig(BaseModel):
    """인스타그램 자동화 설정"""
    enabled: bool = False
    hashtags: List[str] = Field(..., min_items=1, description="해시태그 목록")
    schedule: Schedule
    templates: Optional[List[str]] = Field(None, description="컨텐츠 템플릿 목록")
    auto_post: bool = False
    image_folder: Optional[str] = Field(None, description="이미지 폴더 경로")
    image_style: Optional[str] = Field("modern", description="이미지 스타일")
    account_id: Optional[str] = Field(None, description="연결된 인스타그램 계정 ID")
    max_hashtags: int = Field(30, description="최대 해시태그 수")
    
    @validator('hashtags')
    def validate_hashtags(cls, v):
        if len(v) > 30:
            raise ValueError('해시태그는 최대 30개까지만 설정할 수 있습니다')
        # # 제거 및 추가
        cleaned_hashtags = []
        for hashtag in v:
            if not hashtag.startswith('#'):
                hashtag = '#' + hashtag
            cleaned_hashtags.append(hashtag)
        return cleaned_hashtags

class InstagramPost(BaseModel):
    """인스타그램 포스트"""
    id: Optional[str] = None
    caption: str
    hashtags: List[str]
    image_url: Optional[str] = None
    image_path: Optional[str] = None
    status: PostStatus = PostStatus.DRAFT
    post_url: Optional[str] = None
    likes: Optional[int] = 0
    comments: Optional[int] = 0
    shares: Optional[int] = 0
    reach: Optional[int] = 0
    engagement_rate: Optional[float] = 0.0
    scheduled_for: Optional[datetime] = None
    created_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# ============= 키워드 분석 모델 =============

class KeywordAnalysisRequest(BaseModel):
    """키워드 분석 요청"""
    user_id: int
    keyword: str
    platform: PlatformType
    include_trends: bool = True
    include_related: bool = True

class KeywordAnalysisResponse(BaseModel):
    """키워드 분석 응답"""
    success: bool
    data: Optional[Dict[str, Any]] = None

class KeywordData(BaseModel):
    """키워드 분석 데이터"""
    keyword: str
    search_volume: Optional[int] = None
    competition: Optional[str] = None  # low, medium, high
    trend_score: Optional[int] = None
    difficulty: Optional[int] = None
    cpc: Optional[float] = None
    related_keywords: Optional[List[str]] = None
    monthly_trends: Optional[List[Dict[str, Any]]] = None
    suggestions: Optional[List[str]] = None
    last_analyzed: Optional[datetime] = None

class HashtagData(BaseModel):
    """해시태그 분석 데이터"""
    hashtag: str
    post_count: Optional[int] = None
    avg_likes: Optional[int] = None
    avg_comments: Optional[int] = None
    engagement_rate: Optional[float] = None
    difficulty: Optional[str] = None  # low, medium, high
    related_hashtags: Optional[List[str]] = None
    trending: Optional[bool] = False
    last_analyzed: Optional[datetime] = None

# ============= 컨텐츠 생성 모델 =============

class ContentGenerationRequest(BaseModel):
    """컨텐츠 생성 요청"""
    keyword: Optional[str] = None
    hashtags: Optional[List[str]] = None
    template: Optional[str] = None
    platform: PlatformType
    auto_upload: bool = False
    auto_post: bool = False
    image_style: Optional[str] = "modern"
    blog_config: Optional[Dict[str, Any]] = None
    instagram_config: Optional[Dict[str, Any]] = None

class GeneratedContent(BaseModel):
    """생성된 컨텐츠"""
    title: Optional[str] = None
    content: str
    hashtags: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    image_url: Optional[str] = None
    seo_analysis: Optional[Dict[str, Any]] = None
    word_count: Optional[int] = None
    reading_time: Optional[int] = None
    generated_at: datetime = Field(default_factory=datetime.now)

# ============= 상태 및 통계 모델 =============

class AutomationStatusInfo(BaseModel):
    """자동화 상태 정보"""
    platform: PlatformType
    status: AutomationStatus
    enabled: bool
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    total_posts: int = 0
    success_count: int = 0
    error_count: int = 0
    success_rate: float = 0.0
    active_keywords: Optional[int] = None
    active_hashtags: Optional[int] = None

class AnalyticsData(BaseModel):
    """분석 데이터"""
    platform: PlatformType
    date_range: Dict[str, datetime]
    total_posts: int
    total_views: int
    total_engagement: int
    avg_engagement_rate: float
    top_keywords: Optional[List[Dict[str, Any]]] = None
    top_hashtags: Optional[List[Dict[str, Any]]] = None
    daily_stats: Optional[List[Dict[str, Any]]] = None
    performance_trends: Optional[List[Dict[str, Any]]] = None

# ============= 스케줄러 모델 =============

class ScheduledJob(BaseModel):
    """예약된 작업"""
    id: str
    name: str
    platform: PlatformType
    schedule: Schedule
    status: AutomationStatus
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    config: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

# ============= API 응답 모델 =============

class APIResponse(BaseModel):
    """API 응답"""
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class KeywordAnalysisResponse(BaseModel):
    """키워드 분석 응답"""
    success: bool
    data: Optional[Dict[str, Any]] = None

class BlogContentResponse(BaseModel):
    """블로그 컨텐츠 응답"""
    success: bool
    data: Optional[Dict[str, Any]] = None

class BlogPublishRequest(BaseModel):
    """블로그 발행 요청"""
    content_id: str
    blog_config: Optional[Dict[str, Any]] = None

class BlogPublishResponse(BaseModel):
    """블로그 발행 응답"""
    success: bool
    message: Optional[str] = None

class PaginatedResponse(BaseModel):
    """페이지네이션 응답"""
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int

# ============= 설정 모델 =============

class DatabaseConfig(BaseModel):
    """데이터베이스 설정"""
    host: str = "localhost"
    port: int = 5432
    database: str = "marketing_automation"
    username: str
    password: str
    pool_size: int = 10
    max_overflow: int = 20

class APIConfig(BaseModel):
    """API 설정"""
    naver_client_id: Optional[str] = None
    naver_client_secret: Optional[str] = None
    instagram_access_token: Optional[str] = None
    openai_api_key: Optional[str] = None
    claude_api_key: Optional[str] = None

class AppConfig(BaseModel):
    """애플리케이션 설정"""
    debug: bool = False
    log_level: str = "INFO"
    cors_origins: List[str] = ["*"]
    max_content_length: int = 10000
    max_keywords_per_config: int = 20
    max_hashtags_per_config: int = 30
    database: DatabaseConfig
    api: APIConfig

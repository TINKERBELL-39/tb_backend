"""
네이버 블로그 검색 키워드 통계 기반 컨텐츠 제작 및 업로드 자동화
"""

import asyncio
import aiohttp
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
import openai
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from ..models.schemas import (
    BlogAutomationConfig, 
    BlogPost, 
    KeywordData, 
    GeneratedContent,
    PostStatus,
    AutomationStatus
)
from .keyword import NaverKeywordRecommender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NaverBlogAutomation:
    """네이버 블로그 자동화 클래스"""
    
    def __init__(self):
        self.naver_client_id = None
        self.naver_client_secret = None
        self.openai_client = None
        self.driver = None
        self.automation_config = None
        self.is_running = False
    
    async def setup_automation(self, config: BlogAutomationConfig) -> Dict[str, Any]:
        """블로그 자동화 설정"""
        try:
            self.automation_config = config
            
            # 네이버 API 키 설정 확인
            if not self.naver_client_id or not self.naver_client_secret:
                logger.warning("네이버 API 키가 설정되지 않았습니다.")
            
            # OpenAI 클라이언트 초기화
            if not self.openai_client:
                logger.warning("OpenAI API 키가 설정되지 않았습니다.")
            
            # 웹드라이버 초기화 (헤드리스 모드)
            await self._setup_webdriver()
            
            result = {
                "config_id": f"blog_config_{int(datetime.now().timestamp())}",
                "enabled": config.enabled,
                "keywords": config.keywords,
                "schedule": config.schedule.dict(),
                "auto_publish": config.auto_publish,
                "target_platform": config.target_platform,
                "setup_at": datetime.now().isoformat()
            }
            
            logger.info(f"블로그 자동화 설정 완료: {len(config.keywords)}개 키워드")
            return result
            
        except Exception as e:
            logger.error(f"블로그 자동화 설정 실패: {str(e)}")
            raise e
    
    async def _setup_webdriver(self):
        """웹드라이버 설정"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            # 브라우저 드라이버 초기화 (실제 환경에서는 ChromeDriver 경로 설정 필요)
            # self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("웹드라이버 설정 완료")
            
        except Exception as e:
            logger.error(f"웹드라이버 설정 실패: {str(e)}")
            raise e
    
    async def upload_to_naver_blog(self, content: GeneratedContent, blog_config: Dict[str, Any]) -> Dict[str, Any]:
        """네이버 블로그에 컨텐츠 업로드"""
        try:
            # 실제 구현에서는 네이버 블로그 API 또는 셀레니움 사용
            # 현재는 모의 업로드
            
            blog_id = blog_config.get("blog_id")
            category = blog_config.get("category", "일반")
            
            if not blog_id:
                raise ValueError("블로그 ID가 설정되지 않았습니다.")
            
            # 실제 업로드 로직 (셀레니움 예시)
            upload_result = await self._upload_with_selenium(content, blog_config)
            
            result = {
                "post_id": f"post_{int(datetime.now().timestamp())}",
                "blog_id": blog_id,
                "title": content.title,
                "url": f"https://blog.naver.com/{blog_id}/post_id",
                "status": "published",
                "published_at": datetime.now().isoformat(),
                "category": category,
                "tags": content.tags
            }
            
            logger.info(f"네이버 블로그 업로드 완료: {content.title}")
            return result
            
        except Exception as e:
            logger.error(f"네이버 블로그 업로드 실패: {str(e)}")
            raise e
    
    async def _upload_with_selenium(self, content: GeneratedContent, blog_config: Dict[str, Any]) -> Dict[str, Any]:
        """셀레니움을 사용한 블로그 업로드"""
        try:
            if not self.driver:
                await self._setup_webdriver()
            
            # 네이버 블로그 로그인 및 포스트 작성 로직
            # 실제 구현시에는 보안을 위해 더 안전한 방법 사용
            
            # 모의 업로드 결과
            return {
                "upload_method": "selenium",
                "success": True,
                "upload_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"셀레니움 업로드 실패: {str(e)}")
            raise e
    
    async def get_status(self) -> Dict[str, Any]:
        """블로그 자동화 상태 조회"""
        try:
            # 데이터베이스에서 상태 정보 조회 (실제 구현시)
            status = {
                "enabled": self.automation_config.enabled if self.automation_config else False,
                "is_running": self.is_running,
                "total_posts": 47,  # 모의 데이터
                "active_keywords": len(self.automation_config.keywords) if self.automation_config else 0,
                "last_generated": "2024-01-15T09:00:00Z",
                "next_run": "2024-01-16T09:00:00Z",
                "success_rate": 87.5,
                "error_count": 2,
                "last_error": None
            }
            
            return status
            
        except Exception as e:
            logger.error(f"상태 조회 실패: {str(e)}")
            return {"error": str(e)}
    
    async def get_posts(
        self, 
        page: int = 1, 
        limit: int = 10, 
        keyword: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """생성된 블로그 포스트 목록 조회"""
        try:
            # 데이터베이스에서 포스트 조회 (실제 구현시)
            # 현재는 모의 데이터
            
            posts = []
            for i in range(limit):
                post = {
                    "id": f"post_{i+1}",
                    "keyword": keyword or f"키워드{i+1}",
                    "title": f"{keyword or '키워드'}에 대한 완벽 가이드 {i+1}",
                    "status": status or "published",
                    "word_count": 1200 + i*50,
                    "seo_score": 80 + i*2,
                    "views": 1000 - i*50,
                    "engagement": 7.5 - i*0.1,
                    "created_at": (datetime.now() - timedelta(days=i)).isoformat(),
                    "published_at": (datetime.now() - timedelta(days=i)).isoformat()
                }
                posts.append(post)
            
            return {
                "posts": posts,
                "pagination": {
                    "current_page": page,
                    "total_pages": 5,
                    "total_items": 47,
                    "items_per_page": limit
                }
            }
            
        except Exception as e:
            logger.error(f"포스트 조회 실패: {str(e)}")
            return {"error": str(e)}
    
 
    async def start_automation(self):
        """자동화 시작"""
        self.is_running = True
        logger.info("블로그 자동화 시작")
    
    async def stop_automation(self):
        """자동화 중지"""
        self.is_running = False
        if self.driver:
            self.driver.quit()
        logger.info("블로그 자동화 중지")
    
    def __del__(self):
        """소멸자"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

    async def analyze_naver_keyword(self, keyword: str) -> Dict[str, Any]:
        """네이버 키워드 분석"""
        try:
            config = {
                'datalab': {
                    'client_id': self.naver_client_id,
                    'client_secret': self.naver_client_secret
                },
                'search_ad': {
                    'api_key': 'YOUR_SEARCH_AD_API_KEY',  # 실제 구현시 환경변수에서 로드
                    'secret_key': 'YOUR_SEARCH_AD_SECRET_KEY',
                    'customer_id': 'YOUR_CUSTOMER_ID'
                }
            }
            
            recommender = NaverKeywordRecommender(config)
            filters = {
                'search_volume_range': {'min': 1000, 'max': 100000},
                'category': 'IT'
            }
            
            result = recommender.recommend_keywords(keyword, filters)
            return result
            
        except Exception as e:
            logger.error(f"키워드 분석 실패: {str(e)}")
            raise e
    
    async def generate_content(self, keyword: str, keyword_data: Dict[str, Any], template: Optional[str] = None) -> GeneratedContent:
        """컨텐츠 생성"""
        try:
            if not self.openai_client:
                raise ValueError("OpenAI API 키가 설정되지 않았습니다.")
            
            # 키워드 데이터 기반 프롬프트 생성
            prompt = self._generate_content_prompt(keyword, keyword_data, template)
            
            # OpenAI API를 사용하여 컨텐츠 생성
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "당신은 전문적인 블로그 컨텐츠 작성자입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            
            # 컨텐츠 구조화
            structured_content = self._structure_content(content, keyword)
            
            return GeneratedContent(
                title=structured_content['title'],
                content=structured_content['content'],
                tags=structured_content['tags'],
                keyword=keyword,
                metadata={
                    'word_count': len(content.split()),
                    'generated_at': datetime.now().isoformat(),
                    'keyword_data': keyword_data
                }
            )
            
        except Exception as e:
            logger.error(f"컨텐츠 생성 실패: {str(e)}")
            raise e
    
    def _generate_content_prompt(self, keyword: str, keyword_data: Dict[str, Any], template: Optional[str] = None) -> str:
        """컨텐츠 생성을 위한 프롬프트 생성"""
        base_prompt = f"""
        다음 키워드에 대한 블로그 포스트를 작성해주세요: {keyword}
        
        키워드 정보:
        - 월간 검색량: {keyword_data.get('monthly_search_volume', 'N/A')}
        - 경쟁강도: {keyword_data.get('competition', 'N/A')}
        - 주 타겟층: {self._format_demographics(keyword_data.get('demographics', {}))}
        
        요구사항:
        1. SEO 최적화된 제목
        2. 명확한 개요와 구조
        3. 실용적인 정보와 예시 포함
        4. 독자 참여를 유도하는 결론
        5. 관련 키워드 자연스럽게 포함
        
        포맷:
        - 제목
        - 본문 (최소 1000단어)
        - 태그 (최소 5개)
        """
        
        if template:
            base_prompt += f"\n\n템플릿 요구사항:\n{template}"
        
        return base_prompt
    
    def _structure_content(self, raw_content: str, keyword: str) -> Dict[str, Any]:
        """생성된 컨텐츠 구조화"""
        lines = raw_content.split('\n')
        title = next((line for line in lines if line.strip()), f"{keyword} 완벽 가이드")
        
        # 태그 추출 또는 생성
        tags = self._extract_tags(raw_content, keyword)
        
        return {
            'title': title,
            'content': raw_content,
            'tags': tags
        }
    
    def _format_demographics(self, demographics: Dict[str, Any]) -> str:
        """인구통계 정보 포맷팅"""
        if not demographics:
            return "전체"
            
        age_dist = demographics.get('age_distribution', {})
        main_age = max(age_dist.items(), key=lambda x: x[1])[0] if age_dist else 'N/A'
        
        gender_ratio = demographics.get('female_ratio', 50)
        main_gender = '여성' if gender_ratio > 50 else '남성' if gender_ratio < 50 else '남녀 모두'
        
        return f"{main_age} {main_gender}"
    
    def _extract_tags(self, content: str, main_keyword: str) -> List[str]:
        """컨텐츠에서 태그 추출"""
        tags = [main_keyword]
        
        # 주요 키워드 추출 (실제 구현시 더 정교한 알고리즘 사용)
        words = re.findall(r'\b\w+\b', content.lower())
        word_freq = {}
        for word in words:
            if len(word) > 1:  # 1글자 단어 제외
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # 빈도수 기반 상위 태그 추출
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        for word, _ in sorted_words[:10]:
            if word not in tags and len(tags) < 10:
                tags.append(word)
        
        return tags

    def __del__(self):
        """소멸자"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

"""
마케팅 분석 도구 모듈
네이버 트렌드 분석, 인스타그램 해시태그 분석 등 MCP 기반 마케팅 도구
"""

import os
import json
import base64
import asyncio
import mcp
from mcp.client.streamable_http import streamablehttp_client
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
from collections import Counter

logger = logging.getLogger(__name__)

class MarketingAnalysisTools:
    """마케팅 분석 도구 클래스"""
    
    def __init__(self):
        """분석 도구 초기화"""
        self.smithery_api_key = "056f88d0-aa2e-4ea9-8f2d-382ba74dcb07"
        self.profile = "realistic-possum-fgq4Y7"
        self.config = self._get_config()
    
    def _get_config(self) -> Dict[str, str]:
        """환경 설정 로드"""
        try:
            from shared_modules import get_config
            env_config = get_config()
            return {
                'naver_client_id': env_config.NAVER_CLIENT_ID,
                'naver_client_secret': env_config.NAVER_CLIENT_SECRET,
                'smithery_api_key': getattr(env_config, 'SMITHERY_API_KEY', self.smithery_api_key)
            }
        except Exception as e:
            logger.warning(f"환경 설정 로드 실패: {e}")
            return {
                'naver_client_id': os.getenv('NAVER_CLIENT_ID'),
                'naver_client_secret': os.getenv('NAVER_CLIENT_SECRET'),
                'smithery_api_key': os.getenv('SMITHERY_API_KEY', self.smithery_api_key)
            }
    
    async def analyze_naver_trends(
        self, 
        keywords: List[str], 
        start_date: str = None, 
        end_date: str = None
    ) -> Dict[str, Any]:
        """네이버 검색어 트렌드 분석 (5개씩 나눠 호출)"""
        try:
            # 기본 날짜 설정
            if not start_date or not end_date:
                today = datetime.now()
                start_date = today.replace(day=1).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
            
            # MCP 설정
            config_b64 = base64.b64encode(json.dumps({
                "NAVER_CLIENT_ID": self.config['naver_client_id'],
                "NAVER_CLIENT_SECRET": self.config['naver_client_secret']
            }).encode()).decode()

            url = f"https://server.smithery.ai/@isnow890/naver-search-mcp/mcp?config={config_b64}&api_key={self.config['smithery_api_key']}&profile={self.profile}"

            all_results = []

            async with streamablehttp_client(url) as (read_stream, write_stream, _):
                async with mcp.ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    # 5개씩 나누어 호출
                    for i in range(0, len(keywords), 5):
                        batch = keywords[i:i + 5]
                        keyword_groups = [
                            {"groupName": kw, "keywords": [kw]} for kw in batch
                        ]

                        result = await session.call_tool("datalab_search", {
                            "startDate": start_date,
                            "endDate": end_date,
                            "timeUnit": "month",
                            "keywordGroups": keyword_groups
                        })

                        if result and not result.isError:
                            data = json.loads(result.content[0].text)
                            all_results.extend(data.get("results", []))

            if all_results:
                return {
                    "success": True,
                    "data": all_results,
                    "period": f"{start_date} ~ {end_date}",
                    "keywords": keywords
                }

            return {"success": False, "error": "트렌드 분석 실패"}

        except Exception as e:
            logger.error(f"네이버 트렌드 분석 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def analyze_instagram_hashtags(
        self, 
        question: str, 
        user_hashtags: List[str] = None
    ) -> Dict[str, Any]:
        """인스타그램 해시태그 트렌드 분석"""
        try:
            # 해시태그 추출 및 처리
            hashtags_to_analyze = []
            
            if user_hashtags:
                base_hashtags = [tag.lstrip('#') for tag in user_hashtags]
                hashtags_to_analyze.extend(base_hashtags[:5])
                
            # MCP 설정
            config = {
                "APIFY_API_TOKEN": "apify_api_LAUmyixlrAn8cvwanbU9moalojDpaF2e0deQ"
            }
            config_b64 = base64.b64encode(json.dumps(config).encode()).decode()
            url = f"https://server.smithery.ai/@HeurisTech/product-trends-mcp/mcp?config={config_b64}&api_key={self.smithery_api_key}&profile={self.profile}"
            
            async with streamablehttp_client(url) as (read_stream, write_stream, _):
                async with mcp.ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    result = await session.call_tool("insta_hashtag_scraper", {
                        "hashtags": hashtags_to_analyze,
                        "results_limit": 3000
                    })
                    
                    # 데이터 처리
                    data = json.loads(result.content[0].text)
                    posts = data.get('results', [])
                    
                    # 인기 해시태그 추출
                    popular_hashtags = []
                    for post in posts:
                        likes = post.get("likesCount", 0)
                        hashtags = post.get("hashtags", [])
                        if likes >= 10 and hashtags:
                            popular_hashtags.extend(hashtags)
                    
                    # 중복 제거 및 정제
                    unique_hashtags = list({tag for tag in popular_hashtags if tag and len(tag) > 1})
                    
                    return {
                        "success": True,
                        "searched_hashtags": hashtags_to_analyze,
                        "popular_hashtags": unique_hashtags[:10],  # 상위 30개
                        "total_posts": len(posts)
                    }
            
        except Exception as e:
            logger.error(f"인스타그램 해시태그 분석 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def generate_instagram_content(self) -> Dict[str, Any]:
        """인스타그램 마케팅 콘텐츠 생성"""
        try:
            config = {
                "debug": False,
                "hyperFeedApiKey": "bee-7dc552d8-7dee-46f4-9869-4123dd34f7dd"
            }
            config_b64 = base64.b64encode(json.dumps(config).encode()).decode()
            url = f"https://server.smithery.ai/@synthetic-ci/vibe-marketing/mcp?config={config_b64}&api_key={self.smithery_api_key}&profile={self.profile}"
            
            async with streamablehttp_client(url) as (read_stream, write_stream, _):
                async with mcp.ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    # 인스타그램 훅 생성
                    hooks_result = await session.call_tool("find-hooks", {
                        "network": "instagram",
                        "category": "promotional",
                        "limit": 5
                    })
                    
                    # AIDA 템플릿 생성
                    aida_result = await session.call_tool("get-copywriting-framework", {
                        "network": "instagram",
                        "framework": "aida"
                    })
                    
                    return {
                        "success": True,
                        "hooks": hooks_result.content[0].text if hooks_result.content else "",
                        "aida_template": aida_result.content[0].text if aida_result.content else "",
                        "frameworks_available": True
                    }
            
        except Exception as e:
            logger.error(f"인스타그램 콘텐츠 생성 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback_content": {
                    "hooks": "1. 제품의 핵심 가치 강조\n2. 고객 문제 해결 방법 제시\n3. 실제 사용 사례 공유",
                    "aida_template": "1. Attention: 주목을 끄는 제목\n2. Interest: 흥미 유발\n3. Desire: 구매 욕구 자극\n4. Action: 행동 유도"
                }
            }
    
    async def _extract_hashtags_from_question(self, question: str) -> List[str]:
        """질문에서 해시태그 추출 (LLM 활용)"""
        try:
            from shared_modules import get_llm_manager
            llm_manager = get_llm_manager()
            
            messages = [
                {"role": "system", "content": "사용자 질문에서 마케팅에 유용한 키워드를 5개 추출하세요. 쉼표로 구분하여 키워드만 출력하세요."},
                {"role": "user", "content": f"다음 질문에서 해시태그용 키워드를 추출해주세요: {question}"}
            ]
            
            result = llm_manager.generate_response_sync(messages)
            keywords = [kw.strip() for kw in result.split(',')]
            return [tag for tag in keywords if len(tag) > 1][:5]
            
        except Exception as e:
            logger.error(f"키워드 추출 실패: {e}")
            return []
    
    async def _extract_similar_hashtags(self, hashtag: str) -> List[str]:
        """유사 해시태그 추출 (LLM 활용)"""
        try:
            from shared_modules import get_llm_manager
            llm_manager = get_llm_manager()
            
            messages = [
                {"role": "system", "content": "주어진 해시태그와 유사한 키워드 5개를 추출하세요. 쉼표로 구분하여 키워드만 출력하세요."},
                {"role": "user", "content": f"다음 해시태그와 유사한 키워드를 추출해주세요: {hashtag}"}
            ]
            
            result = llm_manager.generate_response_sync(messages)
            keywords = [kw.strip() for kw in result.split(',')]
            return [tag for tag in keywords if len(tag) > 1][:5]
            
        except Exception as e:
            logger.error(f"유사 키워드 추출 실패: {e}")
            return []
    
    async def generate_related_keywords(self, base_keyword: str, count: int = 10) -> List[str]:
        """LLM을 활용하여 관련 키워드 생성"""
        try:
            from shared_modules import get_llm_manager
            llm_manager = get_llm_manager()
            
            messages = [
                {"role": "system", "content": f"주어진 키워드와 관련된 마케팅에 유용한 키워드 {count}개를 생성하세요. 각 키워드는 마케팅, SEO, 검색 트렌드 관점에서 유용해야 합니다. 쉼표로 구분하여 키워드만 출력하세요."},
                {"role": "user", "content": f"다음 키워드와 관련된 키워드 {count}개를 생성해주세요: {base_keyword}"}
            ]
            
            result = llm_manager.generate_response_sync(messages)
            keywords = [kw.strip() for kw in result.split(',')]
            # 기본 키워드도 포함
            all_keywords = [base_keyword] + [k for k in keywords if k and len(k.strip()) > 1]
            
            return list(dict.fromkeys(all_keywords))[:count]  # 중복 제거 및 개수 제한
            
        except Exception as e:
            logger.error(f"관련 키워드 생성 실패: {e}")
            # 기본값으로 원본 키워드 반환
            return [base_keyword]
    
    async def create_blog_content_workflow(self, base_keyword: str) -> Dict[str, Any]:
        """블로그 컨텐츠 생성 전체 워크플로우"""
        try:
            # 1단계: LLM 기반 관련 키워드 10개 생성
            logger.info(f"1단계: '{base_keyword}'에 대한 관련 키워드 생성")
            related_keywords = await self.generate_related_keywords(base_keyword, 30)
            
            # 2단계: 네이버 검색어 트렌드 분석
            logger.info("2단계: 네이버 검색어 트렌드 분석")
            trend_result = await self.analyze_naver_trends(related_keywords)  # 최대 5개까지 분석
            
            # 3단계: 트렌드 데이터 기반 상위 키워드 선별
            top_keywords = []
            if trend_result.get("success") and trend_result.get("data"):
                # 트렌드 데이터에서 평균값이 높은 순으로 정렬
                trend_scores = []
                for result in trend_result["data"]:
                    if "data" in result:
                        scores = [item["ratio"] for item in result["data"] if "ratio" in item]
                        avg_score = sum(scores) / len(scores) if scores else 0
                        trend_scores.append((result["title"], avg_score))
                
                # 점수순 정렬
                trend_scores.sort(key=lambda x: x[1], reverse=True)
                top_keywords = [keyword for keyword, score in trend_scores[:5]]
            
            # 백업: 트렌드 분석 실패시 원본 키워드 사용
            if not top_keywords:
                top_keywords = related_keywords[:5]
            
            # 4단계: 블로그 콘텐츠 생성 (LLM 활용)
            logger.info("4단계: 블로그 콘텐츠 생성")
            blog_content = await self._generate_blog_content(base_keyword, top_keywords, trend_result)
            
            return {
                "success": True,
                "base_keyword": base_keyword,
                "related_keywords": related_keywords,
                "top_keywords": top_keywords,
                "trend_analysis": trend_result,
                "blog_content": blog_content
            }
            
        except Exception as e:
            logger.error(f"블로그 콘텐츠 워크플로우 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_instagram_content_workflow(self, base_keyword: str) -> Dict[str, Any]:
        """인스타그램 컨텐츠 생성 전체 워크플로우"""
        try:
            # 1단계: LLM 기반 관련 키워드 10개 생성
            logger.info(f"1단계: '{base_keyword}'에 대한 관련 키워드 생성")
            related_keywords = await self.generate_related_keywords(base_keyword, 30)
            
            # 2단계: 관련 인스타 해시태그 추천
            logger.info("2단계: 인스타그램 해시태그 분석")
            hashtag_result = await self.analyze_instagram_hashtags(
                question=f"{base_keyword} 마케팅",
                user_hashtags=[f"#{kw}" for kw in related_keywords]
            )
            
            # 3단계: 마케팅 템플릿 가져오기
            logger.info("3단계: 마케팅 템플릿 생성")
            template_result = await self.generate_instagram_content()
            
            # 4단계: 인스타그램 콘텐츠 생성
            logger.info("4단계: 인스타그램 콘텐츠 생성")
            instagram_content = await self._generate_instagram_content(
                base_keyword, 
                related_keywords, 
                hashtag_result.get("popular_hashtags", []),
                template_result
            )
            
            return {
                "success": True,
                "base_keyword": base_keyword,
                "related_keywords": related_keywords,
                "hashtag_analysis": hashtag_result,
                "template_result": template_result,
                "instagram_content": instagram_content
            }
            
        except Exception as e:
            logger.error(f"인스타그램 콘텐츠 워크플로우 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_blog_content(self, base_keyword: str, top_keywords: List[str], trend_data: Dict) -> Dict[str, Any]:
        """블로그 콘텐츠 생성 (LLM 활용)"""
        try:
            from shared_modules import get_llm_manager
            llm_manager = get_llm_manager()
            
            # 트렌드 정보 요약
            trend_info = ""
            if trend_data.get("success") and trend_data.get("data"):
                trend_info = f"검색 트렌드 분석 결과: {trend_data['period']} 기간 동안 상위 키워드는 {', '.join(top_keywords)} 입니다."
            
            messages = [
                {
                    "role": "system", 
                    "content": """당신은 전문 마케팅 블로그 콘텐츠 작가입니다. 
                    주어진 키워드와 트렌드 데이터를 바탕으로 SEO에 최적화된 블로그 포스트를 작성하세요.
                    
                    다음 구조로 작성하세요:
                    1. 제목 (SEO 최적화)
                    2. 서론 (독자의 관심 유발)
                    3. 본문 (3-4개 섹션으로 구성, 키워드 자연스럽게 포함)
                    4. 결론 (행동 유도)
                    5. 추천 태그
                    
                    톤앤매너: 전문적이면서도 친근하고, 읽기 쉽게 작성하세요."""
                },
                {
                    "role": "user", 
                    "content": f"""주요 키워드: {base_keyword}
                    상위 관련 키워드: {', '.join(top_keywords)}
                    {trend_info}
                    
                    위 정보를 바탕으로 마케팅 블로그 포스트를 작성해주세요."""
                }
            ]
            
            content = llm_manager.generate_response_sync(messages)
            
            return {
                "full_content": content,
                "keywords_used": top_keywords,
                "word_count": len(content.split()),
                "seo_optimized": True
            }
            
        except Exception as e:
            logger.error(f"블로그 콘텐츠 생성 실패: {e}")
            return {
                "full_content": f"{base_keyword}에 대한 마케팅 블로그 콘텐츠 생성 중 오류가 발생했습니다.",
                "error": str(e)
            }
    
    async def _generate_instagram_content(
        self, 
        base_keyword: str, 
        related_keywords: List[str], 
        popular_hashtags: List[str],
        template_data: Dict
    ) -> Dict[str, Any]:
        """인스타그램 콘텐츠 생성 (LLM 활용)"""
        try:
            from shared_modules import get_llm_manager
            llm_manager = get_llm_manager()
            
            # 해시태그 선별 (인기있고 관련성 높은 것)
            selected_hashtags = []
            
            # 기본 키워드들을 해시태그로 변환
            for keyword in related_keywords[:5]:
                selected_hashtags.append(f"#{keyword.replace(' ', '').lower()}")
            
            # 인기 해시태그 중에서 선별
            for hashtag in popular_hashtags[:15]:
                if not hashtag.startswith('#'):
                    hashtag = f"#{hashtag}"
                selected_hashtags.append(hashtag)
            
            # 중복 제거
            selected_hashtags = list(dict.fromkeys(selected_hashtags))[:30]
            
            # 템플릿 정보 추출
            hooks = template_data.get("hooks", "") or "매력적인 인스타그램 콘텐츠를 위한 훅"
            aida_template = template_data.get("aida_template", "") or "AIDA 마케팅 프레임워크"
            
            messages = [
                {
                    "role": "system",
                    "content": """당신은 전문 인스타그램 마케팅 콘텐츠 크리에이터입니다.
                    주어진 키워드와 해시태그, 마케팅 템플릿을 활용하여 인스타그램에 최적화된 콘텐츠를 작성하세요.
                    
                    구성:
                    1. 캐치한 첫 줄 (스크롤을 멈추게 하는)
                    2. 본문 (3-5줄, 감정적 연결)
                    3. 행동 유도 (CTA)
                    4. 관련 해시태그
                    
                    스타일: 친근하고 트렌디하며, 이모지를 적절히 활용하세요."""
                },
                {
                    "role": "user",
                    "content": f"""주요 키워드: {base_keyword}
                    관련 키워드: {', '.join(related_keywords[:5])}
                    
                    마케팅 훅 가이드:
                    {hooks}
                    
                    AIDA 템플릿:
                    {aida_template}
                    
                    추천 해시태그: {' '.join(selected_hashtags[:20])}
                    
                    위 정보를 활용하여 인스타그램 포스트 콘텐츠를 작성해주세요."""
                }
            ]
            
            content = llm_manager.generate_response_sync(messages)
            
            return {
                "post_content": content,
                "selected_hashtags": selected_hashtags,
                "hashtag_count": len(selected_hashtags),
                "template_used": True,
                "engagement_optimized": True
            }
            
        except Exception as e:
            logger.error(f"인스타그램 콘텐츠 생성 실패: {e}")
            return {
                "post_content": f"{base_keyword}에 대한 인스타그램 콘텐츠 생성 중 오류가 발생했습니다.",
                "selected_hashtags": [f"#{base_keyword.replace(' ', '').lower()}"],
                "error": str(e)
            }

# ============================================
# 전역 인스턴스 및 팩토리 함수
# ============================================

_analysis_tools = None

def get_marketing_analysis_tools() -> MarketingAnalysisTools:
    """MCP 기반 마케팅 분석 도구 인스턴스 반환"""
    global _analysis_tools
    if _analysis_tools is None:
        _analysis_tools = MarketingAnalysisTools()
    return _analysis_tools

# 호환성을 위한 별칭 함수들
def get_mcp_tools() -> MarketingAnalysisTools:
    """MCP 도구 인스턴스 반환 (별칭)"""
    return get_marketing_analysis_tools()

def get_trend_analysis_tool() -> MarketingAnalysisTools:
    """트렌드 분석 도구 반환 (별칭)"""
    return get_marketing_analysis_tools()

def get_hashtag_analysis_tool() -> MarketingAnalysisTools:
    """해시태그 분석 도구 반환 (별칭)"""
    return get_marketing_analysis_tools()

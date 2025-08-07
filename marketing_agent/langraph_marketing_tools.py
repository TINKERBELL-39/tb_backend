"""
LangGraph 호환 마케팅 도구 모음
기존 도구들을 LangGraph Node에서 사용할 수 있도록 수정
"""

import json
import logging
import asyncio
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
import openai
from datetime import datetime
from config import config

logger = logging.getLogger(__name__)

class LangGraphMarketingTools:
    """LangGraph 호환 마케팅 도구들"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        self.prompts_dir = config.PROMPTS_DIR
        self._load_templates()
        self._init_industry_configs()
    
    def _load_templates(self):
        """템플릿 로드"""
        self.templates = {}
        
        key_templates = [
            "content_marketing.md",
            "social_media_marketing.md", 
            "blog_marketing.md",
            "digital_advertising.md"
        ]
        
        for template_file in key_templates:
            template_path = self.prompts_dir / template_file
            if template_path.exists():
                try:
                    with open(template_path, 'r', encoding='utf-8') as f:
                        self.templates[template_file] = f.read()
                except Exception as e:
                    logger.warning(f"템플릿 로드 실패: {template_file}, 오류: {e}")
    
    def _init_industry_configs(self):
        """업종별 맞춤 설정"""
        self.industry_configs = {
            "뷰티": {
                "target_platforms": ["인스타그램", "틱톡", "유튜브"],
                "content_focus": ["제품 리뷰", "뷰티 팁", "트렌드"],
                "hashtag_style": "트렌디하고 감각적인",
                "tone": "친근하고 유행에 민감한",
                "keywords": ["뷰티", "화장품", "스킨케어", "메이크업", "트렌드"]
            },
            "음식점": {
                "target_platforms": ["인스타그램", "네이버 지도", "배달앱"],
                "content_focus": ["음식 사진", "매장 분위기", "이벤트"],
                "hashtag_style": "맛집과 지역 중심",
                "tone": "따뜻하고 친근한",
                "keywords": ["맛집", "음식", "레스토랑", "지역명", "분위기"]
            },
            "온라인쇼핑몰": {
                "target_platforms": ["인스타그램", "페이스북", "블로그"],
                "content_focus": ["제품 소개", "후기", "할인 정보"],
                "hashtag_style": "제품과 혜택 중심",
                "tone": "신뢰감 있고 전문적인",
                "keywords": ["쇼핑", "할인", "신제품", "후기", "품질"]
            },
            "서비스업": {
                "target_platforms": ["네이버 블로그", "인스타그램", "유튜브"],
                "content_focus": ["서비스 소개", "고객 사례", "전문성"],
                "hashtag_style": "전문성과 신뢰도 중심",
                "tone": "전문적이고 신뢰감 있는",
                "keywords": ["서비스", "전문", "고객만족", "품질", "신뢰"]
            }
        }
    
    async def generate_content_with_llm(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """LLM을 사용한 콘텐츠 생성"""
        try:
            enhanced_context = self._build_context(context) if context else ""
            full_prompt = f"{enhanced_context}\n\n{prompt}" if enhanced_context else prompt
            
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": """당신은 업종별 마케팅 전문가입니다. 다음 원칙에 따라 콘텐츠를 작성해주세요:

1. **맞춤화**: 업종과 타겟 고객에 특화된 콘텐츠
2. **실행력**: 바로 사용할 수 있는 구체적인 내용
3. **전문성**: 해당 분야의 트렌드와 베스트 프랙티스 반영
4. **차별화**: 경쟁사와 구별되는 독창적 접근
5. **효과성**: 실제 마케팅 성과를 낼 수 있는 실용적 콘텐츠"""},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=config.TEMPERATURE,
                max_tokens=1500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"LLM 콘텐츠 생성 실패: {e}")
            return f"콘텐츠 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _build_context(self, context: Dict[str, Any]) -> str:
        """컨텍스트 구성"""
        context_parts = []
        
        # 핵심 비즈니스 정보
        business_type = context.get("business_type", "일반")
        if business_type != "일반":
            context_parts.append(f"### 비즈니스 컨텍스트\n업종: {business_type}")
            
            # 업종별 추가 인사이트
            industry_config = self.industry_configs.get(business_type, {})
            if industry_config:
                context_parts.append(f"핵심 키워드: {', '.join(industry_config.get('keywords', []))}")
                context_parts.append(f"권장 톤: {industry_config.get('tone', '')}")
        
        # 타겟 및 목표 정보
        target_info = []
        if context.get("target_audience"):
            target_info.append(f"타겟: {context['target_audience']}")
        if context.get("main_goal"):
            target_info.append(f"목표: {context['main_goal']}")
        if target_info:
            context_parts.append(f"### 마케팅 목표\n{', '.join(target_info)}")
        
        # 제품/서비스 정보
        if context.get("product"):
            context_parts.append(f"### 제품/서비스\n{context['product']}")
        
        return "\n\n".join(context_parts) if context_parts else ""
    
    async def create_instagram_post(self, keywords: List[str], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """인스타그램 포스트 생성 - LangGraph 호환"""
        try:
            if not context:
                context = {}
                
            business_type = context.get("business_type", "일반")
            target_audience = context.get("target_audience", "20-30대")
            product = context.get("product", "미정")
            main_goal = context.get("main_goal", "브랜드 인지도 향상")
            
            # 업종별 특화 가이드
            industry_guide = self._get_industry_guide(business_type, "instagram")
            
            prompt = f"""다음 정보를 바탕으로 인스타그램 포스트를 생성해주세요:

업종: {business_type}
제품/서비스: {product}
타겟 고객: {target_audience}
마케팅 목표: {main_goal}
키워드: {', '.join(keywords)}

{industry_guide}

다음 형식으로 생성해주세요:
**📸 캡션**
[매력적이고 자연스러운 캡션 - 2-3문단]

**🔖 해시태그**
#해시태그1 #해시태그2... (20개, 트렌드 + 니치 조합)

**👆 CTA**
[구체적인 행동 유도 문구]

**🎨 이미지 아이디어**
1. [이모지] [구체적인 이미지 콘셉트 1]
2. [이모지] [구체적인 이미지 콘셉트 2] 
3. [이모지] [구체적인 이미지 콘셉트 3]

**💡 포스팅 최적화 팁**
- 최적 업로드 시간: [업종별 권장 시간]
- 인게이지먼트 전략: [구체적인 방법 2-3개]"""
            
            content = await self.generate_content_with_llm(prompt, context)
            
            # 결과 파싱
            result = self._parse_instagram_content(content)
            result.update({
                "success": True,
                "type": "instagram_post",
                "keywords": keywords,
                "business_type": business_type,
                "generated_at": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            logger.error(f"인스타그램 포스트 생성 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "type": "instagram_post"
            }
    
    async def create_blog_post(self, keywords: List[str], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """블로그 포스트 생성 - LangGraph 호환"""
        try:
            if not context:
                context = {}
                
            business_type = context.get("business_type", "일반")
            target_audience = context.get("target_audience", "일반 고객")
            product = context.get("product", "미정")
            main_goal = context.get("main_goal", "전문성 어필")
            
            prompt = f"""다음 정보를 바탕으로 SEO 최적화된 블로그 포스트를 생성해주세요:

업종: {business_type}
제품/서비스: {product}
타겟 독자: {target_audience}
주요 키워드: {', '.join(keywords)}
마케팅 목표: {main_goal}

다음 형식으로 생성해주세요:
**📝 SEO 최적화 제목**
[클릭을 유도하는 매력적인 제목]

**📄 메타 설명 (150자 이내)**
[검색 결과에 노출될 요약 설명]

**📋 목차**
1. [도입부 소제목]
2. [본론 1 소제목]
3. [본론 2 소제목]
4. [본론 3 소제목]
5. [결론 소제목]

**📖 본문 (1500-2000자)**
[각 목차에 따른 상세 내용 - 실용적 정보, 팁, 사례 포함]

**🎯 SEO 키워드**
주요 키워드: [메인 키워드 3개]
관련 키워드: [롱테일 키워드 7개]"""
            
            content = await self.generate_content_with_llm(prompt, context)
            
            # 결과 파싱
            result = self._parse_blog_content(content)
            result.update({
                "success": True,
                "type": "blog_post",
                "keywords": keywords,
                "business_type": business_type,
                "generated_at": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            logger.error(f"블로그 포스트 생성 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "type": "blog_post"
            }
    
    async def create_marketing_strategy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """마케팅 전략 생성 - LangGraph 호환"""
        try:
            business_type = context.get("business_type", "일반")
            main_goal = context.get("main_goal", "매출 증대")
            target_audience = context.get("target_audience", "일반 고객")
            budget = context.get("budget", "미정")
            
            prompt = f"""다음 비즈니스 정보를 바탕으로 실행 가능한 마케팅 전략을 수립해주세요:

업종: {business_type}
제품/서비스: {context.get('product', '미정')}
주요 목표: {main_goal}
타겟 고객: {target_audience}
예산 규모: {budget}

다음 형식으로 생성해주세요:
**🎯 전략 개요**
[핵심 전략 한 줄 요약 + 기대 효과]

**📊 현황 분석**
- 시장 기회: [업종별 트렌드와 기회 요소]
- 경쟁 우위: [차별화 포인트]
- 핵심 과제: [해결해야 할 주요 이슈]

**🏆 목표 설정 (SMART)**
- 주 목표: [구체적, 측정 가능한 목표]
- 부 목표: [보조 목표 2-3개]
- 성공 지표: [KPI 및 측정 방법]

**👥 타겟 전략**
- 주요 타겟: [상세 페르소나]
- 고객 여정: [인식 → 관심 → 구매 → 충성]
- 메시지 전략: [타겟별 핵심 메시지]

**📺 채널 전략**
- 주력 채널: [예산과 효과성 기준 선정]
- 보조 채널: [시너지 효과 기대 채널]
- 채널별 역할: [각 채널의 구체적 활용법]

**📅 실행 로드맵 (3개월)**
**1개월차**: [기반 구축 활동]
**2개월차**: [본격 실행 활동]  
**3개월차**: [최적화 및 확장]

**💰 예산 배분**
- 채널별 예산: [구체적 금액/비율]
- 콘텐츠 제작: [제작비 가이드]
- 운영 비용: [월별 운영비]

**📈 성과 측정**
- 주간 체크: [주요 지표 3개]
- 월간 평가: [종합 성과 리뷰]
- 개선 방안: [지속적 최적화 방법]"""
            
            content = await self.generate_content_with_llm(prompt, context)
            
            return {
                "success": True,
                "type": "marketing_strategy",
                "strategy": content,
                "business_type": business_type,
                "main_goal": main_goal,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"마케팅 전략 생성 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "type": "marketing_strategy"
            }
    
    def _get_industry_guide(self, business_type: str, content_type: str) -> str:
        """업종별 가이드 생성"""
        industry_config = self.industry_configs.get(business_type, {})
        
        if not industry_config:
            return "일반적인 마케팅 원칙을 적용합니다."
        
        if content_type == "instagram":
            return f"""
### {business_type} 업종 인스타그램 특화 전략
- **주요 플랫폼**: {', '.join(industry_config.get('target_platforms', []))}
- **콘텐츠 포커스**: {', '.join(industry_config.get('content_focus', []))}
- **해시태그 스타일**: {industry_config.get('hashtag_style', '')}
- **권장 톤**: {industry_config.get('tone', '')}
- **핵심 키워드**: {', '.join(industry_config.get('keywords', []))}
"""
        
        return "업종별 맞춤 전략을 적용합니다."
    
    def _parse_instagram_content(self, content: str) -> Dict[str, str]:
        """인스타그램 콘텐츠 파싱"""
        try:
            result = {
                "caption": "",
                "hashtags": "",
                "cta": "",
                "image_concepts": [],
                "posting_tips": "",
                "full_content": content
            }
            
            # 섹션별 파싱
            sections = {
                "📸": "caption",
                "🔖": "hashtags", 
                "👆": "cta",
                "🎨": "image_concepts",
                "💡": "posting_tips"
            }
            
            lines = content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                
                # 섹션 헤더 감지
                for emoji, section_name in sections.items():
                    if line.startswith(emoji):
                        current_section = section_name
                        continue
                
                # 내용 추가
                if line and current_section:
                    if current_section == "image_concepts":
                        if line.startswith(('1.', '2.', '3.', '-')):
                            result[current_section].append(line)
                    else:
                        if result[current_section]:
                            result[current_section] += "\n" + line
                        else:
                            result[current_section] = line
            
            return result
            
        except Exception as e:
            logger.error(f"인스타그램 콘텐츠 파싱 실패: {e}")
            return {
                "caption": content[:500] + "..." if len(content) > 500 else content,
                "hashtags": "",
                "cta": "",
                "image_concepts": [],
                "posting_tips": "",
                "full_content": content
            }
    
    def _parse_blog_content(self, content: str) -> Dict[str, str]:
        """블로그 콘텐츠 파싱"""
        try:
            result = {
                "title": "",
                "meta_description": "",
                "outline": "",
                "body": "",
                "seo_keywords": "",
                "full_content": content
            }
            
            # 섹션별 파싱
            sections = {
                "📝": "title",
                "📄": "meta_description",
                "📋": "outline",
                "📖": "body",
                "🎯": "seo_keywords"
            }
            
            lines = content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                
                # 섹션 헤더 감지
                for emoji, section_name in sections.items():
                    if line.startswith(emoji):
                        current_section = section_name
                        continue
                
                # 내용 추가
                if line and current_section:
                    if result[current_section]:
                        result[current_section] += "\n" + line
                    else:
                        result[current_section] = line
            
            return result
            
        except Exception as e:
            logger.error(f"블로그 콘텐츠 파싱 실패: {e}")
            return {
                "title": "블로그 포스트 제목",
                "meta_description": "",
                "outline": "",
                "body": content,
                "seo_keywords": "",
                "full_content": content
            }
    
    def get_available_tools(self) -> List[str]:
        """사용 가능한 도구 목록"""
        return [
            "create_instagram_post",
            "create_blog_post",
            "create_marketing_strategy",
            "generate_content_with_llm"
        ]

# 전역 인스턴스
langraph_marketing_tools = LangGraphMarketingTools()

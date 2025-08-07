"""
마케팅 도구 모음 - mcp_marketing_tools 기능 통합
실제 호출되는 함수들만 정의한 간소화 버전
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

# ============================================
# 모듈 임포트 및 의존성 관리
# ============================================

# 공유 모듈 임포트 (안전한 import)
try:
    from shared_modules import get_llm_manager
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"shared_modules import 실패: {e}")
    
    def get_llm_manager():
        return None

# MCP 마케팅 도구 임포트 (올바른 함수명으로 수정)
try:
    from mcp_marketing_tools import get_marketing_analysis_tools
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"mcp_marketing_tools import 실패: {e}")
    
    def get_marketing_analysis_tools():
        return None

logger = logging.getLogger(__name__)

# ============================================
# 마케팅 도구 클래스
# ============================================

class MarketingTools:
    """마케팅 도구 모음 - mcp_marketing_tools 통합"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        self.prompts_dir = config.PROMPTS_DIR
        # MCP 도구 인스턴스 (lazy loading으로 순환 참조 방지)
        self._mcp_tools = None
        self.llm_manager = get_llm_manager()
        self._load_templates()
        self.logger = logging.getLogger(__name__)
    
    def get_mcp_tools(self):
        """MCP 도구를 lazy loading으로 반환"""
        if self._mcp_tools is None:
            try:
                self._mcp_tools = get_marketing_analysis_tools()
            except Exception as e:
                self.logger.warning(f"MCP 도구 초기화 실패: {e}")
                self._mcp_tools = None
        return self._mcp_tools
    
    def _load_templates(self):
        """마케팅 템플릿 로드"""
        self.templates = {}
        
        # 주요 템플릿들만 로드
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
                    self.logger.warning(f"템플릿 로드 실패: {template_file}, 오류: {e}")
            else:
                self.logger.warning(f"템플릿 파일 없음: {template_path}")
    
    # ============================================
    # MCP 연동 함수들 (mcp_marketing_tools에서 가져옴)
    # ============================================
    
    async def analyze_naver_trends(self, keywords: List[str]) -> Dict[str, Any]:
        """네이버 트렌드 분석 (MCP 연동)"""
        mcp_tools = self.get_mcp_tools()
        if not mcp_tools:
            return {"success": False, "error": "MCP 도구 초기화 실패"}
        
        return await mcp_tools.analyze_naver_trends(keywords)
    
    async def analyze_instagram_hashtags(self, question: str, user_hashtags: List[str]) -> Dict[str, Any]:
        """인스타그램 해시태그 분석 (MCP 연동)"""
        mcp_tools = self.get_mcp_tools()
        if not mcp_tools:
            return {"success": False, "error": "MCP 도구 초기화 실패"}
        
        return await mcp_tools.analyze_instagram_hashtags(question, user_hashtags)
    
    async def create_blog_content_workflow(self, target_keyword: str) -> Dict[str, Any]:
        """블로그 콘텐츠 워크플로우 (MCP 연동)"""
        mcp_tools = self.get_mcp_tools()
        if not mcp_tools:
            return {"success": False, "error": "MCP 도구 초기화 실패"}
        
        result = await mcp_tools.create_blog_content_workflow(target_keyword)
        
        # 결과에 tool_type 추가
        if result.get("success"):
            result["tool_type"] = "content_generation"
            result["content_type"] = "blog"
        
        return result
    
    async def create_instagram_content_workflow(self, target_keyword: str) -> Dict[str, Any]:
        """인스타그램 콘텐츠 워크플로우 (MCP 연동)"""
        mcp_tools = self.get_mcp_tools()
        if not mcp_tools:
            return {"success": False, "error": "MCP 도구 초기화 실패"}
        
        result = await mcp_tools.create_instagram_content_workflow(target_keyword)
        
        # 결과에 tool_type 추가
        if result.get("success"):
            result["tool_type"] = "content_generation"
            result["content_type"] = "instagram"
        
        return result
    
    async def generate_instagram_content(self) -> Dict[str, Any]:
        """인스타그램 마케팅 콘텐츠 생성 (MCP 연동)"""
        mcp_tools = self.get_mcp_tools()
        if not mcp_tools:
            return {"success": False, "error": "MCP 도구 초기화 실패"}
        
        return await mcp_tools.generate_instagram_content()
    
    async def create_strategy_content(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """전략 콘텐츠 생성 워크플로우"""
        try:            
            result = await self.generate_marketing_strategy(context)
            
            if result.get("success"):
                result["tool_type"] = "content_generation"
                result["content_type"] = "strategy"
            
            return result
            
        except Exception as e:
            self.logger.error(f"전략 콘텐츠 생성 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_type": "content_generation",
                "content_type": "strategy"
            }
    
    async def create_campaign_content(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """캠페인 콘텐츠 생성 워크플로우"""
        try:
            result = await self.create_campaign_plan(context)
            
            if result.get("success"):
                result["tool_type"] = "content_generation"
                result["content_type"] = "campaign"
            
            return result
            
        except Exception as e:
            self.logger.error(f"캠페인 콘텐츠 생성 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_type": "content_generation",
                "content_type": "campaign"
            }
    
    # ============================================
    # 로컬 구현 함수들
    # ============================================
    
    async def generate_marketing_strategy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """마케팅 전략 생성"""
        try:
            business_type = context.get("business_type", "일반")
            main_goal = context.get("main_goal", "매출 증대")
            target_audience = context.get("target_audience", "일반 고객")
            budget = context.get("budget", "미정")
            channels = context.get("preferred_channel", "SNS")
            
            prompt = f"""
다음 정보를 바탕으로 종합적인 마케팅 전략을 수립해주세요.

**비즈니스 정보:**
- 업종: {business_type}
- 주요 목표: {main_goal}
- 타겟 고객: {target_audience}
- 예산: {budget}
- 선호 채널: {channels}

**출력 형식:**
```
마케팅 전략 요약:
[핵심 전략 요약]

1. 목표 설정:
[SMART 목표]

2. 타겟 분석:
[페르소나 및 고객 여정]

3. 채널 전략:
[채널별 활용 방안]

4. 콘텐츠 계획:
[콘텐츠 유형 및 일정]

5. 예산 배분:
[채널별 예산 분배]

6. 성과 측정:
[KPI 및 측정 방법]

7. 실행 일정:
[단계별 실행 계획]
```
"""
            
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
            self.logger.error(f"마케팅 전략 생성 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "type": "marketing_strategy"
            }
    
    async def create_campaign_plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """캠페인 계획 생성"""
        try:
            business_type = context.get("business_type", "일반")
            campaign_goal = context.get("campaign_goal", "브랜드 인지도 향상")
            target_audience = context.get("target_audience", "일반 고객")
            budget = context.get("budget", "미정")
            duration = context.get("duration", "1개월")
            channels = context.get("preferred_channel", "SNS")
            
            prompt = f"""
다음 정보를 바탕으로 마케팅 캠페인 계획을 수립해주세요.

**캠페인 정보:**
- 업종: {business_type}
- 캠페인 목표: {campaign_goal}
- 타겟 고객: {target_audience}
- 예산: {budget}
- 기간: {duration}
- 주요 채널: {channels}

**출력 형식:**
```
캠페인 개요:
[캠페인 컨셉 및 핵심 메시지]

1. 캠페인 목표:
- 주 목표: [구체적 목표]
- 부 목표: [보조 목표들]
- 성공 지표: [측정 가능한 KPI]

2. 타겟 오디언스:
- 주 타겟: [상세 페르소나]
- 부 타겟: [보조 타겟층]

3. 핵심 메시지:
- 메인 메시지: [핵심 전달 내용]
- 서브 메시지: [보조 메시지들]

4. 채널별 전략:
- {channels}: [구체적 활용 방안]
- 기타 채널: [추가 채널 활용]

5. 콘텐츠 계획:
- 콘텐츠 유형: [콘텐츠 형태별 계획]
- 제작 일정: [콘텐츠 제작 스케줄]

6. 예산 배분:
- 채널별 예산: [채널별 예산 분배]
- 콘텐츠 제작비: [제작 관련 예산]

7. 실행 일정:
- 준비 단계: [사전 준비 사항]
- 실행 단계: [캠페인 진행]
- 후속 조치: [캠페인 후 활동]

8. 성과 측정 계획:
- 측정 지표: [구체적 KPI]
- 측정 방법: [데이터 수집 방안]
- 보고 주기: [성과 리포팅 일정]
```
"""
            
            content = await self.generate_content_with_llm(prompt, context)
            
            return {
                "success": True,
                "type": "campaign_plan",
                "plan": content,
                "business_type": business_type,
                "campaign_goal": campaign_goal,
                "duration": duration,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"캠페인 계획 생성 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "type": "campaign_plan"
            }
    
    async def create_instagram_post(self, keyword: List[str], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """인스타그램 포스트 생성 (기본 버전)"""
        try:
            business_type = context.get("business_type", "일반") if context else "일반"
            target_audience = context.get("target_audience", "20-30대") if context else "20-30대"
            product = context.get("product", "미정") if context else "미정"
            
            prompt = f"""{keyword}에 대한 인스타그램 포스트를 작성해주세요.

            **요구사항:**
            - 업종: {business_type}
            - 타겟: {target_audience}
            - 제품: {product}
            - 관련 키워드: {', '.join(keyword)}
            - 매력적인 캡션 (이모지 포함)
            - 관련 해시태그 20개
            - 참여를 유도하는 CTA (Call-to-Action)
            - 포스트에 어울리는 이미지 콘셉트 3가지를 제안 (예: 제품 클로즈업, 고객 사용 후기, 라이프스타일 연출 등)

            **출력 형식:**
              
            [매력적인 캡션 내용]
            
            [참여 유도 문구]

            #해시태그1 #해시태그2 ... (20개)

            이미지 아이디어:  
            - [이모지] [이미지 아이디어 1]  
            - [이모지] [이미지 아이디어 2]  
            - [이모지] [이미지 아이디어 3]"""

            content = await self.generate_content_with_llm(prompt, context)
            
            # 결과 파싱
            result = self._parse_instagram_content(content)
            result.update({
                "success": True,
                "type": "instagram_post",
                "keyword": keyword,
                "business_type": business_type,
                "generated_at": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"인스타그램 포스트 생성 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "type": "instagram_post"
            }
    
    async def create_blog_post(self, keyword: List[str], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """블로그 포스트 생성 (기본 버전)"""
        try:
            business_type = context.get("business_type", "일반") if context else "일반"
            target_audience = context.get("target_audience", "일반 고객") if context else "일반 고객"
            product = context.get("product", "미정") if context else "미정"
            
            # 블로그 템플릿 사용
            blog_template = self.templates.get("blog_marketing.md", "")
            
            prompt = f"""
{keyword}에 대한 SEO 최적화된 블로그 포스트를 작성해주세요.

**요구사항:**
- 업종: {business_type}
- 타겟 독자: {target_audience}
- 제품: {product}
- 관련 키워드: {', '.join(keyword)}
- 1500-2000자 분량
- SEO 최적화된 제목
- 목차와 소제목
- 실용적인 정보 제공
- 자연스러운 마케팅 메시지 포함

**블로그 마케팅 가이드:**
{blog_template[:1000]}

**출력 형식:**
```
제목: [SEO 최적화된 제목]

목차:
1. [소제목1]
2. [소제목2]
3. [소제목3]

본문:
[블로그 포스트 내용]

SEO 키워드: [관련 키워드 5개]
```
"""
            
            content = await self.generate_content_with_llm(prompt, context)
            
            # 결과 파싱
            result = self._parse_blog_content(content)
            result.update({
                "success": True,
                "type": "blog_post",
                "keyword": keyword,
                "business_type": business_type,
                "generated_at": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"블로그 포스트 생성 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "type": "blog_post"
            }
    
    async def analyze_keywords(self, keyword: str) -> Dict[str, Any]:
        """키워드 분석 및 관련 키워드 추천"""
        try:
            prompt = f"""
'{keyword}'에 대한 마케팅 키워드 분석을 해주세요.

**관련 키워드**: {', '.join(keyword)}

**분석 항목:**
1. 주요 키워드 특성 분석
2. 트렌드 예상 (상승/하락/유지)
3. 경쟁도 예상 (높음/중간/낮음)
4. 타겟 오디언스 예상
5. 마케팅 활용 방안

**출력 형식:**
```
주요 키워드: {keyword}

키워드 특성:
[키워드의 마케팅적 특성]

관련 키워드 TOP 10:
1. [키워드1] - [활용도]
2. [키워드2] - [활용도]
...

트렌드 분석:
[트렌드 예상 및 근거]

경쟁도 분석:
[경쟁도 예상 및 근거]

타겟 오디언스:
[예상 타겟층]

마케팅 활용 방안:
[구체적인 활용 방법]
```
"""
            
            content = await self.generate_content_with_llm(prompt)
            
            return {
                "success": True,
                "type": "keyword_analysis", 
                "analysis": content,
                "keyword": keyword,
                "analyzed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"키워드 분석 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "type": "keyword_analysis"
            }
    
    # ============================================
    # 헬퍼 메서드들
    # ============================================
    
    async def generate_content_with_llm(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """LLM을 사용한 콘텐츠 생성"""
        try:
            # 컨텍스트 정보 추가
            full_prompt = prompt
            if context:
                context_str = f"\n\n**참고 정보:**\n"
                for key, value in context.items():
                    if value and key not in ['detected_modifications', 'previous_content']:
                        context_str += f"- {key}: {value}\n"
                
                full_prompt = context_str + "\n" + prompt
            
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "당신은 마케팅 전문가입니다. 실용적이고 구체적인 마케팅 콘텐츠를 작성해주세요."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=config.TEMPERATURE,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"LLM 콘텐츠 생성 실패: {e}")
            return f"죄송합니다. 콘텐츠 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _parse_instagram_content(self, content: str) -> Dict[str, str]:
        """인스타그램 콘텐츠 파싱"""
        try:
            lines = content.split('\n')
            result = {
                "caption": "",
                "hashtags": "",
                "cta": "",
                "full_content": content
            }
            
            current_section = None
            for line in lines:
                line = line.strip()
                if line.startswith('캡션:'):
                    current_section = "caption"
                elif line.startswith('해시태그:'):
                    current_section = "hashtags"
                elif line.startswith('CTA:'):
                    current_section = "cta"
                elif line and current_section:
                    if result[current_section]:
                        result[current_section] += "\n" + line
                    else:
                        result[current_section] = line
            
            return result
            
        except Exception as e:
            self.logger.warning(f"인스타그램 콘텐츠 파싱 실패: {e}")
            return {
                "caption": content,
                "hashtags": "",
                "cta": "",
                "full_content": content
            }
    
    def _parse_blog_content(self, content: str) -> Dict[str, str]:
        """블로그 콘텐츠 파싱"""
        try:
            lines = content.split('\n')
            result = {
                "title": "",
                "outline": "",
                "body": "",
                "keywords": "",
                "full_content": content
            }
            
            current_section = None
            for line in lines:
                line = line.strip()
                if line.startswith('제목:'):
                    result["title"] = line.replace('제목:', '').strip()
                elif line.startswith('목차:'):
                    current_section = "outline"
                elif line.startswith('본문:'):
                    current_section = "body"
                elif line.startswith('SEO 키워드:'):
                    result["keywords"] = line.replace('SEO 키워드:', '').strip()
                elif line and current_section:
                    if result[current_section]:
                        result[current_section] += "\n" + line
                    else:
                        result[current_section] = line
            
            return result
            
        except Exception as e:
            self.logger.warning(f"블로그 콘텐츠 파싱 실패: {e}")
            return {
                "title": "블로그 포스트",
                "outline": "",
                "body": content,
                "keywords": "",
                "full_content": content
            }
    
    # ============================================
    # 통합 응답 생성 메서드들 (기존 코드와 호환)
    # ============================================
    
    async def generate_response_with_tool_result(self, user_input: str, intent_analysis: Dict[str, Any], 
                                               context: Dict[str, Any], tool_result: Dict[str, Any]) -> str:
        """툴 결과를 포함한 응답 생성"""
        try:
            tool_type = tool_result.get("tool_type", "unknown")
            success = tool_result.get("success", False)
            
            if not success:
                error_msg = tool_result.get("error", "알 수 없는 오류")
                
                # 단계 제한 오류 특별 처리
                if "stage_requirement" in tool_result:
                    current_stage = tool_result.get("current_stage", "unknown")
                    required_stage = tool_result.get("stage_requirement", "unknown")
                    suggestion = tool_result.get("suggestion", "")
                    
                    response = f"🚧 **콘텐츠 생성 단계 안내**\n\n"
                    response += f"현재 단계: **{current_stage}**\n"
                    response += f"요구 단계: **{required_stage}**\n\n"
                    response += f"📄 **안내사항**:\n{suggestion}\n\n"
                    response += "🚀 **단계별 진행 방법**:\n"
                    response += "• '단계 이동' 또는 '4단계로 이동'이라고 말씀하세요\n"
                    response += "• '체계적 상담 시작'으로 1단계부터 진행하세요\n"
                    response += "• 현재 단계에서 다른 마케팅 질문을 해주세요"
                    
                    return response
                
                return f"죄송합니다. {tool_type} 분석 중 오류가 발생했습니다: {error_msg}\n\n일반적인 마케팅 조언을 드리겠습니다."
            
            # 툴 타입별 결과 포맷팅
            if tool_type == "trend_analysis":
                return await self._format_trend_analysis_response(user_input, tool_result, context)
            elif tool_type == "hashtag_analysis":
                return await self._format_hashtag_analysis_response(user_input, tool_result, context)
            elif tool_type == "content_generation":
                return await self._format_content_generation_response(user_input, tool_result, context)
            elif tool_type == "keyword_research":
                return await self._format_keyword_research_response(user_input, tool_result, context)
            else:
                return await self._format_general_tool_response(user_input, tool_result, context)
                
        except Exception as e:
            self.logger.error(f"툴 결과 응답 생성 실패: {e}")
            return "마케팅 분석을 진행했지만 결과 처리 중 오류가 발생했습니다. 다시 시도해주세요."
    
    async def _format_trend_analysis_response(self, user_input: str, tool_result: Dict[str, Any], context: Dict[str, Any]) -> str:
        """트렌드 분석 결과 포맷팅"""
        try:
            data = tool_result.get("data", [])
            keywords = tool_result.get("keywords", [])
            period = tool_result.get("period", "")
            
            response = f"📈 **키워드 트렌드 분석 결과**\n\n"
            response += f"🔍 **분석 기간**: {period}\n"
            response += f"🎯 **분석 키워드**: {', '.join(keywords)}\n\n"
            
            if data:
                response += "📊 **트렌드 순위**:\n"
                trend_scores = []
                for result in data[:5]:
                    if "data" in result:
                        scores = [item["ratio"] for item in result["data"] if "ratio" in item]
                        avg_score = sum(scores) / len(scores) if scores else 0
                        trend_scores.append((result["title"], avg_score))
                
                trend_scores.sort(key=lambda x: x[1], reverse=True)
                
                for i, (keyword, score) in enumerate(trend_scores, 1):
                    response += f"{i}. **{keyword}** (평균 검색량: {score:.1f})\n"
                
                response += "\n💡 **마케팅 인사이트**:\n"
                if trend_scores:
                    top_keyword = trend_scores[0][0]
                    response += f"• '{top_keyword}'가 가장 높은 검색 트렌드를 보이고 있습니다.\n"
                    response += f"• 이 키워드를 중심으로 콘텐츠를 제작하면 높은 관심도를 얻을 수 있습니다.\n"
            else:
                response += "트렌드 데이터를 가져오는데 문제가 있었습니다.\n"
            
            response += "\n🎬 **다음 단계 제안**:\n"
            response += "• 블로그 콘텐츠 제작\n• 인스타그램 해시태그 분석\n• SEO 최적화 전략 수립\n"
            
            return response
            
        except Exception as e:
            self.logger.error(f"트렌드 분석 응답 포맷팅 실패: {e}")
            return "트렌드 분석을 완료했지만 결과 정리 중 오류가 발생했습니다."
    
    async def _format_hashtag_analysis_response(self, user_input: str, tool_result: Dict[str, Any], context: Dict[str, Any]) -> str:
        """해시태그 분석 결과 포맷팅"""  
        try:
            searched_hashtags = tool_result.get("searched_hashtags", [])
            popular_hashtags = tool_result.get("popular_hashtags", [])
            total_posts = tool_result.get("total_posts", 0)
            
            response = f"#️⃣ **인스타그램 해시태그 분석 결과**\n\n"
            response += f"🔍 **분석 해시태그**: #{', #'.join(searched_hashtags)}\n"
            response += f"📊 **분석된 포스트 수**: {total_posts:,}개\n\n"
            
            if popular_hashtags:
                response += "🔥 **추천 인기 해시태그**:\n"
                for i, hashtag in enumerate(popular_hashtags[:15], 1):
                    if not hashtag.startswith('#'):
                        hashtag = f"#{hashtag}"
                    response += f"{i}. {hashtag}\n"
                
                response += "\n💡 **해시태그 활용 팁**:\n"
                response += "• 인기 해시태그와 틈새 해시태그를 적절히 조합하세요\n"
                response += "• 포스트당 20-30개의 해시태그 사용을 권장합니다\n"
                response += "• 브랜드만의 고유 해시태그도 함께 활용하세요\n"
            else:
                response += "해시태그 데이터 수집에 문제가 있었습니다.\n"
            
            response += "\n📝 **다음 단계 제안**:\n"
            response += "• 인스타그램 콘텐츠 제작\n• 해시태그 성과 분석\n• 경쟁사 해시태그 연구\n"
            
            return response
            
        except Exception as e:
            self.logger.error(f"해시태그 분석 응답 포맷팅 실패: {e}")
            return "해시태그 분석을 완료했지만 결과 정리 중 오류가 발생했습니다."
    
    async def _format_content_generation_response(self, user_input: str, tool_result: Dict[str, Any], context: Dict[str, Any]) -> str:
        """콘텐츠 생성 결과 포맷팅"""
        try:
            content_type = tool_result.get("content_type", "general")
            base_keyword = tool_result.get("base_keyword", "")
            
            response = f"✍️ **{content_type.upper()} 콘텐츠 생성 완료**\n\n"
            response += f"🎯 **주요 키워드**: {base_keyword}\n\n"
            
            if content_type == "blog":
                blog_content = tool_result.get("blog_content", {})
                if blog_content and "full_content" in blog_content:
                    response += "📝 **생성된 블로그 콘텐츠**:\n"
                    response += f"{blog_content['full_content'][:1000]}...\n\n"
                    response += f"📊 **콘텐츠 정보**: 약 {blog_content.get('word_count', 0)}단어\n"
                
            elif content_type == "instagram":
                instagram_content = tool_result.get("instagram_content", {})
                if instagram_content and "post_content" in instagram_content:
                    response += "📱 **생성된 인스타그램 포스트**:\n"
                    response += f"{instagram_content['post_content']}\n\n"
                    
                    hashtags = instagram_content.get("selected_hashtags", [])
                    if hashtags:
                        response += f"#️⃣ **추천 해시태그** ({len(hashtags)}개):\n"
                        response += " ".join(hashtags[:20]) + "\n\n"
            
            related_keywords = tool_result.get("related_keywords", [])
            if related_keywords:
                response += f"🔑 **관련 키워드**: {', '.join(related_keywords[:10])}\n\n"
            
            response += "💡 **활용 가이드**:\n"
            response += "• 생성된 콘텐츠를 브랜드 톤앤매너에 맞게 수정하세요\n"
            response += "• 타겟 고객의 관심사를 반영해 개인화하세요\n"
            response += "• 정기적인 콘텐츠 업데이트로 지속적인 관심을 유도하세요\n"
            
            return response
            
        except Exception as e:
            self.logger.error(f"콘텐츠 생성 응답 포맷팅 실패: {e}")
            return "콘텐츠 생성을 완료했지만 결과 정리 중 오류가 발생했습니다."
    
    async def _format_keyword_research_response(self, user_input: str, tool_result: Dict[str, Any], context: Dict[str, Any]) -> str:
        """키워드 연구 결과 포맷팅"""
        try:
            keywords = tool_result.get("keywords", [])
            trend_data = tool_result.get("trend_data", {})
            
            response = f"🔍 **키워드 연구 결과**\n\n"
            
            if keywords:
                response += f"📝 **추천 키워드** ({len(keywords)}개):\n"
                for i, keyword in enumerate(keywords[:15], 1):
                    response += f"{i}. {keyword}\n"
                response += "\n"
            
            if trend_data.get("success") and trend_data.get("data"):
                response += "📈 **트렌드 분석**:\n"
                for result in trend_data["data"][:5]:
                    if "data" in result:
                        scores = [item["ratio"] for item in result["data"] if "ratio" in item]
                        avg_score = sum(scores) / len(scores) if scores else 0
                        response += f"• {result['title']}: 평균 검색량 {avg_score:.1f}\n"
                response += "\n"
            
            response += "🎯 **SEO 활용 전략**:\n"
            response += "• 장꼬리 키워드(Long-tail)를 활용해 경쟁도를 낮추세요\n"
            response += "• 계절성과 트렌드를 고려한 키워드 선택을 하세요\n"
            response += "• 지역 기반 키워드로 로컬 SEO를 강화하세요\n"
            
            return response
            
        except Exception as e:
            self.logger.error(f"키워드 연구 응답 포맷팅 실패: {e}")
            return "키워드 연구를 완료했지만 결과 정리 중 오류가 발생했습니다."
    
    async def _format_general_tool_response(self, user_input: str, tool_result: Dict[str, Any], context: Dict[str, Any]) -> str:
        """일반 툴 결과 포맷팅"""
        return f"마케팅 분석을 완료했습니다. 결과를 바탕으로 맞춤형 전략을 제안드리겠습니다."
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """사용 가능한 도구 목록"""
        return [
            {
                "name": "trend_analysis",
                "description": "네이버 트렌드 분석 (MCP)",
                "input": "키워드 리스트",
                "output": "트렌드 데이터, 검색량 분석",
                "features": ["MCP - 실시간 트렌드", "검색량 분석", "키워드 비교"]
            },
            {
                "name": "hashtag_analysis", 
                "description": "인스타그램 해시태그 분석 (MCP)",
                "input": "해시태그, 질문",
                "output": "인기 해시태그, 포스트 분석",
                "features": ["MCP - 실시간 분석", "해시태그 추천", "경쟁 분석"]
            },
            {
                "name": "content_generation",
                "description": "고급 콘텐츠 생성 (MCP)",
                "input": "키워드, 콘텐츠 타입",
                "output": "최적화된 콘텐츠",
                "features": ["MCP - 워크플로우", "SEO 최적화", "단계별 제한"]
            },
            {
                "name": "keyword_research",
                "description": "키워드 연구 및 트렌드 (MCP)",
                "input": "기본 키워드",
                "output": "관련 키워드, 트렌드 분석",
                "features": ["MCP - 종합 분석", "키워드 확장", "트렌드 예측"]
            },
            {
                "name": "marketing_strategy",
                "description": "종합 마케팅 전략 수립",
                "input": "비즈니스 정보",
                "output": "전략, 채널별 계획",
                "features": ["전략 수립", "실행 계획"]
            },
            {
                "name": "campaign_plan",
                "description": "캠페인 계획 수립",
                "input": "캠페인 정보",
                "output": "캠페인 계획, 실행 일정",
                "features": ["캠페인 기획", "일정 관리"]
            },
            {
                "name": "instagram_post",
                "description": "인스타그램 포스트 생성",
                "input": "키워드, 컨텍스트",
                "output": "캡션, 해시태그, CTA",
                "features": ["기본 생성", "해시태그 최적화"]
            },
            {
                "name": "blog_post",
                "description": "블로그 포스트 작성",
                "input": "키워드, 컨텍스트", 
                "output": "제목, 본문, SEO 키워드",
                "features": ["SEO 최적화", "구조화된 콘텐츠"]
            },
            {
                "name": "keyword_analysis",
                "description": "키워드 분석 및 추천",
                "input": "키워드",
                "output": "관련 키워드, 트렌드 분석",
                "features": ["키워드 확장", "트렌드 분석"]
            },
            {
                "name": "performance_analysis",
                "description": "콘텐츠 성과 예측 분석",
                "input": "콘텐츠",
                "output": "성과 분석, 개선점",
                "features": ["성과 예측", "개선 제안"]
            }
        ]

# ============================================
# 글로벌 인스턴스 및 팩토리 함수
# ============================================

_marketing_tools = None

def get_marketing_tools() -> MarketingTools:
    """마케팅 도구 인스턴스 반환"""
    global _marketing_tools
    if _marketing_tools is None:
        _marketing_tools = MarketingTools()
    return _marketing_tools

# ============================================
# 기존 코드와의 호환성을 위한 함수들
# ============================================

def get_marketing_mcp_marketing_tools():
    """기존 호환성을 위한 함수 (사용 중단 예정)"""
    logger.warning("기존 호환성 함수 사용. get_marketing_tools()를 사용하세요.")
    return get_marketing_tools()

def get_mcp_analysis_tools():
    """MCP 분석 도구 반환 (별칭)"""
    try:
        return get_marketing_analysis_tools()
    except Exception as e:
        logger.error(f"MCP 분석 도구 초기화 실패: {e}")
        return None
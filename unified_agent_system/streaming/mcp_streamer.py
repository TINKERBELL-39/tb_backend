"""
MCP 진행 상태 스트리밍 시스템
실시간으로 MCP 서비스 호출 진행 상태를 클라이언트에 전송
"""

import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MCPProgressStreamer:
    """MCP 호출 진행 상태를 스트리밍으로 전송하는 클래스"""
    
    def __init__(self):
        self.mcp_services = {
            'naver_search': {
                'name': '네이버 검색',
                'icon': 'search',
                'color': '#03C75A',
                'duration': 2.0
            },
            'instagram_hashtag': {
                'name': '인스타그램 해시태그 분석',
                'icon': 'hash',
                'color': '#E4405F',
                'duration': 3.0
            },
            'amazon_product': {
                'name': '아마존 상품 검색',
                'icon': 'shopping-cart',
                'color': '#FF9900',
                'duration': 2.5
            },
            'youtube_trend': {
                'name': '유튜브 트렌드 분석',
                'icon': 'youtube',
                'color': '#FF0000',
                'duration': 3.5
            },
            'app_store': {
                'name': '앱스토어 데이터 수집',
                'icon': 'smartphone',
                'color': '#007AFF',
                'duration': 2.0
            },
            'web_scraping': {
                'name': '웹 데이터 스크래핑',
                'icon': 'globe',
                'color': '#6B7280',
                'duration': 4.0
            },
            'trend_analysis': {
                'name': '트렌드 데이터 분석',
                'icon': 'trending-up',
                'color': '#8B5CF6',
                'duration': 2.5
            },
            'content_generation': {
                'name': '콘텐츠 생성',
                'icon': 'sparkles',
                'color': '#F59E0B',
                'duration': 3.0
            }
        }
    
    async def stream_mcp_progress(
        self, 
        user_query: str, 
        agent_type: str, 
        user_id: int, 
        conversation_id: int
    ) -> AsyncGenerator[str, None]:
        """MCP 진행 상태를 실시간으로 스트리밍"""
        
        try:
            logger.info(f"MCP 스트리밍 시작 - 사용자: {user_id}, 에이전트: {agent_type}")
            
            # 1. 시작 알림
            yield self._create_sse_event('start', {
                'message': 'AI가 분석을 시작합니다...',
                'agent_type': agent_type,
                'timestamp': datetime.now().isoformat()
            })
            await asyncio.sleep(0.5)
            
            # 2. 에이전트별 MCP 서비스 결정
            mcp_sequence = self._get_mcp_sequence(agent_type, user_query)
            logger.info(f"MCP 시퀀스 결정: {mcp_sequence}")
            
            # 3. 각 MCP 서비스별 진행 상태 전송
            results = {}
            for i, mcp_service in enumerate(mcp_sequence):
                try:
                    # 서비스 시작 알림
                    yield self._create_sse_event('mcp_start', {
                        'service': mcp_service,
                        'service_info': self.mcp_services[mcp_service],
                        'step': i + 1,
                        'total_steps': len(mcp_sequence),
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # 실제 MCP 호출 및 결과 수집
                    logger.info(f"MCP 서비스 실행 시작: {mcp_service}")
                    result = await self._execute_mcp_service(mcp_service, user_query, agent_type)
                    results[mcp_service] = result
                    logger.info(f"MCP 서비스 실행 완료: {mcp_service}, 성공: {result.get('success', False)}")
                    
                    # 서비스 완료 알림
                    yield self._create_sse_event('mcp_complete', {
                        'service': mcp_service,
                        'service_info': self.mcp_services[mcp_service],
                        'step': i + 1,
                        'total_steps': len(mcp_sequence),
                        'success': result.get('success', False),
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    await asyncio.sleep(0.3)
                    
                except Exception as e:
                    logger.error(f"MCP 서비스 {mcp_service} 실행 중 오류: {e}")
                    results[mcp_service] = {'success': False, 'error': str(e)}
                    
                    yield self._create_sse_event('mcp_complete', {
                        'service': mcp_service,
                        'service_info': self.mcp_services[mcp_service],
                        'step': i + 1,
                        'total_steps': len(mcp_sequence),
                        'success': False,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })
            
            # 4. 응답 생성 시작
            yield self._create_sse_event('response_generation', {
                'message': '수집된 데이터를 바탕으로 답변을 생성하고 있습니다...',
                'timestamp': datetime.now().isoformat()
            })
            
            # 5. 최종 응답 생성
            logger.info("최종 응답 생성 시작")
            final_response = await self._generate_final_response(
                user_query, agent_type, results, user_id, conversation_id
            )
            logger.info("최종 응답 생성 완료")
            
            # 6. 최종 응답 전송
            yield self._create_sse_event('final_response', {
                'response': final_response['content'],
                'metadata': final_response.get('metadata', {}),
                'sources': final_response.get('sources', []),
                'timestamp': datetime.now().isoformat()
            })
            
            # 7. 완료 신호
            yield self._create_sse_event('done', {
                'message': '완료되었습니다.',
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"MCP 스트리밍 중 오류 발생: {e}")
            # 오류 발생 시
            yield self._create_sse_event('error', {
                'message': f'오류가 발생했습니다: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
    
    def _create_sse_event(self, event_type: str, data: Dict[str, Any]) -> str:
        """Server-Sent Events 형식으로 이벤트 생성"""
        event_data = {'type': event_type, **data}
        return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
    
    def _get_mcp_sequence(self, agent_type: str, query: str) -> List[str]:
        """에이전트 타입과 쿼리에 따른 MCP 서비스 시퀀스 결정"""
        
        query_lower = query.lower()
        
        if agent_type == 'marketing':
            # 마케팅 에이전트의 경우
            services = ['naver_search']
            
            # 인스타그램 관련 키워드가 있으면 해시태그 분석 추가
            if any(keyword in query_lower for keyword in ['인스타', 'instagram', '해시태그', 'sns', '소셜']):
                services.append('instagram_hashtag')
            
            # 상품/제품 관련 키워드가 있으면 아마존 검색 추가
            if any(keyword in query_lower for keyword in ['상품', '제품', '판매', '쇼핑', '이커머스']):
                services.append('amazon_product')
                
            # 트렌드 분석 추가
            services.append('trend_analysis')
            
            return services
            
        elif agent_type == 'planner':
            # 사업기획 에이전트의 경우
            services = ['web_scraping', 'naver_search']
            
            # 앱 관련 키워드가 있으면 앱스토어 검색 추가
            if any(keyword in query_lower for keyword in ['앱', 'app', '모바일', '어플', '애플리케이션']):
                services.append('app_store')
            
            # 상품 관련이면 아마존 추가
            if any(keyword in query_lower for keyword in ['상품', '제품', '이커머스', '온라인']):
                services.append('amazon_product')
            
            # 트렌드 분석이 필요한 경우
            if any(keyword in query_lower for keyword in ['트렌드', '인기', '유행', '시장']):
                services.append('trend_analysis')
            
            return services
            
        elif agent_type == 'crm':
            # 고객관리 에이전트
            return ['web_scraping', 'trend_analysis']
            
        elif agent_type == 'task':
            # 업무지원 에이전트
            return ['web_scraping']
            
        elif agent_type == 'mentalcare':
            # 멘탈케어 에이전트 (MCP 사용 안함)
            return []
            
        else:
            # 기본 통합 에이전트
            return ['naver_search', 'web_scraping', 'trend_analysis']
    
    async def _execute_mcp_service(self, service: str, query: str, agent_type: str) -> Dict[str, Any]:
        """실제 MCP 서비스 호출"""
        
        try:
            if service == 'naver_search':
                # 네이버 검색 (마케팅 에이전트 도구 사용)
                try:
                    import sys
                    import os
                    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
                    
                    from marketing_agent.mcp_marketing_tools import get_marketing_analysis_tools
                    tools = get_marketing_analysis_tools()
                    
                    # 관련 키워드 생성 후 트렌드 분석
                    keywords = await tools.generate_related_keywords(query, 5)
                    result = await tools.analyze_naver_trends(keywords)
                    
                    return {'success': True, 'data': result, 'source': 'naver'}
                except Exception as e:
                    logger.error(f"네이버 검색 실행 오류: {e}")
                    return {'success': False, 'error': str(e)}
                
            elif service == 'instagram_hashtag':
                # 인스타그램 해시태그 분석
                try:
                    from marketing_agent.mcp_marketing_tools import get_marketing_analysis_tools
                    tools = get_marketing_analysis_tools()
                    result = await tools.analyze_instagram_hashtags(query)
                    return {'success': True, 'data': result, 'source': 'instagram'}
                except Exception as e:
                    logger.error(f"인스타그램 해시태그 분석 오류: {e}")
                    return {'success': False, 'error': str(e)}
                
            elif service == 'amazon_product':
                # 아마존 상품 검색
                try:
                    from buisness_planning_agent.idea_market import get_trending_amazon_products
                    result = await get_trending_amazon_products()
                    return {'success': True, 'data': result, 'source': 'amazon'}
                except Exception as e:
                    logger.error(f"아마존 상품 검색 오류: {e}")
                    return {'success': False, 'error': str(e)}
                
            elif service == 'youtube_trend':
                # 유튜브 트렌드 분석
                try:
                    from buisness_planning_agent.idea_market import get_trending_youtube_videos, youtube_url
                    result = await get_trending_youtube_videos(youtube_url)
                    return {'success': True, 'data': result, 'source': 'youtube'}
                except Exception as e:
                    logger.error(f"유튜브 트렌드 분석 오류: {e}")
                    return {'success': False, 'error': str(e)}
                
            elif service == 'app_store':
                # 앱스토어 데이터 수집
                try:
                    from buisness_planning_agent.idea_market import get_trending_new_app, app_store_url
                    result = await get_trending_new_app(app_store_url)
                    return {'success': True, 'data': result, 'source': 'app_store'}
                except Exception as e:
                    logger.error(f"앱스토어 데이터 수집 오류: {e}")
                    return {'success': False, 'error': str(e)}
                
            elif service == 'web_scraping':
                # 웹 데이터 스크래핑
                try:
                    from buisness_planning_agent.idea_market import get_common, bright_data_url
                    result = await get_common(bright_data_url, query)
                    return {'success': True, 'data': result, 'source': 'web'}
                except Exception as e:
                    logger.error(f"웹 스크래핑 오류: {e}")
                    return {'success': False, 'error': str(e)}
                
            elif service == 'trend_analysis':
                # 트렌드 분석 (복합)
                try:
                    # 여러 소스를 종합한 트렌드 분석
                    results = []
                    
                    # 네이버 트렌드
                    try:
                        from marketing_agent.mcp_marketing_tools import get_marketing_analysis_tools
                        tools = get_marketing_analysis_tools()
                        keywords = await tools.generate_related_keywords(query, 3)
                        naver_result = await tools.analyze_naver_trends(keywords)
                        if naver_result.get('success'):
                            results.append(f"네이버 트렌드: {naver_result.get('data', {})}")
                    except:
                        pass
                    
                    return {'success': True, 'data': results, 'source': 'trend_analysis'}
                except Exception as e:
                    logger.error(f"트렌드 분석 오류: {e}")
                    return {'success': False, 'error': str(e)}
                
            else:
                return {'success': False, 'error': f'Unknown service: {service}'}
                
        except Exception as e:
            logger.error(f"MCP 서비스 {service} 실행 중 전체 오류: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _generate_final_response(
        self, 
        query: str, 
        agent_type: str, 
        mcp_results: Dict[str, Any],
        user_id: int,
        conversation_id: int
    ) -> Dict[str, Any]:
        """MCP 결과를 바탕으로 최종 응답 생성"""
        
        try:
            # 성공한 결과들만 수집
            successful_results = []
            failed_services = []
            
            for service, result in mcp_results.items():
                if result.get('success', False):
                    successful_results.append({
                        'service': service,
                        'data': result.get('data', ''),
                        'source': result.get('source', service)
                    })
                else:
                    failed_services.append(service)
            
            if not successful_results:
                return {
                    'content': '죄송합니다. 데이터 수집 중 모든 서비스에서 오류가 발생했습니다. 다시 시도해 주세요.',
                    'metadata': {'error': True, 'failed_services': failed_services}
                }
            
            # 수집된 데이터를 종합하여 컨텍스트 생성
            context_parts = []
            for result in successful_results:
                service_name = self.mcp_services.get(result['service'], {}).get('name', result['service'])
                data_str = str(result['data'])[:500]  # 데이터 길이 제한
                context_parts.append(f"[{service_name}] {data_str}")
            
            combined_context = "\n\n".join(context_parts)
            
            # 에이전트별 응답 생성 (여기서는 기존 에이전트 시스템 호출)
            try:
                # 기존 query 엔드포인트 로직 재사용
                from unified_agent import UnifiedAgentSystem
                
                agent_system = UnifiedAgentSystem()
                
                # MCP 데이터를 컨텍스트로 포함하여 에이전트 호출
                enhanced_query = f"""사용자 질문: {query}

수집된 관련 데이터:
{combined_context}

위 데이터를 참고하여 사용자의 질문에 대해 구체적이고 실용적인 답변을 제공해주세요."""

                response = await agent_system.process_query(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message=enhanced_query,
                    preferred_agent=agent_type
                )
                
                return {
                    'content': response.get('response', '응답 생성에 실패했습니다.'),
                    'metadata': {
                        'mcp_services_used': [r['service'] for r in successful_results],
                        'successful_services': len(successful_results),
                        'failed_services': failed_services,
                        'agent_type': agent_type,
                        'enhanced_with_mcp': True
                    },
                    'sources': [result['source'] for result in successful_results]
                }
                
            except Exception as e:
                logger.error(f"에이전트 시스템 호출 오류: {e}")
                
                # 에이전트 시스템 호출 실패 시 기본 응답 생성
                response_content = f"""수집된 데이터를 바탕으로 분석한 결과입니다.

**주요 발견사항:**
{combined_context[:800]}

**분석 결과:**
수집된 데이터를 종합하면, {query}에 대해 다음과 같은 인사이트를 얻을 수 있습니다:

1. **현재 트렌드 분석**
   - 관련 키워드들의 검색 동향
   - 시장에서의 관심도 변화

2. **실행 가능한 제안**
   - 데이터 기반 추천 사항
   - 구체적인 다음 단계

더 자세한 분석이나 특정 부분에 대한 질문이 있으시면 언제든 말씀해 주세요."""

                return {
                    'content': response_content,
                    'metadata': {
                        'mcp_services_used': [r['service'] for r in successful_results],
                        'successful_services': len(successful_results),
                        'failed_services': failed_services,
                        'agent_type': agent_type,
                        'fallback_response': True
                    },
                    'sources': [result['source'] for result in successful_results]
                }
                
        except Exception as e:
            logger.error(f"최종 응답 생성 중 오류: {e}")
            return {
                'content': f'응답 생성 중 오류가 발생했습니다: {str(e)}',
                'metadata': {'error': True}
            }

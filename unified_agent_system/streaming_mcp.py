# unified_agent_system/streaming_mcp.py

import json
import asyncio
from typing import AsyncGenerator, Dict, Any
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

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
            # 1. 시작 알림
            yield self._create_sse_event('start', {
                'message': 'AI가 분석을 시작합니다...',
                'agent_type': agent_type
            })
            await asyncio.sleep(0.5)
            
            # 2. 에이전트별 MCP 서비스 결정
            mcp_sequence = self._get_mcp_sequence(agent_type, user_query)
            
            # 3. 각 MCP 서비스별 진행 상태 전송
            results = {}
            for i, mcp_service in enumerate(mcp_sequence):
                # 서비스 시작 알림
                yield self._create_sse_event('mcp_start', {
                    'service': mcp_service,
                    'service_info': self.mcp_services[mcp_service],
                    'step': i + 1,
                    'total_steps': len(mcp_sequence)
                })
                
                # 실제 MCP 호출 및 결과 수집
                result = await self._execute_mcp_service(mcp_service, user_query, agent_type)
                results[mcp_service] = result
                
                # 서비스 완료 알림
                yield self._create_sse_event('mcp_complete', {
                    'service': mcp_service,
                    'service_info': self.mcp_services[mcp_service],
                    'step': i + 1,
                    'total_steps': len(mcp_sequence),
                    'success': result['success']
                })
                
                await asyncio.sleep(0.3)
            
            # 4. 응답 생성 시작
            yield self._create_sse_event('response_generation', {
                'message': '수집된 데이터를 바탕으로 답변을 생성하고 있습니다...'
            })
            
            # 5. 최종 응답 생성
            final_response = await self._generate_final_response(
                user_query, agent_type, results, user_id, conversation_id
            )
            
            # 6. 최종 응답 전송
            yield self._create_sse_event('final_response', {
                'response': final_response['content'],
                'metadata': final_response.get('metadata', {}),
                'sources': final_response.get('sources', [])
            })
            
            # 7. 완료 신호
            yield self._create_sse_event('done', {'message': '완료되었습니다.'})
            
        except Exception as e:
            # 오류 발생 시
            yield self._create_sse_event('error', {
                'message': f'오류가 발생했습니다: {str(e)}'
            })
    
    def _create_sse_event(self, event_type: str, data: Dict[str, Any]) -> str:
        """Server-Sent Events 형식으로 이벤트 생성"""
        return f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n"
    
    def _get_mcp_sequence(self, agent_type: str, query: str) -> list:
        """에이전트 타입과 쿼리에 따른 MCP 서비스 시퀀스 결정"""
        
        if agent_type == 'marketing':
            # 마케팅 에이전트의 경우
            services = ['naver_search']
            
            # 인스타그램 관련 키워드가 있으면 해시태그 분석 추가
            if any(keyword in query.lower() for keyword in ['인스타', 'instagram', '해시태그', 'sns']):
                services.append('instagram_hashtag')
            
            # 상품/제품 관련 키워드가 있으면 아마존 검색 추가
            if any(keyword in query.lower() for keyword in ['상품', '제품', '판매', '쇼핑']):
                services.append('amazon_product')
            
            return services
            
        elif agent_type == 'planner':
            # 사업기획 에이전트의 경우
            services = ['web_scraping', 'naver_search']
            
            # 앱 관련 키워드가 있으면 앱스토어 검색 추가
            if any(keyword in query.lower() for keyword in ['앱', 'app', '모바일', '어플']):
                services.append('app_store')
            
            # 트렌드 분석이 필요한 경우
            if any(keyword in query.lower() for keyword in ['트렌드', '인기', '유행']):
                services.append('youtube_trend')
            
            return services
            
        else:
            # 기본 통합 에이전트
            return ['naver_search', 'web_scraping']
    
    async def _execute_mcp_service(self, service: str, query: str, agent_type: str) -> Dict[str, Any]:
        """실제 MCP 서비스 호출"""
        
        try:
            if service == 'naver_search':
                from marketing_agent.mcp_marketing_tools import get_marketing_analysis_tools
                tools = get_marketing_analysis_tools()
                result = await tools.analyze_naver_trends([query])
                return {'success': True, 'data': result, 'source': 'naver'}
                
            elif service == 'instagram_hashtag':
                from marketing_agent.mcp_marketing_tools import get_marketing_analysis_tools
                tools = get_marketing_analysis_tools()
                result = await tools.analyze_instagram_hashtags(query)
                return {'success': True, 'data': result, 'source': 'instagram'}
                
            elif service == 'amazon_product':
                from buisness_planning_agent.idea_market import get_trending_amazon_products
                result = await get_trending_amazon_products()
                return {'success': True, 'data': result, 'source': 'amazon'}
                
            elif service == 'youtube_trend':
                from buisness_planning_agent.idea_market import get_trending_youtube_videos, youtube_url
                result = await get_trending_youtube_videos(youtube_url)
                return {'success': True, 'data': result, 'source': 'youtube'}
                
            elif service == 'app_store':
                from buisness_planning_agent.idea_market import get_trending_new_app, app_store_url
                result = await get_trending_new_app(app_store_url)
                return {'success': True, 'data': result, 'source': 'app_store'}
                
            elif service == 'web_scraping':
                from buisness_planning_agent.idea_market import get_common, bright_data_url
                result = await get_common(bright_data_url, query)
                return {'success': True, 'data': result, 'source': 'web'}
                
            else:
                return {'success': False, 'error': f'Unknown service: {service}'}
                
        except Exception as e:
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
        
        # 기존 LLM 호출 로직을 여기에 구현
        # 수집된 MCP 데이터를 종합하여 최종 답변 생성
        
        successful_results = [
            result['data'] for result in mcp_results.values() 
            if result.get('success', False)
        ]
        
        if not successful_results:
            return {
                'content': '죄송합니다. 데이터 수집 중 오류가 발생했습니다.',
                'metadata': {'error': True}
            }
        
        # 실제로는 여기서 LLM에 컨텍스트와 함께 전달하여 응답 생성
        combined_data = "\n\n".join([str(data) for data in successful_results])
        
        # 임시 응답 (실제 구현에서는 LLM 호출)
        response_content = f"""수집된 데이터를 바탕으로 분석한 결과입니다.

{combined_data[:500]}...

위 데이터를 종합하여 다음과 같이 제안드립니다:

1. 현재 트렌드 분석 결과
2. 시장 기회 요소
3. 실행 가능한 전략

자세한 내용은 추가 질문해 주시면 더 구체적으로 설명드리겠습니다."""

        return {
            'content': response_content,
            'metadata': {
                'mcp_services_used': list(mcp_results.keys()),
                'successful_services': len(successful_results),
                'agent_type': agent_type
            },
            'sources': [
                result.get('source', 'unknown') 
                for result in mcp_results.values() 
                if result.get('success')
            ]
        }


# FastAPI 라우터에 추가
@app.post("/query/stream")
async def stream_query_with_mcp_progress(request: QueryRequest):
    """MCP 진행 상태를 포함한 스트리밍 쿼리 처리"""
    
    streamer = MCPProgressStreamer()
    
    return StreamingResponse(
        streamer.stream_mcp_progress(
            request.message, 
            request.preferred_agent,
            request.user_id,
            request.conversation_id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )
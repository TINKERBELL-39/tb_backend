"""
RAG 서비스
RAG 매니저를 래핑하는 서비스 레이어
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class RAGService:
    """RAG 서비스 - 지식 검색 및 관리"""
    
    def __init__(self, rag_manager):
        """RAG 서비스 초기화"""
        self.rag_manager = rag_manager
        logger.info("RAGService 초기화 완료")

    async def search_knowledge(self, query: str, persona: str = None, 
                             intent: str = None) -> Dict[str, Any]:
        """지식 검색"""
        try:
            search_result = await self.rag_manager.search_knowledge(query, persona, intent)
            
            # 검색 결과 후처리
            return {
                "context": self._extract_context(search_result),
                "sources": self._extract_sources(search_result),
                "confidence": search_result.get("confidence", 0.5) if search_result else 0.0,
                "chunk_count": len(search_result.get("chunks", [])) if search_result else 0
            }
        except Exception as e:
            logger.error(f"지식 검색 실패: {e}")
            return {"context": "", "sources": "", "confidence": 0.0, "chunk_count": 0}

    def _extract_context(self, search_result) -> str:
        """검색 결과에서 컨텍스트 추출"""
        try:
            if not search_result:
                return ""
            
            # search_result가 딕셔너리인 경우
            if isinstance(search_result, dict):
                chunks = search_result.get("chunks", [])
            # search_result가 객체인 경우
            elif hasattr(search_result, 'chunks'):
                chunks = search_result.chunks
            else:
                return ""
            
            if not chunks:
                return ""
            
            context_chunks = []
            for chunk in chunks[:3]:  # 최대 3개 청크
                if isinstance(chunk, dict):
                    context_chunks.append(chunk.get("content", ""))
                elif hasattr(chunk, 'content'):
                    context_chunks.append(chunk.content)
                else:
                    context_chunks.append(str(chunk))
            
            return "\n\n".join(context_chunks)
        except Exception as e:
            logger.error(f"컨텍스트 추출 실패: {e}")
            return ""

    def _extract_sources(self, search_result) -> str:
        """검색 결과에서 소스 추출"""
        try:
            if not search_result:
                return ""
            
            # search_result가 딕셔너리인 경우
            if isinstance(search_result, dict):
                sources = search_result.get("sources", [])
            # search_result가 객체인 경우
            elif hasattr(search_result, 'sources'):
                sources = search_result.sources
            else:
                return ""
                
            if not sources:
                return ""
                
            if isinstance(sources, list):
                return ", ".join(str(source) for source in sources)
            else:
                return str(sources)
                
        except Exception as e:
            logger.error(f"소스 추출 실패: {e}")
            return ""

    async def get_status(self) -> Dict[str, Any]:
        """서비스 상태 조회"""
        try:
            return {
                "service": "RAGService",
                "version": "5.0.0",
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "rag_manager": self.rag_manager.get_status() if hasattr(self.rag_manager, 'get_status') else {"status": "unknown"}
            }
        except Exception as e:
            return {"service": "RAGService", "status": "error", "error": str(e)}

    async def cleanup(self):
        """서비스 정리"""
        try:
            if hasattr(self.rag_manager, 'cleanup'):
                await self.rag_manager.cleanup()
            logger.info("RAGService 정리 완료")
        except Exception as e:
            logger.error(f"RAGService 정리 실패: {e}")

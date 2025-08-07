"""
Task Agent RAG 시스템 v4
공통 모듈의 vector_utils를 활용하여 RAG 구현
"""

import sys
import os
import logging
from typing import List, Optional, Dict, Any

# 공통 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "../shared_modules"))

from vector_utils import get_vector_manager, VectorStoreManager
from langchain_core.documents import Document

from models import SearchResult, KnowledgeChunk, PersonaType
from config import config

logger = logging.getLogger(__name__)

class TaskAgentRAGManager:
    """Task Agent 전용 RAG 매니저"""
    
    def __init__(self):
        """RAG 매니저 초기화"""
        # 공통 벡터 스토어 매니저 사용
        self.vector_manager = get_vector_manager()
        
        # Task Agent 전용 컬렉션 이름들
        self.collections = {
            "knowledge": "task-agent-knowledge",
            "conversations": "task-agent-conversations",
            "automation": "task-agent-automation"
        }
        
        logger.info("Task Agent RAG 매니저 초기화 완료")
        
    async def search_knowledge(self, query: str, persona, 
                             topic: Optional[str] = None) -> SearchResult:
        """지식 베이스 검색"""
        try:
            # 메타데이터 필터 구성
            persona_str = persona.value if hasattr(persona, 'value') else str(persona)
            filter_dict = {
                "persona": persona_str
            }
            
            if topic:
                filter_dict["topic"] = topic
            
            # 벡터 스토어에서 검색
            results = self.vector_manager.search_with_scores(
                query=query,
                collection_name=self.collections["knowledge"],
                k=config.MAX_SEARCH_RESULTS,
                filter_dict=filter_dict
            )
            
            # 결과 처리
            chunks = []
            sources = set()
            
            for doc, score in results:
                chunk = KnowledgeChunk(
                    content=doc.page_content,
                    metadata=doc.metadata,
                    relevance_score=score
                )
                chunks.append(chunk)
                
                if "source" in doc.metadata:
                    sources.add(doc.metadata["source"])
            
            # 공통 지식도 검색 (persona가 "common"이 아닌 경우)
            if persona != PersonaType.COMMON:
                common_filter = {"persona": "common"}
                if topic:
                    common_filter["topic"] = topic
                
                common_results = self.vector_manager.search_with_scores(
                    query=query,
                    collection_name=self.collections["knowledge"],
                    k=max(1, config.MAX_SEARCH_RESULTS // 2),
                    filter_dict=common_filter
                )
                
                for doc, score in common_results:
                    chunk = KnowledgeChunk(
                        content=doc.page_content,
                        metadata=doc.metadata,
                        relevance_score=score * 0.8  # 공통 지식은 가중치 낮춤
                    )
                    chunks.append(chunk)
                    
                    if "source" in doc.metadata:
                        sources.add(doc.metadata["source"])
            
            # 점수 순으로 정렬하고 최대 개수 제한
            chunks.sort(key=lambda x: x.relevance_score, reverse=True)
            chunks = chunks[:config.MAX_SEARCH_RESULTS]
            
            return SearchResult(
                chunks=chunks,
                sources=list(sources),
                total_results=len(chunks)
            )
            
        except Exception as e:
            logger.error(f"지식 검색 실패: {e}")
            return SearchResult(chunks=[], sources=[], total_results=0)
    
    async def search_conversation_history(self, user_id: str, query: str, 
                                        limit: int = 5) -> List[Dict[str, Any]]:
        """대화 기록 검색"""
        try:
            filter_dict = {"user_id": user_id}
            
            results = self.vector_manager.search_documents(
                query=query,
                collection_name=self.collections["conversations"],
                k=limit,
                filter_dict=filter_dict
            )
            
            conversations = []
            for doc in results:
                conversation_data = {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "timestamp": doc.metadata.get("timestamp")
                }
                conversations.append(conversation_data)
            
            return conversations
            
        except Exception as e:
            logger.error(f"대화 기록 검색 실패: {e}")
            return []
    
    async def search_automation_examples(self, query: str, task_type: str = None) -> List[Dict[str, Any]]:
        """자동화 예제 검색"""
        try:
            filter_dict = {}
            if task_type:
                filter_dict["task_type"] = task_type
            
            results = self.vector_manager.search_documents(
                query=query,
                collection_name=self.collections["automation"],
                k=config.MAX_SEARCH_RESULTS,
                filter_dict=filter_dict
            )
            
            examples = []
            for doc in results:
                example_data = {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "task_type": doc.metadata.get("task_type"),
                    "success_rate": doc.metadata.get("success_rate", 0.0)
                }
                examples.append(example_data)
            
            return examples
            
        except Exception as e:
            logger.error(f"자동화 예제 검색 실패: {e}")
            return []
    
    async def add_knowledge(self, content: str, persona, 
                      topic: str, source: str = "manual") -> bool:
        """지식 추가"""
        try:
            persona_str = persona.value if hasattr(persona, 'value') else str(persona)
            
            # 문서를 청크로 분할
            chunks = self._split_content(content)
            
            documents = []
            for i, chunk in enumerate(chunks):
                doc = Document(
                    page_content=chunk,
                    metadata={
                        "persona": persona.value,
                        "topic": topic,
                        "source": source,
                        "chunk_id": i,
                        "timestamp": self._get_current_timestamp()
                    }
                )
                documents.append(doc)
            
            # 벡터 스토어에 추가
            success = self.vector_manager.add_documents(
                documents=documents,
                collection_name=self.collections["knowledge"]
            )
            
            if success:
                logger.info(f"지식 추가 완료: {len(chunks)} chunks, 페르소나: {persona_str}, 주제: {topic}")
            
            return success
            
        except Exception as e:
            logger.error(f"지식 추가 실패: {e}")
            return False
    
    async def add_conversation(self, user_id: str, conversation_data: Dict[str, Any]) -> bool:
        """대화 기록 추가"""
        try:
            doc = Document(
                page_content=conversation_data.get("content", ""),
                metadata={
                    "user_id": user_id,
                    "conversation_id": conversation_data.get("conversation_id"),
                    "intent": conversation_data.get("intent"),
                    "timestamp": conversation_data.get("timestamp", self._get_current_timestamp()),
                    "persona": conversation_data.get("persona", "common")
                }
            )
            
            success = self.vector_manager.add_documents(
                documents=[doc],
                collection_name=self.collections["conversations"]
            )
            
            if success:
                logger.info(f"대화 기록 추가 완료: 사용자 {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"대화 기록 추가 실패: {e}")
            return False
    
    async def add_automation_example(self, task_data: Dict[str, Any], 
                                   success_rate: float = 1.0) -> bool:
        """자동화 예제 추가"""
        try:
            content = f"작업: {task_data.get('title', '')}\n설명: {task_data.get('description', '')}"
            
            doc = Document(
                page_content=content,
                metadata={
                    "task_type": task_data.get("task_type"),
                    "success_rate": success_rate,
                    "parameters": task_data.get("task_data", {}),
                    "timestamp": self._get_current_timestamp()
                }
            )
            
            success = self.vector_manager.add_documents(
                documents=[doc],
                collection_name=self.collections["automation"]
            )
            
            if success:
                logger.info(f"자동화 예제 추가 완료: {task_data.get('task_type')}")
            
            return success
            
        except Exception as e:
            logger.error(f"자동화 예제 추가 실패: {e}")
            return False
    
    def _split_content(self, content: str) -> List[str]:
        """컨텐츠를 청크로 분할"""
        # 간단한 문단 기반 분할
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk + paragraph) > config.CHUNK_SIZE and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [content]  # 최소 1개 청크 보장
    
    def _get_current_timestamp(self) -> str:
        """현재 타임스탬프 반환"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """컬렉션 통계 반환"""
        stats = {}
        
        for name, collection_name in self.collections.items():
            try:
                info = self.vector_manager.get_collection_info(collection_name)
                stats[name] = info
            except Exception as e:
                stats[name] = {"error": str(e)}
        
        return stats
    
    def get_status(self) -> Dict[str, Any]:
        """RAG 매니저 상태 반환"""
        vector_status = self.vector_manager.get_status()
        
        return {
            "task_agent_rag": {
                "collections": self.collections,
                "chunk_size": config.CHUNK_SIZE,
                "max_search_results": config.MAX_SEARCH_RESULTS
            },
            "vector_manager_status": vector_status,
            "collection_stats": self.get_collection_stats()
        }


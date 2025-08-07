"""
벡터 스토어 유틸리티 공통 모듈
각 에이전트에서 공통으로 사용하는 벡터 스토어 및 임베딩 관련 함수
"""

import logging
from typing import Dict, Any, List, Optional, Union
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from shared_modules.env_config import get_config

logger = logging.getLogger(__name__)

class VectorStoreManager:
    """벡터 스토어 관리 클래스"""
    
    def __init__(self, config=None):
        """
        벡터 스토어 매니저 초기화
        
        Args:
            config: 환경 설정 객체 (기본값: 전역 설정 사용)
        """
        self.config = config if config else get_config()
        self.embedding = None
        self.vectorstores = {}
        self.default_collection = "global-documents"
        
        self._initialize_embedding()
    
    def _ensure_chroma_schema(self, persist_directory: str):
        """
        ChromaDB 스키마 확인 및 자동 수정
        collections.topic 컶럼이 없으면 추가
        """
        import sqlite3
        import os
        
        db_path = os.path.join(persist_directory, "chroma.sqlite3")
        
        if not os.path.exists(db_path):
            return  # DB 파일이 없으면 스키프
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # collections 테이블 확인
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='collections'")
            if cursor.fetchone():
                # topic 컶럼 확인
                cursor.execute("PRAGMA table_info(collections)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'topic' not in columns:
                    logger.info("ChromaDB collections 테이블에 topic 컶럼 추가 중...")
                    cursor.execute("ALTER TABLE collections ADD COLUMN topic TEXT DEFAULT 'general'")
                    cursor.execute("UPDATE collections SET topic = 'general' WHERE topic IS NULL")
                    conn.commit()
                    logger.info("✅ ChromaDB collections.topic 컶럼 추가 완료")
            
            conn.close()
            
        except Exception as e:
            logger.warning(f"ChromaDB 스키마 수정 실패: {e}")
            if 'conn' in locals():
                conn.close()
    
    def _initialize_embedding(self):
        """임베딩 모델 초기화"""
        try:
            if not self.config.OPENAI_API_KEY:
                logger.warning("OpenAI API 키가 없어 임베딩을 초기화할 수 없습니다")
                return
            
            self.embedding = OpenAIEmbeddings(
                model=self.config.EMBEDDING_MODEL,
                dimensions=1536 if "small" in self.config.EMBEDDING_MODEL else 3072,
                openai_api_key=self.config.OPENAI_API_KEY
            )
            
            logger.info(f"임베딩 모델 초기화 성공: {self.config.EMBEDDING_MODEL}")
            
        except Exception as e:
            logger.error(f"임베딩 모델 초기화 실패: {e}")
    
    def get_vectorstore(
        self, 
        collection_name: str = None, 
        persist_directory: str = None,
        create_if_not_exists: bool = True
    ) -> Optional[Chroma]:
        """
        벡터 스토어 반환
        
        Args:
            collection_name: 컬렉션 이름 (기본값: global-documents)
            persist_directory: 저장 디렉토리 (기본값: 설정에서 가져옴)
            create_if_not_exists: 존재하지 않을 때 생성 여부
        
        Returns:
            Chroma: 벡터 스토어 객체
        """
        if not self.embedding:
            logger.error("임베딩 모델이 초기화되지 않았습니다")
            return None
        
        # 기본값 설정
        if collection_name is None:
            collection_name = self.default_collection
        
        if persist_directory is None:
            persist_directory = self.config.CHROMA_DIR
        
        # 캐시에서 확인
        cache_key = f"{collection_name}_{persist_directory}"
        if cache_key in self.vectorstores:
            return self.vectorstores[cache_key]
        
        try:
            # ChromaDB 스키마 자동 수정 (collections.topic 컶럼 추가)
            self._ensure_chroma_schema(persist_directory)
            
            # 벡터 스토어 생성/로드
            vectorstore = Chroma(
                collection_name=collection_name,
                persist_directory=persist_directory,
                embedding_function=self.embedding
            )
            
            # 캐시에 저장
            self.vectorstores[cache_key] = vectorstore
            
            logger.info(f"벡터 스토어 로드 성공: {collection_name}")
            return vectorstore
            
        except Exception as e:
            logger.error(f"벡터 스토어 로드 실패: {e}, persist_directory : {persist_directory}")
            if create_if_not_exists:
                try:
                    # 새로 생성 시도
                    vectorstore = Chroma(
                        collection_name=collection_name,
                        persist_directory=persist_directory,
                        embedding_function=self.embedding
                    )
                    
                    self.vectorstores[cache_key] = vectorstore
                    logger.info(f"새 벡터 스토어 생성 성공: {collection_name}")
                    return vectorstore
                    
                except Exception as create_error:
                    logger.error(f"벡터 스토어 생성 실패: {create_error}")
            
            return None
    
    def get_retriever(
        self,
        collection_name: str = None,
        persist_directory: str = None,
        k: int = 5,
        search_type: str = "similarity",
        search_kwargs: Dict[str, Any] = None
    ):
        """
        검색기 반환
        
        Args:
            collection_name: 컬렉션 이름
            persist_directory: 저장 디렉토리
            k: 반환할 문서 수
            search_type: 검색 타입 ("similarity", "mmr")
            search_kwargs: 추가 검색 매개변수
        
        Returns:
            VectorStoreRetriever: 검색기 객체
        """
        vectorstore = self.get_vectorstore(collection_name, persist_directory)
        if not vectorstore:
            return None
        
        # 검색 매개변수 설정
        if search_kwargs is None:
            search_kwargs = {"k": k}
        else:
            search_kwargs = {**search_kwargs, "k": k}
        
        try:
            retriever = vectorstore.as_retriever(
                search_type=search_type,
                search_kwargs=search_kwargs
            )
            
            logger.info(f"검색기 생성 성공: {collection_name or self.default_collection}")
            return retriever
            
        except Exception as e:
            logger.error(f"검색기 생성 실패: {e}")
            return None
    
    def add_documents(
        self,
        documents: List[Document],
        collection_name: str = None,
        persist_directory: str = None
    ) -> bool:
        """
        문서 추가
        
        Args:
            documents: 추가할 문서 리스트
            collection_name: 컬렉션 이름
            persist_directory: 저장 디렉토리
        
        Returns:
            bool: 성공 여부
        """
        vectorstore = self.get_vectorstore(collection_name, persist_directory)
        if not vectorstore:
            return False
        
        try:
            vectorstore.add_documents(documents)
            logger.info(f"{len(documents)}개 문서 추가 성공")
            return True
            
        except Exception as e:
            logger.error(f"문서 추가 실패: {e}")
            return False
    
    def add_texts(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]] = None,
        collection_name: str = None,
        persist_directory: str = None
    ) -> bool:
        """
        텍스트 추가
        
        Args:
            texts: 추가할 텍스트 리스트
            metadatas: 메타데이터 리스트
            collection_name: 컬렉션 이름
            persist_directory: 저장 디렉토리
        
        Returns:
            bool: 성공 여부
        """
        vectorstore = self.get_vectorstore(collection_name, persist_directory)
        if not vectorstore:
            return False
        
        try:
            vectorstore.add_texts(texts, metadatas=metadatas)
            logger.info(f"{len(texts)}개 텍스트 추가 성공")
            return True
            
        except Exception as e:
            logger.error(f"텍스트 추가 실패: {e}")
            return False
    
    def search_documents(
        self,
        query: str,
        collection_name: str = None,
        persist_directory: str = None,
        k: int = 5,
        filter_dict: Dict[str, Any] = None
    ) -> List[Document]:
        """
        문서 검색
        
        Args:
            query: 검색 쿼리
            collection_name: 컬렉션 이름
            persist_directory: 저장 디렉토리
            k: 반환할 문서 수
            filter_dict: 필터 조건
        
        Returns:
            List[Document]: 검색된 문서 리스트
        """
        vectorstore = self.get_vectorstore(collection_name, persist_directory)
        if not vectorstore:
            return []
        
        try:
            if filter_dict:
                documents = vectorstore.similarity_search(
                    query, 
                    k=k,
                    filter=filter_dict
                )
            else:
                documents = vectorstore.similarity_search(query, k=k)
            
            logger.info(f"문서 검색 성공: {len(documents)}개 문서 반환")
            return documents
            
        except Exception as e:
            logger.error(f"문서 검색 실패: {e}")
            return []
    
    def search_with_scores(
        self,
        query: str,
        collection_name: str = None,
        persist_directory: str = None,
        k: int = 5,
        filter_dict: Dict[str, Any] = None
    ) -> List[tuple]:
        """
        점수와 함께 문서 검색
        
        Args:
            query: 검색 쿼리
            collection_name: 컬렉션 이름
            persist_directory: 저장 디렉토리
            k: 반환할 문서 수
            filter_dict: 필터 조건
        
        Returns:
            List[tuple]: (Document, score) 튜플 리스트
        """
        vectorstore = self.get_vectorstore(collection_name, persist_directory)
        if not vectorstore:
            return []
        
        try:
            if filter_dict:
                results = vectorstore.similarity_search_with_score(
                    query,
                    k=k,
                    filter=filter_dict
                )
            else:
                results = vectorstore.similarity_search_with_score(query, k=k)
            
            logger.info(f"점수 포함 검색 성공: {len(results)}개 문서 반환")
            return results
            
        except Exception as e:
            logger.error(f"점수 포함 검색 실패: {e}")
            return []
    
    def delete_collection(
        self,
        collection_name: str,
        persist_directory: str = None
    ) -> bool:
        """
        컬렉션 삭제
        
        Args:
            collection_name: 삭제할 컬렉션 이름
            persist_directory: 저장 디렉토리
        
        Returns:
            bool: 성공 여부
        """
        try:
            if persist_directory is None:
                persist_directory = self.config.CHROMA_DIR
            
            # 캐시에서 제거
            cache_key = f"{collection_name}_{persist_directory}"
            if cache_key in self.vectorstores:
                del self.vectorstores[cache_key]
            
            # 실제 컬렉션 삭제는 Chroma 클라이언트를 통해 수행
            vectorstore = Chroma(
                collection_name=collection_name,
                persist_directory=persist_directory,
                embedding_function=self.embedding
            )
            
            vectorstore.delete_collection()
            logger.info(f"컬렉션 삭제 성공: {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"컬렉션 삭제 실패: {e}")
            return False
    
    def get_collection_info(self, collection_name: str = None) -> Dict[str, Any]:
        """
        컬렉션 정보 반환
        
        Args:
            collection_name: 컬렉션 이름
        
        Returns:
            dict: 컬렉션 정보
        """
        vectorstore = self.get_vectorstore(collection_name)
        if not vectorstore:
            return {"error": "컬렉션을 찾을 수 없습니다"}
        
        try:
            # ChromaDB 클라이언트를 통해 정보 수집
            collection = vectorstore._collection
            count = collection.count()
            
            return {
                "collection_name": collection_name or self.default_collection,
                "document_count": count,
                "embedding_model": self.config.EMBEDDING_MODEL,
                "persist_directory": self.config.CHROMA_DIR
            }
            
        except Exception as e:
            logger.error(f"컬렉션 정보 조회 실패: {e}")
            return {"error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """벡터 스토어 매니저 상태 반환"""
        return {
            "embedding_available": bool(self.embedding),
            "embedding_model": self.config.EMBEDDING_MODEL if self.embedding else None,
            "default_collection": self.default_collection,
            "persist_directory": self.config.CHROMA_DIR,
            "cached_vectorstores": len(self.vectorstores),
            "cached_collections": list(self.vectorstores.keys())
        }


# 전역 벡터 스토어 매니저 인스턴스
_global_vector_manager = None

def get_vector_manager(config=None) -> VectorStoreManager:
    """
    전역 벡터 스토어 매니저 인스턴스 반환 (싱글톤)
    
    Args:
        config: 환경 설정 객체
    
    Returns:
        VectorStoreManager: 벡터 스토어 매니저 인스턴스
    """
    global _global_vector_manager
    if _global_vector_manager is None:
        _global_vector_manager = VectorStoreManager(config)
    return _global_vector_manager

def reload_vector_manager(config=None) -> VectorStoreManager:
    """
    벡터 스토어 매니저 재로드
    
    Args:
        config: 환경 설정 객체
    
    Returns:
        VectorStoreManager: 새로운 벡터 스토어 매니저 인스턴스
    """
    global _global_vector_manager
    _global_vector_manager = VectorStoreManager(config)
    return _global_vector_manager

# 편의 함수들
def get_vectorstore(collection_name: str = None, persist_directory: str = None) -> Optional[Chroma]:
    """벡터 스토어 반환"""
    return get_vector_manager().get_vectorstore(collection_name, persist_directory)

def get_retriever(collection_name: str = None, k: int = 5, **kwargs):
    """검색기 반환"""
    return get_vector_manager().get_retriever(collection_name, k=k, **kwargs)

def search_documents(query: str, collection_name: str = None, k: int = 5, **kwargs) -> List[Document]:
    """문서 검색"""
    return get_vector_manager().search_documents(query, collection_name, k=k, **kwargs)

def add_documents(documents: List[Document], collection_name: str = None) -> bool:
    """문서 추가"""
    return get_vector_manager().add_documents(documents, collection_name)

def add_texts(texts: List[str], metadatas: List[Dict[str, Any]] = None, collection_name: str = None) -> bool:
    """텍스트 추가"""
    return get_vector_manager().add_texts(texts, metadatas, collection_name)

# 기존 코드와의 호환성을 위한 변수들 (lazy loading으로 변경)
embedding = None  # lazy loading
vectorstore = None  # lazy loading  
retriever = None  # lazy loading

def get_default_embedding():
    """기본 임베딩 반환 (lazy loading)"""
    global embedding
    if embedding is None:
        embedding = get_vector_manager().embedding
    return embedding

def get_default_vectorstore():
    """기본 벡터스토어 반환 (lazy loading)"""
    global vectorstore
    if vectorstore is None:
        vectorstore = get_vectorstore()
    return vectorstore

def get_default_retriever():
    """기본 검색기 반환 (lazy loading)"""
    global retriever
    if retriever is None:
        retriever = get_retriever()
    return retriever

"""
데이터베이스 연결 공통 모듈
각 에이전트에서 공통으로 사용하는 데이터베이스 연결 및 세션 관리
"""

import logging
from typing import Generator, Optional
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError

from shared_modules.env_config import get_config

logger = logging.getLogger(__name__)

# 환경 변수에서 MySQL 접속 URL 가져오기
config = get_config()
DATABASE_URL = config.get_mysql_url()

# SQLAlchemy DB 엔진 생성
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # 연결 살아있는지 체크
    pool_recycle=3600,   # 1시간마다 연결 재사용
    echo=False           # SQL 로그 안 찍음 (True로 하면 콘솔에 쿼리 출력됨)
)

# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# SQLAlchemy Base 클래스
Base = declarative_base()

class DatabaseManager:
    """데이터베이스 연결 관리 클래스"""
    
    def __init__(self, config=None):
        """
        데이터베이스 매니저 초기화
        
        Args:
            config: 환경 설정 객체 (기본값: 전역 설정 사용)
        """
        self.config = config if config else get_config()
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None
        self._initialize_engine()
    
    def _initialize_engine(self):
        """SQLAlchemy 엔진 초기화"""
        try:
            mysql_url = self.config.get_mysql_url()
            if not mysql_url:
                logger.warning("MySQL URL이 설정되지 않았습니다")
                return
            
            # 엔진 생성
            self.engine = create_engine(
                mysql_url,
                echo=False,  # SQL 로그 출력 여부
                pool_pre_ping=True,  # 연결 확인
                pool_recycle=3600,  # 연결 재사용 시간 (1시간)
                pool_timeout=30,  # 연결 타임아웃
                max_overflow=10  # 최대 오버플로우 연결 수
            )
            
            # 세션 팩토리 생성
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            logger.info("데이터베이스 엔진 초기화 성공")
            
        except Exception as e:
            logger.error(f"데이터베이스 엔진 초기화 실패: {e}")
            raise
    
    def get_mysql_connector_engine(self):
        """MySQL Connector 엔진 생성 (기존 코드 호환성용)"""
        try:
            mysql_url = self.config.get_mysql_connector_url()
            if not mysql_url:
                logger.warning("MySQL Connector URL이 설정되지 않았습니다")
                return None
            
            engine = create_engine(mysql_url, echo=False)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            
            return engine, SessionLocal
            
        except Exception as e:
            logger.error(f"MySQL Connector 엔진 생성 실패: {e}")
            return None, None
    
    def get_session(self) -> Optional[Session]:
        """
        데이터베이스 세션 반환 (직접 사용)
        
        Returns:
            Session: SQLAlchemy 세션 객체
        """
        if not self.SessionLocal:
            logger.error("세션 팩토리가 초기화되지 않았습니다")
            return None
        
        return self.SessionLocal()
    
    def get_db_dependency(self) -> Generator[Session, None, None]:
        """
        FastAPI 의존성으로 사용할 데이터베이스 세션 제너레이터
        
        Yields:
            Session: SQLAlchemy 세션 객체
        """
        if not self.SessionLocal:
            logger.error("세션 팩토리가 초기화되지 않았습니다")
            yield None
            return
        
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    @contextmanager
    def get_session_context(self):
        """
        컨텍스트 매니저로 사용할 데이터베이스 세션
        
        Example:
            with db_manager.get_session_context() as session:
                # 데이터베이스 작업
                pass
        """
        if not self.SessionLocal:
            logger.error("세션 팩토리가 초기화되지 않았습니다")
            yield None
            return
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"데이터베이스 트랜잭션 오류: {e}")
            raise
        finally:
            session.close()
    
    def test_connection(self) -> bool:
        """
        데이터베이스 연결 테스트
        
        Returns:
            bool: 연결 성공 여부
        """
        try:
            if not self.engine:
                return False
            
            with self.engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                return result.fetchone()[0] == 1
                
        except Exception as e:
            logger.error(f"데이터베이스 연결 테스트 실패: {e}")
            return False
    
    def create_tables(self):
        """데이터베이스 테이블 생성"""
        try:
            if not self.engine:
                logger.error("엔진이 초기화되지 않았습니다")
                return False
            
            Base.metadata.create_all(bind=self.engine)
            logger.info("데이터베이스 테이블 생성 완료")
            return True
            
        except Exception as e:
            logger.error(f"테이블 생성 실패: {e}")
            return False
    
    def drop_tables(self):
        """데이터베이스 테이블 삭제 (주의: 모든 데이터 삭제됨)"""
        try:
            if not self.engine:
                logger.error("엔진이 초기화되지 않았습니다")
                return False
            
            Base.metadata.drop_all(bind=self.engine)
            logger.info("데이터베이스 테이블 삭제 완료")
            return True
            
        except Exception as e:
            logger.error(f"테이블 삭제 실패: {e}")
            return False
    
    def get_engine_info(self) -> dict:
        """엔진 정보 반환"""
        if not self.engine:
            return {"status": "not_initialized"}
        
        return {
            "status": "initialized",
            "url": str(self.engine.url).replace(self.engine.url.password, "***") if self.engine.url.password else str(self.engine.url),
            "driver": self.engine.dialect.name,
            "pool_size": self.engine.pool.size() if hasattr(self.engine.pool, 'size') else "N/A",
            "pool_checked_in": self.engine.pool.checkedin() if hasattr(self.engine.pool, 'checkedin') else "N/A",
            "pool_checked_out": self.engine.pool.checkedout() if hasattr(self.engine.pool, 'checkedout') else "N/A"
        }


# 전역 데이터베이스 매니저 인스턴스
_global_db_manager = None

def get_db_manager(config=None) -> DatabaseManager:
    """
    전역 데이터베이스 매니저 인스턴스 반환 (싱글톤)
    
    Args:
        config: 환경 설정 객체
    
    Returns:
        DatabaseManager: 데이터베이스 매니저 인스턴스
    """
    global _global_db_manager
    if _global_db_manager is None:
        _global_db_manager = DatabaseManager(config)
    return _global_db_manager

def reload_db_manager(config=None) -> DatabaseManager:
    """
    데이터베이스 매니저 재로드
    
    Args:
        config: 환경 설정 객체
    
    Returns:
        DatabaseManager: 새로운 데이터베이스 매니저 인스턴스
    """
    global _global_db_manager
    _global_db_manager = DatabaseManager(config)
    return _global_db_manager

# 편의 함수들
def get_db_session() -> Optional[Session]:
    """데이터베이스 세션 반환"""
    return get_db_manager().get_session()

def get_db_dependency() -> Generator[Session, None, None]:
    """FastAPI 의존성용 세션 제너레이터"""
    yield from get_db_manager().get_db_dependency()

def get_session_context():
    """컨텍스트 매니저 세션"""
    return get_db_manager().get_session_context()

def test_db_connection() -> bool:
    """데이터베이스 연결 테스트"""
    return get_db_manager().test_connection()

def create_all_tables():
    """모든 테이블 생성"""
    return get_db_manager().create_tables()

def get_engine_and_session():
    """
    기존 코드 호환성을 위한 엔진과 세션 반환
    
    Returns:
        tuple: (engine, SessionLocal)
    """
    db_manager = get_db_manager()
    return db_manager.engine, db_manager.SessionLocal

def get_mysql_connector_engine_and_session():
    """
    MySQL Connector 엔진과 세션 반환 (기존 코드 호환성용)
    
    Returns:
        tuple: (engine, SessionLocal)
    """
    return get_db_manager().get_mysql_connector_engine()

# 기존 코드와의 호환성을 위한 변수들
engine, SessionLocal = get_engine_and_session()

# 기존 코드와의 호환성을 위한 함수 별칭
get_session = get_db_session  # get_session -> get_db_session 별칭



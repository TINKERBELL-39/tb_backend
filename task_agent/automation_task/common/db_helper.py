"""
데이터베이스 헬퍼 공통 모듈 v2
공통 모듈의 database를 활용하여 데이터베이스 작업 수행
"""

import sys
import os
from typing import Dict, Any, Optional, List
import logging

from shared_modules.database import get_session, engine
from shared_modules.db_models import User, Conversation, Message, AutomationTask
from shared_modules.env_config import get_config

logger = logging.getLogger(__name__)

from contextlib import contextmanager

class AutomationDatabaseHelper:
    """자동화 작업을 위한 데이터베이스 헬퍼 클래스 (공통 모듈 기반)"""
    
    def __init__(self):
        """데이터베이스 헬퍼 초기화"""
        self.config = get_config()
        
    @contextmanager
    def session_scope(self):
        """데이터베이스 세션 컨텍스트 매니저"""
        session = get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"데이터베이스 작업 실패: {e}")
            raise
        finally:
            session.close()
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """사용자 ID로 사용자 정보 조회"""
        try:
            with self.session_scope() as session:
                user = session.query(User).filter(User.user_id == user_id).first()
                if not user:
                    return None
                return {
                    "user_id": user.user_id,
                    "email": user.email,
                    "nickname": user.nickname,
                    "business_type": user.business_type,
                    "created_at": user.created_at,
                    "admin": user.admin
                }
        except Exception as e:
            logger.error(f"사용자 조회 실패 (user_id={user_id}): {e}")
            return None
    
    async def get_user_email(self, user_id: int) -> Optional[str]:
        """사용자 이메일 주소 조회"""
        user = await self.get_user_by_id(user_id)
        return user.get("email") if user else None
    
    async def get_user_phone(self, user_id: int) -> Optional[str]:
        """사용자 전화번호 조회"""
        user = await self.get_user_by_id(user_id)
        return user.get("phone_number") if user else None
    
    async def get_automation_task_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        """자동화 작업 ID로 작업 정보 조회"""
        try:
            with self.session_scope() as session:
                task = session.query(AutomationTask).filter(AutomationTask.task_id == task_id).first()
                if not task:
                    return None
                return {
                    "task_id": task.task_id,
                    "user_id": task.user_id,
                    "conversation_id": task.conversation_id,
                    "task_type": task.task_type,
                    "title": task.title,
                    "task_data": task.task_data,
                    "status": task.status,
                    "scheduled_at": task.scheduled_at,
                    "executed_at": task.executed_at,
                    "created_at": task.created_at
                }
        except Exception as e:
            logger.error(f"자동화 작업 조회 실패 (task_id={task_id}): {e}")
            return None
    
    async def update_automation_task_status(self, task_id: int, status: str, 
                                          executed_at: Optional[Any] = None,
                                          result_data: Optional[Dict[str, Any]] = None) -> bool:
        """자동화 작업 상태 업데이트"""
        try:
            with self.session_scope() as session:
                task = session.query(AutomationTask).filter(AutomationTask.task_id == task_id).first()
                if not task:
                    logger.warning(f"자동화 작업을 찾을 수 없음 (task_id={task_id})")
                    return False
                
                task.status = status
                if executed_at:
                    task.executed_at = executed_at
                
                if result_data:
                    if task.task_data is None:
                        task.task_data = {}
                    task.task_data.update({"result": result_data})
                
                logger.info(f"자동화 작업 상태 업데이트 완료 (task_id={task_id}, status={status})")
                return True
        except Exception as e:
            logger.error(f"자동화 작업 상태 업데이트 실패 (task_id={task_id}, status={status}): {e}")
            return False
    
    async def get_pending_automation_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """대기 중인 자동화 작업 목록 조회"""
        try:
            with self.session_scope() as session:
                tasks = session.query(AutomationTask)\
                              .filter(AutomationTask.status == 'pending')\
                              .order_by(AutomationTask.created_at.asc())\
                              .limit(limit)\
                              .all()
                
                return [{
                    "task_id": task.task_id,
                    "user_id": task.user_id,
                    "conversation_id": task.conversation_id,
                    "task_type": task.task_type,
                    "title": task.title,
                    "task_data": task.task_data,
                    "status": task.status,
                    "scheduled_at": task.scheduled_at,
                    "created_at": task.created_at
                } for task in tasks]
        except Exception as e:
            logger.error(f"대기 중인 자동화 작업 조회 실패 (limit={limit}): {e}")
            return []

    async def get_user_automation_tasks(self, user_id: int, status: Optional[str] = None, 
                                      limit: int = 50) -> List[Dict[str, Any]]:
        """사용자의 자동화 작업 목록 조회"""
        try:
            with self.session_scope() as session:
                query = session.query(AutomationTask).filter(AutomationTask.user_id == user_id)
                
                if status:
                    query = query.filter(AutomationTask.status == status)
                
                tasks = query.order_by(AutomationTask.created_at.desc()).limit(limit).all()
                
                return [{
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "title": task.title,
                    "status": task.status,
                    "scheduled_at": task.scheduled_at,
                    "executed_at": task.executed_at,
                    "created_at": task.created_at
                } for task in tasks]
        except Exception as e:
            logger.error(f"사용자 자동화 작업 조회 실패 (user_id={user_id}, status={status}): {e}")
            return []
    
    async def save_automation_log(self, task_id: int, log_type: str, 
                                message: str, success: bool, 
                                error_message: Optional[str] = None) -> bool:
        """자동화 작업 로그 저장"""
        try:
            with self.session_scope() as session:
                from datetime import datetime
                from sqlalchemy import text
                
                log_query = text("""
                    INSERT INTO automation_logs 
                    (task_id, log_type, message, success, error_message, created_at)
                    VALUES (:task_id, :log_type, :message, :success, :error_message, :created_at)
                """)
                
                session.execute(log_query, {
                    "task_id": task_id,
                    "log_type": log_type,
                    "message": message,
                    "success": success,
                    "error_message": error_message,
                    "created_at": datetime.now()
                })
                return True
        except Exception as e:
            logger.debug(f"자동화 로그 저장 실패 (task_id={task_id}, log_type={log_type}): {e}")
            return False
    
    async def get_conversation_context(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """대화 컨텍스트 조회"""
        try:
            with self.session_scope() as session:
                conversation = session.query(Conversation)\
                                     .filter(Conversation.conversation_id == conversation_id)\
                                     .first()
                
                if not conversation:
                    return None
                    
                return {
                    "conversation_id": conversation.conversation_id,
                    "user_id": conversation.user_id,
                    "started_at": conversation.started_at,
                    "ended_at": conversation.ended_at,
                    "is_visible": conversation.is_visible
                }
        except Exception as e:
            logger.error(f"대화 컨텍스트 조회 실패 (conversation_id={conversation_id}): {e}")
            return None
    
    async def get_recent_messages(self, conversation_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """최근 메시지 목록 조회"""
        try:
            with self.session_scope() as session:
                messages = session.query(Message)\
                                 .filter(Message.conversation_id == conversation_id)\
                                 .order_by(Message.created_at.desc())\
                                 .limit(limit)\
                                 .all()
                
                return [{
                    "message_id": msg.message_id,
                    "sender_type": msg.sender_type,
                    "agent_type": msg.agent_type,
                    "content": msg.content,
                    "created_at": msg.created_at
                } for msg in messages]
        except Exception as e:
            logger.error(f"최근 메시지 조회 실패 (conversation_id={conversation_id}, limit={limit}): {e}")
            return []

    async def check_user_permissions(self, user_id: int, permission: str) -> bool:
        """사용자 권한 확인"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        # 관리자는 모든 권한 허용
        if user.get("admin", False):
            return True
        
        # 기본적으로는 모든 사용자에게 자동화 권한 허용
        # 추후 세분화된 권한 체계 구현 가능
        allowed_permissions = [
            "automation_create",
            "automation_read",
            "automation_update",
            "automation_delete"
        ]
        
        return permission in allowed_permissions
    
    def health_check(self) -> bool:
        """데이터베이스 연결 상태 확인"""
        try:
            if not engine:
                return False
            
            with engine.connect() as connection:
                from sqlalchemy import text
                connection.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"데이터베이스 연결 확인 실패: {e}")
            return False
    
    async def get_task_statistics(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """작업 통계 조회"""
        try:
            with self.session_scope() as session:
                from sqlalchemy import func
                
                query = session.query(
                    AutomationTask.status,
                    func.count(AutomationTask.task_id).label('count')
                )
                
                if user_id:
                    query = query.filter(AutomationTask.user_id == user_id)
                
                stats = query.group_by(AutomationTask.status).all()
                
                result = {
                    "total": 0,
                    "pending": 0,
                    "processing": 0,
                    "success": 0,
                    "failed": 0,
                    "cancelled": 0
                }
                
                for status, count in stats:
                    result[status] = count
                    result["total"] += count
                
                return result
        except Exception as e:
            logger.error(f"작업 통계 조회 실패 (user_id={user_id}): {e}")
            return {}
        
    async def save_keyword_analysis(self, user_id: int, keyword: str, platform: str, analysis_data: dict) -> bool:
        """키워드 분석 결과 저장

        Args:
            user_id: 사용자 ID
            keyword: 분석할 키워드
            platform: 플랫폼 정보
            analysis_data: 분석 데이터 (JSON)

        Returns:
            bool: 저장 성공 여부
        """
        try:
            with self.session_scope() as session:
                from sqlalchemy import text
                query = text("""
                    INSERT INTO pantaDB.keyword 
                    (user_id, keyword, platform, analysis_data) 
                    VALUES (:user_id, :keyword, :platform, :analysis_data)
                """)
                
                session.execute(query, {
                    "user_id": user_id,
                    "keyword": keyword,
                    "platform": platform,
                    "analysis_data": analysis_data
                })
                return True
                
        except Exception as e:
            logger.error(f"키워드 분석 결과 저장 실패: {str(e)}")
            return False

    async def get_keyword_history(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 10,
        keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """키워드 분석 히스토리 조회

        Args:
            user_id: 사용자 ID
            page: 페이지 번호
            limit: 페이지당 결과 수
            keyword: 검색할 키워드 (선택사항)

        Returns:
            Dict: {
                'total': 전체 결과 수,
                'items': 키워드 분석 결과 목록
            }
        """
        try:
            with self.session_scope() as session:
                from sqlalchemy import text
                
                # 기본 WHERE 절
                where_clause = "WHERE user_id = :user_id"
                params = {"user_id": user_id}
                
                # 키워드 검색 조건 추가
                if keyword:
                    where_clause += " AND keyword LIKE :keyword"
                    params["keyword"] = f"%{keyword}%"
                
                # 전체 결과 수 조회
                count_query = text(f"SELECT COUNT(*) FROM pantaDB.keyword {where_clause}")
                total = session.execute(count_query, params).scalar()
                
                # 페이지네이션 파라미터 추가
                params["limit"] = limit
                params["offset"] = (page - 1) * limit
                
                # 결과 조회
                query = text(f"""
                    SELECT id, user_id, keyword, platform, analysis_data, created_at 
                    FROM pantaDB.keyword 
                    {where_clause}
                    ORDER BY created_at DESC 
                    LIMIT :limit OFFSET :offset
                """)
                
                rows = session.execute(query, params).fetchall()
                
                items = [
                    {
                        "id": row.id,
                        "user_id": row.user_id,
                        "keyword": row.keyword,
                        "platform": row.platform,
                        "analysis_data": row.analysis_data,
                        "created_at": row.created_at.isoformat() if row.created_at else None
                    }
                    for row in rows
                ]
                
                return {
                    "total": total,
                    "items": items
                }
                
        except Exception as e:
            logger.error(f"키워드 히스토리 조회 실패: {str(e)}")
            return {"total": 0, "items": []}

    async def save_blog_content(self, keyword: str, content: Dict[str, Any], template: str) -> bool:
        """블로그 컨텐츠 저장"""
        try:
            with self.session_scope() as session:
                from sqlalchemy import text
                query = text("""
                    INSERT INTO blog_contents 
                    (keyword, content, template, created_at)
                    VALUES (:keyword, :content, :template, NOW())
                """)
                
                session.execute(query, {
                    "keyword": keyword,
                    "content": content,
                    "template": template
                })
                return True
        except Exception as e:
            logger.error(f"블로그 컨텐츠 저장 실패: {str(e)}")
            return False

    async def get_content_history(
        self,
        page: int = 1,
        limit: int = 10,
        keyword: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """블로그 컨텐츠 히스토리 조회"""
        try:
            with self.session_scope() as session:
                from sqlalchemy import text
                
                where_clause = "WHERE 1=1"
                params = {}
                
                if keyword:
                    where_clause += " AND keyword LIKE :keyword"
                    params["keyword"] = f"%{keyword}%"
                
                if status:
                    where_clause += " AND status = :status"
                    params["status"] = status
                
                count_query = text(f"SELECT COUNT(*) FROM blog_contents {where_clause}")
                total = session.execute(count_query, params).scalar()
                
                params["limit"] = limit
                params["offset"] = (page - 1) * limit
                
                query = text(f"""
                    SELECT id, keyword, content, template, status, created_at 
                    FROM blog_contents 
                    {where_clause}
                    ORDER BY created_at DESC 
                    LIMIT :limit OFFSET :offset
                """)
                
                rows = session.execute(query, params).fetchall()
                
                items = [
                    {
                        "id": row.id,
                        "keyword": row.keyword,
                        "content": row.content,
                        "template": row.template,
                        "status": row.status,
                        "created_at": row.created_at.isoformat() if row.created_at else None
                    }
                    for row in rows
                ]
                
                return {
                    "total": total,
                    "items": items
                }
        except Exception as e:
            logger.error(f"블로그 컨텐츠 히스토리 조회 실패: {str(e)}")
            return {"total": 0, "items": []}

    async def get_content_detail(self, content_id: str) -> Optional[Dict[str, Any]]:
        """블로그 컨텐츠 상세 조회"""
        try:
            with self.session_scope() as session:
                from sqlalchemy import text
                query = text("""
                    SELECT id, keyword, content, template, status, created_at 
                    FROM blog_contents 
                    WHERE id = :content_id
                """)
                
                row = session.execute(query, {"content_id": content_id}).first()
                if not row:
                    return None
                    
                return {
                    "id": row.id,
                    "keyword": row.keyword,
                    "content": row.content,
                    "template": row.template,
                    "status": row.status,
                    "created_at": row.created_at.isoformat() if row.created_at else None
                }
        except Exception as e:
            logger.error(f"블로그 컨텐츠 상세 조회 실패: {str(e)}")
            return None

    async def update_content_status(self, content_id: str, status: str) -> bool:
        """블로그 컨텐츠 상태 업데이트"""
        try:
            with self.session_scope() as session:
                from sqlalchemy import text
                query = text("""
                    UPDATE blog_contents
                    SET status = :status, updated_at = NOW()
                    WHERE id = :content_id
                """)
                
                session.execute(query, {
                    "content_id": content_id,
                    "status": status
                })
                return True
        except Exception as e:
            logger.error(f"블로그 컨텐츠 상태 업데이트 실패: {str(e)}")
            return False

# 전역 인스턴스
_automation_db_helper = None

def get_automation_db_helper() -> AutomationDatabaseHelper:
    """AutomationDatabaseHelper 싱글톤 인스턴스 반환"""
    global _automation_db_helper
    if _automation_db_helper is None:
        _automation_db_helper = AutomationDatabaseHelper()
    return _automation_db_helper

# 편의 함수들
async def get_user_email(user_id: int) -> Optional[str]:
    """사용자 이메일 조회 (편의 함수)"""
    return await get_automation_db_helper().get_user_email(user_id)

async def get_automation_task(task_id: int) -> Optional[Dict[str, Any]]:
    """자동화 작업 조회 (편의 함수)"""
    return await get_automation_db_helper().get_automation_task_by_id(task_id)

async def update_task_status(task_id: int, status: str, **kwargs) -> bool:
    """작업 상태 업데이트 (편의 함수)"""
    return await get_automation_db_helper().update_automation_task_status(task_id, status, **kwargs)

# 키워드 분석 관련 함수들
async def save_keyword_analysis(user_id: int, keyword: str, platform: str, analysis_data: dict) -> bool:
    """키워드 분석 결과 저장 (편의 함수)"""
    return await get_automation_db_helper().save_keyword_analysis(user_id, keyword, platform, analysis_data)

async def get_keyword_history(
        user_id: int,
        page: int = 1,
        limit: int = 10,
        keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """키워드 분석 히스토리 조회 (편의 함수)"""
        return await get_automation_db_helper().get_keyword_history(user_id, page, limit, keyword)

# 블로그 컨텐츠 관련 메서드
async def save_blog_content(keyword: str, content: Dict[str, Any], template: str) -> bool:
    """블로그 컨텐츠 저장"""
    try:
        with get_automation_db_helper().session_scope() as session:
            from sqlalchemy import text
            query = text("""
                INSERT INTO blog_contents 
                (keyword, content, template, created_at)
                VALUES (:keyword, :content, :template, NOW())
            """)
            
            session.execute(query, {
                "keyword": keyword,
                "content": content,
                "template": template
            })
            return True
    except Exception as e:
        logger.error(f"블로그 컨텐츠 저장 실패: {str(e)}")
        return False

async def get_content_history(
    page: int = 1,
    limit: int = 10,
    keyword: Optional[str] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """블로그 컨텐츠 히스토리 조회"""
    try:
        with get_automation_db_helper().session_scope() as session:
            from sqlalchemy import text
            
            where_clause = "WHERE 1=1"
            params = {}
            
            if keyword:
                where_clause += " AND keyword LIKE :keyword"
                params["keyword"] = f"%{keyword}%"
            
            if status:
                where_clause += " AND status = :status"
                params["status"] = status
            
            count_query = text(f"SELECT COUNT(*) FROM blog_contents {where_clause}")
            total = session.execute(count_query, params).scalar()
            
            params["limit"] = limit
            params["offset"] = (page - 1) * limit
            
            query = text(f"""
                SELECT id, keyword, content, template, status, created_at 
                FROM blog_contents 
                {where_clause}
                ORDER BY created_at DESC 
                LIMIT :limit OFFSET :offset
            """)
            
            rows = session.execute(query, params).fetchall()
            
            items = [
                {
                    "id": row.id,
                    "keyword": row.keyword,
                    "content": row.content,
                    "template": row.template,
                    "status": row.status,
                    "created_at": row.created_at.isoformat() if row.created_at else None
                }
                for row in rows
            ]
            
            return {
                "total": total,
                "items": items
            }
    except Exception as e:
        logger.error(f"블로그 컨텐츠 히스토리 조회 실패: {str(e)}")
        return {"total": 0, "items": []}

async def get_content_detail(content_id: str) -> Optional[Dict[str, Any]]:
    """블로그 컨텐츠 상세 조회"""
    try:
        with get_automation_db_helper().session_scope() as session:
            from sqlalchemy import text
            query = text("""
                SELECT id, keyword, content, template, status, created_at 
                FROM blog_contents 
                WHERE id = :content_id
            """)
            
            row = session.execute(query, {"content_id": content_id}).first()
            if not row:
                return None
                
            return {
                "id": row.id,
                "keyword": row.keyword,
                "content": row.content,
                "template": row.template,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None
            }
    except Exception as e:
        logger.error(f"블로그 컨텐츠 상세 조회 실패: {str(e)}")
        return None

# 기존 코드와의 호환성을 위한 별칭
DatabaseHelper = AutomationDatabaseHelper
get_db_helper = get_automation_db_helper

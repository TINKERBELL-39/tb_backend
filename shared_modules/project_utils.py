"""
프로젝트 자동 저장 유틸리티
사업 기획서와 마케팅 전략 완료 시 자동으로 Project와 ProjectDocument 테이블에 저장
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# shared_modules import
from shared_modules.db_models import Project, ProjectDocument
from shared_modules.database import get_session_context

logger = logging.getLogger(__name__)

def create_project(db: Session, user_id: int, title: str, description: str = None, 
                  category: str = None) -> Optional[Project]:
    """
    프로젝트 생성
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        title: 프로젝트 제목
        description: 프로젝트 설명
        category: 프로젝트 카테고리 (business_plan, marketing_strategy 등)
    
    Returns:
        Project: 생성된 프로젝트 객체 또는 None
    """
    try:
        project = Project(
            user_id=user_id,
            title=title,
            description=description,
            category=category,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        logger.info(f"프로젝트 생성 완료: ID={project.id}, 제목='{title}', 카테고리={category}")
        return project
        
    except SQLAlchemyError as e:
        logger.error(f"프로젝트 생성 실패: {e}")
        db.rollback()
        return None

def create_project_document(db: Session, user_id: int, project_id: int, 
                          file_name: str, content: str, conversation_id: int = None) -> Optional[ProjectDocument]:
    """
    프로젝트 문서 생성
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        project_id: 프로젝트 ID
        file_name: 파일명
        content: 문서 내용
        conversation_id: 대화 ID (선택)
    
    Returns:
        ProjectDocument: 생성된 문서 객체 또는 None
    """
    try:
        # 내용을 파일로 저장하는 대신 JSON으로 저장
        file_path = json.dumps({
            "content": content,
            "created_at": datetime.now().isoformat(),
            "type": "auto_generated"
        })
        
        document = ProjectDocument(
            conversation_id=conversation_id,
            user_id=user_id,
            project_id=project_id,
            file_name=file_name,
            file_path=file_path,
            uploaded_at=datetime.now()
        )
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        logger.info(f"프로젝트 문서 생성 완료: ID={document.document_id}, 파일명='{file_name}'")
        return document
        
    except SQLAlchemyError as e:
        logger.error(f"프로젝트 문서 생성 실패: {e}")
        db.rollback()
        return None

def save_business_plan_as_project(user_id: int, conversation_id: int, business_plan_content: str, 
                                business_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    사업 기획서를 프로젝트로 저장
    
    Args:
        user_id: 사용자 ID
        conversation_id: 대화 ID
        business_plan_content: 사업 기획서 내용
        business_info: 수집된 비즈니스 정보
    
    Returns:
        Dict: 저장 결과 {"success": bool, "project_id": int, "document_id": int}
    """
    try:
        with get_session_context() as db:
            # 프로젝트 제목 생성
            business_type = business_info.get("business_type", "일반") if business_info else "일반"
            title = f"사업 기획서 - {business_type} ({datetime.now().strftime('%Y-%m-%d')})"
            
            # 프로젝트 설명 생성
            description = "AI 에이전트가 생성한 사업 기획서"
            if business_info:
                desc_parts = []
                if business_info.get("main_goal"):
                    desc_parts.append(f"목표: {business_info['main_goal']}")
                if business_info.get("target_audience"):
                    desc_parts.append(f"타겟: {business_info['target_audience']}")
                if desc_parts:
                    description += " - " + ", ".join(desc_parts)
            
            # 프로젝트 생성
            project = create_project(
                db=db,
                user_id=user_id,
                title=title,
                description=description,
                category="business_plan"
            )
            
            if not project:
                return {"success": False, "error": "프로젝트 생성 실패"}
            
            # 문서 생성
            file_name = f"business_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            document = create_project_document(
                db=db,
                user_id=user_id,
                project_id=project.id,
                file_name=file_name,
                content=business_plan_content,
                conversation_id=conversation_id
            )
            
            if not document:
                return {"success": False, "error": "문서 생성 실패"}
            
            logger.info(f"사업 기획서 프로젝트 저장 완료: project_id={project.id}, document_id={document.document_id}")
            
            return {
                "success": True,
                "project_id": project.id,
                "document_id": document.document_id,
                "title": title,
                "file_name": file_name
            }
            
    except Exception as e:
        logger.error(f"사업 기획서 프로젝트 저장 실패: {e}")
        return {"success": False, "error": str(e)}

def save_marketing_strategy_as_project(user_id: int, conversation_id: int, 
                                     marketing_strategy_content: str, 
                                     marketing_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    마케팅 전략을 프로젝트로 저장
    
    Args:
        user_id: 사용자 ID
        conversation_id: 대화 ID
        marketing_strategy_content: 마케팅 전략 내용
        marketing_info: 수집된 마케팅 정보
    
    Returns:
        Dict: 저장 결과 {"success": bool, "project_id": int, "document_id": int}
    """
    try:
        with get_session_context() as db:
            # 프로젝트 제목 생성
            business_type = marketing_info.get("business_type", "일반") if marketing_info else "일반"
            title = f"마케팅 전략 - {business_type} ({datetime.now().strftime('%Y-%m-%d')})"
            
            # 프로젝트 설명 생성
            description = "AI 에이전트가 생성한 마케팅 전략"
            if marketing_info:
                desc_parts = []
                if marketing_info.get("main_goal"):
                    desc_parts.append(f"목표: {marketing_info['main_goal']}")
                if marketing_info.get("channels"):
                    desc_parts.append(f"채널: {marketing_info['channels']}")
                if marketing_info.get("target_audience"):
                    desc_parts.append(f"타겟: {marketing_info['target_audience']}")
                if desc_parts:
                    description += " - " + ", ".join(desc_parts)
            
            # 프로젝트 생성
            project = create_project(
                db=db,
                user_id=user_id,
                title=title,
                description=description,
                category="marketing_strategy"
            )
            
            if not project:
                return {"success": False, "error": "프로젝트 생성 실패"}
            
            # 문서 생성
            file_name = f"marketing_strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            document = create_project_document(
                db=db,
                user_id=user_id,
                project_id=project.id,
                file_name=file_name,
                content=marketing_strategy_content,
                conversation_id=conversation_id
            )
            
            if not document:
                return {"success": False, "error": "문서 생성 실패"}
            
            logger.info(f"마케팅 전략 프로젝트 저장 완료: project_id={project.id}, document_id={document.document_id}")
            
            return {
                "success": True,
                "project_id": project.id,
                "document_id": document.document_id,
                "title": title,
                "file_name": file_name
            }
            
    except Exception as e:
        logger.error(f"마케팅 전략 프로젝트 저장 실패: {e}")
        return {"success": False, "error": str(e)}

def get_user_projects(db: Session, user_id: int, category: str = None, limit: int = 50) -> list:
    """
    사용자 프로젝트 목록 조회
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        category: 프로젝트 카테고리 필터 (선택)
        limit: 조회 개수 제한
    
    Returns:
        list: 프로젝트 목록
    """
    try:
        query = db.query(Project).filter(Project.user_id == user_id)
        if category:
            query = query.filter(Project.category == category)
        
        projects = query.order_by(Project.created_at.desc()).limit(limit).all()
        
        logger.info(f"사용자 프로젝트 조회 완료: user_id={user_id}, 조회된 개수={len(projects)}")
        return projects
        
    except SQLAlchemyError as e:
        logger.error(f"사용자 프로젝트 조회 실패: {e}")
        return []

def get_project_documents(db: Session, project_id: int) -> list:
    """
    프로젝트 문서 목록 조회
    
    Args:
        db: 데이터베이스 세션
        project_id: 프로젝트 ID
    
    Returns:
        list: 문서 목록
    """
    try:
        documents = db.query(ProjectDocument).filter(
            ProjectDocument.project_id == project_id
        ).order_by(ProjectDocument.uploaded_at.desc()).all()
        
        logger.info(f"프로젝트 문서 조회 완료: project_id={project_id}, 문서 개수={len(documents)}")
        return documents
        
    except SQLAlchemyError as e:
        logger.error(f"프로젝트 문서 조회 실패: {e}")
        return []

def check_project_completion(conversation_id: int, stage: str) -> bool:
    """
    프로젝트 완료 상태 확인
    
    Args:
        conversation_id: 대화 ID
        stage: 현재 단계
    
    Returns:
        bool: 완료 여부
    """
    # 사업 기획서 완료 조건
    if stage == "최종 기획서 작성":
        return True
    
    # 마케팅 전략 완료 조건 (단계가 "전략" 이상이고 충분한 정보가 수집된 경우)
    if stage in ["전략", "콘텐츠 생성", "완료"]:
        return True
    
    return False

def auto_save_completed_project(user_id: int, conversation_id: int, content: str, 
                               project_type: str, additional_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    완료된 프로젝트 자동 저장 (통합 함수)
    
    Args:
        user_id: 사용자 ID
        conversation_id: 대화 ID
        content: 프로젝트 내용
        project_type: 프로젝트 타입 ("business_plan" 또는 "marketing_strategy")
        additional_info: 추가 정보
    
    Returns:
        Dict: 저장 결과
    """
    try:
        if project_type == "business_plan":
            return save_business_plan_as_project(
                user_id=user_id,
                conversation_id=conversation_id,
                business_plan_content=content,
                business_info=additional_info
            )
        elif project_type == "marketing_strategy":
            return save_marketing_strategy_as_project(
                user_id=user_id,
                conversation_id=conversation_id,
                marketing_strategy_content=content,
                marketing_info=additional_info
            )
        else:
            logger.error(f"지원하지 않는 프로젝트 타입: {project_type}")
            return {"success": False, "error": "지원하지 않는 프로젝트 타입"}
            
    except Exception as e:
        logger.error(f"자동 프로젝트 저장 실패: {e}")
        return {"success": False, "error": str(e)}

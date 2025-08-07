"""
데이터베이스 쿼리 함수 모음 v6
Fully qualified path 사용으로 SQLAlchemy 충돌 완전 해결
"""

from sqlalchemy.orm import Session
from datetime import datetime
import logging
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import bindparam, text
from shared_modules.database import DatabaseManager
from typing import Optional, List
from sqlalchemy import or_
from task_agent.models import TaskTypeEnum

# SQLAlchemy 충돌 방지를 위해 fully qualified import 사용
import shared_modules.db_models as db_models

engine = DatabaseManager().engine
logger = logging.getLogger(__name__)

# -------------------
# User 관련 함수 (새 DDL 스키마 적용)
# -------------------
# queries.py의 create_user_social 함수를 다음과 같이 수정하세요:

def create_user_social(db: Session, provider: str, social_id: str, email: str, 
                      nickname: str = "", 
                      access_token: str = "", 
                      refresh_token: str = None,
                      business_type: str = None,
                      experience: int =None,
                      admin: bool = False):
    """소셜 로그인 사용자 생성 (새 DDL 스키마) - 파라미터 순서 수정"""
    try:
        # 🔍 디버깅 로그 추가
        logger.info(f"create_user_social 함수 호출:")
        logger.info(f"  - provider: {provider}")
        logger.info(f"  - social_id: {social_id}")
        logger.info(f"  - email: {email}")
        logger.info(f"  - nickname: {nickname}")
        logger.info(f"  - business_type: {business_type}")
        logger.info(f"  - experience: {experience}")
        
        user = db_models.User(
            email=email,
            nickname=nickname or email.split('@')[0],
            business_type=business_type,
            provider=provider,
            social_id=social_id,
            admin=admin,
            experience=experience,  # 🔧 이 필드가 제대로 설정되도록 수정
            access_token=access_token,
            refresh_token=refresh_token
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # 🔍 생성 후 확인 로그
        logger.info(f"사용자 생성 완료:")
        logger.info(f"  - user_id: {user.user_id}")
        logger.info(f"  - nickname: {user.nickname}")
        logger.info(f"  - business_type: {user.business_type}")
        logger.info(f"  - experience: {user.experience}")
        
        return user
        
    except Exception as e:
        logger.error(f"[create_user_social 오류] {e}", exc_info=True)
        db.rollback()
        return None

def get_user_by_email(db: Session, email: str):
    try:
        return db.query(db_models.User).filter(db_models.User.email == email).first()
    except Exception as e:
        logger.error(f"[get_user_by_email 오류] {e}", exc_info=True)
        return None

def get_user_by_id(db: Session, user_id: int):
    try:
        return db.query(db_models.User).filter(db_models.User.user_id == user_id).first()
    except Exception as e:
        logger.error(f"[get_user_by_id 오류] {e}", exc_info=True)
        return None

def get_user_by_social(db: Session, provider: str, social_id: str):
    try:
        return db.query(db_models.User).filter(
            db_models.User.provider == provider, 
            db_models.User.social_id == social_id
        ).first()
    except Exception as e:
        logger.error(f"[get_user_by_social 오류] {e}", exc_info=True)
        return None

def update_user_tokens(db: Session, user_id: int, access_token: str, refresh_token: str = None) -> bool:
    """사용자 토큰 업데이트"""
    try:
        user = db.query(db_models.User).filter(db_models.User.user_id == user_id).first()
        if user:
            user.access_token = access_token
            if refresh_token:
                user.refresh_token = refresh_token
            db.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"[update_user_tokens 오류] {e}", exc_info=True)
        db.rollback()
        return False

def update_user_experience(db: Session, user_id: int, experience: int) -> bool:
    """사용자 경험 여부 업데이트"""
    try:
        user = db.query(db_models.User).filter(db_models.User.user_id == user_id).first()
        if user:
            user.experience = experience
            db.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"[update_user_experience 오류] {e}", exc_info=True)
        db.rollback()
        return False

# -------------------
# FAQ 관련 함수 (새로 추가)
# -------------------
def create_faq(db: Session, category: str, question: str):
    """FAQ 생성"""
    try:
        faq = db_models.FAQ(
            category=category,
            question=question,
            view_count=0,
            is_active=True
        )
        db.add(faq)
        db.commit()
        db.refresh(faq)
        return faq
    except Exception as e:
        logger.error(f"[create_faq 오류] {e}", exc_info=True)
        db.rollback()
        return None

def get_faqs_by_category(db: Session, category: str = None, active_only: bool = True) -> list:
    """카테고리별 FAQ 조회"""
    try:
        query = db.query(db_models.FAQ)
        if category:
            query = query.filter(db_models.FAQ.category == category)
        if active_only:
            query = query.filter(db_models.FAQ.is_active == True)
        return query.order_by(db_models.FAQ.view_count.desc()).all()
    except Exception as e:
        logger.error(f"[get_faqs_by_category 오류] {e}", exc_info=True)
        return []

def increment_faq_view(db: Session, faq_id: int) -> bool:
    """FAQ 조회수 증가"""
    try:
        faq = db.query(db_models.FAQ).filter(db_models.FAQ.faq_id == faq_id).first()
        if faq:
            faq.view_count += 1
            db.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"[increment_faq_view 오류] {e}", exc_info=True)
        db.rollback()
        return False

# -------------------
# Conversation 관련 함수
# -------------------
def check_database_connection(db: Session) -> bool:
    """데이터베이스 연결 상태 확인"""
    try:
        # 간단한 쿼리로 연결 테스트
        result = db.execute(text("SELECT 1")).fetchone()
        if result and result[0] == 1:
            logger.info("[check_database_connection] 데이터베이스 연결 정상")
            return True
        else:
            logger.error("[check_database_connection] 데이터베이스 연결 실패")
            return False
    except Exception as e:
        logger.error(f"[check_database_connection] 연결 테스트 오류: {e}")
        return False

def ensure_test_user(db: Session, user_id: int):
    """테스트용 사용자가 존재하지 않으면 생성"""
    try:
        user = db.query(db_models.User).filter(db_models.User.user_id == user_id).first()
        if user:
            logger.info(f"[ensure_test_user] 사용자 존재: {user.email}")
            return user
            
        # 이메일로 조회
        email = f"test_user_{user_id}@example.com"
        user = db.query(db_models.User).filter(db_models.User.email == email).first()
        if user:
            logger.info(f"[ensure_test_user] 이메일로 사용자 찾음: {email}")
            return user
        
        # 테스트 사용자 생성
        logger.warning(f"[ensure_test_user] 사용자 ID {user_id} 없음. 테스트 사용자 생성 중...")
        
        test_user = db_models.User(
            email=f"test_user_{user_id}@example.com",
            nickname=f"TestUser{user_id}",
            business_type="test",
            provider="local",
            social_id=f"test_{user_id}",
            admin=False,
            experience=0,
            access_token=f"test_token_{user_id}",
            refresh_token=None
        )
        
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        logger.info(f"[ensure_test_user] 테스트 사용자 생성 완료: {test_user.email} (ID: {test_user.user_id})")
        return test_user
        
    except Exception as e:
        logger.error(f"[ensure_test_user 오류] {e}", exc_info=True)
        db.rollback()
        return None

def create_conversation(db: Session, user_id: int):
    """대화 생성 - 자세한 로깅 포함"""
    try:
        logger.info(f"[create_conversation] 시작 - user_id: {user_id}")
        
        # 0. 데이터베이스 연결 상태 확인
        if not check_database_connection(db):
            logger.error("[create_conversation] 데이터베이스 연결 실패")
            return None
        
        # 1. 사용자 존재 여부 확인 및 자동 생성
        user = ensure_test_user(db, user_id)
        if not user:
            logger.error(f"[create_conversation] 사용자 생성/조회 실패 - user_id: {user_id}")
            return None
        
        # 실제 사용할 user_id (새로 생성된 경우 다를 수 있음)
        actual_user_id = user.user_id
        logger.info(f"[create_conversation] 사용자 확인됨: {user.email} (ID: {actual_user_id})")
        
        # 2. Conversation 객체 생성
        conversation = db_models.Conversation(
            user_id=actual_user_id,
            started_at=datetime.now(),
            is_visible=True
        )
        logger.info(f"[create_conversation] Conversation 객체 생성됨")
        
        # 3. 데이터베이스에 추가
        db.add(conversation)
        logger.info(f"[create_conversation] DB에 추가됨")
        
        # 4. 커밋
        db.commit()
        logger.info(f"[create_conversation] 커밋 완료")
        
        # 5. 새로고침
        db.refresh(conversation)
        logger.info(f"[create_conversation] 새로고침 완료 - conversation_id: {conversation.conversation_id}")
        
        return conversation
        
    except Exception as e:
        logger.error(f"[create_conversation 상세 오류] {type(e).__name__}: {e}", exc_info=True)
        try:
            db.rollback()
            logger.info(f"[create_conversation] 롤백 완료")
        except Exception as rollback_error:
            logger.error(f"[create_conversation] 롤백 실패: {rollback_error}")
        return None

def get_conversation_by_id(db: Session, conversation_id: int):
    try:
        return db.query(db_models.Conversation).filter(
            db_models.Conversation.conversation_id == conversation_id
        ).first()
    except Exception as e:
        logger.error(f"[get_conversation_by_id 오류] {e}", exc_info=True)
        return None

def get_user_conversations(db: Session, user_id: int, visible_only: bool = True):
    try:
        query = db.query(db_models.Conversation).filter(db_models.Conversation.user_id == user_id)
        if visible_only:
            query = query.filter(db_models.Conversation.is_visible == True)
        return query.order_by(db_models.Conversation.started_at.desc()).all()
    except Exception as e:
        logger.error(f"[get_user_conversations 오류] {e}", exc_info=True)
        return []

def end_conversation(db: Session, conversation_id: int) -> bool:
    try:
        conversation = db.query(db_models.Conversation).filter(
            db_models.Conversation.conversation_id == conversation_id
        ).first()
        if conversation:
            conversation.ended_at = datetime.now()
            db.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"[end_conversation 오류] {e}", exc_info=True)
        db.rollback()
        return False

# -------------------
# Message 관련 함수 (DDL sender_type 제약조건 적용)
# -------------------
def create_message(db: Session, conversation_id: int, sender_type: str, agent_type: str, content: str):
    """메시지 생성 (중복 방지 + DDL 제약조건: sender_type은 'USER' 또는 'AGENT')"""
    try:
        # sender_type을 DDL 제약조건에 맞게 변환
        if sender_type.lower() == 'user':
            sender_type = 'USER'
        elif sender_type.lower() == 'agent':
            sender_type = 'AGENT'

        # **중복 메시지 방지 로직**
        last_msg = (
            db.query(db_models.Message)
            .filter(db_models.Message.conversation_id == conversation_id)
            .order_by(db_models.Message.created_at.desc())
            .first()
        )
        if last_msg and last_msg.content == content and last_msg.sender_type == sender_type:
            logger.info(f"[create_message] 중복 메시지 감지: {content[:30]}...")
            return last_msg

        # 새로운 메시지 생성
        msg = db_models.Message(
            conversation_id=conversation_id,
            sender_type=sender_type,
            agent_type=agent_type,
            content=content
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg
    except Exception as e:
        logger.error(f"[create_message 오류] {e}", exc_info=True)
        db.rollback()
        return None


def get_conversation_messages(db: Session, conversation_id: int, limit: int = 100, offset: int = 0):
    try:
        return db.query(db_models.Message).filter(
            db_models.Message.conversation_id == conversation_id
        ).order_by(db_models.Message.created_at.asc()).offset(offset).limit(limit).all()
    except Exception as e:
        logger.error(f"[get_conversation_messages 오류] {e}", exc_info=True)
        return []

def get_recent_messages(db: Session, conversation_id: int, limit: int = 10):
    try:
        return db.query(db_models.Message).filter(
            db_models.Message.conversation_id == conversation_id
        ).order_by(db_models.Message.created_at.desc()).limit(limit).all()
    except Exception as e:
        logger.error(f"[get_recent_messages 오류] {e}", exc_info=True)
        return []

def get_conversation_history(db: Session, conversation_id: int, limit=6):
    try:
        messages = db.query(db_models.Message).filter(
            db_models.Message.conversation_id == conversation_id
        ).order_by(db_models.Message.message_id).all()
        history = []
        for m in messages[-limit:]:
            prefix = "Human" if m.sender_type == "USER" else "AI"
            history.append(f"{prefix}: {m.content}")
        return "\n".join(history)
    except Exception as e:
        logger.error(f"[get_conversation_history 오류] {e}", exc_info=True)
        return ""

# -------------------
# Feedback 관련 함수 (새로 추가)
# -------------------
def create_feedback(db: Session, user_id: int, rating: int, comment: str = None, conversation_id: int = None):
    """피드백 생성 (rating: 1-5)"""
    try:
        if not (1 <= rating <= 5):
            raise ValueError("Rating must be between 1 and 5")
        
        feedback = db_models.Feedback(
            user_id=user_id,
            conversation_id=conversation_id,
            rating=rating,
            comment=comment
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback
    except Exception as e:
        logger.error(f"[create_feedback 오류] {e}", exc_info=True)
        db.rollback()
        return None

def get_user_feedbacks(db: Session, user_id: int, limit: int = 50):
    """사용자 피드백 조회"""
    try:
        return db.query(db_models.Feedback).filter(
            db_models.Feedback.user_id == user_id
        ).order_by(db_models.Feedback.created_at.desc()).limit(limit).all()
    except Exception as e:
        logger.error(f"[get_user_feedbacks 오류] {e}", exc_info=True)
        return []

def get_average_rating(db: Session, user_id: int = None) -> float:
    """평균 평점 조회"""
    try:
        query = db.query(db_models.Feedback)
        if user_id:
            query = query.filter(db_models.Feedback.user_id == user_id)
        
        feedbacks = query.all()
        if not feedbacks:
            return 0.0
        
        total_rating = sum(f.rating for f in feedbacks)
        return total_rating / len(feedbacks)
    except Exception as e:
        logger.error(f"[get_average_rating 오류] {e}", exc_info=True)
        return 0.0

# -------------------
# PHQ9 관련 함수 (level을 Integer로 수정)
# -------------------
def save_or_update_phq9_result(db: Session, user_id: int, score: int, level: int):
    """PHQ9 결과 저장/업데이트 (level은 Integer)"""
    try:
        now = datetime.now()
        result = db.query(db_models.PHQ9Result).filter_by(user_id=user_id).first()
        if result:
            result.score = score
            result.level = level
            result.updated_at = now
        else:
            result = db_models.PHQ9Result(
                user_id=user_id,
                score=score,
                level=level,
                updated_at=now
            )
            db.add(result)
        db.commit()
        return result
    except Exception as e:
        logger.error(f"[save_or_update_phq9_result 오류] {e}", exc_info=True)
        db.rollback()
        return None

def get_latest_phq9_by_user(db: Session, user_id: int):
    try:
        return db.query(db_models.PHQ9Result).filter_by(user_id=user_id).first()
    except Exception as e:
        logger.error(f"[get_latest_phq9_by_user 오류] {e}", exc_info=True)
        return None
    
def get_user_context_from_db(db: Session, user_id: int):
    phq9 = get_latest_phq9_by_user(db, user_id)
    context_parts = []
    if phq9:
        context_parts.append(
            f"PHQ-9 점수: {phq9.score}점 (레벨: {phq9.level}, {phq9.updated_at.strftime('%Y-%m-%d %H:%M')})"
        )
    return "\n".join(context_parts) if context_parts else "이전 세션 정보 없음"

# -------------------
# Report 관련 함수
# -------------------
def create_report(db: Session, user_id: int, report_type: str, title: str, 
                 content_data: dict = None, file_url: str = None, conversation_id: int = None):
    """리포트 생성"""
    try:
        report = db_models.Report(
            user_id=user_id,
            conversation_id=conversation_id,
            report_type=report_type,
            title=title,
            content_data=content_data,
            file_url=file_url
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report
    except Exception as e:
        logger.error(f"[create_report 오류] {e}", exc_info=True)
        db.rollback()
        return None

def get_user_reports(db: Session, user_id: int, report_type: str = None, limit: int = 50):
    """사용자 리포트 조회"""
    try:
        query = db.query(db_models.Report).filter(db_models.Report.user_id == user_id)
        if report_type:
            query = query.filter(db_models.Report.report_type == report_type)
        return query.order_by(db_models.Report.created_at.desc()).limit(limit).all()
    except Exception as e:
        logger.error(f"[get_user_reports 오류] {e}", exc_info=True)
        return []

def get_report_by_id(db: Session, report_id: int):
    """단일 리포트 조회"""
    try:
        return db.query(db_models.Report).filter(db_models.Report.report_id == report_id).first()
    except Exception as e:
        logger.error(f"[get_report_by_id 오류] {e}", exc_info=True)
        return None
    
# -------------------
# Subscription 관련 함수 (새로 추가)
# -------------------
def create_subscription(db: Session, user_id: int, plan_type: str, monthly_fee: float, 
                       start_date: datetime, end_date: datetime = None):
    """구독 생성 (plan_type: BASIC, PREMIUM, ENTERPRISE)"""
    try:
        if plan_type not in ['BASIC', 'PREMIUM', 'ENTERPRISE']:
            raise ValueError("Invalid plan_type. Must be BASIC, PREMIUM, or ENTERPRISE")
        
        if monthly_fee < 0:
            raise ValueError("Monthly fee must be >= 0")
        
        subscription = db_models.Subscription(
            user_id=user_id,
            plan_type=plan_type,
            monthly_fee=monthly_fee,
            start_date=start_date,
            end_date=end_date
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        return subscription
    except Exception as e:
        logger.error(f"[create_subscription 오류] {e}", exc_info=True)
        db.rollback()
        return None

def get_user_subscription(db: Session, user_id: int):
    """사용자의 활성 구독 조회"""
    try:
        now = datetime.now()
        return db.query(db_models.Subscription).filter(
            db_models.Subscription.user_id == user_id,
            db_models.Subscription.start_date <= now,
            (db_models.Subscription.end_date.is_(None)) | (db_models.Subscription.end_date > now)
        ).first()
    except Exception as e:
        logger.error(f"[get_user_subscription 오류] {e}", exc_info=True)
        return None

def cancel_subscription(db: Session, subscription_id: int) -> bool:
    """구독 취소"""
    try:
        subscription = db.query(db_models.Subscription).filter(
            db_models.Subscription.subscription_id == subscription_id
        ).first()
        if subscription:
            subscription.end_date = datetime.now()
            db.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"[cancel_subscription 오류] {e}", exc_info=True)
        db.rollback()
        return False

# -------------------
# TemplateMessage 관련 함수 (DDL 제약조건 적용)
# -------------------
def create_template_message(db: Session, user_id: int, template_type: str, channel_type: str,
                           title: str, content: str, content_type: str = None):
    """템플릿 메시지 생성 (channel_type: EMAIL, SMS, PUSH, SLACK)"""
    try:
        if channel_type not in ['EMAIL', 'SMS', 'PUSH', 'SLACK']:
            raise ValueError("Invalid channel_type. Must be EMAIL, SMS, PUSH, or SLACK")
        
        template = db_models.TemplateMessage(
            user_id=user_id,
            template_type=template_type,
            channel_type=channel_type,
            title=title,
            content=content,
            content_type=content_type
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        return template
    except Exception as e:
        logger.error(f"[create_template_message 오류] {e}", exc_info=True)
        db.rollback()
        return None

def get_templates_by_user_and_type(db: Session,user_id: int,template_type: Optional[str] = None,
include_public_user_id: int = 3,
) -> List[db_models.TemplateMessage]:
    """
    지정 user_id + 공용 템플릿(user_id=include_public_user_id)을 함께 조회.
    template_type == "전체" 또는 None 이면 타입 필터 없음.
    """
    query = db.query(db_models.TemplateMessage).filter(
        or_(
            db_models.TemplateMessage.user_id == include_public_user_id,
            db_models.TemplateMessage.user_id == user_id,
        )
    )
    if template_type and template_type != "전체":
        query = query.filter(db_models.TemplateMessage.template_type == template_type)

    return query.order_by(db_models.TemplateMessage.created_at.desc()).all()

def get_template_by_id(db: Session, template_id: int):
    """템플릿 ID로 조회"""
    try:
        return db.query(db_models.TemplateMessage).filter(
            db_models.TemplateMessage.template_id == template_id
        ).first()
    except Exception as e:
        logger.error(f"[get_template_by_id 오류] {e}", exc_info=True)
        return None

def update_template_message(db: Session, template_id: int, **kwargs) -> bool:
    """템플릿 메시지 업데이트"""
    try:
        template = db.query(db_models.TemplateMessage).filter(
            db_models.TemplateMessage.template_id == template_id
        ).first()
        if not template:
            return False
        
        # 유효한 필드만 업데이트
        valid_fields = ['template_type', 'channel_type', 'title', 'content', 'content_type']
        for field, value in kwargs.items():
            if field in valid_fields and value is not None:
                setattr(template, field, value)
        
        db.commit()
        return True
    except Exception as e:
        logger.error(f"[update_template_message 오류] {e}", exc_info=True)
        db.rollback()
        return False

def delete_template_message(db: Session, template_id: int) -> bool:
    """템플릿 메시지 삭제"""
    try:
        template = db.query(db_models.TemplateMessage).filter(
            db_models.TemplateMessage.template_id == template_id
        ).first()
        if template:
            db.delete(template)
            db.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"[delete_template_message 오류] {e}", exc_info=True)
        db.rollback()
        return False

        return templates[:limit]
    
    except Exception as e:
        print(f"❌ 템플릿 추천 오류: {e}")
        return []
    
def extract_template_keyword(text: str) -> str:
    text_lower = text.lower()
    mapping = {
        "생일": "생일/기념일", 
        "기념일": "생일/기념일",
        "축하": "생일/기념일",
        "리뷰": "리뷰 요청", 
        "후기": "리뷰 요청",
        "평가": "리뷰 요청",
        "예약": "예약",
        "설문": "설문 요청",
        "감사": "구매 후 안내", 
        "출고": "구매 후 안내", 
        "배송": "구매 후 안내",
        "발송": "구매 후 안내",
        "재구매": "재구매 유도", 
        "재방문": "재방문",
        "다시": "재구매 유도",
        "VIP": "고객 맞춤 메시지", 
        "맞춤": "고객 맞춤 메시지",
        "특별": "고객 맞춤 메시지",
        "이벤트": "이벤트 안내", 
        "할인": "이벤트 안내", 
        "프로모션": "이벤트 안내",
        "세일": "이벤트 안내"
    }
    for keyword, template_type in mapping.items():
        if keyword in text_lower:
            print(f"🎯 키워드 '{keyword}' → 템플릿 타입 '{template_type}'")
            return template_type
    
    print("🔍 특정 키워드 없음 → '전체' 템플릿")
    return "전체"

# 템플릿 감지 함수
def is_template_query(text: str) -> bool:
    template_keywords = [
        "템플릿", "문자", "메시지", "문구", "추천", "예시", 
        "샘플", "양식", "포맷", "멘트", "말", "텍스트"
    ]
    text_lower = text.lower()
    is_template = any(keyword in text_lower for keyword in template_keywords)
    
    print(f"📝 템플릿 쿼리 감지: {is_template} (입력: '{text}')")
    return is_template

# 템플릿 추천 로직
def recommend_templates_core(query: str, limit: int = 5) -> list:
    """템플릿 추천 로직 (공통 모듈 사용)"""
    try:
        keyword = extract_template_keyword(query)
        print(f"📌 추출된 템플릿 키워드: {keyword}")
        
        # DB에서 템플릿 조회 (공통 모듈 사용)
        templates = get_templates_by_type(keyword)
        print(f"📋 조회된 템플릿 수: {len(templates)}")
        
        # 템플릿이 없으면 전체 템플릿에서 검색
        if not templates and keyword != "전체":
            print("⚠️ 특정 타입 템플릿 없음, 전체에서 검색...")
            templates = get_templates_by_type("전체")
        
        # 디버깅을 위한 템플릿 정보 출력
        for i, template in enumerate(templates[:3]):  # 처음 3개만
            print(f"템플릿 {i+1}: {template.get('title', 'No Title')}")
        
        return templates[:limit]
        
    except Exception as e:
        print(f"❌ 템플릿 추천 오류: {e}")
        return []
    
def get_user_template_by_title(db: Session, user_id: int, title: str):
    """사용자의 템플릿 중 제목이 일치하는 템플릿을 조회"""
    try:
        return db.query(db_models.TemplateMessage).filter(
            db_models.TemplateMessage.user_id == user_id,
            db_models.TemplateMessage.title == title
        ).first()
    except Exception as e:
        logger.error(f"[get_user_template_by_title 오류] {e}", exc_info=True)
        return None
# -------------------
# AutomationTask 관련 함수 (template_id FK 추가)
# -------------------
def create_automation_task(db: Session, user_id: int, task_type: str, title: str,
                          template_id: int = None, task_data: dict = None, 
                          conversation_id: int = None, scheduled_at: datetime = None,
                          status: str = "PENDING"):
    """자동화 작업 생성 (status: PENDING, RUNNING, COMPLETED, FAILED)"""
    try:
        # ✅ 문자열을 Enum으로 변환 시도
        task_type_enum = TaskTypeEnum(task_type)

        task = db_models.AutomationTask(
            user_id=user_id,
            conversation_id=conversation_id,
            task_type=task_type_enum,  # ✅ Enum 인스턴스로 전달
            title=title,
            template_id=template_id,
            task_data=task_data,
            status=status,
            scheduled_at=scheduled_at
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    except ValueError as ve:
        logger.error(f"[create_automation_task Enum 변환 실패] '{task_type}'는 유효하지 않은 TaskTypeEnum 값입니다.", exc_info=True)
        db.rollback()
        return None
    except Exception as e:
        logger.error(f"[create_automation_task 오류] {e}", exc_info=True)
        db.rollback()
        return None
def get_user_tasks(db: Session, user_id: int, status: str = None, limit: int = 50):
    try:
        query = db.query(db_models.AutomationTask).filter(db_models.AutomationTask.user_id == user_id)
        if status:
            query = query.filter(db_models.AutomationTask.status == status)
        return query.order_by(db_models.AutomationTask.created_at.desc()).limit(limit).all()
    except Exception as e:
        logger.error(f"[get_user_tasks 오류] {e}", exc_info=True)
        return []

def get_pending_tasks(db: Session, limit: int = 100):
    try:
        return db.query(db_models.AutomationTask).filter(
            db_models.AutomationTask.status == "PENDING"
        ).order_by(db_models.AutomationTask.scheduled_at.asc()).limit(limit).all()
    except Exception as e:
        logger.error(f"[get_pending_tasks 오류] {e}", exc_info=True)
        return []

def update_task_status(db: Session, task_id: int, status: str, executed_at: datetime = None) -> bool:
    """작업 상태 업데이트"""
    try:
        if status not in ['PENDING', 'RUNNING', 'COMPLETED', 'FAILED']:
            raise ValueError("Invalid status")
        
        task = db.query(db_models.AutomationTask).filter(
            db_models.AutomationTask.task_id == task_id
        ).first()
        if task:
            task.status = status
            if executed_at:
                task.executed_at = executed_at
            elif status in ['COMPLETED', 'FAILED']:
                task.executed_at = datetime.now()
            db.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"[update_task_status 오류] {e}", exc_info=True)
        db.rollback()
        return False

# -------------------
# 유틸리티 함수들
# -------------------
def handle_db_error(e: Exception, operation: str):
    logger.error(f"[{operation} 오류] {type(e).__name__}: {e}", exc_info=True)
    if isinstance(e, SQLAlchemyError):
        return {"error": "Database operation failed"}
    return {"error": "System error"}

# -------------------
# Raw SQL 함수들 (기존 코드 호환성용)
# -------------------
def insert_user_raw(email: str, nickname: str, provider: str, social_id: str, 
                   access_token: str, experience: int, admin: bool = False,
                   business_type: str = None, refresh_token: str = None) -> int:
    """Raw SQL을 사용한 사용자 삽입 (새 DDL 스키마)"""
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                INSERT INTO user (email, nickname, business_type, provider, social_id, 
                                admin, experience, access_token, refresh_token)
                VALUES (:email, :nickname, :business_type, :provider, :social_id, 
                        :admin, :experience, :access_token, :refresh_token)
                """),
                {
                    "email": email,
                    "nickname": nickname,
                    "business_type": business_type,
                    "provider": provider,
                    "social_id": social_id,
                    "admin": admin,
                    "experience": experience,
                    "access_token": access_token,
                    "refresh_token": refresh_token
                }
            )
            return result.lastrowid
    except SQLAlchemyError as e:
        logger.error(f"Error inserting user: {e}")
        return -1

def get_business_type(user_id: int) -> str:
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT business_type FROM user WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            row = result.fetchone()
            return row.business_type if row else "common"
    except Exception as e:
        return handle_db_error(e, "get_business_type") or "common"

def get_user_raw(user_id: int) -> dict:
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM user WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            row = result.fetchone()
            return dict(row._mapping) if row else {}
    except Exception as e:
        return handle_db_error(e, "get_user") or {}

def get_user_by_email_raw(email: str) -> dict:
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM user WHERE email = :email"),
                {"email": email}
            )
            row = result.fetchone()
            return dict(row._mapping) if row else {}
    except Exception as e:
        return handle_db_error(e, "get_user_by_email") or {}

def get_all_users() -> list:
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM user")
            )
            return [dict(row._mapping) for row in result]
    except Exception as e:
        return handle_db_error(e, "get_all_users") or []

def insert_message_raw(conversation_id: int, sender_type: str, content: str, agent_type: str = None) -> bool:
    """Raw SQL을 사용한 메시지 삽입 (DDL 제약조건 적용)"""
    try:
        # sender_type을 DDL 제약조건에 맞게 변환
        if sender_type.lower() == 'user':
            sender_type = 'USER'
        elif sender_type.lower() == 'agent':
            sender_type = 'AGENT'
        
        with engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO message 
                (conversation_id, sender_type, agent_type, content)
                VALUES (:conversation_id, :sender_type, :agent_type, :content)
                """),
                {
                    "conversation_id": conversation_id,
                    "sender_type": sender_type,
                    "agent_type": agent_type,
                    "content": content
                }
            )
        return True
    except SQLAlchemyError as e:
        logger.error(f"Error inserting message: {e}")
        return False

def get_recent_messages_raw(conversation_id: int, limit: int = 5) -> list:
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT sender_type, content, agent_type, created_at
                    FROM message
                    WHERE conversation_id = :conversation_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"conversation_id": conversation_id, "limit": limit}
            )
            return [dict(row._mapping) for row in result]
    except Exception as e:
        return handle_db_error(e, "get_recent_messages") or []

# 기존 template 관련 함수들 (하위 호환성)
def insert_template(user_id: int, template_type: str = None, channel_type: str = None, 
                   title: str = None, content: str = None) -> int:
    """템플릿 삽입 (하위 호환성)"""
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                INSERT INTO template_message 
                (user_id, template_type, channel_type, title, content, created_at)
                VALUES (:user_id, :template_type, :channel_type, :title, :content, :created_at)
                """),
                {
                    "user_id": user_id,
                    "template_type": template_type,
                    "channel_type": channel_type,
                    "title": title,
                    "content": content,
                    "created_at": datetime.utcnow()
                }
            )
            return result.lastrowid
    except Exception as e:
        logger.error(f"Error inserting template: {e}")
        return -1

def get_template(template_id: int) -> dict:
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM template_message WHERE template_id = :template_id"),
                {"template_id": template_id}
            )
            row = result.fetchone()
            return dict(row._mapping) if row else {}
    except Exception as e:
        return handle_db_error(e, "get_template") or {}

def get_template_by_title(title: str) -> dict:
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM template_message WHERE title = :title"),
                {"title": title}
            )
            row = result.fetchone()
            return dict(row._mapping) if row else {}
    except Exception as e:
        return handle_db_error(e, "get_template_by_title") or {}

def get_templates_by_type(template_type: str) -> list:
    """템플릿 타입별 조회 함수"""
    try:
        with engine.connect() as conn:
            if template_type == "전체":
                result = conn.execute(
                    text("SELECT * FROM template_message ORDER BY created_at DESC")
                )
            else:
                result = conn.execute(
                    text("""
                        SELECT * FROM template_message 
                        WHERE template_type = :template_type 
                        ORDER BY created_at DESC
                    """),
                    {"template_type": template_type}
                )
            
            templates = [dict(row._mapping) for row in result]
            logger.info(f"📋 DB 조회 결과: {len(templates)}개 템플릿 (타입: {template_type})")
            return templates
            
    except Exception as e:
        logger.error(f"❌ get_templates_by_type 오류: {e}")
        return handle_db_error(e, "get_templates_by_type") or []

def update_template(template_id: int, **kwargs) -> bool:
    try:
        valid_keys = {"template_type", "channel_type", "title", "content", "content_type"}
        update_data = {k: kwargs.get(k, None) for k in valid_keys if k in kwargs}
        
        if not update_data:
            return False
            
        set_clause = ", ".join([f"{k} = {bindparam(k)}" for k in update_data.keys()])
        
        with engine.begin() as conn:
            stmt = text(f"UPDATE template_message SET {set_clause} WHERE template_id = :template_id")
            params = {**update_data, "template_id": template_id}
            result = conn.execute(stmt, params)
            return result.rowcount > 0
    except Exception as e:
        return handle_db_error(e, "update_template") or False

def delete_template(template_id: int) -> bool:
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM template_message WHERE template_id = :template_id"),
                {"template_id": template_id}
            )
            return result.rowcount > 0
    except Exception as e:
        return handle_db_error(e, "delete_template") or False

def get_user_tokens(db: Session, user_id: int) -> Optional[dict]:
    """사용자 ID로 토큰 정보 조회"""
    try:
        user = db.query(db_models.User).filter(db_models.User.user_id == user_id).first()
        if user:
            return {
                'access_token': user.access_token,
                'refresh_token': user.refresh_token,
                'user_id': user.user_id,
                'email': user.email
            }
        return None
    except Exception as e:
        logger.error(f"[get_user_tokens 오류] {e}", exc_info=True)
        return None

def check_user_token_exists(db: Session, user_id: int) -> bool:
    """사용자의 토큰 존재 여부 확인"""
    try:
        user = db.query(db_models.User).filter(db_models.User.user_id == user_id).first()
        if user and user.access_token:
            return True
        return False
    except Exception as e:
        logger.error(f"[check_user_token_exists 오류] {e}", exc_info=True)
        return False

def get_user_persona_info(db: Session, user_id: int) -> dict:
    """사용자의 페르소나 정보 조회"""
    try:
        user = db.query(db_models.User).filter(db_models.User.user_id == user_id).first()
        if not user:
            logger.warning(f"사용자 ID {user_id}를 찾을 수 없습니다")
            return {}
        
        persona_info = {
            "business_type": user.business_type,
            "experience": user.experience,
            "nickname": user.nickname,
            "email": user.email
        }
        logger.info(f"페르소나 정보 조회 완료: user_id={user_id}, business_type={persona_info.get('business_type')}")
        return persona_info
        
    except Exception as e:
        logger.error(f"[get_user_persona_info 오류] {e}", exc_info=True)
        return {}
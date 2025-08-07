"""
대화 관리 서비스
사용자와의 대화 세션 및 메시지 관리
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# 공통 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "../../shared_modules"))

try:
    from shared_modules import (
        create_conversation, 
        create_message, 
        get_conversation_by_id, 
        get_recent_messages,
        get_session_context,
        insert_message_raw
    )
    SHARED_MODULES_AVAILABLE = True
except ImportError:
    SHARED_MODULES_AVAILABLE = False

logger = logging.getLogger(__name__)

class ConversationService:
    """대화 관리 서비스"""
    
    def __init__(self):
        """대화 서비스 초기화"""
        logger.info("ConversationService 초기화 완료")
        if not SHARED_MODULES_AVAILABLE:
            logger.warning("공통 모듈을 사용할 수 없습니다. 로컬 구현을 사용합니다.")

    async def get_history(self, conversation_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """대화 히스토리 조회"""
        try:
            if not SHARED_MODULES_AVAILABLE:
                return self._get_dummy_history(conversation_id, limit)
            
            with get_session_context() as db:
                messages = get_recent_messages(db, conversation_id, limit)
                
                history = []
                for msg in reversed(messages):  # 시간순 정렬
                    # Handle both dict and object types
                    if isinstance(msg, dict):
                        history.append({
                            "role": "user" if msg.get("sender_type") == "user" else "assistant",
                            "content": msg.get("content", ""),
                            "timestamp": msg.get("created_at").isoformat() if msg.get("created_at") else None,
                            "agent_type": msg.get("agent_type"),
                            "message_id": msg.get("message_id")
                        })
                    else:
                        # If msg is an object (ORM model)
                        history.append({
                            "role": "user" if getattr(msg, "sender_type", None) == "user" else "assistant",
                            "content": getattr(msg, "content", ""),
                            "timestamp": getattr(msg, "created_at", None).isoformat() if getattr(msg, "created_at", None) else None,
                            "agent_type": getattr(msg, "agent_type", None),
                            "message_id": getattr(msg, "message_id", None)
                        })
                
                return history
                
        except Exception as e:
            logger.error(f"대화 히스토리 조회 실패: {e}")
            return []

    def _get_dummy_history(self, conversation_id: int, limit: int) -> List[Dict[str, Any]]:
        """더미 대화 히스토리 (공통 모듈이 없는 경우)"""
        return [
            {
                "role": "user",
                "content": "안녕하세요",
                "timestamp": datetime.now().isoformat(),
                "agent_type": None,
                "message_id": 1
            }
        ]

    async def save_message(self, conversation_id: int, content: str, sender_type: str, 
                          agent_type: str = None) -> Dict[str, Any]:
        """메시지 저장"""
        try:
            if not SHARED_MODULES_AVAILABLE:
                return self._save_dummy_message(conversation_id, content, sender_type, agent_type)
            
            with get_session_context() as db:
                message = create_message(db, conversation_id, sender_type, agent_type, content)
                
                if not message:
                    logger.error(f"메시지 저장 실패 - conversation_id: {conversation_id}")
                    raise Exception("메시지 저장에 실패했습니다")
                
                return {
                    "message_id": message.message_id,
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"메시지 저장 실패: {e}")
            # 대안적인 저장 방법 시도
            try:
                if SHARED_MODULES_AVAILABLE:
                    insert_message_raw(
                        conversation_id=conversation_id,
                        sender_type=sender_type,
                        agent_type=agent_type,
                        content=content
                    )
                    return {
                        "message_id": None,
                        "created_at": datetime.now().isoformat(),
                        "success": True,
                        "method": "raw_insert"
                    }
                else:
                    return self._save_dummy_message(conversation_id, content, sender_type, agent_type)
            except Exception as fallback_error:
                logger.error(f"대안 메시지 저장도 실패: {fallback_error}")
                return {
                    "message_id": None,
                    "created_at": datetime.now().isoformat(),
                    "success": False,
                    "method": "dummy"
                }

    def _save_dummy_message(self, conversation_id: int, content: str, 
                           sender_type: str, agent_type: str = None) -> Dict[str, Any]:
        """더미 메시지 저장 (공통 모듈이 없는 경우)"""
        return {
            "message_id": int(datetime.now().timestamp() * 1000) % 1000000,
            "created_at": datetime.now().isoformat(),
            "success": True,
            "method": "dummy"
        }

    async def get_conversation_info(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """대화 정보 조회"""
        try:
            if not SHARED_MODULES_AVAILABLE:
                return self._get_dummy_conversation_info(conversation_id)
            
            with get_session_context() as db:
                conversation = get_conversation_by_id(db, conversation_id)
                
                if not conversation:
                    return None
                
                # Handle both dict and object types
                if isinstance(conversation, dict):
                    return {
                        "conversation_id": conversation.get("conversation_id"),
                        "user_id": conversation.get("user_id"),
                        "title": conversation.get("title"),
                        "created_at": conversation.get("created_at").isoformat() if conversation.get("created_at") else None,
                        "updated_at": conversation.get("updated_at").isoformat() if conversation.get("updated_at") else None,
                        "status": conversation.get("status", "active")
                    }
                else:
                    # If conversation is an object (ORM model)
                    return {
                        "conversation_id": getattr(conversation, "conversation_id", None),
                        "user_id": getattr(conversation, "user_id", None),
                        "title": getattr(conversation, "title", None),
                        "created_at": getattr(conversation, "created_at", None).isoformat() if getattr(conversation, "created_at", None) else None,
                        "updated_at": getattr(conversation, "updated_at", None).isoformat() if getattr(conversation, "updated_at", None) else None,
                        "status": getattr(conversation, "status", "active")
                    }
                
        except Exception as e:
            logger.error(f"대화 정보 조회 실패: {e}")
            return None

    def _get_dummy_conversation_info(self, conversation_id: int) -> Dict[str, Any]:
        """더미 대화 정보 (공통 모듈이 없는 경우)"""
        return {
            "conversation_id": conversation_id,
            "user_id": 1,
            "title": f"대화 {conversation_id}",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "status": "active"
        }

    async def create_conversation(self, user_id: int, title: str = None) -> Dict[str, Any]:
        """새 대화 생성"""
        try:
            if not SHARED_MODULES_AVAILABLE:
                return self._create_dummy_conversation(user_id, title)
            
            with get_session_context() as db:
                conversation = create_conversation(
                    db, 
                    user_id, 
                    title or f"대화 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                
                if not conversation:
                    raise Exception("대화 생성에 실패했습니다")
                
                return {
                    "conversation_id": conversation.conversation_id,
                    "user_id": conversation.user_id,
                    "title": conversation.title,
                    "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"대화 생성 실패: {e}")
            raise

    def _create_dummy_conversation(self, user_id: int, title: str = None) -> Dict[str, Any]:
        """더미 대화 생성 (공통 모듈이 없는 경우)"""
        conversation_id = int(datetime.now().timestamp() * 1000) % 1000000
        return {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "title": title or f"대화 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "created_at": datetime.now().isoformat(),
            "success": True
        }

    async def get_status(self) -> Dict[str, Any]:
        """서비스 상태 조회"""
        try:
            return {
                "service": "ConversationService",
                "version": "5.0.0",
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "features": {
                    "message_storage": True,
                    "conversation_management": True,
                    "shared_modules_available": SHARED_MODULES_AVAILABLE
                }
            }
        except Exception as e:
            logger.error(f"상태 조회 실패: {e}")
            return {
                "service": "ConversationService",
                "version": "5.0.0",
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def cleanup(self):
        """서비스 정리"""
        try:
            # 메모리 캐시 정리 등
            logger.info("ConversationService 정리 완료")
        except Exception as e:
            logger.error(f"ConversationService 정리 실패: {e}")

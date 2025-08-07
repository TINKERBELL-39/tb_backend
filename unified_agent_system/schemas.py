# schemas.py

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class EmailTemplateCreate(BaseModel):
    user_id: int
    title: str
    content: str
    channel_type: str = "EMAIL"  # 기본 EMAIL
    content_type: str

class EmailTemplateUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None



class TaskTypeEnum(str, Enum):
    calendar_sync = "calendar_sync"
    reminder_notify = "reminder_notify"
    content_generate = "content_generate"
    sns_publish_instagram = "sns_publish_instagram"
    sns_publish_blog = "sns_publish_blog"
    send_email = "send_email"
    mcp_insta = "mcp_insta"
    mcp_blog = "mcp_blog"

# task_data 필드는 JSON이므로 별도 객체로 명시
class TaskData(BaseModel):
    content: str
    platform: str
    keywords: Optional[str] = None  # DB 상 json 필드이므로 키워드 있어도 되고 없어도 됨

class AutomationRequest(BaseModel):
    user_id: int
    conversation_id: Optional[int] = None
    task_type: TaskTypeEnum
    title: str
    template_id: Optional[int] = None
    task_data: TaskData
    status: Optional[str] = "scheduled"
    scheduled_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None


# 이메일 자동 발송 요청 스키마

class EmailAutomationRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    html_body: Optional[str] = None
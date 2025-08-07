"""
이메일 발송 공통 모듈
"""

import mimetypes
import os
import re
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
from typing import Dict, List, Any, Optional
import logging

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
    import base64
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

logger = logging.getLogger(__name__)


class EmailManager:
    """이메일 발송을 위한 공통 클래스"""
    
    def __init__(self):
        pass
    
    def is_valid_email(self, email: str) -> bool:
        """이메일 주소 형식 검증"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    async def send_email(self, service: str, to_emails: List[str], subject: str, body: str,
                        html_body: Optional[str] = None, attachments: List[str] = None,
                        cc_emails: List[str] = None, bcc_emails: List[str] = None,
                        from_email: Optional[str] = None, from_name: Optional[str] = None) -> Dict[str, Any]:
        """통합 이메일 발송"""
        
        # 이메일 주소 검증
        for email in to_emails:
            if not self.is_valid_email(email):
                return {"success": False, "error": f"유효하지 않은 이메일 주소: {email}"}
        
        if service.lower() == "smtp":
            return await self.send_via_smtp(to_emails, subject, body, html_body, 
                                          attachments, cc_emails, bcc_emails, from_email, from_name)
        elif service.lower() == "sendgrid":
            return await self.send_via_sendgrid(to_emails, subject, body, html_body,
                                              attachments, cc_emails, bcc_emails, from_email, from_name)
        elif service.lower() == "aws_ses":
            return await self.send_via_aws_ses(to_emails, subject, body, html_body,
                                             attachments, cc_emails, bcc_emails, from_email, from_name)
        else:
            return {"success": False, "error": f"지원하지 않는 이메일 서비스: {service}"}
    
    async def send_via_smtp(self, to_emails: List[str], subject: str, body: str,
                           html_body: Optional[str] = None, attachments: List[str] = None,
                           cc_emails: List[str] = None, bcc_emails: List[str] = None,
                           from_email: Optional[str] = None, from_name: Optional[str] = None) -> Dict[str, Any]:
        """SMTP를 통한 이메일 발송"""
        try:
            # SMTP 설정 가져오기
            smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_user = os.getenv('SMTP_USER')
            smtp_password = os.getenv('SMTP_PASSWORD')
            smtp_use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
            
            if not smtp_user or not smtp_password:
                return {"success": False, "error": "SMTP 인증 정보가 설정되지 않았습니다"}
            
            # 발신자 정보 설정
            sender_email = from_email or smtp_user
            sender_name = from_name or "자동 이메일 시스템"
            
            # 메시지 생성 (한글 지원)
            from email.header import Header
            
            message = MIMEMultipart('alternative')
            message['From'] = formataddr((str(Header(sender_name, 'utf-8')), sender_email))
            message['To'] = ', '.join(to_emails)
            message['Subject'] = str(Header(subject, 'utf-8'))
            
            if cc_emails:
                message['Cc'] = ', '.join(cc_emails)
            
            # 본문 추가 (UTF-8 인코딩 명시)
            if body:
                text_part = MIMEText(body, 'plain', 'utf-8')
                message.attach(text_part)
            
            if html_body:
                html_part = MIMEText(html_body, 'html', 'utf-8')
                message.attach(html_part)
            
            # 첨부파일 추가
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as attachment_file:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment_file.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {os.path.basename(file_path)}'
                            )
                            message.attach(part)
            
            # 전체 수신자 목록
            all_recipients = to_emails + (cc_emails or []) + (bcc_emails or [])
            
            # SMTP 서버 연결 및 전송
            context = ssl.create_default_context()
            
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_use_tls:
                    server.starttls(context=context)
                server.login(smtp_user, smtp_password)
                
                # 이메일 전송
                server.send_message(message, to_addrs=all_recipients)
            
            return {
                "success": True,
                "message_id": message.get('Message-ID'),
                "recipients_count": len(all_recipients)
            }
            
        except Exception as e:
            logger.error(f"SMTP 이메일 발송 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_via_sendgrid(self, to_emails: List[str], subject: str, body: str,
                               html_body: Optional[str] = None, attachments: List[str] = None,
                               cc_emails: List[str] = None, bcc_emails: List[str] = None,
                               from_email: Optional[str] = None, from_name: Optional[str] = None) -> Dict[str, Any]:
        """SendGrid를 통한 이메일 발송"""
        if not SENDGRID_AVAILABLE:
            return {"success": False, "error": "SendGrid 라이브러리가 설치되지 않았습니다. 'pip install sendgrid' 명령으로 설치하세요."}
        
        try:
            # SendGrid 설정 가져오기
            api_key = os.getenv('SENDGRID_API_KEY')
            default_from_email = os.getenv('SENDGRID_FROM_EMAIL')
            default_from_name = os.getenv('SENDGRID_FROM_NAME', '자동 이메일 시스템')
            
            if not api_key:
                return {"success": False, "error": "SendGrid API 키가 설정되지 않았습니다"}
            
            if not default_from_email:
                return {"success": False, "error": "SendGrid 발신자 이메일이 설정되지 않았습니다"}
            
            # 발신자 정보
            sender_email = from_email or default_from_email
            sender_name = from_name or default_from_name
            
            # 메일 객체 생성
            from_email_obj = Email(sender_email, sender_name)
            
            # 수신자 목록 생성
            to_list = [To(email) for email in to_emails]
            
            # 컨텐츠 설정
            if html_body:
                content = Content("text/html", html_body)
            else:
                content = Content("text/plain", body)
            
            # Mail 객체 생성
            mail = Mail(
                from_email=from_email_obj,
                to_emails=to_list,
                subject=subject
            )
            mail.add_content(content)
            
            # CC, BCC 추가
            if cc_emails:
                for cc_email in cc_emails:
                    mail.add_cc(Email(cc_email))
            
            if bcc_emails:
                for bcc_email in bcc_emails:
                    mail.add_bcc(Email(bcc_email))
            
            # 첨부파일 추가
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            data = f.read()
                        encoded = base64.b64encode(data).decode()
                        
                        attachment = Attachment()
                        attachment.file_content = FileContent(encoded)
                        attachment.file_name = FileName(os.path.basename(file_path))
                        attachment.file_type = FileType(mimetypes.guess_type(file_path)[0] or 'application/octet-stream')
                        attachment.disposition = Disposition('attachment')
                        
                        mail.add_attachment(attachment)
            
            # SendGrid 클라이언트로 전송
            sg = sendgrid.SendGridAPIClient(api_key=api_key)
            response = sg.send(mail)
            
            if response.status_code in [200, 202]:
                return {
                    "success": True,
                    "message_id": response.headers.get('X-Message-Id'),
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"SendGrid API 오류: {response.status_code} - {response.body}"
                }
            
        except Exception as e:
            logger.error(f"SendGrid 이메일 발송 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_via_aws_ses(self, to_emails: List[str], subject: str, body: str,
                              html_body: Optional[str] = None, attachments: List[str] = None,
                              cc_emails: List[str] = None, bcc_emails: List[str] = None,
                              from_email: Optional[str] = None, from_name: Optional[str] = None) -> Dict[str, Any]:
        """AWS SES를 통한 이메일 발송"""
        if not BOTO3_AVAILABLE:
            return {"success": False, "error": "boto3 라이브러리가 설치되지 않았습니다. 'pip install boto3' 명령으로 설치하세요."}
        
        try:
            # AWS SES 설정 가져오기
            aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            default_from_email = os.getenv('SES_FROM_EMAIL')
            default_from_name = os.getenv('SES_FROM_NAME', '자동 이메일 시스템')
            
            if not default_from_email:
                return {"success": False, "error": "AWS SES 발신자 이메일이 설정되지 않았습니다"}
            
            # 발신자 정보
            sender_email = from_email or default_from_email
            sender_name = from_name or default_from_name
            
            # AWS SES 클라이언트 생성
            ses_client = boto3.client(
                'ses',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
            
            # 첨부파일이 있는 경우 Raw 메시지 사용
            if attachments:
                # 메시지 생성
                msg = MIMEMultipart()
                msg['From'] = formataddr((sender_name, sender_email))
                msg['To'] = ', '.join(to_emails)
                msg['Subject'] = subject
                
                if cc_emails:
                    msg['Cc'] = ', '.join(cc_emails)
                
                # 본문 추가
                if html_body:
                    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
                else:
                    msg.attach(MIMEText(body, 'plain', 'utf-8'))
                
                # 첨부파일 추가
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as attachment_file:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment_file.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {os.path.basename(file_path)}'
                            )
                            msg.attach(part)
                
                # Raw 메시지 전송
                destinations = to_emails + (cc_emails or []) + (bcc_emails or [])
                response = ses_client.send_raw_email(
                    Source=sender_email,
                    Destinations=destinations,
                    RawMessage={'Data': msg.as_string()}
                )
            else:
                # 단순 메시지 전송
                destinations = {
                    'ToAddresses': to_emails,
                }
                
                if cc_emails:
                    destinations['CcAddresses'] = cc_emails
                
                if bcc_emails:
                    destinations['BccAddresses'] = bcc_emails
                
                message = {
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {}
                }
                
                if html_body:
                    message['Body']['Html'] = {'Data': html_body, 'Charset': 'UTF-8'}
                else:
                    message['Body']['Text'] = {'Data': body, 'Charset': 'UTF-8'}
                
                response = ses_client.send_email(
                    Source=formataddr((sender_name, sender_email)),
                    Destination=destinations,
                    Message=message
                )
            
            return {
                "success": True,
                "message_id": response['MessageId'],
                "response_metadata": response.get('ResponseMetadata', {})
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS SES 클라이언트 오류: {error_code} - {error_message}")
            return {"success": False, "error": f"AWS SES 오류: {error_code} - {error_message}"}
        except Exception as e:
            logger.error(f"AWS SES 이메일 발송 실패: {e}")
            return {"success": False, "error": str(e)}
    
    def create_html_template(self, title: str, content: str, 
                           additional_info: Optional[str] = None) -> str:
        """기본 HTML 이메일 템플릿 생성"""
        from datetime import datetime
        current_time = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
        
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #007bff;">
                <h2 style="color: #007bff; margin-top: 0;">{title}</h2>
                <p style="font-size: 16px; margin: 15px 0;">{content}</p>
                
                {f'<p style="font-size: 14px; color: #666;">{additional_info}</p>' if additional_info else ''}
                
                <hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
                
                <p style="font-size: 14px; color: #666; margin: 10px 0;">
                    <strong>발송 시간:</strong> {current_time}
                </p>
                
                <div style="margin-top: 20px; padding: 15px; background-color: #e9ecef; border-radius: 5px;">
                    <p style="font-size: 14px; color: #666; margin: 0;">
                        이 이메일은 자동으로 발송되었습니다.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_template


# 전역 인스턴스
_email_manager = None

def get_email_manager() -> EmailManager:
    """EmailManager 싱글톤 인스턴스 반환"""
    global _email_manager
    if _email_manager is None:
        _email_manager = EmailManager()
    return _email_manager

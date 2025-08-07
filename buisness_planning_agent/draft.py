# pip install markdown
# pip install weasyprint

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import markdown
import os
import tempfile
#from weasyprint import HTML
import pdfkit

# 공통 모듈
from shared_modules import (
    create_report,
    get_db_dependency,
)

draft_router = APIRouter()

# ---------- PDF 유틸 함수 ----------

def generate_pdf_from_html(html: str) -> bytes:
    pdf_bytes = pdfkit.from_string(html, False)
    return pdf_bytes

def save_pdf_to_temp(pdf_bytes: bytes) -> str:
    """PDF 바이트를 임시 파일로 저장하고 file_id 반환"""
    temp_dir = tempfile.gettempdir()
    file_id = f"report_{os.urandom(4).hex()}"
    file_path = os.path.join(temp_dir, f"{file_id}.pdf")
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)
    return file_id

# ---------- 1. PDF 생성 ----------
class IdeaValidationPdfGenerateRequest(BaseModel):
    markdown_content: str

@draft_router.post("/report/markdown/pdf/create")
async def generate_idea_validation_pdf(
    data: IdeaValidationPdfGenerateRequest,
):
    try:
        # 1. 마크다운 → HTML 변환
        html = markdown.markdown(data.markdown_content)

        # 2. HTML → PDF 변환
        pdf_bytes = generate_pdf_from_html(html)
        file_id = save_pdf_to_temp(pdf_bytes)
        file_url = f"/report/pdf/download/{file_id}"

        return JSONResponse({"file_id": file_id, "file_url": file_url})
    except Exception as e:
        raise HTTPException(status_code=500, detail="사업기획서 PDF 생성 중 오류 발생")


# ---------- 2. DB 저장 ----------
class IdeaValidationReportCreateRequest(BaseModel):
    user_id: int
    conversation_id: int = None
    title: str
    markdown_content: str
    file_url: str

@draft_router.post("/report/markdown/create")
async def create_idea_validation_report(
    data: IdeaValidationReportCreateRequest,
    db: Session = Depends(get_db_dependency),
):
    try:
        # 마크다운을 JSON에 그대로 저장
        content_data = {"markdown": data.markdown_content}

        report = create_report(
            db=db,
            user_id=data.user_id,
            conversation_id=data.conversation_id,
            report_type="사업기획서",
            title=data.title or "아이디어 검증 보고서",
            content_data=content_data,
            file_url=data.file_url,
        )

        if not report:
            raise Exception("DB 저장 실패")

        return JSONResponse({"report_id": report.report_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail="사업기획서 보고서 저장 중 오류 발생")

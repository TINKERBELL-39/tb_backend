import os
import sys
import boto3
from datetime import datetime
from fastapi import FastAPI, Request, APIRouter, UploadFile, File
from fastapi.responses import RedirectResponse, JSONResponse
import httpx
from pydantic import BaseModel
from sqlalchemy import desc


INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID")
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET")
REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI")
S3_BUCKET = os.getenv("AWS_S3_BUCKET_NAME")

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from shared_modules.db_models import InstagramToken
from shared_modules.database import get_session_context

s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "ap-northeast-2")
)

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 테스트 시 전체 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
router = APIRouter()

# ======== Instagram OAuth 로그인 URL ========
@router.get("/auth/instagram")
def instagram_login(user_id: int):
    auth_url = (
        f"https://www.instagram.com/oauth/authorize"
        f"?client_id={INSTAGRAM_APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=business_basic,business_content_publish"
        f"&response_type=code"
        f"&state={user_id}"  # user_id를 state로 넘김
    )
    return auth_url

# ======== OAuth Callback ========
@router.get("/auth/instagram/callback")
async def instagram_callback(code: str, state: str):
    user_id = int(state)  # state 파라미터로 user_id를 복원

    # Access Token 교환
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.instagram.com/oauth/access_token",
            data={
                "client_id": INSTAGRAM_APP_ID,
                "client_secret": INSTAGRAM_APP_SECRET,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
                "code": code,
            },
        )
    token_data = res.json()
    access_token = token_data.get("access_token")

    if not access_token:
        return JSONResponse({"error": "토큰 발급 실패", "details": token_data}, status_code=400)

    # 계정 정보 가져오기 (graph_id, username)
    async with httpx.AsyncClient() as client:
        me_res = await client.get(
            "https://graph.instagram.com/me",
            params={"fields": "id,username", "access_token": access_token},
        )
    me_data = me_res.json()

    if "id" not in me_data:
        return JSONResponse({"error": "계정 정보 조회 실패", "details": me_data}, status_code=400)

    # DB 저장 (faq.py 스타일)
    with get_session_context() as db:
        account = InstagramToken(
            user_id=user_id,
            access_token=access_token,
            graph_id=me_data["id"],
            username=me_data.get("username"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(account)
        db.commit()
        db.refresh(account)

    return JSONResponse({"message": "Instagram 계정 연동 성공", "data": me_data})

class InstagramPostRequest(BaseModel):
    user_id: int
    caption: str
    image_url: str

@router.post("/instagram/post")
async def instagram_post(body: InstagramPostRequest):
    user_id = body.user_id
    caption = body.caption
    image_url = body.image_url
    
    with get_session_context() as db:
        account = db.query(InstagramToken).filter(InstagramToken.user_id == user_id).order_by(desc(InstagramToken.updated_at)).first()
        if not account:
            return JSONResponse(
                {"error": f"Instagram 계정(user_id={user_id})이 등록되지 않았습니다."},
                status_code=400
            )

        # 1. 미디어 생성
        async with httpx.AsyncClient(timeout=20.0) as client:
            create_res = await client.post(
                f"https://graph.instagram.com/{account.graph_id}/media",
                params={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": account.access_token,
                },
            )
        create_data = create_res.json()
        creation_id = create_data.get("id")

        if not creation_id:
            return JSONResponse({"error": "미디어 생성 실패", "details": create_data}, status_code=400)

        # 2. 게시 요청
        async with httpx.AsyncClient() as client:
            publish_res = await client.post(
                f"https://graph.instagram.com/{account.graph_id}/media_publish",
                params={
                    "creation_id": creation_id,
                    "access_token": account.access_token,
                },
            )
    return publish_res.json()

from pydantic import BaseModel

@router.post("/s3/upload")
async def upload_image_to_s3(file: UploadFile = File(...)):
    try:
        filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}"

        # ACL 관련 옵션 제거
        s3_client.upload_fileobj(
            file.file,
            S3_BUCKET,
            filename,
            ExtraArgs={"ContentType": file.content_type}  # ACL 없음
        )

        file_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{filename}"
        return {"file_url": file_url}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e) or "S3 업로드 실패"}, status_code=500)

@router.post("/instagram/refresh-token")
async def refresh_instagram_token(user_id: int = 56):
    try:
        with get_session_context() as db:
            account = db.query(InstagramToken).filter(InstagramToken.user_id == user_id).order_by(desc(InstagramToken.updated_at)).first()
            if not account:
                return JSONResponse(
                    {"error": f"Instagram 계정(user_id={user_id})이 등록되지 않았습니다."},
                    status_code=400
                )

            # Instagram API 호출
            async with httpx.AsyncClient() as client:
                refresh_res = await client.get(
                    "https://graph.instagram.com/refresh_access_token",
                    params={
                        "grant_type": "ig_refresh_token",
                        "access_token": account.access_token
                    },
                )
            refresh_data = refresh_res.json()

            if "access_token" not in refresh_data:
                return JSONResponse({"error": "토큰 갱신 실패", "details": refresh_data}, status_code=400)

            # DB에 갱신된 토큰 저장
            account.access_token = refresh_data["access_token"]
            db.commit()

        return {
            "message": "Instagram Access Token 갱신 완료",
            "access_token": refresh_data["access_token"],
            "expires_in": refresh_data.get("expires_in", 0)
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
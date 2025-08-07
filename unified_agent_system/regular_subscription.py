# ✅ 전체 통합 정기결제 시스템 (FastAPI)

from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import requests
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

# 경로 설정 (shared_modules import용)
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared_modules.database import get_session_context
from shared_modules.db_models import Subscription
from apscheduler.schedulers.background import BackgroundScheduler
# from shared_modules.utils import utc_to_kst

import logging

logger = logging.getLogger(__name__)

app = FastAPI()
router = APIRouter()

# ✅ DB 초기화용 스케줄러 생성
scheduler = BackgroundScheduler()

# ✅ 결제 준비 API
class SubscriptionRequest(BaseModel):
    user_id: int
    plan_type: str
    monthly_fee: float

@router.post("/ready")
def subscription_ready(data: SubscriptionRequest):
    # now = utc_to_kst(datetime.now(timezone.utc))
    # end = now + timedelta(days=30)
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=30)

    with get_session_context() as db:
        # 기존 ACTIVE 구독 확인
        active_sub = db.query(Subscription).filter(
            Subscription.user_id == data.user_id,
            Subscription.status == "ACTIVE"
        ).first()

        # 업그레이드 시 차액 계산
        if active_sub:
            remaining_days = max((active_sub.end_date.replace(tzinfo=timezone.utc) - now).days, 0)
            total_days = (active_sub.end_date.replace(tzinfo=timezone.utc) - active_sub.start_date.replace(tzinfo=timezone.utc)).days or 30
            previous_value = float(active_sub.monthly_fee) * (remaining_days / total_days)
            partial_payment = round(data.monthly_fee - previous_value, 2)

        else:
            partial_payment = data.monthly_fee

        # 카카오페이 결제 준비 요청
        temp_data = {
            "cid": os.getenv("KAKAOPAY_REG_CID"),
            "partner_order_id": f"order_{data.user_id}",
            "partner_user_id": str(data.user_id),
            "item_name": f"{data.plan_type} 구독",
            "quantity": 1,
            "total_amount": int(partial_payment),
            "vat_amount": 0,
            "tax_free_amount": 0,
            "approval_url": f"http://localhost:8080/subscription/approve?user_id={data.user_id}&plan_type={data.plan_type}&monthly_fee={data.monthly_fee}",
            "cancel_url": "http://localhost:8080/subscription/cancel",
            "fail_url": "http://localhost:8080/subscription/fail"
        }

        headers = {
            "Authorization": f"SECRET_KEY {os.getenv('KAKAOPAY_SECRET_DEV')}",
            "Content-Type": "application/json"
        }

        response = requests.post("https://open-api.kakaopay.com/online/v1/payment/ready", headers=headers, json=temp_data)
        response.raise_for_status()
        result = response.json()

        # 새로운 PENDING 구독 insert
        new_sub = Subscription(
            user_id=data.user_id,
            plan_type=data.plan_type,
            monthly_fee=data.monthly_fee,
            tid=result["tid"],
            start_date=now,
            end_date=end,
            status="PENDING"
        )
        db.add(new_sub)
        db.commit()

        return {"redirect_url": result["next_redirect_pc_url"]}

@router.get("/approve")
def payment_approve(
    pg_token: str = Query(...),
    user_id: int = Query(...),
    plan_type: str = Query(...),
    monthly_fee: float = Query(...)
):
    with get_session_context() as db:
        # 1️⃣ 최신 PENDING 구독 가져오기
        sub = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == "PENDING"
        ).order_by(Subscription.subscription_id.desc()).first()

        if not sub or not sub.tid:
            raise HTTPException(status_code=404, detail="구독 정보 없음")

        # 2️⃣ 카카오페이 승인 요청
        headers = {
            "Authorization": f"KakaoAK {os.getenv('KAKAO_ADMIN_KEY')}",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
        }

        data = {
            "cid": os.getenv("KAKAOPAY_REG_CID"),
            "tid": sub.tid,
            "partner_order_id": f"order_{user_id}",
            "partner_user_id": str(user_id),
            "pg_token": pg_token
        }

        response = requests.post("https://kapi.kakao.com/v1/payment/approve", headers=headers, data=data)
        result = response.json()

        if "sid" not in result:
            raise HTTPException(status_code=400, detail=f"카카오페이 승인 실패: {result}")

        # 3️⃣ 기존 ACTIVE 구독 → MODIFIED
        active_sub = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == "ACTIVE"
        ).first()
        if active_sub:
            active_sub.status = "MODIFIED"
            db.add(active_sub)

        # 4️⃣ 현재 구독 → ACTIVE 처리
        # now = utc_to_kst(datetime.now(timezone.utc))
        now = datetime.now(timezone.utc)
        sub.sid = result["sid"]
        sub.plan_type = plan_type
        sub.monthly_fee = monthly_fee
        sub.start_date = now
        sub.end_date = now + timedelta(days=30)
        sub.status = "ACTIVE"

        db.add(sub)
        db.commit()

        return RedirectResponse(
            url=f"http://localhost:3000/mypage"
        )

# ✅ 해지 API
def cancel_kakaopay_payment(tid: str, cancel_amount: float):
    url = "https://open-api.kakaopay.com/online/v1/payment/cancel"
    headers = {
        "Authorization": f"SECRET_KEY {os.getenv('KAKAOPAY_SECRET_DEV')}",
        "Content-Type": "application/json"
    }
    payload = {
        "cid": os.getenv('KAKAOPAY_CID'),
        "tid": tid,
        "cancel_amount": cancel_amount,
        "cancel_tax_free_amount": 0
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"KakaoPay 결제 취소 실패: {response.text}")
    return response.json()

def get_kakaopay_order_info(tid: str) -> dict:
    """
    카카오페이 결제 정보 조회 (환불 가능 금액 포함)
    """
    url = "https://kapi.kakao.com/v1/payment/order"
    headers = {
        "Authorization": f"KakaoAK {os.getenv('KAKAO_ADMIN_KEY')}",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
    }
    data = {
        "cid": os.getenv("KAKAOPAY_REG_CID"),
        "tid": tid
    }

    response = requests.post(url, headers=headers, data=data)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"KakaoPay 결제 정보 조회 실패: {response.text}"
        )

    return response.json()

@router.post("/cancel")
def cancel_subscription(user_id: int = Query(...)):
    with get_session_context() as db:
        subs = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(["ACTIVE", "MODIFIED"])
        ).order_by(Subscription.subscription_id.desc()).all()

        if not subs:
            raise HTTPException(status_code=404, detail="유효한 구독 내역이 없습니다.")

        # now = utc_to_kst(datetime.utcnow())
        now = datetime.now(timezone.utc)

        # 환불 총액 계산 (전체 기간 대비 남은 일수 기준)
        latest_sub = subs[0]  # 가장 최근 결제 기준으로 계산
        total_days = (latest_sub.end_date - latest_sub.start_date).days or 30
        # remaining_days = max((utc_to_kst(latest_sub.end_date.replace(tzinfo=timezone.utc)) - now).days, 0)
        remaining_days = max((latest_sub.end_date.replace(tzinfo=timezone.utc) - now).days, 0)
        total_refund_needed = round(float(latest_sub.monthly_fee) * (remaining_days / total_days), 2)

        cancel_results = []
        refunded_total = 0

        for sub in subs:
            if not sub.tid:
                continue

            # KakaoPay에서 cancel 가능한 금액 조회
            try:
                order_info = get_kakaopay_order_info(sub.tid)  
                cancelable = order_info.get("cancel_available_amount", {}).get("total", 0)
            except Exception as e:
                logger.warning(f"[카카오페이 조회 실패] TID {sub.tid}: {e}")
                continue

            if cancelable <= 0:
                continue

            refund_amount = min(cancelable, total_refund_needed - refunded_total)
            if refund_amount <= 0:
                continue

            try:
                response = cancel_kakaopay_payment(sub.tid, refund_amount)
                cancel_results.append({
                    "tid": sub.tid,
                    "refund_amount": refund_amount,
                    "response": response
                })
                refunded_total += refund_amount
            except HTTPException as e:
                logger.warning(f"[구독 해지 실패] TID {sub.tid}: {e.detail}")
                continue

            if refunded_total >= total_refund_needed:
                break

        # 구독 상태 모두 변경
        for sub in subs:
            sub.status = "CANCELLED"
            sub.monthly_fee = 0
            sub.sid = None
            sub.end_date = now

        db.commit()

        if not cancel_results:
            raise HTTPException(status_code=400, detail="결제 취소에 실패했습니다.")

        return {
            "success": True,
            "message": "구독이 해지되었으며 일부 또는 전체 결제가 취소되었습니다.",
            "total_refund": refunded_total,
            "canceled": cancel_results
        }


# ✅ 다운그레이드 처리 (개선된 버전)
@router.post("/downgrade")
def downgrade_subscription(user_id: int = Query(...), new_fee: float = Query(...)):
    with get_session_context() as db:
        subs = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(["ACTIVE", "MODIFIED"])
        ).order_by(Subscription.subscription_id.desc()).all()

        if not subs:
            raise HTTPException(status_code=404, detail="유효한 구독 내역이 없습니다.")

        # now = utc_to_kst(datetime.utcnow())
        now = datetime.now(timezone.utc)
        latest_sub = subs[0]  # 가장 최근 구독 기준
        plan_type = latest_sub.plan_type

        # 1. 잔여일수 계산 (가장 최근 구독 기준)
        sub_end = latest_sub.end_date.replace(tzinfo=timezone.utc) if latest_sub.end_date.tzinfo is None else latest_sub.end_date
        sub_start = latest_sub.start_date.replace(tzinfo=timezone.utc) if latest_sub.start_date.tzinfo is None else latest_sub.start_date
        total_days = (sub_end - sub_start).days or 30
        remaining_days = max((sub_end - now).days, 0)

        if remaining_days <= 0:
            raise HTTPException(status_code=400, detail="만료된 구독입니다.")

        # 2. 환불액 계산: 이전 구독 요금 × (잔여일수 / 전체 구독일수) - 새 요금제 금액
        previous_value = float(latest_sub.monthly_fee) * (remaining_days / total_days)
        refund_amount = round(previous_value - new_fee, 2)

        total_refund = 0
        cancel_results = []

        if refund_amount > 0:
            remaining_refund = refund_amount

            for sub in subs:
                if not sub.tid or remaining_refund <= 0:
                    continue

                try:
                    info = get_kakaopay_order_info(sub.tid)
                    available = info["cancel_available_amount"]["total"]
                    cancel_amount = min(available, remaining_refund)

                    if cancel_amount <= 0:
                        continue

                    cancel_response = cancel_kakaopay_payment(sub.tid, cancel_amount)
                    cancel_results.append({
                        "tid": sub.tid,
                        "refund_amount": cancel_amount,
                        "response": cancel_response
                    })
                    total_refund += cancel_amount
                    remaining_refund -= cancel_amount

                    if remaining_refund <= 0:
                        break

                except HTTPException:
                    continue

        elif refund_amount < 0:
            additional_payment = abs(refund_amount)

            payment_data = {
                "cid": os.getenv("KAKAOPAY_REG_CID"),
                "partner_order_id": f"order_{user_id}",
                "partner_user_id": str(user_id),
                "item_name": f"구독 다운그레이드 차액",
                "quantity": 1,
                "total_amount": int(additional_payment),
                "vat_amount": 0,
                "tax_free_amount": 0,
                "approval_url": f"http://localhost:8080/subscription/approve?user_id={user_id}&plan_type={plan_type}&monthly_fee={new_fee}",
                "cancel_url": "http://localhost:8080/subscription/cancel",
                "fail_url": "http://localhost:8080/subscription/fail"
            }

            headers = {
                "Authorization": f"SECRET_KEY {os.getenv('KAKAOPAY_SECRET_DEV')}",
                "Content-Type": "application/json"
            }

            try:
                response = requests.post("https://open-api.kakaopay.com/online/v1/payment/ready", headers=headers, json=payment_data)
                response.raise_for_status()
                result = response.json()

                new_plan = "basic" if new_fee == 0 else "premium" if new_fee == 2900 else "enterprise"

                pending_sub = Subscription(
                    user_id=user_id,
                    plan_type=new_plan,
                    monthly_fee=new_fee,
                    tid=result["tid"],
                    start_date=now,
                    end_date=now + timedelta(days=remaining_days),
                    status="PENDING"
                )
                db.add(pending_sub)
                db.commit()

                return {
                    "success": True,
                    "message": "추가 결제가 필요합니다.",
                    "additional_payment": additional_payment,
                    "redirect_url": result["next_redirect_pc_url"],
                    "action": "payment_required"
                }

            except requests.RequestException as e:
                raise HTTPException(status_code=400, detail=f"카카오페이 결제 준비 실패: {str(e)}")

        # 이전 구독은 상태 변경
        for sub in subs:
            sub.status = "CANCELLED"

        # 새 구독 생성
        if new_fee == Decimal('0.00'):
            new_plan = "basic"
        elif new_fee == Decimal('2900.00'):
            new_plan = "premium"
        else:
            new_plan = "enterprise"

        new_sub = Subscription(
            user_id=user_id,
            plan_type=new_plan,
            monthly_fee=new_fee,
            start_date=now,
            end_date=now + timedelta(days=remaining_days),
            status="ACTIVE",
            sid=latest_sub.sid
        )
        db.add(new_sub)
        db.commit()

        return {
            "success": True,
            "message": "다운그레이드 완료",
            "refund_amount": total_refund if refund_amount > 0 else 0,
            "remaining_days": remaining_days,
            "canceled": cancel_results if refund_amount > 0 else [],
            "additional_payment_required": abs(refund_amount) if refund_amount < 0 else 0
        }

@router.get("/status")
def get_subscription_status(user_id: int = Query(...)):
    with get_session_context() as db:
        active_sub = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == "ACTIVE"
        ).order_by(Subscription.subscription_id.desc()).first()

        if not active_sub:
            return {"plan_type": "free", "monthly_fee": 0}

        return {
            "plan_type": active_sub.plan_type,
            "monthly_fee": float(active_sub.monthly_fee)
        }


# ✅ 정기결제 스케줄러
@scheduler.scheduled_job("cron", hour=0)
def run_recurring_payments():
    with get_session_context() as db:
        # today = utc_to_kst(datetime.now(timezone.utc)).date()
        today = datetime.now(timezone.utc).date()
        subs = db.query(Subscription).filter(Subscription.status == "ACTIVE").all()
        for sub in subs:
            if sub.end_date.date() <= today:
                data = {
                    "cid": os.getenv("KAKAOPAY_REG_CID"),
                    "sid": sub.sid,
                    "partner_order_id": f"order_{sub.user_id}_{today}",
                    "partner_user_id": str(sub.user_id),
                    "quantity": 1,
                    "total_amount": int(sub.monthly_fee),
                    "item_name": sub.plan_type
                }
                headers = {
                    "Authorization": f"SECRET_KEY {os.getenv('KAKAOPAY_SECRET_DEV')}",
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
                }
                try:
                    res = requests.post("https://open-api.kakaopay.com/online/v1/payment/subscription", headers=headers, data=data)
                    res.raise_for_status()
                    sub.start_date = sub.end_date
                    sub.end_date = sub.start_date + timedelta(days=30)
                    db.commit()
                except:
                    sub.status = "EXPIRED"
                    db.commit()

scheduler.start()

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("regular_subscription:app", host="127.0.0.1", port=8080, reload=True)
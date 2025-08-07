from fastapi import APIRouter, Depends, HTTPException
from fastapi import FastAPI, HTTPException, BackgroundTasks, Body, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from unified_agent_system.database import get_db
from datetime import datetime, date, timedelta
import aiohttp
import asyncio
import logging
from sqlalchemy import func
from unified_agent_system.database import get_db
from shared_modules.db_models import Report

logger = logging.getLogger(__name__)
router = APIRouter()

# ===== 실시간 에이전트 상태 확인 함수 =====
AGENT_ENDPOINTS = {
    "business_planning": "http://localhost:8001",
    "marketing": "http://localhost:8003", 
    "customer_service": "http://localhost:8002",
    "mental_health": "http://localhost:8004",
    "task_automation": "https://localhost:8005"
}

async def check_agent_health(agent_name: str, base_url: str):
    """개별 에이전트 상태 확인"""
    try:
        async with aiohttp.ClientSession() as session:
            start_time = asyncio.get_event_loop().time()
            async with session.get(f"{base_url}/health", timeout=3) as response:
                end_time = asyncio.get_event_loop().time()
                response_time = round(end_time - start_time, 2)
                
                if response.status == 200:
                    return {"status": "healthy", "response_time": response_time}
                else:
                    return {"status": "warning", "response_time": response_time}
    except asyncio.TimeoutError:
        return {"status": "critical", "response_time": 3.0}
    except Exception:
        return {"status": "critical", "response_time": 0}

async def get_agents_real_status():
    """모든 에이전트의 실제 상태 확인"""
    tasks = [check_agent_health(name, url) for name, url in AGENT_ENDPOINTS.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 결과를 에이전트명과 매핑
    agent_status = {}
    for i, (agent_name, _) in enumerate(AGENT_ENDPOINTS.items()):
        if i < len(results) and isinstance(results[i], dict):
            agent_status[agent_name] = results[i]
        else:
            agent_status[agent_name] = {"status": "critical", "response_time": 0}
    
    # 전체 상태 판정
    healthy_count = sum(1 for status in agent_status.values() if status["status"] == "healthy")
    warning_count = sum(1 for status in agent_status.values() if status["status"] == "warning")
    critical_count = sum(1 for status in agent_status.values() if status["status"] == "critical")
    
    if critical_count > 0:
        overall_status = "critical"
    elif warning_count > 0:
        overall_status = "warning"
    else:
        overall_status = "healthy"
    
    return {"overall_status": overall_status, "agents": agent_status}

@router.get("/dashboard")
async def get_dashboard_data(db: Session = Depends(get_db)):
    today = date.today()
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # ✅ 오늘 생성된 리포트 수
    start_of_today = datetime.combine(today, datetime.min.time())
    end_of_today = datetime.combine(today, datetime.max.time())

    today_count = db.query(func.count()).filter(Report.created_at >= start_of_today).filter(Report.created_at <= end_of_today).scalar()

    # 최근 7일 리포트 수
    last_7_days_count = db.query(func.count()).filter(Report.created_at >= seven_days_ago).scalar()

    # 최근 30일 리포트 수
    last_30_days_count = db.query(func.count()).filter(Report.created_at >= thirty_days_ago).scalar()

    # 에이전트 상태
    agent_status_response = await get_agents_real_status()

    # 기본 통계
    total_users = db.execute(text("SELECT COUNT(*) FROM user")).scalar()
    active_users = db.execute(text("""
        SELECT COUNT(DISTINCT user_id)
        FROM conversation
        WHERE started_at >= :thirty_days_ago
    """), {"thirty_days_ago": thirty_days_ago}).scalar()

    premium_users = db.execute(text("""
        SELECT COUNT(*) FROM subscription
        WHERE (end_date IS NULL OR end_date > NOW())
        AND plan_type IN ('premium', 'enterprise')
    """)).scalar()
    queries_today = db.execute(text("""
        SELECT COUNT(*) FROM conversation
        WHERE DATE(started_at) = :today
    """), {"today": today}).scalar()

    # 추가 통계
    visitors_today = db.execute(text("""
        SELECT COUNT(DISTINCT user_id)
        FROM conversation
        WHERE DATE(started_at) = :today
    """), {"today": today}).scalar()
    today_created_users = db.execute(text("""
        SELECT COUNT(*) FROM user
        WHERE DATE(created_at) = :today
    """), {"today": today}).scalar()
    today_generated_report = db.execute(text("""
        SELECT COUNT(*) FROM report
        WHERE DATE(created_at) = :today
    """), {"today": today}).scalar()

    # task automation 비율
    task_automation_count = db.execute(text("""
            SELECT COUNT(*) FROM message
            WHERE DATE(created_at) = :today
            AND agent_type = 'task_automation'
        """), {"today": today}).scalar()

    total_conversations_today = db.execute(text("""
            SELECT COUNT(*) FROM message
            WHERE DATE(created_at) = :today
        """), {"today": today}).scalar()
    task_automation_ratio = (
        round(task_automation_count / total_conversations_today, 3)
        if total_conversations_today > 0 else 0.0
    )

    # 에이전트별 통계
    agent_conversations = db.execute(text("""
    SELECT 
        COALESCE(agent_type, 'business_planning') as agent_type,
        COUNT(*) as conversation_count
    FROM message
    WHERE created_at >= :date
    GROUP BY agent_type
"""), {"date": thirty_days_ago}).fetchall()
    today_stats = {agent.agent_type: agent.conversation_count for agent in agent_conversations}
    for name in AGENT_ENDPOINTS.keys():
        today_stats.setdefault(name, 0)

    # 평균 응답 시간
    response_times = [a["response_time"] for a in agent_status_response["agents"].values()]
    avg_response_time = round(sum(response_times) / len(response_times), 2) if response_times else 0.0

    # LLM & DB 상태 (하드코딩)
    llm_services = {
        "openai": {"status": "healthy", "success_rate": 0.98},
        "gemini": {"status": "healthy", "success_rate": 0.96}
    }
    databases = {
        "mysql": {"status": "healthy", "connections": 15},
        "chroma_db": {"status": "healthy", "collections": 5}
    }

    return {
          "system_health": {
            "overall_status": agent_status_response["overall_status"],
            "ai_agents": agent_status_response["agents"],
            "llm_services": llm_services,
            "databases": databases
        },
        "real_time_metrics": {
            "active_users": active_users,
            "queries_today": queries_today,
            "avg_response_time": avg_response_time,
            "error_rate": 0.02,
            "total_users": total_users,
            "premium_subscribers": premium_users,
            "visitors_today": visitors_today,
            "today_created_users": today_created_users,
            "today_generated_reports": today_count,  # ✅ key 수정
            "task_automation_ratio": task_automation_ratio,
            "last_7_days_reports": last_7_days_count,
            "last_30_days_reports": last_30_days_count
        },
        "today_stats": today_stats
    }

@router.get("/users")
def get_users(db: Session = Depends(get_db)):
    try:
        # ===== 사용자 + 최근 구독 + 대화 통계 조회 =====
        users_query = text("""
            SELECT 
                u.user_id,
                u.email,
                u.nickname,
                u.business_type,
                u.created_at,
                u.admin,
                u.experience,
                s.subscription_id,
                s.plan_type,
                s.start_date,
                s.end_date,
                s.monthly_fee,
                s.sid,
                s.tid,
                COUNT(DISTINCT c.conversation_id) AS total_conversations,
                MAX(c.started_at) AS last_active
            FROM user u
            LEFT JOIN (
                SELECT s1.*
                FROM subscription s1
                INNER JOIN (
                    SELECT user_id, MAX(start_date) AS latest_start
                    FROM subscription
                    GROUP BY user_id
                ) latest ON s1.user_id = latest.user_id AND s1.start_date = latest.latest_start
            ) s ON u.user_id = s.user_id
            LEFT JOIN conversation c ON u.user_id = c.user_id
            GROUP BY u.user_id
            ORDER BY u.created_at DESC
            LIMIT 100
        """)
        users_result = db.execute(users_query).fetchall()
        user_list = []

        for user in users_result:
            # ===== 활동 상태 판별 =====
            status = "active" if user.last_active and (datetime.now() - user.last_active).days <= 30 else "inactive"

            # ===== 구독 상태 계산 =====
            plan_type = user.plan_type or "basic"
            subscription_status = "active"
            expires_at = user.end_date.isoformat() if user.end_date else "2025-12-31"
            if user.end_date and user.end_date < datetime.now():
                subscription_status = "expired"

            # ===== 비즈니스 단계 추정 =====
            if user.experience == 1:
                business_stage = "성장"
            elif user.total_conversations > 50:
                business_stage = "확장"
            elif user.total_conversations > 10:
                business_stage = "초기"
            else:
                business_stage = "아이디어"

            # ===== 선호 에이전트 계산 =====
            favorite_agent_result = db.execute(text("""
                SELECT m.agent_type, COUNT(*) AS usage_count
                FROM message m
                JOIN conversation c ON m.conversation_id = c.conversation_id
                WHERE c.user_id = :user_id AND m.agent_type IS NOT NULL
                GROUP BY m.agent_type
                ORDER BY usage_count DESC
                LIMIT 1
            """), {"user_id": user.user_id}).fetchone()
            favorite_agent = favorite_agent_result.agent_type if favorite_agent_result else "business_planning"

            user_data = {
                "user_id": user.user_id,
                "email": user.email,
                "nickname": user.nickname or f"사용자{user.user_id}",
                "business_type": user.business_type or "미설정",
                "business_stage": business_stage,
                "status": status,
                "created_at": user.created_at.isoformat(),
                "subscription": {
                    "subscription_id": user.subscription_id,
                    "plan_type": plan_type,
                    "status": subscription_status,
                    "expires_at": expires_at,
                    "tid": user.tid,
                    "sid": user.sid
                },
                "usage_stats": {
                    "total_queries": user.total_conversations,
                    "last_active": user.last_active.isoformat() if user.last_active else None,
                    "favorite_agent": favorite_agent
                }
            }
            user_list.append(user_data)

        # ===== 전체 통계 =====
        total_users_count = db.execute(text("SELECT COUNT(*) FROM user")).scalar()
        active_users_count = sum(1 for u in user_list if u["status"] == "active")

        # 프리미엄 사용자 수: 유효 구독 중 최신 구독만
        premium_users_count = db.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT s.user_id
                FROM subscription s
                INNER JOIN (
                    SELECT user_id, MAX(start_date) AS latest_start
                    FROM subscription
                    GROUP BY user_id
                ) latest ON s.user_id = latest.user_id AND s.start_date = latest.latest_start
                WHERE s.plan_type IN ('premium', 'enterprise') AND (s.end_date IS NULL OR s.end_date > NOW())
            ) AS valid_paid
        """)).scalar()

        # 이번 달 신규 가입자
        this_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_this_month = db.execute(text(
            "SELECT COUNT(*) FROM user WHERE created_at >= :start_date"
        ), {"start_date": this_month_start}).scalar()

        return {
            "summary": {
                "total_users": total_users_count,
                "active_users": active_users_count,
                "premium_users": premium_users_count,
                "new_this_month": new_this_month
            },
            "users": user_list,
            "pagination": {
                "page": 1,
                "limit": len(user_list),
                "total": total_users_count,
                "total_pages": max(1, (total_users_count + 99) // 100)
            }
        }

    except Exception as e:
        logger.error(f"사용자 데이터 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"사용자 데이터 조회 실패: {str(e)}")


@router.get("/subscription")
def get_subscription(db: Session = Depends(get_db)):
    now = datetime.utcnow()

    # === user별 최신 구독 (유효한 end_date)
    latest_paid = db.execute(text("""
        SELECT s.user_id, s.plan_type
        FROM subscription s
        INNER JOIN (
            SELECT user_id, MAX(start_date) AS latest_start
            FROM subscription
            GROUP BY user_id
        ) latest ON s.user_id = latest.user_id AND s.start_date = latest.latest_start
        WHERE s.end_date > :now AND s.plan_type IN ('premium', 'enterprise')
    """), {"now": now}).fetchall()

    # === 집계 처리
    premium_subscribers = sum(1 for row in latest_paid if row.plan_type == "premium")
    enterprise_subscribers = sum(1 for row in latest_paid if row.plan_type == "enterprise")
    total_paid_users = premium_subscribers + enterprise_subscribers
    monthly_revenue = premium_subscribers * 2900 + enterprise_subscribers * 4900
    avg_revenue_per_user = int(monthly_revenue / total_paid_users) if total_paid_users > 0 else 0

    # === 전체 ACTIVE 사용자 수 (basic 포함)
    basic_subscribers = db.execute(text("""
        SELECT COUNT(DISTINCT s.user_id)
        FROM subscription s
        INNER JOIN (
            SELECT user_id, MAX(start_date) AS latest_start
            FROM subscription
            GROUP BY user_id
        ) latest ON s.user_id = latest.user_id AND s.start_date = latest.latest_start
        WHERE s.plan_type = 'basic' AND s.end_date > :now
    """), {"now": now}).scalar() or 0

    total_subscribers = basic_subscribers + total_paid_users

    # === 전체 구독 경험자 수 (churn 계산용)
    total_ever_subscribed = db.execute(text("""
        SELECT COUNT(DISTINCT user_id) FROM subscription
    """)).scalar()

    churn_rate = (
        max(0, (total_ever_subscribed - total_subscribers) / total_ever_subscribed)
        if total_ever_subscribed > 0 else 0
    )

    # 체험 → 유료 전환율 (전체 유저 중 유료 plan_type 있는 유저 비율)
    trial_anytime_q = db.execute(text("""
        SELECT
            COUNT(DISTINCT u.user_id) AS total_users,
            COUNT(DISTINCT s.user_id) AS converted_users
        FROM user u
        LEFT JOIN (
            SELECT user_id
            FROM subscription
            WHERE plan_type IN ('premium', 'enterprise')
        ) s ON u.user_id = s.user_id
    """)).fetchone()

    trial_to_paid_anytime_rate = round(
        (trial_anytime_q.converted_users or 0) / max(trial_anytime_q.total_users or 1, 1), 4
    )
    # === 7일 이내 유료 전환율
    early_q = db.execute(text("""
        SELECT COUNT(DISTINCT u.user_id) AS total_users,
               SUM(CASE
                   WHEN s.plan_type IN ('premium', 'enterprise')
                        AND s.start_date <= DATE_ADD(u.created_at, INTERVAL 7 DAY)
                        AND s.end_date > :now
                   THEN 1 ELSE 0 END) AS early_paid
        FROM user u
        LEFT JOIN subscription s ON u.user_id = s.user_id
    """), {"now": now}).fetchone()

    early_conversion_rate = round(
        (early_q.early_paid or 0) / max(early_q.total_users or 1, 1), 4
    )

    monthly_churn_rate = churn_rate / 12 if churn_rate > 0 else 0.01
    lifetime_value = int(avg_revenue_per_user / monthly_churn_rate)

    # 업그레이드 수
    upgrade_q = db.execute(text("""
        SELECT COUNT(*) AS upgrade_count
        FROM subscription
        WHERE status = 'MODIFIED' AND plan_type IN ('premium', 'enterprise')
    """)).fetchone()
    upgrade_count = upgrade_q.upgrade_count or 0

    # basic 체류일
    basic_duration = db.execute(text("""
        SELECT AVG(DATEDIFF(end_date, start_date)) AS avg_days
        FROM subscription
        WHERE plan_type = 'basic' AND end_date IS NOT NULL
    """)).fetchone()
    avg_basic_duration_days = round(basic_duration.avg_days or 0, 1)

    # 유료 체류일
    duration_q = db.execute(text("""
        SELECT AVG(DATEDIFF(end_date, start_date)) AS avg_days
        FROM subscription
        WHERE plan_type IN ('premium', 'enterprise')
        AND end_date > :now
        AND start_date IS NOT NULL AND end_date IS NOT NULL
    """), {"now": now}).fetchone()
    avg_days = float(duration_q.avg_days or 30)
    advanced_ltv = int(avg_revenue_per_user * (avg_days / 30))

    # 결제 이슈 (예시 placeholder)
    failed_payments = 0
    pending_retries = 0
    requiring_attention = 0

    # === 응답 ===
    return {
        "subscription_overview": {
            "total_subscribers": total_subscribers,
            "basic_subscribers": basic_subscribers,
            "premium_subscribers": premium_subscribers,
            "enterprise_subscribers": enterprise_subscribers,
            "monthly_revenue": monthly_revenue,
            "churn_rate": round(churn_rate, 3),
            "total_paid_users": total_paid_users
        },
        "revenue_metrics": {
            "mrr": monthly_revenue,
            "arr": monthly_revenue * 12,
            "average_revenue_per_user": avg_revenue_per_user,
            "lifetime_value": lifetime_value
        },
        "conversion_funnel": {
            "trial_users": trial_anytime_q.total_users,
            "trial_to_paid_rate": trial_to_paid_anytime_rate,   # 전체 기준
            "early_conversion_rate": early_conversion_rate,      # 7일 기준 → 이 항목은 behavioral_insights에 둠
            "basic_to_premium_rate": 0.0,
            "reactivation_rate": 0.15
        },
        "behavioral_insights": {
            "early_conversion_rate": early_conversion_rate,
            "avg_basic_duration_days": avg_basic_duration_days,
            "upgrade_count": upgrade_count,
            "estimated_ltv": advanced_ltv
        },
        "payment_issues": {
            "failed_payments": failed_payments,
            "pending_retries": pending_retries,
            "requiring_attention": requiring_attention
        }
    }


@router.get("/feedback")
def get_feedback(db: Session = Depends(get_db)):
    try:
        # ===== 피드백 전체 통계 (실제 DB 계산) =====
        feedback_overview = db.execute(text("""
            SELECT 
                COUNT(*) as total_feedback,
                AVG(rating) as avg_rating,
                COUNT(CASE WHEN rating <= 2 THEN 1 END) as low_ratings,
                COUNT(CASE WHEN comment IS NOT NULL AND comment != '' THEN 1 END) as with_comments
            FROM feedback
        """)).fetchone()
        
        total_feedback = feedback_overview.total_feedback or 0
        avg_rating = feedback_overview.avg_rating or 0.0
        low_ratings_count = feedback_overview.low_ratings or 0
        # 응답률 = 댓글이 있는 피드백 / 전체 피드백
        response_rate = (feedback_overview.with_comments / total_feedback) if total_feedback > 0 else 0

        AGENT_TYPE_MAPPING = {
            "task_automation": "task_agent",  # 통합 처리
            "business_planning": "business_planning",
            "marketing": "marketing",
            "customer_service": "customer_service",
            "mental_health": "mental_health",
            "task_agent": "task_agent",
            # 필요한 매핑 추가 가능
        }        
        # ===== 평점 분포 (실제 계산) =====
        rating_distribution = {}
        for rating in range(1, 6):
            count = db.execute(text(
                "SELECT COUNT(*) FROM feedback WHERE rating = :rating"
            ), {"rating": rating}).scalar()
            rating_distribution[str(rating)] = count
        
        # ===== 최근 낮은 평점 피드백 조회 (처리 필요한 실제 데이터) =====
        low_rating_feedbacks = db.execute(text("""
            SELECT 
                f.feedback_id, 
                f.user_id, 
                f.rating, 
                f.comment, 
                f.created_at,
                u.nickname
            FROM feedback f
            LEFT JOIN user u ON f.user_id = u.user_id
            WHERE f.rating <= 2
            ORDER BY f.created_at DESC
            LIMIT 10
        """)).fetchall()
        
        requires_attention = [
            {
                "feedback_id": fb.feedback_id,
                "user_id": fb.user_id,
                "rating": float(fb.rating) if fb.rating is not None else 0.0,
                "comment": fb.comment or "댓글 없음",
                "created_at": fb.created_at.isoformat() if fb.created_at else None,
                "nickname": fb.nickname or "알 수 없음",
                "status": "pending"
            }
            for fb in low_rating_feedbacks
        ]
        
        # ===== 에이전트별 만족도 계산 =====
        # conversation 테이블과 연결하여 에이전트별 평균 평점 계산
        agent_satisfaction = []
        agent_satisfaction_query = db.execute(text("""
            SELECT 
                COALESCE(m.agent_type, 'business_planning') AS agent_type,
                AVG(f.rating) AS avg_rating,
                COUNT(f.feedback_id) AS feedback_count
            FROM feedback f
            LEFT JOIN (
                SELECT m1.conversation_id, m1.agent_type
                FROM message m1
                INNER JOIN (
                    SELECT conversation_id, MAX(created_at) AS latest_time
                    FROM message
                    WHERE agent_type IS NOT NULL
                    GROUP BY conversation_id
                ) latest ON m1.conversation_id = latest.conversation_id AND m1.created_at = latest.latest_time
            ) m ON f.conversation_id = m.conversation_id
            WHERE f.rating IS NOT NULL
            GROUP BY m.agent_type
            HAVING feedback_count > 0;
        """)).fetchall()
        
       # 쿼리 후 통합된 agent_type으로 재가공
        for agent_stat in agent_satisfaction_query:
            raw_type = agent_stat.agent_type or "unknown"
            unified_type = AGENT_TYPE_MAPPING.get(raw_type, raw_type)

            avg_rating = round(float(agent_stat.avg_rating), 1) if agent_stat.avg_rating is not None else 0.0
            count = agent_stat.feedback_count or 0
            trend = "상승" if avg_rating >= 4.0 else "보통" if avg_rating >= 3.5 else "하락"

            # 집계할 항목이 이미 있으면 누적
            existing = next((a for a in agent_satisfaction if a["agent_type"] == unified_type), None)
            if existing:
                existing["total_feedback"] += count
                existing["average_rating"] = round((existing["average_rating"] * existing["total_feedback"] + avg_rating * count) / (existing["total_feedback"] + count), 1)
            else:
                agent_satisfaction.append({
                    "agent_type": unified_type,
                    "average_rating": avg_rating,
                    "total_feedback": count,
                    "satisfaction_trend": trend
                })
        # ===== 공통 이슈 분석 =====
        # 실제 댓글에서 키워드 기반으로 이슈 분류 (간단한 키워드 매칭)
        common_issues_query = db.execute(text("""
            SELECT 
                CASE 
                    WHEN LOWER(comment) LIKE '%느림%' OR LOWER(comment) LIKE '%slow%' THEN '응답 속도 느림'
                    WHEN LOWER(comment) LIKE '%틀림%' OR LOWER(comment) LIKE '%잘못%' OR LOWER(comment) LIKE '%부정확%' THEN '부정확한 정보'
                    WHEN LOWER(comment) LIKE '%이해%' OR LOWER(comment) LIKE '%맥락%' THEN '맥락 이해 부족'
                    ELSE '기타'
                END as issue_type,
                COUNT(*) as issue_count
            FROM feedback 
            WHERE rating <= 2 AND comment IS NOT NULL AND comment != ''
            GROUP BY issue_type
            ORDER BY issue_count DESC
        """)).fetchall()
        
        common_issues = []
        total_categorized_issues = sum(issue.issue_count for issue in common_issues_query)
        
        for issue in common_issues_query:
            percentage = issue.issue_count / total_categorized_issues if total_categorized_issues > 0 else 0
            common_issues.append({
                "issue": issue.issue_type,
                "count": issue.issue_count,
                "percentage": round(percentage, 2)
            })
        
        # ===== 개선 추세 계산 =====
        # 최근 30일 vs 이전 30일 평점 비교
        thirty_days_ago = datetime.now() - timedelta(days=30)
        sixty_days_ago = datetime.now() - timedelta(days=60)
        
        recent_avg = db.execute(text(
            "SELECT AVG(rating) FROM feedback WHERE created_at >= :thirty_days_ago"
        ), {"thirty_days_ago": thirty_days_ago}).scalar() or 0
        
        previous_avg = db.execute(text(
            "SELECT AVG(rating) FROM feedback WHERE created_at BETWEEN :sixty_days_ago AND :thirty_days_ago"
        ), {"sixty_days_ago": sixty_days_ago, "thirty_days_ago": thirty_days_ago}).scalar() or 0
        
        improvement = recent_avg - previous_avg if previous_avg > 0 else 0
        improvement_trend = f"{improvement:+.1f}점" if improvement != 0 else "변화없음"

        return {
            "overview": {
                "total_feedback": total_feedback,           # 실제 피드백 수
                "average_rating": round(avg_rating, 1),     # 실제 평균 평점
                "response_rate": round(response_rate, 2),   # 실제 응답률
                "improvement_trend": improvement_trend      # 실제 계산된 추세
            },
            "rating_distribution": rating_distribution,    # 실제 평점 분포
            "agent_satisfaction": agent_satisfaction,      # 실제 에이전트별 만족도
            "negative_feedback": {
                "total_low_ratings": low_ratings_count,    # 실제 낮은 평점 수
                "common_issues": common_issues,            # 실제 이슈 분석
                "requires_attention": requires_attention   # 실제 처리 필요 피드백
            }
        }
        
    except Exception as e:
        logger.error(f"피드백 데이터 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"피드백 데이터 조회 실패: {str(e)}")

# ===== 추가: 에이전트별 상세 성능 모니터링 엔드포인트 =====
@router.get("/agents/performance")
async def get_agents_performance():
    """에이전트별 상세 성능 모니터링"""
    try:
        # 여러 번 체크해서 더 정확한 응답 시간 측정
        performance_data = {}
        
        for agent_name, base_url in AGENT_ENDPOINTS.items():
            # 3번 체크해서 평균값 계산
            response_times = []
            statuses = []
            
            for _ in range(3):
                result = await check_agent_health(agent_name, base_url)
                response_times.append(result["response_time"])
                statuses.append(result["status"])
            
            # 가장 많이 나온 상태 선택
            most_common_status = max(set(statuses), key=statuses.count)
            avg_response_time = round(sum(response_times) / len(response_times), 3)
            
            performance_data[agent_name] = {
                "status": most_common_status,
                "avg_response_time": avg_response_time,
                "min_response_time": round(min(response_times), 3),
                "max_response_time": round(max(response_times), 3),
                "check_count": len(response_times)
            }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "agents": performance_data
        }
        
    except Exception as e:
        logger.error(f"에이전트 성능 모니터링 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

"""
Task Agent 자동화 시스템 v5
리팩토링된 자동화 작업 관리 및 스케쥴링
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

# 공통 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "../shared_modules"))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

# 공통 모듈의 DB 모델들
try:
    import shared_modules.db_models as db_models
    from database import get_db_session
except ImportError:
    # 공통 모듈이 없는 경우 더미 클래스
    class db_models:
        class AutomationTask:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
    
    def get_db_session():
        return None

from models import AutomationRequest, AutomationResponse, AutomationStatus, AutomationTaskType
from utils import TaskAgentLogger, create_success_response, create_error_response

# 자동화 작업 실행기들
from automation_executors.email_executor import EmailExecutor
from automation_executors.calendar_executor import CalendarExecutor
from automation_executors.instagram_executor import InstagramExecutor

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """작업 상태"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class AutomationTask:
    """자동화 작업 데이터 클래스"""
    task_id: int
    user_id: int
    task_type: str
    title: str
    task_data: Dict[str, Any]
    status: str
    scheduled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    result_data: Optional[Dict[str, Any]] = None

class AutomationManager:
    """자동화 매니저 - 핵심 기능에 집중"""
    
    def __init__(self):
        """자동화 매니저 초기화"""
        try:
            # 스케줄러 설정
            self._setup_scheduler()
            
            # 실행기들 초기화
            self._setup_executors()
            
            # 상태 추적
            self.active_tasks: Dict[int, AutomationTask] = {}
            
            logger.info("자동화 매니저 v5 초기화 완료")
            
        except Exception as e:
            logger.error(f"자동화 매니저 초기화 실패: {e}")
            raise

    def _setup_scheduler(self):
        """스케줄러 설정"""
        try:
            # 스케줄러 설정
            jobstores = {'default': MemoryJobStore()}
            executors = {'default': AsyncIOExecutor()}
            job_defaults = {
                'coalesce': True,
                'max_instances': 3,
                'misfire_grace_time': 300  # 5분 유예시간
            }
            
            self.scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults
            )
            
            # 스케줄러 시작
            self.scheduler.start()
            
            logger.info("스케줄러 초기화 완료")
            
        except Exception as e:
            logger.error(f"스케줄러 초기화 실패: {e}")
            raise

    def _setup_executors(self):
        """작업 실행기들 초기화"""
        try:
            self.executors = {
                AutomationTaskType.SEND_EMAIL.value: EmailExecutor(),
                AutomationTaskType.SCHEDULE_CALENDAR.value: CalendarExecutor(),
                AutomationTaskType.POST_INSTAGRAM.value: InstagramExecutor()
            }
            
            logger.info("자동화 실행기들 초기화 완료")
            
        except Exception as e:
            logger.error(f"실행기 초기화 실패: {e}")
            # 실행기 초기화 실패해도 매니저는 동작하도록 함
            self.executors = {}

    async def create_automation_task(self, request: AutomationRequest) -> AutomationResponse:
        """자동화 작업 생성 및 등록"""
        try:
            TaskAgentLogger.log_automation_task(
                task_id="creating",
                task_type=request.task_type.value,
                status="creating",
                details=f"user_id: {request.user_id}, title: {request.title}"
            )
            
            # # 1. 데이터 검증
            # validation_result = self._validate_task_data(request)
            # if not validation_result["is_valid"]:
            #     return AutomationResponse(
            #         task_id=-1,
            #         status=AutomationStatus.FAILED,
            #         message=f"작업 데이터 검증 실패: {', '.join(validation_result['errors'])}"
            #     )
            
            # 2. DB에 작업 저장
            task_id = await self._save_task_to_db(request)
            
            # 3. 스케쥴링 또는 즉시 실행
            if request.scheduled_at:
                # 예약 실행
                result = await self._schedule_task(task_id, request.scheduled_at)
                return AutomationResponse(
                    task_id=task_id,
                    status=AutomationStatus.PENDING,
                    message=f"작업이 {request.scheduled_at.strftime('%Y-%m-%d %H:%M')}에 예약되었습니다.",
                    scheduled_time=request.scheduled_at
                )
            else:
                # 즉시 실행
                result = await self._execute_task_immediately(task_id)
                return AutomationResponse(
                    task_id=task_id,
                    status=AutomationStatus.SUCCESS if result["success"] else AutomationStatus.FAILED,
                    message=result["message"]
                )
                
        except Exception as e:
            logger.error(f"자동화 작업 생성 실패: {e}")
            TaskAgentLogger.log_automation_task(
                task_id="failed",
                task_type=request.task_type.value,
                status="failed",
                details=f"creation error: {str(e)}"
            )
            
            return AutomationResponse(
                task_id=-1,
                status=AutomationStatus.FAILED,
                message=f"작업 생성 실패: {str(e)}"
            )

    async def _save_task_to_db(self, request: AutomationRequest) -> int:
        """작업을 데이터베이스에 저장"""
        try:
            db_session = get_db_session()
            if not db_session:
                # DB 세션이 없는 경우 임시 ID 생성
                task_id = int(datetime.now().timestamp() * 1000) % 1000000
                
                # 메모리에 작업 정보 저장
                self.active_tasks[task_id] = AutomationTask(
                    task_id=task_id,
                    user_id=request.user_id,
                    task_type=request.task_type.value,
                    title=request.title,
                    task_data=request.task_data,
                    status=AutomationStatus.PENDING.value,
                    scheduled_at=request.scheduled_at,
                    created_at=datetime.now()
                )
                
                return task_id
            
            try:
                automation_task = db_models.AutomationTask(
                    user_id=request.user_id,
                    task_type=request.task_type.value,
                    title=request.title,
                    task_data=request.task_data,
                    status=AutomationStatus.PENDING.value,
                    scheduled_at=request.scheduled_at,
                    created_at=datetime.now()
                )
                
                db_session.add(automation_task)
                db_session.commit()
                db_session.refresh(automation_task)
                
                task_id = automation_task.task_id
                
                # 메모리에 작업 정보 저장
                self.active_tasks[task_id] = AutomationTask(
                    task_id=task_id,
                    user_id=request.user_id,
                    task_type=request.task_type.value,
                    title=request.title,
                    task_data=request.task_data,
                    status=AutomationStatus.PENDING.value,
                    scheduled_at=request.scheduled_at,
                    created_at=automation_task.created_at
                )
                
                TaskAgentLogger.log_automation_task(
                    task_id=str(task_id),
                    task_type=request.task_type.value,
                    status="saved_to_db",
                    details="작업이 데이터베이스에 저장됨"
                )
                
                return task_id
                
            finally:
                db_session.close()
                
        except Exception as e:
            logger.error(f"DB 저장 실패: {e}")
            raise

    async def _schedule_task(self, task_id: int, scheduled_at: datetime) -> Dict[str, Any]:
        """작업 스케쥴링"""
        try:
            # 스케줄러에 작업 등록
            self.scheduler.add_job(
                self._execute_scheduled_task,
                'date',
                run_date=scheduled_at,
                args=[task_id],
                id=f"auto_{task_id}",
                misfire_grace_time=300  # 5분 유예시간
            )
            
            # DB 상태 업데이트
            await self._update_task_status(task_id, TaskStatus.SCHEDULED.value)
            
            TaskAgentLogger.log_automation_task(
                task_id=str(task_id),
                task_type="unknown",
                status="scheduled",
                details=f"작업이 {scheduled_at}에 예약됨"
            )
            
            return {"success": True, "message": "작업이 성공적으로 예약되었습니다."}
            
        except Exception as e:
            logger.error(f"작업 스케쥴링 실패 (ID: {task_id}): {e}")
            # 스케쥴링 실패시 즉시 실행으로 폴백
            return await self._execute_task_immediately(task_id)

    async def _execute_task_immediately(self, task_id: int) -> Dict[str, Any]:
        """작업 즉시 실행"""
        try:
            result = await self._execute_task_by_id(task_id)
            return {
                "success": result.get("status") == "success",
                "message": result.get("message", "작업이 실행되었습니다.")
            }
        except Exception as e:
            logger.error(f"즉시 실행 실패 (ID: {task_id}): {e}")
            return {"success": False, "message": f"실행 실패: {str(e)}"}

    async def _execute_scheduled_task(self, task_id: int):
        """스케쥴러에서 호출되는 작업 실행"""
        try:
            TaskAgentLogger.log_automation_task(
                task_id=str(task_id),
                task_type="unknown",
                status="triggered_by_scheduler",
                details="스케쥴러에 의해 작업 실행 시작"
            )
            
            await self._execute_task_by_id(task_id)
            
        except Exception as e:
            logger.error(f"스케쥴된 작업 실행 실패 (ID: {task_id}): {e}")
            await self._update_task_status(
                task_id, 
                TaskStatus.FAILED.value, 
                result_data={"error": str(e)}
            )

    async def _execute_task_by_id(self, task_id: int) -> Dict[str, Any]:
        """ID로 작업 실행"""
        try:
            # 1. 작업 정보 조회
            task = await self._get_task_by_id(task_id)
            if not task:
                error_msg = f"작업을 찾을 수 없습니다 (ID: {task_id})"
                TaskAgentLogger.log_automation_task(
                    task_id=str(task_id),
                    task_type="unknown",
                    status="not_found",
                    details=error_msg
                )
                return {"status": "failed", "message": error_msg}
            
            # 2. 실행 상태로 업데이트
            await self._update_task_status(
                task_id, 
                TaskStatus.PROCESSING.value,
                executed_at=datetime.now()
            )
            
            TaskAgentLogger.log_automation_task(
                task_id=str(task_id),
                task_type=task.task_type,
                status="executing",
                details=f"작업 실행 시작: {task.title}"
            )
            
            # 3. 타입별 실행
            result = await self._execute_by_type(task)
            
            # 4. 결과에 따른 상태 업데이트
            final_status = TaskStatus.SUCCESS.value if result["status"] == "success" else TaskStatus.FAILED.value
            await self._update_task_status(task_id, final_status, result_data=result)
            
            TaskAgentLogger.log_automation_task(
                task_id=str(task_id),
                task_type=task.task_type,
                status=final_status,
                details=f"실행 완료: {result.get('message', 'no message')}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"작업 실행 실패 (ID: {task_id}): {e}")
            
            # 실패 상태로 업데이트
            await self._update_task_status(
                task_id, 
                TaskStatus.FAILED.value,
                result_data={"error": str(e)}
            )
            
            return {"status": "failed", "message": str(e)}

    async def _execute_by_type(self, task: AutomationTask) -> Dict[str, Any]:
        """타입별 작업 실행"""
        try:
            executor = self.executors.get(task.task_type)
            
            if not executor:
                return {
                    "status": "failed",
                    "message": f"지원하지 않는 작업 타입: {task.task_type}"
                }
            
            # 실행기를 통한 작업 실행
            result = await executor.execute(task.task_data, task.user_id)
            
            return {
                "status": "success" if result.get("success") else "failed",
                "message": result.get("message", "작업이 실행되었습니다."),
                "details": result
            }
            
        except Exception as e:
            logger.error(f"타입별 작업 실행 실패 ({task.task_type}): {e}")
            return {"status": "failed", "message": str(e)}

    async def _get_task_by_id(self, task_id: int) -> Optional[AutomationTask]:
        """ID로 작업 조회"""
        try:
            # 먼저 메모리에서 조회
            if task_id in self.active_tasks:
                return self.active_tasks[task_id]
            
            # DB에서 조회 (DB가 있는 경우)
            db_session = get_db_session()
            if not db_session:
                return None
            
            try:
                db_task = db_session.query(db_models.AutomationTask).filter(
                    db_models.AutomationTask.task_id == task_id
                ).first()
                
                if db_task:
                    task = AutomationTask(
                        task_id=db_task.task_id,
                        user_id=db_task.user_id,
                        task_type=db_task.task_type,
                        title=db_task.title,
                        task_data=db_task.task_data or {},
                        status=db_task.status,
                        scheduled_at=db_task.scheduled_at,
                        created_at=db_task.created_at,
                        executed_at=db_task.executed_at,
                        result_data=db_task.result_data
                    )
                    
                    # 메모리에 캐시
                    self.active_tasks[task_id] = task
                    return task
                
                return None
                
            finally:
                db_session.close()
                
        except Exception as e:
            logger.error(f"작업 조회 실패 (ID: {task_id}): {e}")
            return None

    async def _update_task_status(self, task_id: int, status: str, 
                                executed_at: Optional[datetime] = None,
                                result_data: Optional[Dict[str, Any]] = None):
        """작업 상태 업데이트"""
        try:
            # 메모리 업데이트
            if task_id in self.active_tasks:
                self.active_tasks[task_id].status = status
                if executed_at:
                    self.active_tasks[task_id].executed_at = executed_at
                if result_data:
                    self.active_tasks[task_id].result_data = result_data
            
            # DB 업데이트 (DB가 있는 경우)
            db_session = get_db_session()
            if not db_session:
                return
            
            try:
                db_task = db_session.query(db_models.AutomationTask).filter(
                    db_models.AutomationTask.task_id == task_id
                ).first()
                
                if db_task:
                    db_task.status = status
                    if executed_at:
                        db_task.executed_at = executed_at
                    if result_data:
                        db_task.result_data = result_data
                    
                    db_session.commit()
                
            finally:
                db_session.close()
                
        except Exception as e:
            logger.error(f"상태 업데이트 실패 (ID: {task_id}): {e}")

    def _validate_task_data(self, request: AutomationRequest) -> Dict[str, Any]:
        """작업 데이터 검증"""
        errors = []
        warnings = []
        
        # 기본 검증
        if not request.title.strip():
            errors.append("작업 제목이 필요합니다")
        
        if not request.task_data:
            errors.append("작업 데이터가 필요합니다")
        
        # 타입별 검증
        task_type = request.task_type
        task_data = request.task_data
        
        if task_type == AutomationTaskType.SEND_EMAIL:
            if not task_data.get("to_emails"):
                errors.append("수신자 이메일이 필요합니다")
            if not task_data.get("subject"):
                errors.append("이메일 제목이 필요합니다")
            if not task_data.get("body"):
                errors.append("이메일 내용이 필요합니다")
                
        elif task_type == AutomationTaskType.SCHEDULE_CALENDAR:
            if not task_data.get("title"):
                errors.append("일정 제목이 필요합니다")
            if not task_data.get("start_time"):
                errors.append("시작 시간이 필요합니다")
                
        elif task_type == AutomationTaskType.SEND_REMINDER:
            if not task_data.get("message"):
                errors.append("리마인더 메시지가 필요합니다")
            if not task_data.get("remind_time"):
                errors.append("알림 시간이 필요합니다")
                
        elif task_type == AutomationTaskType.SEND_MESSAGE:
            if not task_data.get("platform"):
                errors.append("메시지 플랫폼이 필요합니다")
            if not task_data.get("content"):
                errors.append("메시지 내용이 필요합니다")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    # ===== 공개 API =====

    async def get_task_status(self, task_id: int) -> Dict[str, Any]:
        """작업 상태 조회"""
        try:
            task = await self._get_task_by_id(task_id)
            
            if not task:
                return {"error": "작업을 찾을 수 없습니다"}
            
            return {
                "task_id": task_id,
                "status": task.status,
                "title": task.title,
                "task_type": task.task_type,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "executed_at": task.executed_at.isoformat() if task.executed_at else None,
                "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
                "user_id": task.user_id,
                "result_data": task.result_data
            }
            
        except Exception as e:
            logger.error(f"작업 상태 조회 실패: {e}")
            return {"error": str(e)}

    async def cancel_task(self, task_id: int) -> bool:
        """작업 취소"""
        try:
            # 스케줄러에서 제거
            try:
                self.scheduler.remove_job(f"auto_{task_id}")
                logger.info(f"스케줄러에서 작업 제거 완료: {task_id}")
            except Exception as scheduler_error:
                logger.warning(f"스케줄러 작업 제거 실패: {scheduler_error}")
            
            # 상태 업데이트
            await self._update_task_status(task_id, TaskStatus.CANCELLED.value)
            
            TaskAgentLogger.log_automation_task(
                task_id=str(task_id),
                task_type="unknown",
                status="cancelled",
                details="사용자 요청에 의해 작업 취소"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"작업 취소 실패: {e}")
            return False

    async def get_user_tasks(self, user_id: int, status: Optional[str] = None, 
                           limit: int = 50) -> List[Dict[str, Any]]:
        """사용자의 자동화 작업 목록 조회"""
        try:
            # 메모리에서 조회
            result = []
            for task in self.active_tasks.values():
                if task.user_id == user_id:
                    if status is None or task.status == status:
                        result.append({
                            "task_id": task.task_id,
                            "title": task.title,
                            "task_type": task.task_type,
                            "status": task.status,
                            "created_at": task.created_at.isoformat() if task.created_at else None,
                            "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
                            "executed_at": task.executed_at.isoformat() if task.executed_at else None
                        })
            
            # 생성 시간 기준 내림차순 정렬
            result.sort(key=lambda x: x["created_at"] or "", reverse=True)
            
            return result[:limit]
                
        except Exception as e:
            logger.error(f"사용자 작업 목록 조회 실패: {e}")
            return []

    async def get_system_stats(self) -> Dict[str, Any]:
        """시스템 통계 조회"""
        try:
            # 기본 통계
            total_tasks = len(self.active_tasks)
            
            # 상태별 통계
            status_stats = {}
            for status in TaskStatus:
                count = sum(1 for task in self.active_tasks.values() 
                           if task.status == status.value)
                status_stats[status.value] = count
            
            # 스케줄러 정보
            scheduler_jobs = len(self.scheduler.get_jobs())
            
            # 실행기 상태
            executor_status = {}
            for task_type, executor in self.executors.items():
                executor_status[task_type] = hasattr(executor, 'is_available') and executor.is_available()
            
            return {
                "total_tasks": total_tasks,
                "status_distribution": status_stats,
                "scheduler_jobs": scheduler_jobs,
                "executor_status": executor_status,
                "active_tasks_in_memory": len(self.active_tasks),
                "timestamp": datetime.now().isoformat()
            }
                
        except Exception as e:
            logger.error(f"시스템 통계 조회 실패: {e}")
            return {"error": str(e)}

    async def cleanup(self):
        """자동화 매니저 정리"""
        try:
            # 스케줄러 종료
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("스케줄러 종료 완료")
            
            # 실행기들 정리
            for executor in self.executors.values():
                if hasattr(executor, 'cleanup'):
                    try:
                        await executor.cleanup()
                    except Exception as e:
                        logger.warning(f"실행기 정리 실패: {e}")
            
            # 메모리 정리
            self.active_tasks.clear()
            
            logger.info("자동화 매니저 정리 완료")
            
        except Exception as e:
            logger.error(f"자동화 매니저 정리 실패: {e}")


# 기존 코드와의 호환성을 위한 별칭
TaskAgentAutomationManager = AutomationManager

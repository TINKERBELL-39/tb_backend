# 마케팅 자동화 API

네이버 블로그 검색 키워드 통계 기반 컨텐츠 제작 및 인스타그램 포스팅을 자동화하는 FastAPI 기반 서비스입니다.

## 📋 주요 기능

### 🔍 키워드 분석
- 네이버 검색 API를 통한 키워드 트렌드 분석
- 검색량, 경쟁도, 관련 키워드 추출
- 실시간 트렌딩 키워드 모니터링

### 📝 블로그 자동화
- 키워드 기반 SEO 최적화 블로그 콘텐츠 자동 생성
- 네이버 블로그 자동 업로드
- 스케줄링 기반 정기 포스팅
- 성과 분석 및 리포팅

### 📸 인스타그램 자동화
- 해시태그 분석 및 최적화
- 이미지 생성 및 캡션 작성
- 자동 포스팅 및 스케줄링
- 인게이지먼트 트래킹

### ⚙️ 스케줄링 및 모니터링
- APScheduler 기반 작업 스케줄링
- 실시간 상태 모니터링
- 오류 처리 및 재시도 로직
- 상세한 활동 로그

## 🚀 빠른 시작

### 1. 요구사항
- Python 3.8 이상
- PostgreSQL 12 이상 (선택사항, SQLite 폴백 지원)
- Redis (선택사항, 캐싱용)

### 2. 설치

```bash
# 저장소 클론
git clone <repository-url>
cd task_agent/automation_task/marketing

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\\Scripts\\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 3. 환경 설정

```bash
# 환경변수 파일 생성
cp .env.example .env

# .env 파일 편집
nano .env
```

필수 환경변수:
```env
# API 키 설정
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
INSTAGRAM_ACCESS_TOKEN=your_instagram_access_token
OPENAI_API_KEY=your_openai_api_key

# 데이터베이스 설정 (PostgreSQL 사용시)
DATABASE_URL=postgresql://user:password@localhost:5432/marketing_automation

# 보안 설정
SECRET_KEY=your-very-secret-key-change-this
```

### 4. 데이터베이스 초기화

```bash
# PostgreSQL 사용시
createdb marketing_automation

# SQLite 사용시 (자동 생성됨)
# 별도 설정 불필요
```

### 5. 서버 실행

```bash
# 개발 서버 실행
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 또는 main.py 직접 실행
python main.py
```

서버가 시작되면 다음 URL에서 접근 가능합니다:
- API 문서: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- API 엔드포인트: http://localhost:8000

## 📚 API 사용법

### 블로그 자동화 설정

```python
import requests

# 블로그 자동화 설정
config = {
    "enabled": True,
    "keywords": ["마케팅 자동화", "AI 마케팅", "소셜미디어"],
    "schedule": {
        "frequency": "daily",
        "time": "09:00",
        "days": ["monday", "wednesday", "friday"]
    },
    "template": "안녕하세요! 오늘은 {keyword}에 대해 이야기해보겠습니다...",
    "auto_publish": False,
    "target_platform": "naver_blog"
}

response = requests.post("http://localhost:8000/blog/setup", json=config)
print(response.json())
```

### 인스타그램 자동화 설정

```python
# 인스타그램 자동화 설정
config = {
    "enabled": True,
    "hashtags": ["#마케팅", "#비즈니스", "#AI", "#인사이트"],
    "schedule": {
        "frequency": "daily",
        "time": "12:00"
    },
    "auto_post": False,
    "image_style": "modern"
}

response = requests.post("http://localhost:8000/instagram/setup", json=config)
print(response.json())
```

### 키워드 분석

```python
# 네이버 키워드 분석
response = requests.post(
    "http://localhost:8000/keywords/analyze",
    json={
        "keyword": "마케팅 자동화",
        "platform": "naver"
    }
)
print(response.json())
```

### 콘텐츠 생성

```python
# 블로그 콘텐츠 생성
response = requests.post(
    "http://localhost:8000/blog/generate",
    json={
        "keyword": "AI 마케팅",
        "template": "커스텀 템플릿...",
        "auto_upload": False
    }
)
print(response.json())
```

## 🏗️ 프로젝트 구조

```
marketing/
├── main.py                 # FastAPI 메인 애플리케이션
├── config.py              # 설정 관리
├── requirements.txt       # 의존성 패키지
├── models/
│   └── schemas.py         # Pydantic 모델 정의
├── blog/
│   └── naver_blog_automation.py  # 네이버 블로그 자동화
├── instagram/
│   └── instagram_automation.py   # 인스타그램 자동화
├── keywords/
│   └── keyword_analyzer.py      # 키워드 분석
└── utils/
    ├── database.py        # 데이터베이스 관리
    ├── scheduler.py       # 스케줄러 관리
    └── logger.py          # 로깅 유틸리티
```

## 🔧 고급 설정

### 스케줄러 설정

```python
# 커스텀 스케줄 설정
schedule_config = {
    "frequency": "custom",
    "custom_cron": "0 9,12,18 * * *",  # 매일 9시, 12시, 18시
    "timezone": "Asia/Seoul"
}
```

### 데이터베이스 연결 풀 설정

```env
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
```

### 캐싱 설정

```env
REDIS_URL=redis://localhost:6379/0
CACHE_TTL=3600
```

## 📊 모니터링 및 로깅

### 실시간 상태 확인

```bash
# API를 통한 상태 확인
curl http://localhost:8000/dashboard/overview
curl http://localhost:8000/scheduler/jobs
```

### 로그 파일 위치

```
logs/
├── marketing_automation_2024-01-15.log  # 일반 로그
├── marketing_automation_errors.log      # 에러 로그
└── activity/                            # 활동 로그
    ├── blog_automation.log
    └── instagram_automation.log
```

### 성과 분석

```python
# 분석 데이터 조회
response = requests.get(
    "http://localhost:8000/dashboard/analytics",
    params={
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "platform": "blog"
    }
)
```

## 🔒 보안 고려사항

### API 키 보안
- 환경변수를 통한 API 키 관리
- `.env` 파일을 버전 관리에서 제외
- 프로덕션에서는 시크릿 매니저 사용 권장

### 데이터베이스 보안
- 강력한 비밀번호 사용
- SSL/TLS 연결 활성화
- 정기적인 백업 수행

### CORS 설정
```env
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

## 🧪 테스트

### 단위 테스트 실행

```bash
# 모든 테스트 실행
pytest

# 특정 모듈 테스트
pytest tests/test_blog_automation.py

# 커버리지 리포트
pytest --cov=marketing --cov-report=html
```

### API 테스트

```bash
# HTTP 파일을 사용한 API 테스트
# tests/api_tests.http 파일 참조
```

## 🚀 배포

### Docker를 사용한 배포

```dockerfile
# Dockerfile 예시
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Docker 빌드 및 실행
docker build -t marketing-automation .
docker run -p 8000:8000 --env-file .env marketing-automation
```

### 프로덕션 배포 체크리스트

- [ ] 환경변수 설정 확인
- [ ] 데이터베이스 백업 설정
- [ ] 로그 회전 설정
- [ ] 모니터링 도구 연동
- [ ] SSL 인증서 설정
- [ ] 방화벽 규칙 설정
- [ ] 자동 재시작 설정

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### 개발 가이드라인

- 코드 스타일: Black, Flake8 사용
- 타입 힌팅: mypy 검증 통과
- 테스트 커버리지: 80% 이상 유지
- 문서화: 모든 함수에 docstring 작성

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 🐛 문제 신고

버그를 발견하거나 기능 요청이 있으시면 [Issues](../../issues) 페이지에서 신고해 주세요.

## 📞 지원

- 이메일: support@example.com
- 문서: [Wiki](../../wiki)
- FAQ: [자주 묻는 질문](../../wiki/FAQ)

## 🔄 업데이트 로그

### v1.0.0 (2024-01-15)
- 초기 릴리스
- 네이버 블로그 자동화 기능
- 인스타그램 자동화 기능
- 키워드 분석 기능
- 스케줄링 시스템

---

**참고**: 이 README는 마케팅 자동화 API의 기본 사용법을 다룹니다. 더 자세한 내용은 API 문서(`/docs`)를 참조하세요.

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import quote_plus

MYSQL_HOST="penta-db.czocsimuw0dc.ap-northeast-2.rds.amazonaws.com"
MYSQL_USER="root"
MYSQL_PASSWORD="skn11penta!!"
MYSQL_DB="pantaDB"
MYSQL_PORT=3306

print(f"🔗 DB 연결 정보 (하드코딩):")
print(f"  HOST: {MYSQL_HOST}")
print(f"  PORT: {MYSQL_PORT}")
print(f"  USER: {MYSQL_USER}")
print(f"  DB: {MYSQL_DB}")


# 비밀번호 URL 인코딩 (특수문자 대응)
encoded_password = quote_plus(MYSQL_PASSWORD)

SQLALCHEMY_DATABASE_URL = (
    f"mysql+mysqlconnector://{MYSQL_USER}:{encoded_password}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
)

print(f"🔗 연결 URL: mysql+mysqlconnector://{MYSQL_USER}:****@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}")

try:
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, echo=True)
    print("✅ 데이터베이스 엔진 생성 성공!")
except Exception as e:
    print(f"❌ 데이터베이스 엔진 생성 실패: {e}")
    engine = None   # ⛔ 주의: None으로라도 초기화 안 하면 오류남

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

print("✅ database.py 설정 완료!")
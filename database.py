"""SQLite 엔진과 세션. python database.py 실행으로 DB를 생성한다."""

from pathlib import Path
from sqlite3 import Connection

from sqlalchemy import URL, create_engine, event, inspect
from sqlalchemy.orm import sessionmaker

from models import Base


# 실행 위치와 관계없이 이 파일 옆에 DB를 생성한다.
DB_PATH = Path(__file__).resolve().parent / "customer.db"
engine = create_engine(URL.create("sqlite", database=str(DB_PATH)))


@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection: Connection, connection_record: object) -> None:
    """SQLite의 외래 키 제약을 연결마다 활성화한다."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine)


def create_database() -> None:
    """등록된 네 테이블을 생성한다. 기존 테이블과 데이터는 유지한다."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_database()
    print(f"Database created: {DB_PATH}")
    print(f"Tables: {', '.join(inspect(engine).get_table_names())}")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.database import resolve_db_path


def _build_sqlalchemy_url() -> str:
    """构建SQLAlchemy连接URL"""
    db_path = resolve_db_path()
    normalized = db_path.replace("\\", "/")
    return f"sqlite:///{normalized}"


SQLALCHEMY_DATABASE_URL = _build_sqlalchemy_url()

engine_kwargs = {
    "connect_args": {
        "check_same_thread": False,
        "timeout": 30,
    },
    "pool_pre_ping": True,
}

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """依赖注入获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

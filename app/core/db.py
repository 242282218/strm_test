from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.database import resolve_db_path


def _build_sqlalchemy_url() -> str:
    """构建SQLAlchemy连接URL"""
    db_path = resolve_db_path()
    normalized = db_path.replace("\\", "/")
    return f"sqlite:///{normalized}"


SQLALCHEMY_DATABASE_URL = _build_sqlalchemy_url()

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """依赖注入获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

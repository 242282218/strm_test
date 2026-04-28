"""
数据库模块单元测试

测试数据库连接、CRUD 操作和连接池管理
"""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Database
from app.core.db import Base
from app.models.strm_record import ScanRecord, StrmRecord


class TestDatabaseCompatLayer:
    """Database 兼容层测试套件"""

    @pytest.fixture
    def db_engine(self, temp_db_path: str):
        """创建测试数据库引擎"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        yield engine
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    @pytest.fixture
    def db_session(self, db_engine):
        """创建测试数据库会话"""
        Session = sessionmaker(bind=db_engine)
        session = Session()
        yield session
        session.close()

    def test_save_strm_success(self, db_session, temp_db_path: str):
        """测试保存 STRM 记录成功"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        @contextmanager
        def get_test_session():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("app.core.database.get_db_session", get_test_session):
            db = Database(temp_db_path)
            result = db.save_strm(
                key="test_key_1",
                name="test_video.mp4",
                local_dir="/tmp/strm",
                remote_dir="/videos",
                raw_url="http://example.com/video.mp4",
            )

            assert result is True

            # 验证记录已保存
            with get_test_session() as session:
                record = session.query(StrmRecord).filter_by(file_id="test_key_1").first()
                assert record is not None
                assert record.file_name == "test_video.mp4"

        engine.dispose()

    def test_get_strm_success(self, db_session, temp_db_path: str):
        """测试获取 STRM 记录成功"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        # 先创建记录
        session = Session()
        record = StrmRecord(
            file_id="test_key_2",
            file_name="test_video2.mp4",
            local_dir="/tmp/strm",
            remote_dir="/videos",
            raw_url="http://example.com/video2.mp4",
        )
        session.add(record)
        session.commit()
        session.close()

        @contextmanager
        def get_test_session():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("app.core.database.get_db_session", get_test_session):
            db = Database(temp_db_path)
            result = db.get_strm("test_key_2")

            assert result is not None
            assert result["file_name"] == "test_video2.mp4"
            assert result["key"] == "test_key_2"

        engine.dispose()

    def test_get_strm_not_found(self, db_session, temp_db_path: str):
        """测试获取不存在的 STRM 记录"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        @contextmanager
        def get_test_session():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("app.core.database.get_db_session", get_test_session):
            db = Database(temp_db_path)
            result = db.get_strm("non_existent_key")

            assert result is None

        engine.dispose()

    def test_delete_strm_success(self, db_session, temp_db_path: str):
        """测试删除 STRM 记录成功"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        # 先创建记录
        session = Session()
        record = StrmRecord(
            file_id="test_key_3",
            file_name="test_video3.mp4",
            local_dir="/tmp/strm",
            remote_dir="/videos",
            raw_url="http://example.com/video3.mp4",
        )
        session.add(record)
        session.commit()
        session.close()

        @contextmanager
        def get_test_session():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("app.core.database.get_db_session", get_test_session):
            db = Database(temp_db_path)
            result = db.delete_strm("test_key_3")

            assert result is True

        engine.dispose()

    def test_delete_strm_not_found(self, db_session, temp_db_path: str):
        """测试删除不存在的 STRM 记录"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        @contextmanager
        def get_test_session():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("app.core.database.get_db_session", get_test_session):
            db = Database(temp_db_path)
            result = db.delete_strm("non_existent_key")

            assert result is False

        engine.dispose()

    def test_get_strms_by_remote_dir(self, db_session, temp_db_path: str):
        """测试根据远程目录获取 STRM 列表"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        # 创建多条记录
        session = Session()
        for i in range(3):
            record = StrmRecord(
                file_id=f"test_key_{i}",
                file_name=f"test_video_{i}.mp4",
                local_dir="/tmp/strm",
                remote_dir="/videos/movies",
                raw_url=f"http://example.com/video_{i}.mp4",
            )
            session.add(record)
        session.commit()
        session.close()

        @contextmanager
        def get_test_session():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("app.core.database.get_db_session", get_test_session):
            db = Database(temp_db_path)
            result = db.get_strms_by_remote_dir("/videos/movies")

            assert len(result) == 3

        engine.dispose()

    def test_get_all_strms(self, db_session, temp_db_path: str):
        """测试获取所有 STRM 记录"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        # 创建多条记录
        session = Session()
        for i in range(5):
            record = StrmRecord(
                file_id=f"all_test_key_{i}",
                file_name=f"all_test_video_{i}.mp4",
                local_dir="/tmp/strm",
                remote_dir=f"/videos/dir_{i % 2}",
                raw_url=f"http://example.com/video_{i}.mp4",
            )
            session.add(record)
        session.commit()
        session.close()

        @contextmanager
        def get_test_session():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("app.core.database.get_db_session", get_test_session):
            db = Database(temp_db_path)
            result = db.get_all_strms()

            assert len(result) == 5

        engine.dispose()

    def test_save_scan_record(self, db_session, temp_db_path: str):
        """测试保存扫描记录"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        @contextmanager
        def get_test_session():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("app.core.database.get_db_session", get_test_session):
            db = Database(temp_db_path)
            result = db.save_record("/videos/scan_test")

            assert result is True

        engine.dispose()

    def test_get_records(self, db_session, temp_db_path: str):
        """测试获取扫描记录"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        # 创建扫描记录
        session = Session()
        record = ScanRecord(remote_dir="/videos/record_test")
        session.add(record)
        session.commit()
        session.close()

        @contextmanager
        def get_test_session():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("app.core.database.get_db_session", get_test_session):
            db = Database(temp_db_path)
            result = db.get_records()

            assert "/videos/record_test" in result

        engine.dispose()

    def test_delete_record(self, db_session, temp_db_path: str):
        """测试删除扫描记录"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        # 创建扫描记录
        session = Session()
        record = ScanRecord(remote_dir="/videos/delete_test")
        session.add(record)
        session.commit()
        session.close()

        @contextmanager
        def get_test_session():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("app.core.database.get_db_session", get_test_session):
            db = Database(temp_db_path)
            result = db.delete_record("/videos/delete_test")

            assert result is True

        engine.dispose()


class TestResolveDbPath:
    """数据库路径解析测试"""

    def test_resolve_relative_path_does_not_create_data_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        from app.core.db import resolve_db_path

        result = resolve_db_path("relative/test.db")

        assert result.endswith("relative/test.db") or result.endswith("relative\\test.db")
        assert not (tmp_path / "data").exists()

    def test_importing_db_module_does_not_initialize_config_or_engine(self, tmp_path, monkeypatch):
        import importlib
        import sys

        monkeypatch.chdir(tmp_path)
        original_module = sys.modules.get("app.core.db")
        sys.modules.pop("app.core.db", None)

        try:
            with patch(
                "app.services.config_service.get_config_service",
                side_effect=AssertionError("should not init on import"),
            ):
                db_module = importlib.import_module("app.core.db")

            assert db_module.engine is None
        finally:
            if original_module is not None:
                sys.modules["app.core.db"] = original_module
            else:
                sys.modules.pop("app.core.db", None)

    def test_resolve_absolute_path(self):
        """测试解析绝对路径"""
        with patch("app.services.config_service.get_config_service") as mock:
            mock_cfg = MagicMock()
            mock_cfg.get_config.return_value.database = "/absolute/path/db.sqlite"
            mock.return_value = mock_cfg

            from app.core.db import resolve_db_path

            result = resolve_db_path("/absolute/path/test.db")

            # Windows 会转换为带盘符的路径
            assert "absolute" in result and "test.db" in result

    def test_resolve_relative_path(self):
        """测试解析相对路径"""
        with patch("app.services.config_service.get_config_service") as mock:
            mock_cfg = MagicMock()
            mock_cfg.get_config.return_value.database = "relative/path/db.sqlite"
            mock.return_value = mock_cfg

            from app.core.db import resolve_db_path

            result = resolve_db_path("relative/test.db")

            # 应该解析到 data 目录
            assert "data" in result or "relative" in result

    def test_resolve_default_path(self):
        """测试解析默认路径（从配置）"""
        with patch("app.services.config_service.get_config_service") as mock:
            mock_cfg = MagicMock()
            mock_cfg.get_config.return_value.database = "config_db.sqlite"
            mock.return_value = mock_cfg

            from app.core.db import resolve_db_path

            result = resolve_db_path()

            assert result is not None


class TestDatabaseSession:
    """数据库会话管理测试"""

    def test_get_db_session_context(self, temp_db_path: str):
        """测试数据库会话上下文管理器"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        with patch("app.core.db.SessionLocal", Session):
            from app.core.db import get_db_session

            with get_db_session() as session:
                assert session is not None

        engine.dispose()

    def test_init_db(self, temp_db_path: str):
        """测试初始化数据库表"""
        import app.core.db as db_module

        with (
            patch("app.core.db.SQLALCHEMY_DATABASE_URL", f"sqlite:///{temp_db_path}"),
            patch("app.core.db.engine", None),
        ):
            try:
                db_module.init_db()
                engine = db_module.get_engine()

                # 验证表已创建
                from sqlalchemy import inspect

                inspector = inspect(engine)

                tables = inspector.get_table_names()
                assert "strm_records" in tables
                assert "scan_records" in tables
            finally:
                if db_module.engine is not None:
                    db_module.engine.dispose()
                    db_module.engine = None


class TestStrmRecord:
    """StrmRecord 模型测试"""

    @pytest.fixture
    def session_factory(self, temp_db_path: str):
        """创建会话工厂"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        yield Session
        engine.dispose()

    def test_create_strm_record(self, session_factory):
        """测试创建 STRM 记录"""
        session = session_factory()

        record = StrmRecord.create_or_update(
            db=session,
            file_id="model_test_1",
            file_name="model_test.mp4",
            local_dir="/local",
            remote_dir="/remote",
            raw_url="http://test.url/video.mp4",
        )

        assert record.id is not None
        assert record.file_id == "model_test_1"
        assert record.file_name == "model_test.mp4"

        session.close()

    def test_update_strm_record(self, session_factory):
        """测试更新 STRM 记录"""
        session = session_factory()

        # 先创建
        StrmRecord.create_or_update(
            db=session,
            file_id="model_test_2",
            file_name="original.mp4",
            local_dir="/local",
            remote_dir="/remote",
            raw_url="http://test.url/video.mp4",
        )

        # 再更新
        updated = StrmRecord.create_or_update(
            db=session,
            file_id="model_test_2",
            file_name="updated.mp4",
            local_dir="/local_new",
            remote_dir="/remote_new",
            raw_url="http://test.url/new.mp4",
        )

        assert updated.file_name == "updated.mp4"
        assert updated.local_dir == "/local_new"

        session.close()

    def test_to_dict(self, session_factory):
        """测试转换为字典"""
        session = session_factory()

        record = StrmRecord.create_or_update(
            db=session,
            file_id="dict_test",
            file_name="dict_test.mp4",
            local_dir="/local",
            remote_dir="/remote",
            raw_url="http://test.url/video.mp4",
        )

        result = record.to_dict()

        assert result["file_id"] == "dict_test"
        assert result["key"] == "dict_test"  # 兼容字段
        assert result["name"] == "dict_test.mp4"  # 兼容字段

        session.close()


class TestScanRecord:
    """ScanRecord 模型测试"""

    @pytest.fixture
    def session_factory(self, temp_db_path: str):
        """创建会话工厂"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        yield Session
        engine.dispose()

    def test_create_scan_record(self, session_factory):
        """测试创建扫描记录"""
        session = session_factory()

        record = ScanRecord.create_or_update(session, "/scan/path")

        assert record.id is not None
        assert record.remote_dir == "/scan/path"
        assert record.last_scan is not None

        session.close()

    def test_get_all_scan_records(self, session_factory):
        """测试获取所有扫描记录"""
        session = session_factory()

        # 创建多条记录
        for i in range(3):
            ScanRecord.create_or_update(session, f"/scan/path/{i}")

        result = ScanRecord.get_all(session)

        assert len(result) == 3
        assert all(isinstance(v, datetime) for v in result.values())

        session.close()

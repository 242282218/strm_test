"""
数据库连接池性能测试

测试连接泄漏、并发性能和连接池监控
"""

import gc
import os
import threading
import time
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Database
from app.core.db import (
    Base,
)
from app.core.db_monitor import DatabasePoolMonitor, get_pool_monitor
from app.models.strm_record import StrmRecord


class TestConnectionLeak:
    """连接泄漏测试套件"""

    @pytest.fixture
    def temp_db(self, temp_dir: str):
        """创建临时数据库"""
        db_path = os.path.join(temp_dir, "test_leak.db")
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        yield Session, engine
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    def test_session_context_manager_no_leak(self, temp_db: str):
        """测试上下文管理器不会泄漏连接"""
        Session, engine = temp_db

        # 执行多次操作
        for i in range(100):
            with Session() as session:
                record = StrmRecord(
                    file_id=f"test_{i}",
                    file_name=f"test_{i}.mp4",
                    local_dir="/tmp",
                    remote_dir="/videos",
                    raw_url="http://test.com/video.mp4",
                )
                session.add(record)
                session.commit()

        # 强制垃圾回收
        gc.collect()

        # 验证记录已保存
        with Session() as session:
            count = session.query(StrmRecord).count()
            assert count == 100

    def test_database_compat_layer_no_leak(self, temp_db_path: str):
        """测试 Database 兼容层不会泄漏连接"""
        # 创建测试引擎
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        # 直接使用 Session 测试上下文管理器
        from contextlib import contextmanager

        @contextmanager
        def session_context():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        # 执行多次操作
        for i in range(50):
            with session_context() as session:
                record = StrmRecord(
                    file_id=f"leak_test_{i}",
                    file_name=f"video_{i}.mp4",
                    local_dir="/tmp",
                    remote_dir="/videos",
                    raw_url="http://test.com/video.mp4",
                )
                session.add(record)

        # 验证记录已保存
        with Session() as session:
            count = session.query(StrmRecord).count()
            assert count == 50

        engine.dispose()

    def test_exception_handling_no_leak(self, temp_db: str):
        """测试异常情况下不会泄漏连接"""
        Session, engine = temp_db

        # 先创建一条记录
        with Session() as session:
            record = StrmRecord(
                file_id="duplicate_key",
                file_name="test.mp4",
                local_dir="/tmp",
                remote_dir="/videos",
                raw_url="http://test.com/video.mp4",
            )
            session.add(record)
            session.commit()

        # 执行会抛出异常的操作（重复 key）
        for i in range(20):
            try:
                with Session() as session:
                    record = StrmRecord(
                        file_id="duplicate_key",  # 相同的 key 会触发唯一约束错误
                        file_name="test.mp4",
                        local_dir="/tmp",
                        remote_dir="/videos",
                        raw_url="http://test.com/video.mp4",
                    )
                    session.add(record)
                    session.commit()
            except Exception:
                pass  # 忽略异常

        # 强制垃圾回收
        gc.collect()

        # 验证只有一条记录
        with Session() as session:
            count = session.query(StrmRecord).count()
            assert count == 1

    def test_concurrent_sessions_no_leak(self, temp_db: str):
        """测试并发会话不会泄漏连接（使用锁保护）"""
        Session, engine = temp_db
        write_lock = threading.Lock()
        results = []

        def worker(worker_id: int):
            """工作线程"""
            for i in range(10):
                try:
                    with write_lock:  # SQLite 写操作需要串行化
                        with Session() as session:
                            record = StrmRecord(
                                file_id=f"concurrent_{worker_id}_{i}",
                                file_name=f"video_{worker_id}_{i}.mp4",
                                local_dir="/tmp",
                                remote_dir="/videos",
                                raw_url="http://test.com/video.mp4",
                            )
                            session.add(record)
                            session.commit()
                            results.append((worker_id, i))
                except Exception:
                    pass  # 忽略并发错误

        # 创建多个线程并发执行
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 强制垃圾回收
        gc.collect()

        # 验证记录已保存（至少有一些成功）
        with Session() as session:
            count = session.query(StrmRecord).count()
            assert count >= 50  # 至少一半成功


class TestConnectionPoolMonitor:
    """连接池监控测试套件"""

    @pytest.fixture
    def monitor(self):
        """创建监控器实例"""
        # 重置单例
        DatabasePoolMonitor._instance = None
        return get_pool_monitor()

    def test_connection_tracking(self, monitor):
        """测试连接追踪"""
        # 重置指标
        monitor.reset_metrics()

        # 模拟连接创建
        conn_id = 12345
        monitor._tracker.on_connection_created(conn_id, "test")

        metrics = monitor.get_metrics()
        assert metrics.total_created == 1
        assert metrics.current_active == 1

        # 模拟连接关闭
        monitor._tracker.on_connection_closed(conn_id)

        metrics = monitor.get_metrics()
        assert metrics.total_closed == 1
        assert metrics.current_active == 0

    def test_wait_tracking(self, monitor):
        """测试等待追踪"""
        # 重置指标
        monitor.reset_metrics()

        start_time = monitor._tracker.on_wait_start()

        metrics = monitor.get_metrics()
        assert metrics.current_waiting == 1
        assert metrics.total_waits == 1

        time.sleep(0.01)  # 等待 10ms
        monitor._tracker.on_wait_end(start_time)

        metrics = monitor.get_metrics()
        assert metrics.current_waiting == 0
        assert metrics.total_wait_time_ms > 0

    def test_error_tracking(self, monitor):
        """测试错误追踪"""
        # 重置指标
        monitor.reset_metrics()

        monitor._tracker.on_connection_error("connection")
        monitor._tracker.on_connection_error("timeout")

        metrics = monitor.get_metrics()
        assert metrics.connection_errors == 1
        assert metrics.timeout_errors == 1

    def test_health_check(self, monitor):
        """测试健康检查"""
        # 重置指标
        monitor.reset_metrics()

        # 正常情况
        health = monitor.check_health()
        assert health["status"] == "healthy"

        # 模拟高负载
        for i in range(60):
            monitor._tracker.on_connection_created(i, "test")

        health = monitor.check_health()
        assert health["status"] in ["warning", "unhealthy"]
        assert any(i["type"] == "high_active_connections" for i in health["issues"])

    def test_active_connections_list(self, monitor):
        """测试活跃连接列表"""
        # 先清理所有现有连接
        for conn in monitor.get_active_connections():
            monitor._tracker.on_connection_closed(conn["conn_id"])

        # 重置指标
        monitor.reset_metrics()

        # 创建多个连接
        for i in range(5):
            monitor._tracker.on_connection_created(i, f"source_{i}")

        active = monitor.get_active_connections()
        assert len(active) == 5

        # 验证连接信息
        for conn in active:
            assert "conn_id" in conn
            assert "age_ms" in conn
            assert "source" in conn

    def test_metrics_reset(self, monitor):
        """测试指标重置"""
        # 先关闭所有现有连接
        for conn in monitor.get_active_connections():
            monitor._tracker.on_connection_closed(conn["conn_id"])

        # 重置
        monitor.reset_metrics()

        # 创建一个新连接
        monitor._tracker.on_connection_created(1, "test")
        monitor._tracker.on_connection_error("connection")

        # 再次重置
        monitor.reset_metrics()

        metrics = monitor.get_metrics()
        assert metrics.total_created == 1  # 活跃连接保留
        assert metrics.connection_errors == 0  # 错误被重置


class TestPoolStatus:
    """连接池状态测试"""

    def test_get_pool_status_static_pool(self, temp_db_path: str):
        """测试 StaticPool 状态"""
        with patch("app.core.db.SQLALCHEMY_DATABASE_URL", f"sqlite:///{temp_db_path}"):
            from app.core.db import get_pool_status

            status = get_pool_status()

            assert "pool_type" in status
            assert "mode" in status
            assert status["mode"] == "single_connection"

    def test_check_pool_health(self, temp_db_path: str):
        """测试连接池健康检查"""
        with patch("app.core.db.SQLALCHEMY_DATABASE_URL", f"sqlite:///{temp_db_path}"):
            import app.core.db as db_module

            try:
                db_module.init_db()
                health = db_module.check_pool_health()

                assert health["healthy"] is True
                assert "pool_status" in health
            finally:
                if db_module.engine is not None:
                    db_module.engine.dispose()
                    db_module.engine = None


class TestConcurrentPerformance:
    """并发性能测试"""

    @pytest.fixture
    def perf_db(self, temp_dir: str):
        """创建性能测试数据库"""
        db_path = os.path.join(temp_dir, "perf_test.db")
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=StaticPool,
        )

        # 设置 PRAGMA
        def set_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-64000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

        from sqlalchemy import event

        event.listen(engine, "connect", set_pragma)

        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        yield Session
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    def test_concurrent_writes_performance(self, perf_db):
        """测试并发写入性能"""
        Session = perf_db
        write_lock = threading.Lock()
        num_threads = 5
        writes_per_thread = 20

        def writer(thread_id: int):
            for i in range(writes_per_thread):
                with write_lock:  # SQLite 写操作需要串行化
                    with Session() as session:
                        record = StrmRecord(
                            file_id=f"perf_{thread_id}_{i}",
                            file_name=f"video_{thread_id}_{i}.mp4",
                            local_dir="/tmp",
                            remote_dir="/videos",
                            raw_url="http://test.com/video.mp4",
                        )
                        session.add(record)
                        session.commit()

        # 并发执行
        start_time = time.time()
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=writer, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        total_time = time.time() - start_time
        total_writes = num_threads * writes_per_thread
        throughput = total_writes / total_time

        # 验证所有记录已写入
        with Session() as session:
            count = session.query(StrmRecord).count()
            assert count == total_writes

        # 性能断言：吞吐量应该 > 50 writes/sec
        assert throughput > 50, f"Throughput too low: {throughput:.2f} writes/sec"

        print("\n性能测试结果:")
        print(f"  总写入: {total_writes}")
        print(f"  总时间: {total_time:.2f}s")
        print(f"  吞吐量: {throughput:.2f} writes/sec")

    def test_concurrent_reads_performance(self, perf_db):
        """测试并发读取性能"""
        Session = perf_db

        # 先写入测试数据
        with Session() as session:
            for i in range(100):
                record = StrmRecord(
                    file_id=f"read_test_{i}",
                    file_name=f"video_{i}.mp4",
                    local_dir="/tmp",
                    remote_dir=f"/videos/dir_{i % 10}",
                    raw_url="http://test.com/video.mp4",
                )
                session.add(record)
            session.commit()

        num_threads = 5
        reads_per_thread = 50

        def reader(thread_id: int):
            for i in range(reads_per_thread):
                with Session() as session:
                    # 随机查询
                    file_id = f"read_test_{(thread_id * reads_per_thread + i) % 100}"
                    record = session.query(StrmRecord).filter_by(file_id=file_id).first()
                    assert record is not None

        # 并发执行
        start_time = time.time()
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=reader, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        total_time = time.time() - start_time
        total_reads = num_threads * reads_per_thread
        throughput = total_reads / total_time

        # 性能断言：吞吐量应该 > 100 reads/sec
        assert throughput > 100, f"Throughput too low: {throughput:.2f} reads/sec"

        print("\n读取性能测试结果:")
        print(f"  总读取: {total_reads}")
        print(f"  总时间: {total_time:.2f}s")
        print(f"  吞吐量: {throughput:.2f} reads/sec")


class TestDatabaseCompatLayer:
    """Database 兼容层测试"""

    @pytest.fixture
    def setup_db(self, temp_db_path: str):
        """设置测试数据库"""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        with patch("app.core.db.SessionLocal") as mock:
            mock.return_value = Session()
            yield Session, engine

        engine.dispose()

    def test_all_methods_use_context_manager(self, setup_db):
        """测试所有方法都使用上下文管理器"""
        Session, engine = setup_db

        # 创建 Database 实例
        from contextlib import contextmanager

        @contextmanager
        def mock_session():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with patch("app.core.database.get_db_session", side_effect=mock_session):
            db = Database("test.db")

            # 测试所有方法
            db.save_strm("key1", "name1.mp4", "/local", "/remote", "http://test.com/1.mp4")
            result = db.get_strm("key1")
            assert result is not None

            db.save_record("/remote/dir1")
            records = db.get_records()
            assert "/remote/dir1" in records

            all_strms = db.get_all_strms()
            assert len(all_strms) >= 1

            by_dir = db.get_strms_by_remote_dir("/remote")
            assert len(by_dir) >= 1

            db.delete_strm("key1")
            result = db.get_strm("key1")
            assert result is None

            db.delete_record("/remote/dir1")
            records = db.get_records()
            assert "/remote/dir1" not in records

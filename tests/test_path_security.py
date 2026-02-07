"""
路径安全测试
测试路径遍历防护和文件操作安全
"""

import os
import pytest
import tempfile
import shutil
from app.core.validators import validate_path, InputValidationError
from app.core.path_security import (
    validate_file_path,
    safe_open,
    safe_makedirs,
    safe_rename,
    PathSecurityError,
    get_allowed_directories,
)


class TestValidatePath:
    """测试基础路径验证"""

    def test_valid_relative_path(self):
        """测试有效的相对路径"""
        result = validate_path("strm/movies/test.mkv")
        assert result == "strm/movies/test.mkv"

    def test_path_with_dotdot(self):
        """测试包含 .. 的路径应该被拒绝"""
        with pytest.raises(InputValidationError) as exc_info:
            validate_path("strm/../../etc/passwd")
        assert "path traversal" in str(exc_info.value).lower()

    def test_absolute_path_rejected(self):
        """测试绝对路径应该被拒绝"""
        with pytest.raises(InputValidationError) as exc_info:
            validate_path("/etc/passwd")
        assert "relative path" in str(exc_info.value).lower()

        with pytest.raises(InputValidationError) as exc_info:
            validate_path("C:\\Windows\\system32")
        assert "relative path" in str(exc_info.value).lower()

    def test_absolute_path_allowed_with_explicit_flag(self):
        """测试显式开启时允许绝对路径"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "movie.mkv")
            result = validate_path(test_file, allow_absolute=True)
            assert result == test_file

    def test_null_bytes_rejected(self):
        """测试空字节应该被拒绝"""
        with pytest.raises(InputValidationError) as exc_info:
            validate_path("strm/test\x00.mkv")
        # 空字节会被 _CONTROL_CHAR_PATTERN 捕获
        assert "invalid characters" in str(exc_info.value).lower()

    def test_base_dir_validation(self):
        """测试基础目录验证"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 有效路径
            result = validate_path("subdir/file.txt", base_dir=tmpdir)
            assert result == "subdir/file.txt"

            # 路径遍历攻击 - 使用 ../../ 确保超出基础目录
            with pytest.raises(InputValidationError) as exc_info:
                validate_path("../../outside.txt", base_dir=tmpdir)
            # 错误消息可能是 "path traversal" 或 "outside"
            error_msg = str(exc_info.value).lower()
            assert "path traversal" in error_msg or "outside" in error_msg

    def test_allowed_dirs_validation(self):
        """测试允许目录列表验证"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 测试绝对路径在允许目录内
            test_file = os.path.join(tmpdir, "file.txt")
            allowed = [tmpdir]
            
            # 有效路径 - 使用绝对路径
            result = validate_path(test_file, allowed_dirs=allowed)
            assert result == test_file

            # 不允许的路径 - 使用绝对路径在允许目录外
            outside_dir = os.path.join(os.path.dirname(tmpdir), "outside")
            outside_file = os.path.join(outside_dir, "file.txt")
            with pytest.raises(InputValidationError) as exc_info:
                validate_path(outside_file, allowed_dirs=allowed)
            assert "allowed directories" in str(exc_info.value).lower()


class TestPathSecurity:
    """测试路径安全模块"""

    def test_validate_file_path_with_allowed_dirs(self):
        """测试带允许目录的文件路径验证"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test")

            # 有效路径
            result = validate_file_path(test_file, allowed_dirs=[tmpdir], check_exists=True)
            assert os.path.abspath(result) == os.path.abspath(test_file)

            # 不存在的文件
            with pytest.raises(PathSecurityError) as exc_info:
                validate_file_path(
                    os.path.join(tmpdir, "nonexistent.txt"),
                    allowed_dirs=[tmpdir],
                    check_exists=True
                )
            assert "does not exist" in str(exc_info.value).lower()

    def test_path_traversal_attack_blocked(self):
        """测试路径遍历攻击被阻止"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 尝试通过 .. 访问上级目录
            attack_path = os.path.join(tmpdir, "subdir", "..", "..", "etc", "passwd")
            
            with pytest.raises(PathSecurityError) as exc_info:
                validate_file_path(attack_path, allowed_dirs=[tmpdir])
            assert "outside" in str(exc_info.value).lower() or "not in allowed" in str(exc_info.value).lower()

    @pytest.mark.skipif(os.name == 'nt', reason="Windows requires special privileges to create symlinks")
    def test_symlink_blocked_by_default(self):
        """测试默认情况下符号链接被阻止"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建符号链接
            real_file = os.path.join(tmpdir, "real.txt")
            symlink_file = os.path.join(tmpdir, "link.txt")
            with open(real_file, "w") as f:
                f.write("test")
            os.symlink(real_file, symlink_file)

            # 默认情况下应该拒绝符号链接
            with pytest.raises(PathSecurityError) as exc_info:
                validate_file_path(symlink_file, allowed_dirs=[tmpdir])
            assert "symbolic links" in str(exc_info.value).lower()

            # 允许符号链接时应该通过
            result = validate_file_path(symlink_file, allowed_dirs=[tmpdir], allow_symlinks=True)
            assert os.path.abspath(result) == os.path.abspath(symlink_file)

    def test_safe_makedirs(self):
        """测试安全创建目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "new", "nested", "dir")
            
            result = safe_makedirs(new_dir, allowed_dirs=[tmpdir])
            assert os.path.exists(result)
            assert os.path.isdir(result)

            # 尝试在允许范围外创建目录
            outside_dir = os.path.join(os.path.dirname(tmpdir), "outside")
            with pytest.raises(PathSecurityError):
                safe_makedirs(os.path.join(outside_dir, "new_dir"), allowed_dirs=[tmpdir])

    def test_safe_open_write(self):
        """测试安全打开文件写入"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            
            # 写入文件
            with safe_open(test_file, "w", encoding="utf-8", allowed_dirs=[tmpdir]) as f:
                f.write("Hello, World!")
            
            # 验证内容
            with open(test_file, "r") as f:
                assert f.read() == "Hello, World!"

    def test_safe_open_read(self):
        """测试安全打开文件读取"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("Test content")

            # 读取文件
            with safe_open(test_file, "r", encoding="utf-8", allowed_dirs=[tmpdir]) as f:
                content = f.read()
                assert content == "Test content"

    def test_safe_open_outside_allowed_dirs(self):
        """测试在允许范围外打开文件应该失败"""
        with tempfile.TemporaryDirectory() as tmpdir:
            outside_dir = os.path.join(os.path.dirname(tmpdir), "outside")
            os.makedirs(outside_dir, exist_ok=True)
            outside_file = os.path.join(outside_dir, "test.txt")

            with pytest.raises(PathSecurityError):
                with safe_open(outside_file, "w", allowed_dirs=[tmpdir]) as f:
                    f.write("test")

    def test_safe_rename(self):
        """测试安全重命名文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "source.txt")
            dst_file = os.path.join(tmpdir, "dest.txt")
            
            with open(src_file, "w") as f:
                f.write("test content")

            safe_rename(src_file, dst_file, allowed_dirs=[tmpdir])
            
            assert not os.path.exists(src_file)
            assert os.path.exists(dst_file)
            with open(dst_file, "r") as f:
                assert f.read() == "test content"

    def test_safe_rename_outside_allowed(self):
        """测试重命名到允许范围外应该失败"""
        with tempfile.TemporaryDirectory() as tmpdir:
            outside_dir = os.path.join(os.path.dirname(tmpdir), "outside")
            os.makedirs(outside_dir, exist_ok=True)
            
            src_file = os.path.join(tmpdir, "source.txt")
            dst_file = os.path.join(outside_dir, "dest.txt")
            
            with open(src_file, "w") as f:
                f.write("test")

            with pytest.raises(PathSecurityError):
                safe_rename(src_file, dst_file, allowed_dirs=[tmpdir])


class TestGetAllowedDirectories:
    """测试获取允许目录列表"""

    def test_default_directories(self):
        """测试默认返回的目录列表"""
        dirs = get_allowed_directories()
        assert isinstance(dirs, list)
        assert len(dirs) >= 4  # 至少有默认的4个目录
        
        # 检查是否都是绝对路径
        for d in dirs:
            assert os.path.isabs(d)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

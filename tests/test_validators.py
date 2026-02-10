"""
验证器模块测试
对应测试矩阵: CORE-003, CORE-004
"""
import pytest


class TestPathValidator:
    """路径验证器测试"""
    
    def test_validate_valid_path(self):
        """CORE-003: 验证合法相对路径"""
        from app.core.validators import validate_path
        
        # 合法相对路径（默认不允许绝对路径）
        result = validate_path("test/path", "test_path")
        assert result == "test/path"
        
        # 带尾部斜杠的路径
        result = validate_path("test/path/", "test_path")
        assert result == "test/path/"
    
    def test_validate_path_with_parent_directory(self):
        """CORE-004: 路径包含..应抛出异常"""
        from app.core.validators import validate_path, InputValidationError
        
        # 包含父目录引用的路径
        with pytest.raises(InputValidationError) as exc_info:
            validate_path("/test/../etc/passwd", "test_path")
        
        assert "path" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
    
    def test_validate_empty_path(self):
        """测试空路径验证"""
        from app.core.validators import validate_path, InputValidationError
        
        with pytest.raises(InputValidationError):
            validate_path("", "test_path")
    
    def test_validate_path_too_long(self):
        """测试超长路径"""
        from app.core.validators import validate_path, InputValidationError
        from app.core.constants import MAX_PATH_LENGTH
        
        # 创建超长路径
        long_path = "/test" + "/a" * (MAX_PATH_LENGTH + 100)
        
        with pytest.raises(InputValidationError) as exc_info:
            validate_path(long_path, "test_path")
        
        assert "length" in str(exc_info.value).lower() or "max" in str(exc_info.value).lower()


class TestHTTPUrlValidator:
    """HTTP URL验证器测试"""
    
    def test_validate_valid_http_url(self):
        """测试有效HTTP URL"""
        from app.core.validators import validate_http_url
        
        # 有效URL
        validate_http_url("http://localhost:8000", "test_url")
        validate_http_url("https://example.com/path", "test_url")
        validate_http_url("http://192.168.1.1:8080", "test_url")
    
    def test_validate_invalid_url_scheme(self):
        """测试无效URL协议"""
        from app.core.validators import validate_http_url, InputValidationError
        
        with pytest.raises(InputValidationError) as exc_info:
            validate_http_url("ftp://example.com", "test_url")
        
        assert "http" in str(exc_info.value).lower() or "scheme" in str(exc_info.value).lower()
    
    def test_validate_invalid_url_format(self):
        """测试无效URL格式"""
        from app.core.validators import validate_http_url, InputValidationError
        
        with pytest.raises(InputValidationError):
            validate_http_url("not_a_url", "test_url")


class TestIdentifierValidator:
    """标识符验证器测试"""
    
    def test_validate_valid_identifier(self):
        """测试有效标识符"""
        from app.core.validators import validate_identifier
        
        # 有效标识符
        result = validate_identifier("valid_id_123", "test_id")
        assert result == "valid_id_123"
        
        result = validate_identifier("test-id", "test_id")
        assert result == "test-id"
    
    def test_validate_invalid_identifier(self):
        """测试无效标识符"""
        from app.core.validators import validate_identifier, InputValidationError
        
        # 包含特殊字符
        with pytest.raises(InputValidationError):
            validate_identifier("id<script>alert(1)</script>", "test_id")
        
        # 空标识符
        with pytest.raises(InputValidationError):
            validate_identifier("", "test_id")

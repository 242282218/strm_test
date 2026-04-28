"""
配置加密模块单元测试

测试动态盐加密和向后兼容性
"""

import base64
import json

import pytest

from app.core.encryption import ConfigEncryption


class TestConfigEncryption:
    """ConfigEncryption 类测试套件"""

    def test_encrypt_with_dynamic_salt_produces_unique_ciphertext(self):
        """
        测试：相同明文使用动态盐加密产生不同密文

        验证：
        1. 每次加密生成不同的盐值
        2. 相同明文产生不同密文
        3. 密文格式为 JSON 并包含 version、salt、ciphertext
        """
        password = "test_password_123"
        plaintext = "sensitive_config_value"

        encryptor = ConfigEncryption(password)

        # 加密相同明文两次
        ciphertext1 = encryptor.encrypt(plaintext)
        ciphertext2 = encryptor.encrypt(plaintext)

        # 验证：两次加密结果不同
        assert ciphertext1 != ciphertext2, "相同明文应产生不同密文（动态盐）"

        # 验证：密文格式为 JSON
        data1 = json.loads(base64.b64decode(ciphertext1).decode())
        data2 = json.loads(base64.b64decode(ciphertext2).decode())

        # 验证：JSON 结构包含必需字段
        assert "version" in data1, "密文应包含 version 字段"
        assert "salt" in data1, "密文应包含 salt 字段"
        assert "ciphertext" in data1, "密文应包含 ciphertext 字段"

        # 验证：版本号为 2
        assert data1["version"] == 2, "新格式版本号应为 2"

        # 验证：盐值不同
        assert data1["salt"] != data2["salt"], "每次加密应使用不同盐值"

        # 验证：密文主体不同
        assert data1["ciphertext"] != data2["ciphertext"], "密文主体应不同"

    def test_decrypt_with_correct_password_succeeds(self):
        """
        测试：使用正确密码解密成功

        验证：
        1. 加密后可正确解密
        2. 解密结果与原始明文一致
        """
        password = "secure_password_456"
        plaintext = "api_key_abc123xyz"

        encryptor = ConfigEncryption(password)

        # 加密
        ciphertext = encryptor.encrypt(plaintext)

        # 解密
        decrypted = encryptor.decrypt(ciphertext)

        # 验证：解密结果与原始明文一致
        assert decrypted == plaintext, "解密结果应与原始明文一致"

    def test_legacy_format_backward_compatibility(self):
        """
        测试：旧格式密文向后兼容解密

        验证：
        1. 旧格式（静态盐）密文可正常解密
        2. 解密结果正确
        """
        password = "legacy_password_789"
        plaintext = "legacy_secret_value"

        # 模拟旧格式加密（使用静态盐）
        # 注意：这里需要访问旧的静态盐值进行测试
        encryptor = ConfigEncryption(password)

        # 使用旧格式加密（直接调用内部方法模拟）
        legacy_ciphertext = encryptor._encrypt_legacy(plaintext)

        # 解密旧格式密文
        decrypted = encryptor.decrypt(legacy_ciphertext)

        # 验证：旧格式密文可正确解密
        assert decrypted == plaintext, "旧格式密文应能正确解密"

    def test_salt_length_meets_nist_recommendation(self):
        """
        测试：盐值长度符合 NIST 推荐（>= 16 字节）
        """
        password = "test_password"
        plaintext = "test_data"

        encryptor = ConfigEncryption(password)
        ciphertext = encryptor.encrypt(plaintext)

        # 解析密文
        data = json.loads(base64.b64decode(ciphertext).decode())
        salt_bytes = base64.b64decode(data["salt"])

        # 验证：盐值长度 >= 16
        assert len(salt_bytes) >= 16, f"盐值长度应为至少 16 字节，实际为 {len(salt_bytes)}"

    def test_iterations_meets_owasp_recommendation(self):
        """
        测试：迭代次数符合 OWASP 推荐（>= 600,000）
        """
        password = "test_password"

        encryptor = ConfigEncryption(password)

        # 验证：迭代次数 >= 600000
        assert encryptor.iterations >= 600000, f"迭代次数应为至少 600,000，实际为 {encryptor.iterations}"

    def test_wrong_password_decryption_fails(self):
        """
        测试：错误密码解密失败
        """
        password = "correct_password"
        wrong_password = "wrong_password"
        plaintext = "secret_data"

        # 使用正确密码加密
        encryptor1 = ConfigEncryption(password)
        ciphertext = encryptor1.encrypt(plaintext)

        # 使用错误密码解密
        encryptor2 = ConfigEncryption(wrong_password)

        # 验证：解密应失败
        with pytest.raises(ValueError, match="解密失败"):
            encryptor2.decrypt(ciphertext)

    def test_new_format_can_be_decrypted_multiple_times(self):
        """
        测试：新格式密文可多次解密
        """
        password = "test_password"
        plaintext = "reusable_secret"

        encryptor = ConfigEncryption(password)
        ciphertext = encryptor.encrypt(plaintext)

        # 多次解密
        for i in range(3):
            decrypted = encryptor.decrypt(ciphertext)
            assert decrypted == plaintext, f"第 {i + 1} 次解密结果应与原始明文一致"

"""
配置加密模块

提供敏感配置项的加密和解密功能
支持动态盐加密（v2）和向后兼容旧格式（v1）
"""

import base64
import json
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class ConfigEncryption:
    """
    配置加密器，使用Fernet对称加密算法

    安全特性：
    - 动态盐值：每次加密生成随机盐（NIST 推荐 >= 16 字节）
    - 高迭代次数：600,000 次（OWASP 2023 推荐）
    - 向后兼容：支持解密旧格式静态盐密文
    """

    # 安全常量
    SALT_LENGTH = 16  # NIST 推荐最小盐值长度
    ITERATIONS = 600000  # OWASP 2023 推荐迭代次数
    VERSION = 2  # 当前加密格式版本

    # 旧版本静态盐（仅用于向后兼容解密）
    LEGACY_SALT = b"static_salt_for_smart_media_config_encryption"
    LEGACY_ITERATIONS = 100000  # 旧版本迭代次数

    def __init__(self, password: str = None):
        """
        初始化加密器

        Args:
            password: 用于生成加密密钥的密码，如果未提供则从环境变量获取

        Raises:
            ValueError: 密码为空时抛出
        """
        if password is None:
            password = os.getenv("CONFIG_ENCRYPTION_PASSWORD", "")

        if not password:
            raise ValueError("加密密码不能为空，请设置 CONFIG_ENCRYPTION_PASSWORD 环境变量")

        self.password = password.encode()
        self.iterations = self.ITERATIONS

    def _generate_salt(self) -> bytes:
        """
        生成加密安全的随机盐值

        Returns:
            随机盐值字节（长度为 SALT_LENGTH）
        """
        return os.urandom(self.SALT_LENGTH)

    def _derive_key(self, password: bytes, salt: bytes, iterations: int = None) -> bytes:
        """
        从密码和盐值派生加密密钥

        Args:
            password: 密码字节
            salt: 盐值字节
            iterations: PBKDF2 迭代次数，默认使用当前版本迭代次数

        Returns:
            Fernet 兼容的加密密钥（Base64 编码）
        """
        if iterations is None:
            iterations = self.ITERATIONS

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key

    def encrypt(self, plaintext: str) -> str:
        """
        加密明文（使用动态盐）

        每次加密生成新的随机盐值，确保相同明文产生不同密文。
        密文格式：Base64 编码的 JSON 结构
        {
            "version": 2,
            "salt": "base64_encoded_salt",
            "ciphertext": "base64_encoded_fernet_ciphertext"
        }

        Args:
            plaintext: 待加密的明文

        Returns:
            加密后的字符串（Base64 编码的 JSON）
        """
        # 生成随机盐值
        salt = self._generate_salt()

        # 派生密钥
        key = self._derive_key(self.password, salt, self.ITERATIONS)
        cipher_suite = Fernet(key)

        # 加密明文
        ciphertext = cipher_suite.encrypt(plaintext.encode())

        # 构建密文结构
        encrypted_data = {
            "version": self.VERSION,
            "salt": base64.b64encode(salt).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
        }

        # 返回 Base64 编码的 JSON
        return base64.b64encode(json.dumps(encrypted_data).encode()).decode()

    def decrypt(self, encrypted_text: str) -> str:
        """
        解密密文（支持新旧格式自动识别）

        自动检测密文格式：
        - 新格式（v2）：JSON 结构，使用动态盐解密
        - 旧格式（v1）：纯 Base64，使用静态盐解密

        Args:
            encrypted_text: 待解密的字符串

        Returns:
            解密后的明文

        Raises:
            ValueError: 解密失败时抛出
        """
        try:
            # 尝试解析为新格式（JSON）
            decoded = base64.b64decode(encrypted_text.encode())

            # 检查是否为 JSON 格式
            try:
                data = json.loads(decoded.decode())

                # 验证 JSON 结构
                if isinstance(data, dict) and "version" in data and "salt" in data and "ciphertext" in data:
                    # 新格式解密
                    return self._decrypt_new_format(data)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 不是 JSON，尝试旧格式解密
                pass

            # 旧格式解密
            return self._decrypt_legacy_format(encrypted_text)

        except Exception as e:
            raise ValueError(f"解密失败: {e!s}")

    def _decrypt_new_format(self, data: dict) -> str:
        """
        解密新格式密文（v2）

        Args:
            data: 解析后的密文数据结构

        Returns:
            解密后的明文
        """
        # 提取盐值和密文
        salt = base64.b64decode(data["salt"])
        ciphertext = base64.b64decode(data["ciphertext"])

        # 派生密钥
        key = self._derive_key(self.password, salt, self.ITERATIONS)
        cipher_suite = Fernet(key)

        # 解密
        decrypted_bytes = cipher_suite.decrypt(ciphertext)
        return decrypted_bytes.decode()

    def _decrypt_legacy_format(self, encrypted_text: str) -> str:
        """
        解密旧格式密文（v1，静态盐）

        Args:
            encrypted_text: 旧格式密文（Base64 编码的 Fernet 密文）

        Returns:
            解密后的明文
        """
        # 使用静态盐派生密钥
        key = self._derive_key(self.password, self.LEGACY_SALT, self.LEGACY_ITERATIONS)
        cipher_suite = Fernet(key)

        # 解密
        encrypted_bytes = base64.b64decode(encrypted_text.encode())
        decrypted_bytes = cipher_suite.decrypt(encrypted_bytes)
        return decrypted_bytes.decode()

    def _encrypt_legacy(self, plaintext: str) -> str:
        """
        使用旧格式加密（仅用于测试向后兼容性）

        Args:
            plaintext: 待加密的明文

        Returns:
            旧格式密文（Base64 编码）
        """
        # 使用静态盐派生密钥
        key = self._derive_key(self.password, self.LEGACY_SALT, self.LEGACY_ITERATIONS)
        cipher_suite = Fernet(key)

        # 加密
        ciphertext = cipher_suite.encrypt(plaintext.encode())
        return base64.b64encode(ciphertext).decode()


def get_encrypted_config_value(config_value: str, encryption_password: str = None) -> str:
    """
    加密配置值

    Args:
        config_value: 配置值
        encryption_password: 加密密码

    Returns:
        加密后的配置值（带 "encrypted:" 前缀）
    """
    if not config_value:
        return config_value

    try:
        encryptor = ConfigEncryption(encryption_password)
        return f"encrypted:{encryptor.encrypt(config_value)}"
    except Exception:
        # 如果加密失败，返回原始值（这在某些情况下可能是必要的）
        return config_value


def get_decrypted_config_value(encrypted_config_value: str, encryption_password: str = None) -> str:
    """
    解密配置值

    Args:
        encrypted_config_value: 加密的配置值（带 "encrypted:" 前缀）
        encryption_password: 加密密码

    Returns:
        解密后的配置值

    Raises:
        ValueError: 解密失败时抛出
    """
    if not encrypted_config_value or not encrypted_config_value.startswith("encrypted:"):
        return encrypted_config_value

    try:
        encrypted_part = encrypted_config_value[10:]  # 移除 "encrypted:" 前缀
        encryptor = ConfigEncryption(encryption_password)
        return encryptor.decrypt(encrypted_part)
    except Exception:
        # 如果解密失败，抛出异常
        raise ValueError("无法解密配置值，请检查加密密码是否正确")


# 示例使用
if __name__ == "__main__":
    # 示例：如何使用加密功能
    password = "my_secure_password_for_config"
    encryptor = ConfigEncryption(password)

    # 加密（新格式，动态盐）
    secret_data = "my_secret_api_key"
    encrypted = encryptor.encrypt(secret_data)
    print(f"加密后: {encrypted}")

    # 解密
    decrypted = encryptor.decrypt(encrypted)
    print(f"解密后: {decrypted}")

    # 验证相同明文产生不同密文
    encrypted2 = encryptor.encrypt(secret_data)
    print(f"\n相同明文第二次加密: {encrypted2}")
    print(f"两次加密结果不同: {encrypted != encrypted2}")

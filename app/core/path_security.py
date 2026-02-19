"""
Path security utilities for safe file operations
"""

import os
from typing import List, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


class PathSecurityError(Exception):
    """Path security violation error"""
    pass


def get_allowed_directories() -> List[str]:
    """
    获取允许的文件操作目录列表
    从配置中读取或返回默认值
    """
    # 默认允许的工作目录
    default_dirs = [
        os.path.abspath("./strm"),
        os.path.abspath("./output"),
        os.path.abspath("./tmp"),
        os.path.abspath("./data"),
    ]
    
    # 尝试从配置读取
    try:
        from app.services.config_service import ConfigManager
        config = ConfigManager()
        
        # 从 endpoints 配置读取本地目录
        endpoints = config.get('endpoints', [])
        if endpoints and len(endpoints) > 0:
            endpoint = endpoints[0]
            dirs = endpoint.get('dirs', [])
            if dirs and len(dirs) > 0:
                local_dir = dirs[0].get('local_directory')
                if local_dir:
                    abs_dir = os.path.abspath(local_dir)
                    if abs_dir not in default_dirs:
                        default_dirs.append(abs_dir)
    except Exception as e:
        logger.warning(f"Failed to load allowed directories from config: {e}")
    
    return default_dirs


def validate_file_path(
    file_path: str,
    allowed_dirs: Optional[List[str]] = None,
    check_exists: bool = False,
    allow_symlinks: bool = False
) -> str:
    """
    验证文件路径是否在允许的目录范围内
    
    Args:
        file_path: 待验证的文件路径
        allowed_dirs: 允许的目录列表，默认为 None（使用配置中的目录）
        check_exists: 是否检查文件是否存在
        allow_symlinks: 是否允许符号链接
    
    Returns:
        验证后的绝对路径
    
    Raises:
        PathSecurityError: 路径验证失败时抛出
    """
    if not file_path:
        raise PathSecurityError("File path cannot be empty")
    
    # 获取允许的目录
    if allowed_dirs is None:
        allowed_dirs = get_allowed_directories()
    
    if not allowed_dirs:
        raise PathSecurityError("No allowed directories configured")
    
    # 转换为绝对路径
    abs_path = os.path.abspath(file_path)
    
    # 检查是否是符号链接
    if not allow_symlinks and os.path.islink(file_path):
        raise PathSecurityError(f"Symbolic links are not allowed: {file_path}")
    
    # 解析真实路径（处理符号链接）
    try:
        real_path = os.path.realpath(abs_path)
    except Exception as e:
        raise PathSecurityError(f"Failed to resolve path: {file_path}, error: {e}")
    
    # 检查路径是否在允许的目录内
    in_allowed = False
    for allowed_dir in allowed_dirs:
        abs_allowed = os.path.abspath(allowed_dir)
        # 确保允许目录以分隔符结尾，防止前缀匹配问题
        if not abs_allowed.endswith(os.sep):
            abs_allowed += os.sep
        
        if real_path.startswith(abs_allowed) or real_path == abs_allowed.rstrip(os.sep):
            in_allowed = True
            break
    
    if not in_allowed:
        logger.warning(
            f"Path security violation: {real_path} is not in allowed directories: {allowed_dirs}"
        )
        raise PathSecurityError(
            f"Access denied: file path is outside of allowed directories"
        )
    
    # 检查文件是否存在（如果要求）
    if check_exists and not os.path.exists(real_path):
        raise PathSecurityError(f"File does not exist: {file_path}")
    
    return real_path


def safe_open(
    file_path: str,
    mode: str = 'r',
    encoding: Optional[str] = None,
    allowed_dirs: Optional[List[str]] = None,
    **kwargs
):
    """
    安全地打开文件
    
    Args:
        file_path: 文件路径
        mode: 打开模式
        encoding: 编码
        allowed_dirs: 允许的目录列表
        **kwargs: 其他传递给 open() 的参数
    
    Returns:
        文件对象
    
    Raises:
        PathSecurityError: 路径验证失败时抛出
    """
    # 验证路径
    validated_path = validate_file_path(file_path, allowed_dirs)
    
    # 如果是写入模式，确保目录存在
    if 'w' in mode or 'a' in mode:
        dir_path = os.path.dirname(validated_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
    
    # 打开文件
    if encoding:
        return open(validated_path, mode, encoding=encoding, **kwargs)
    else:
        return open(validated_path, mode, **kwargs)


def safe_makedirs(
    path: str,
    mode: int = 0o755,
    exist_ok: bool = True,
    allowed_dirs: Optional[List[str]] = None
) -> str:
    """
    安全地创建目录
    
    Args:
        path: 目录路径
        mode: 权限模式
        exist_ok: 如果目录已存在是否报错
        allowed_dirs: 允许的目录列表
    
    Returns:
        创建的目录的绝对路径
    
    Raises:
        PathSecurityError: 路径验证失败时抛出
    """
    # 验证父目录是否在允许范围内
    abs_path = os.path.abspath(path)
    parent_dir = os.path.dirname(abs_path) or abs_path
    
    # 如果目录已存在，验证它本身
    if os.path.exists(abs_path) and os.path.isdir(abs_path):
        validate_file_path(abs_path, allowed_dirs)
        return abs_path
    
    # 验证父目录
    validate_file_path(parent_dir, allowed_dirs)
    
    # 创建目录
    os.makedirs(abs_path, mode=mode, exist_ok=exist_ok)
    
    return abs_path


def safe_rename(
    src: str,
    dst: str,
    allowed_dirs: Optional[List[str]] = None
) -> None:
    """
    安全地重命名/移动文件
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
        allowed_dirs: 允许的目录列表
    
    Raises:
        PathSecurityError: 路径验证失败时抛出
    """
    # 验证源文件和目标路径
    src_validated = validate_file_path(src, allowed_dirs, check_exists=True)
    dst_validated = validate_file_path(dst, allowed_dirs)
    
    # 确保目标目录存在
    dst_dir = os.path.dirname(dst_validated)
    if dst_dir and not os.path.exists(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)
    
    # 执行重命名
    os.rename(src_validated, dst_validated)


def safe_symlink(
    src: str,
    dst: str,
    allowed_dirs: Optional[List[str]] = None
) -> None:
    """
    安全地创建符号链接
    
    Args:
        src: 源文件路径
        dst: 目标链接路径
        allowed_dirs: 允许的目录列表
    
    Raises:
        PathSecurityError: 路径验证失败时抛出
    """
    # 验证源文件（允许符号链接）
    src_validated = validate_file_path(src, allowed_dirs, check_exists=True, allow_symlinks=True)
    dst_validated = validate_file_path(dst, allowed_dirs)
    
    # 确保目标目录存在
    dst_dir = os.path.dirname(dst_validated)
    if dst_dir and not os.path.exists(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)
    
    # 创建符号链接
    os.symlink(src_validated, dst_validated)


def safe_hardlink(
    src: str,
    dst: str,
    allowed_dirs: Optional[List[str]] = None
) -> None:
    """
    安全地创建硬链接
    
    Args:
        src: 源文件路径
        dst: 目标链接路径
        allowed_dirs: 允许的目录列表
    
    Raises:
        PathSecurityError: 路径验证失败时抛出
    """
    import shutil
    
    # 验证源文件和目标路径
    src_validated = validate_file_path(src, allowed_dirs, check_exists=True)
    dst_validated = validate_file_path(dst, allowed_dirs)
    
    # 确保目标目录存在
    dst_dir = os.path.dirname(dst_validated)
    if dst_dir and not os.path.exists(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)
    
    # 尝试创建硬链接，如果跨设备则降级为复制
    try:
        os.link(src_validated, dst_validated)
    except OSError as e:
        if e.errno == 18:  # EXDEV - 跨设备链接
            logger.warning(f"Cross-device link detected, falling back to copy: {src} -> {dst}")
            shutil.copy2(src_validated, dst_validated)
        else:
            raise

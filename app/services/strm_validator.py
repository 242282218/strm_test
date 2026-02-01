"""
STRM有效性检查模块

参考: alist-strm strm_validator.py
"""

import os
import asyncio
import aiohttp
from typing import List, Dict, Set, Optional
from enum import Enum
from app.core.logging import get_logger

logger = get_logger(__name__)


class ScanMode(Enum):
    """扫描模式"""
    QUICK = "quick"
    SLOW = "slow"


class ValidationResult:
    """验证结果"""

    def __init__(
        self,
        valid_files: List[str],
        invalid_files: List[str],
        missing_files: List[str],
        extra_files: List[str]
    ):
        """
        初始化验证结果

        Args:
            valid_files: 有效的STRM文件列表
            invalid_files: 无效的STRM文件列表
            missing_files: 缺失的STRM文件列表
            extra_files: 多余的STRM文件列表
        """
        self.valid_files = valid_files
        self.invalid_files = invalid_files
        self.missing_files = missing_files
        self.extra_files = extra_files

    def to_dict(self) -> Dict[str, any]:
        """转换为字典"""
        return {
            "valid_count": len(self.valid_files),
            "invalid_count": len(self.invalid_files),
            "missing_count": len(self.missing_files),
            "extra_count": len(self.extra_files),
            "total_count": len(self.valid_files) + len(self.invalid_files),
            "valid_files": self.valid_files[:10],  # 只返回前10个
            "invalid_files": self.invalid_files[:10],
            "missing_files": self.missing_files[:10],
            "extra_files": self.extra_files[:10]
        }


class StrmValidator:
    """STRM有效性检查器"""

    def __init__(
        self,
        target_directory: str,
        remote_base: str,
        video_formats: Set[str],
        size_threshold_mb: int = 100,
        cache_file: Optional[str] = None
    ):
        """
        初始化STRM有效性检查器

        Args:
            target_directory: 目标目录
            remote_base: 远程根路径
            video_formats: 视频格式集合
            size_threshold_mb: 文件大小阈值（MB）
            cache_file: 缓存文件路径
        """
        self.target_directory = target_directory
        self.remote_base = remote_base.rstrip('/')
        self.video_formats = video_formats
        self.size_threshold_bytes = size_threshold_mb * 1024 * 1024
        self.cache_file = cache_file
        self.cached_tree: Optional[Dict] = None
        logger.info(f"StrmValidator initialized: {target_directory}")

    def load_cached_tree(self) -> Optional[Dict]:
        """
        加载缓存的目录树

        Returns:
            缓存的目录树字典
        """
        if self.cache_file and os.path.exists(self.cache_file):
            try:
                import json
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cached_tree = json.load(f)
                    logger.info(f"Loaded cached tree from: {self.cache_file}")
                    return self.cached_tree
            except Exception as e:
                logger.error(f"Failed to load cached tree: {str(e)}")
        return None

    def list_local_strm_files(self) -> List[str]:
        """
        列出本地STRM文件

        Returns:
            STRM文件路径列表
        """
        strm_files = []
        for root, dirs, files in os.walk(self.target_directory):
            for file in files:
                if file.lower().endswith('.strm'):
                    full_path = os.path.abspath(os.path.join(root, file))
                    strm_files.append(full_path)
        logger.info(f"Found {len(strm_files)} local .strm files")
        return strm_files

    def build_expected_strm_set(self, file_tree: Dict, current_path: str = '') -> Set[str]:
        """
        构建期望的STRM文件集合

        Args:
            file_tree: 文件树字典
            current_path: 当前路径

        Returns:
            期望的STRM文件路径集合
        """
        expected_strm_set = set()

        def process_node(node: Dict, path: str):
            """递归处理节点"""
            if not isinstance(node, dict):
                return

            for key, value in node.items():
                if key == "children" and isinstance(value, list):
                    for child in value:
                        process_node(child, path)
                elif isinstance(value, dict):
                    file_name = value.get("name", "")
                    file_size = value.get("size", 0)
                    is_directory = value.get("is_dir", False)

                    if not file_name.startswith(self.remote_base):
                        continue

                    if is_directory:
                        children = value.get("children", [])
                        if children:
                            process_node({"children": children}, path)
                    else:
                        # 检查文件大小
                        if file_size < self.size_threshold_bytes:
                            logger.debug(f"Skipping small file: {file_name}")
                            continue

                        # 检查文件扩展名
                        file_extension = os.path.splitext(file_name)[1].lower().lstrip('.')
                        if file_extension in self.video_formats:
                            # 生成STRM文件路径
                            relative_path = os.path.relpath(file_name, self.remote_base)
                            video_relative_dir = os.path.dirname(relative_path)
                            video_base_name = os.path.splitext(os.path.basename(relative_path))[0]
                            strm_file_name = f"{video_base_name}.strm"
                            strm_file_path = os.path.abspath(
                                os.path.join(self.target_directory, video_relative_dir, strm_file_name)
                            )
                            expected_strm_set.add(strm_file_path)
                            logger.debug(f"Expected .strm file: {strm_file_path}")

        process_node(file_tree, current_path)
        return expected_strm_set

    async def fast_scan(self, local_strm_files: List[str]) -> ValidationResult:
        """
        快速扫描模式

        参考: alist-strm strm_validator.py fast_scan

        Args:
            local_strm_files: 本地STRM文件列表

        Returns:
            验证结果
        """
        logger.info("Starting fast scan mode...")

        # 加载缓存树
        cached_tree = self.load_cached_tree()

        if not cached_tree:
            logger.warning("No cached tree found, treating all local .strm files as invalid")
            return ValidationResult(
                valid_files=[],
                invalid_files=local_strm_files,
                missing_files=[],
                extra_files=[]
            )

        # 构建期望的STRM文件集合
        expected_strm_files = self.build_expected_strm_set(cached_tree)
        local_strm_files_set = set(local_strm_files)

        # 计算差异
        extra_local_files = local_strm_files_set - expected_strm_files
        missing_files_in_local = expected_strm_files - local_strm_files_set

        # 有效的文件
        valid_files = list(local_strm_files_set - extra_local_files)
        # 无效的文件（多余+缺失）
        invalid_files = list(extra_local_files) + list(missing_files_in_local)

        logger.info(f"Fast scan completed: {len(valid_files)} valid, {len(invalid_files)} invalid")
        return ValidationResult(
            valid_files=valid_files,
            invalid_files=invalid_files,
            missing_files=list(missing_files_in_local),
            extra_files=list(extra_local_files)
        )

    async def slow_scan(
        self,
        local_strm_files: List[str],
        concurrent_limit: int = 5,
        download_interval: tuple = (1, 3)
    ) -> ValidationResult:
        """
        慢速扫描模式

        参考: alist-strm strm_validator.py slow_scan

        Args:
            local_strm_files: 本地STRM文件列表
            concurrent_limit: 并发限制
            download_interval: 下载间隔范围（秒）

        Returns:
            验证结果
        """
        logger.info("Starting slow scan mode...")

        valid_files = []
        invalid_files = []
        total_files = len(local_strm_files)

        semaphore = asyncio.Semaphore(concurrent_limit)

        async def validate_strm_file(strm_file: str, idx: int):
            """验证单个STRM文件"""
            async with semaphore:
                try:
                    # 读取STRM文件内容
                    with open(strm_file, 'r', encoding='utf-8') as f:
                        url = f.read().strip()

                    if not url:
                        logger.warning(f"Empty .strm file: {strm_file}")
                        invalid_files.append(strm_file)
                        return

                    # 验证URL
                    logger.info(f"({idx}/{total_files}) Validating: {url}")
                    async with aiohttp.ClientSession() as session:
                        async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            if response.status in [200, 206, 302]:
                                logger.info(f"Valid .strm file: {strm_file}")
                                valid_files.append(strm_file)
                            else:
                                logger.warning(f"Invalid .strm file: {strm_file}, status: {response.status}")
                                invalid_files.append(strm_file)

                except Exception as e:
                    logger.error(f"Error validating .strm file: {strm_file}, error: {str(e)}")
                    invalid_files.append(strm_file)

        # 并发验证
        tasks = []
        for idx, strm_file in enumerate(local_strm_files, 1):
            task = validate_strm_file(strm_file, idx)
            tasks.append(task)

        await asyncio.gather(*tasks)

        logger.info(f"Slow scan completed: {len(valid_files)} valid, {len(invalid_files)} invalid")
        return ValidationResult(
            valid_files=valid_files,
            invalid_files=invalid_files,
            missing_files=[],
            extra_files=[]
        )

    async def validate(
        self,
        mode: ScanMode,
        concurrent_limit: int = 5,
        download_interval: tuple = (1, 3)
    ) -> ValidationResult:
        """
        验证STRM文件

        Args:
            mode: 扫描模式
            concurrent_limit: 并发限制
            download_interval: 下载间隔范围

        Returns:
            验证结果
        """
        local_strm_files = self.list_local_strm_files()

        if mode == ScanMode.QUICK:
            return await self.fast_scan(local_strm_files)
        elif mode == ScanMode.SLOW:
            return await self.slow_scan(local_strm_files, concurrent_limit, download_interval)
        else:
            raise ValueError(f"Unknown scan mode: {mode}")
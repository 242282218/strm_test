"""
媒体重命名服务

集成rename包的媒体重命名功能
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from app.core.sdk_config import sdk_config
from app.core.logging import get_logger

logger = get_logger(__name__)


class MediaRenameService:
    """媒体重命名服务"""

    def __init__(self):
        self._engine = None

    def _check_sdk(self) -> bool:
        """检查SDK是否可用"""
        if not sdk_config.is_available():
            logger.error("rename SDK不可用，请检查SDK路径配置")
            return False
        return True

    def _get_engine(self):
        """获取重命名引擎"""
        if self._engine is None:
            self._engine = sdk_config.create_rename_engine()
        return self._engine

    async def preview_rename(
        self,
        path: str,
        recursive: bool = True
    ) -> Dict[str, Any]:
        """
        预览重命名

        Args:
            path: 媒体文件路径
            recursive: 是否递归处理

        Returns:
            重命名任务列表
        """
        if not self._check_sdk():
            return {
                "tasks": [],
                "progress": [],
                "error": "SDK不可用"
            }

        try:
            engine = self._get_engine()
            if engine is None:
                return {
                    "tasks": [],
                    "progress": [],
                    "error": "重命名引擎初始化失败"
                }

            # 设置进度回调
            progress_messages = []

            def on_progress(msg, current, total):
                progress_messages.append({
                    "message": msg,
                    "current": current,
                    "total": total
                })

            engine.on_progress = on_progress

            # 执行预览
            tasks = engine.preview(path, recursive=recursive)

            # 转换结果
            result = []
            for task in tasks:
                parsed_info = task.parsed_info
                result.append({
                    "source_path": str(task.source_path),
                    "new_filename": task.new_filename,
                    "target_path": str(task.target_path) if task.target_path else None,
                    "media_type": parsed_info.media_type.value if hasattr(parsed_info.media_type, 'value') else str(parsed_info.media_type),
                    "title": parsed_info.title,
                    "cleaned_title": parsed_info.cleaned_title,
                    "year": parsed_info.year,
                    "season": parsed_info.season,
                    "episode": parsed_info.episode,
                    "resolution": parsed_info.resolution,
                    "codec": parsed_info.codec,
                    "source": parsed_info.source,
                    "confidence": parsed_info.confidence,
                    "needs_confirmation": task.needs_confirmation,
                    "confirmation_reason": task.confirmation_reason,
                    "tmdb_match": {
                        "title": task.tmdb_match.title if task.tmdb_match else None,
                        "year": task.tmdb_match.year if task.tmdb_match else None,
                        "confidence": task.tmdb_match.confidence if task.tmdb_match else None
                    } if task.tmdb_match else None
                })

            return {
                "tasks": result,
                "progress": progress_messages,
                "total_tasks": len(result),
                "needs_confirmation": sum(1 for t in result if t["needs_confirmation"])
            }

        except Exception as e:
            logger.error(f"预览重命名失败: {e}")
            return {
                "tasks": [],
                "progress": [],
                "error": str(e)
            }

    async def execute_rename(
        self,
        path: str,
        selected_tasks: Optional[List[str]] = None,
        recursive: bool = True
    ) -> Dict[str, Any]:
        """
        执行重命名

        Args:
            path: 媒体文件路径
            selected_tasks: 要执行的任务源路径列表（None表示全部）
            recursive: 是否递归处理

        Returns:
            执行结果
        """
        if not self._check_sdk():
            return {
                "success_count": 0,
                "failed_count": 0,
                "success": [],
                "failed": [],
                "error": "SDK不可用"
            }

        try:
            engine = self._get_engine()
            if engine is None:
                return {
                    "success_count": 0,
                    "failed_count": 0,
                    "success": [],
                    "failed": [],
                    "error": "重命名引擎初始化失败"
                }

            engine.dry_run = False

            # 如果指定了selected_tasks，需要先获取任务列表
            if selected_tasks:
                preview_tasks = engine.preview(path, recursive=recursive)
                tasks_to_execute = [
                    t for t in preview_tasks
                    if str(t.source_path) in selected_tasks
                ]
                if not tasks_to_execute:
                    return {
                        "success_count": 0,
                        "failed_count": 0,
                        "success": [],
                        "failed": [],
                        "error": "未找到指定的任务"
                    }
                results = engine.execute(tasks_to_execute)
            else:
                # 执行全部
                results = engine.rename(path, recursive=recursive, dry_run=False)

            # 转换结果
            success = []
            failed = []

            for result in results:
                item = {
                    "source_path": str(result.source_path),
                    "target_path": str(result.target_path) if result.target_path else None,
                    "success": result.success,
                    "error": result.error_message
                }

                if result.success:
                    success.append(item)
                else:
                    failed.append(item)

            return {
                "success_count": len(success),
                "failed_count": len(failed),
                "success": success,
                "failed": failed
            }

        except Exception as e:
            logger.error(f"执行重命名失败: {e}")
            return {
                "success_count": 0,
                "failed_count": 0,
                "success": [],
                "failed": [],
                "error": str(e)
            }

    async def get_media_info(
        self,
        file_path: str
    ) -> Dict[str, Any]:
        """
        获取媒体文件信息

        Args:
            file_path: 文件路径

        Returns:
            媒体信息
        """
        if not self._check_sdk():
            return {"error": "SDK不可用"}

        try:
            engine = self._get_engine()
            if engine is None:
                return {"error": "重命名引擎初始化失败"}

            # 解析单个文件
            path = Path(file_path)
            if not path.exists():
                return {"error": "文件不存在"}

            # 使用parser解析
            parsed_info = engine.parser.parse(path)

            return {
                "original_filename": parsed_info.original_filename,
                "media_type": parsed_info.media_type.value if hasattr(parsed_info.media_type, 'value') else str(parsed_info.media_type),
                "title": parsed_info.title,
                "cleaned_title": parsed_info.cleaned_title,
                "year": parsed_info.year,
                "season": parsed_info.season,
                "episode": parsed_info.episode,
                "resolution": parsed_info.resolution,
                "codec": parsed_info.codec,
                "source": parsed_info.source,
                "confidence": parsed_info.confidence
            }

        except Exception as e:
            logger.error(f"获取媒体信息失败: {e}")
            return {"error": str(e)}

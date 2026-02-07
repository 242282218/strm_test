from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.core.metrics_collector import get_metrics_collector
from app.core.retry import TransientError, retry_on_transient
from app.core.validators import validate_path
from app.core.path_security import (
    safe_open,
    safe_makedirs,
    safe_rename,
    safe_symlink,
    safe_hardlink,
    validate_file_path,
    PathSecurityError,
)
from app.models.scrape import CategoryStrategy, ScrapeItem, ScrapeJob, ScrapeRecord
from app.services.emby_service import get_emby_service
from app.services.notification_service import (
    NotificationService,
    NotificationType,
    get_notification_service,
)
from app.services.scrape_state_machine import ScrapeStateMachine
from app.services.tmdb_service import TMDBService, get_tmdb_service
from app.utils.media_parser import MediaParser

logger = get_logger(__name__)

DEFAULT_CATEGORY_FOLDERS = {
    "anime": "动漫文件夹",
    "movie": "电影",
    "tv": "电视剧",
}
DEFAULT_ANIME_KEYWORDS = [
    "anime",
    "animation",
    "动漫",
    "番剧",
]


class ScrapeService:
    """Scrape pipeline service with staged state transitions."""

    _instance = None
    _lock = threading.Lock()

    def __init__(
        self,
        tmdb_service: Optional[TMDBService] = None,
        notification_service: Optional[NotificationService] = None,
        emby_service: Optional[Any] = None,
        db_session_factory=SessionLocal,
    ):
        from app.services.tmdb_service import _global_tmdb_service

        self.tmdb_service = tmdb_service or _global_tmdb_service
        self.notification_service = notification_service or get_notification_service()
        self.emby_service = emby_service or get_emby_service()
        self.db_session_factory = db_session_factory
        self.state_machine = ScrapeStateMachine()
        self._active_jobs: dict[str, asyncio.Task] = {}
        self.metrics_collector = get_metrics_collector()
        # 添加信号量限制并发任务数
        self._job_semaphore = asyncio.Semaphore(10)
        self._job_lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "ScrapeService":
        """线程安全的单例获取方法"""
        if cls._instance is None:
            with cls._lock:
                # 双重检查锁定模式
                if cls._instance is None:
                    cls._instance = ScrapeService()
        return cls._instance

    async def create_job(
        self,
        target_path: str,
        media_type: str = "auto",
        options: Optional[Dict[str, Any]] = None,
    ) -> ScrapeJob:
        """Create scrape job."""
        target_path = validate_path(target_path, "target_path")
        job_id = str(uuid.uuid4())
        normalized_options = self._normalize_options(
            target_path=target_path,
            media_type=media_type,
            options=options or {},
        )

        db = self.db_session_factory()
        try:
            job = ScrapeJob(
                job_id=job_id,
                target_path=target_path,
                media_type=media_type,
                status="pending",
                options=normalized_options,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return job
        finally:
            db.close()

    async def start_job(self, job_id: str) -> bool:
        """Start job in background with idempotent protection and concurrency limit."""
        existing_task = self._active_jobs.get(job_id)
        if existing_task and not existing_task.done():
            logger.info("Job %s is already running", job_id)
            return True

        # 使用信号量限制并发任务数
        async with self._job_semaphore:
            db = None
            try:
                db = self.db_session_factory()
                job = db.query(ScrapeJob).filter(ScrapeJob.job_id == job_id).first()
                if not job:
                    logger.error("Job %s not found", job_id)
                    return False

                if job.status == "running":
                    # Recover in case process restarted and in-memory task was lost.
                    task = asyncio.create_task(self._process_job(job_id))
                    self._active_jobs[job_id] = task
                    return True

                job.status = "running"
                job.started_at = datetime.now()
                db.commit()

                task = asyncio.create_task(self._process_job(job_id))
                self._active_jobs[job_id] = task
                return True
            except Exception as e:
                logger.error("Error starting job %s: %s", job_id, e)
                return False
            finally:
                if db:
                    try:
                        db.close()
                    except Exception as e:
                        logger.warning("Error closing database connection: %s", e)

    async def stop_job(self, job_id: str) -> bool:
        """Cancel running job."""
        db = None
        try:
            db = self.db_session_factory()
            job = db.query(ScrapeJob).filter(ScrapeJob.job_id == job_id).first()
            if not job:
                return False
            job.status = "cancelled"
            job.completed_at = datetime.now()
            db.commit()
        except Exception as e:
            logger.error("Error stopping job %s: %s", job_id, e)
            return False
        finally:
            if db:
                try:
                    db.close()
                except Exception as e:
                    logger.warning("Error closing database connection: %s", e)

        # 取消正在运行的任务
        task = self._active_jobs.get(job_id)
        if task and not task.done():
            try:
                task.cancel()
                # 等待任务实际取消，但设置超时
                await asyncio.wait_for(task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for job %s to cancel", job_id)
            except asyncio.CancelledError:
                pass  # 预期内的异常
            except Exception as e:
                logger.warning("Error cancelling job %s: %s", job_id, e)
        return True

    async def _process_job(self, job_id: str):
        """Main orchestrator: scan -> identify -> scrape -> organize -> update."""
        logger.info("Starting scrape job %s", job_id)

        await self._safe_notify(
            NotificationType.TASK_STARTED,
            "Scrape job started",
            f"job_id={job_id}",
        )

        db = None
        try:
            db = self.db_session_factory()
            job = db.query(ScrapeJob).filter(ScrapeJob.job_id == job_id).first()
            if not job:
                logger.error("Job %s disappeared before execution", job_id)
                return

            options = self._normalize_options(
                target_path=job.target_path,
                media_type=job.media_type,
                options=job.options or {},
            )
            source_path = options["source_path"]
            files_to_process = self._scan_directory(source_path)

            job.total_items = len(files_to_process)
            db.commit()

            for file_path in files_to_process:
                db.refresh(job)
                if job.status == "cancelled":
                    break

                item = ScrapeItem(
                    job_id=job_id,
                    file_path=file_path,
                    file_name=os.path.basename(file_path),
                    status="pending",
                )
                db.add(item)
                db.commit()
                db.refresh(item)
                record = self._create_record(job_id=job_id, options=options, item=item)
                db.add(record)
                db.commit()
                db.refresh(record)

                try:
                    self._transition_item_status(item, "scanned")
                    self._sync_record_from_item(record, item)
                    db.commit()

                    should_scrape = options["scrape_mode"] != "only_rename"
                    should_rename = options["scrape_mode"] in {
                        "scrape_and_rename",
                        "only_rename",
                    }

                    if should_scrape:
                        self._transition_item_status(item, "scraping")
                        self._sync_record_from_item(record, item)
                        db.commit()

                        scrape_success, scrape_error = await self._scrape_single_item(
                            item,
                            options,
                        )
                        if not scrape_success:
                            if scrape_error:
                                item.error_message = json.dumps(scrape_error, ensure_ascii=False)
                            self._transition_item_status(item, "scrape_failed")
                            self._sync_record_from_item(record, item)
                            job.failed_items += 1
                            job.processed_items += 1
                            db.commit()
                            continue

                        self._transition_item_status(item, "scraped")
                        self._sync_record_from_item(record, item)
                        db.commit()
                    else:
                        self._transition_item_status(item, "scraping")
                        self._sync_record_from_item(record, item)
                        db.commit()
                        info = MediaParser.parse(item.file_name)
                        self._hydrate_item_from_parser(
                            item=item,
                            info=info,
                            requested_media_type=options.get("media_type", "auto"),
                        )
                        self._transition_item_status(item, "scraped")
                        self._sync_record_from_item(record, item)
                        db.commit()

                    if should_rename:
                        self._transition_item_status(item, "renaming")
                        self._sync_record_from_item(record, item)
                        db.commit()
                        renamed, target_path, rename_error = self._organize_item(
                            item=item,
                            options=options,
                        )
                        if not renamed:
                            if rename_error:
                                item.error_message = json.dumps(rename_error, ensure_ascii=False)
                            self._transition_item_status(item, "rename_failed")
                            self._sync_record_from_item(record, item)
                            job.failed_items += 1
                        else:
                            self._transition_item_status(item, "renamed")
                            # Keep target path discoverable until dedicated record model exists.
                            if target_path:
                                item.fanart_path = target_path
                            self._sync_record_from_item(record, item, target_file=target_path)
                            job.success_items += 1
                    else:
                        self._sync_record_from_item(record, item)
                        job.success_items += 1

                    job.processed_items += 1
                    db.commit()
                except Exception as exc:
                    logger.exception("Unexpected error while processing item %s", item.file_name)
                    item.error_message = json.dumps(
                        self._standardize_error("SCRAPE_PIPELINE_ERROR", "Unexpected item failure", str(exc)),
                        ensure_ascii=False,
                    )
                    fallback = "scrape_failed"
                    if item.status in {"renaming", "rename_failed"}:
                        fallback = "rename_failed"
                    try:
                        self._transition_item_status(item, fallback)
                    except Exception:
                        item.status = fallback
                    self._sync_record_from_item(record, item)
                    job.failed_items += 1
                    job.processed_items += 1
                    db.commit()

            if job.status != "cancelled":
                job.status = "completed" if job.failed_items < job.total_items else "failed"
            job.completed_at = datetime.now()
            total_items = int(job.total_items or 0)
            failed_items = int(job.failed_items or 0)
            failure_rate = (failed_items / total_items) if total_items > 0 else 0.0
            runtime_seconds = 0.0
            if job.started_at and job.completed_at:
                runtime_seconds = max(
                    0.0,
                    (job.completed_at - job.started_at).total_seconds(),
                )

            self.metrics_collector.record_metric(
                "scrape.job.failure_rate",
                failure_rate,
                tags={"job_id": job_id, "status": job.status},
            )
            self.metrics_collector.record_metric(
                "scrape.job.failed_items",
                float(failed_items),
                tags={"job_id": job_id, "status": job.status},
            )
            self.metrics_collector.record_metric(
                "scrape.job.runtime_seconds",
                runtime_seconds,
                tags={"job_id": job_id, "status": job.status},
            )
            db.commit()

            if job.status == "completed":
                await self._safe_notify(
                    NotificationType.TASK_COMPLETED,
                    "Scrape job completed",
                    f"success={job.success_items}, failed={job.failed_items}",
                )
            elif job.status == "failed":
                await self._safe_notify(
                    NotificationType.TASK_FAILED,
                    "Scrape job failed",
                    f"success={job.success_items}, failed={job.failed_items}",
                )

            # Trigger optional Emby refresh.
            emby_library_id = options.get("emby_library_id")
            if emby_library_id is not None:
                try:
                    await self.emby_service.refresh_library(emby_library_id)
                except Exception as exc:
                    logger.warning("Failed to trigger Emby refresh for %s: %s", job_id, exc)

        except asyncio.CancelledError:
            logger.info("Scrape job %s cancelled", job_id)
            job = db.query(ScrapeJob).filter(ScrapeJob.job_id == job_id).first()
            if job:
                job.status = "cancelled"
                job.completed_at = datetime.now()
                db.commit()
            raise
        except Exception as exc:
            logger.exception("Scrape job %s failed", job_id)
            job = db.query(ScrapeJob).filter(ScrapeJob.job_id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = json.dumps(
                    self._standardize_error("SCRAPE_JOB_FAILED", "Job execution failed", str(exc)),
                    ensure_ascii=False,
                )
                job.completed_at = datetime.now()
                db.commit()
            await self._safe_notify(
                NotificationType.TASK_FAILED,
                "Scrape job failed",
                str(exc),
            )
        finally:
            # 确保任务从活跃列表中移除
            try:
                task = self._active_jobs.get(job_id)
                if task:
                    if task.done() or task.cancelled():
                        self._active_jobs.pop(job_id, None)
                    else:
                        # 如果任务还在运行，尝试取消
                        task.cancel()
                        self._active_jobs.pop(job_id, None)
            except Exception as e:
                logger.warning("Error cleaning up active job %s: %s", job_id, e)
            
            # 确保数据库连接关闭
            if db:
                try:
                    db.close()
                except Exception as e:
                    logger.warning("Error closing database connection for job %s: %s", job_id, e)

    def _transition_item_status(self, item: ScrapeItem, target_status: str) -> None:
        current = item.status or "pending"
        self.state_machine.assert_transition(current, target_status)
        item.status = target_status

    def _create_record(self, job_id: str, options: Dict[str, Any], item: ScrapeItem) -> ScrapeRecord:
        return ScrapeRecord(
            record_id=str(uuid.uuid4()),
            job_id=job_id,
            path_id=options.get("path_id"),
            item_id=item.id,
            source_file=item.file_path,
            target_file=None,
            media_type=item.media_type,
            tmdb_id=item.tmdb_id,
            title=item.title,
            year=item.year,
            status=item.status or "pending",
            recognition_result={},
        )

    def _sync_record_from_item(
        self,
        record: ScrapeRecord,
        item: ScrapeItem,
        *,
        target_file: Optional[str] = None,
    ) -> None:
        record.status = item.status or record.status
        record.media_type = item.media_type
        record.tmdb_id = item.tmdb_id
        record.title = item.title
        record.year = item.year
        if target_file:
            record.target_file = target_file
        if item.fanart_path and not record.target_file:
            # fanart_path is currently used by legacy flow to carry target file.
            record.target_file = item.fanart_path

        record.recognition_result = {
            "title": item.title,
            "original_title": item.original_title,
            "year": item.year,
            "season": item.season,
            "episode": item.episode,
            "confidence": item.confidence,
        }
        error_code, error_message = self._parse_error_payload(item.error_message)
        record.error_code = error_code
        record.error_message = error_message

    def _parse_error_payload(self, raw_error: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        if not raw_error:
            return None, None
        try:
            payload = json.loads(raw_error)
            if isinstance(payload, dict):
                code = payload.get("code")
                message = payload.get("message")
                detail = payload.get("detail")
                if message and detail:
                    return code, f"{message}: {detail}"
                if message:
                    return code, str(message)
                return code, raw_error
        except Exception:
            pass
        return None, raw_error

    def _normalize_options(
        self,
        target_path: str,
        media_type: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized = dict(options)
        normalized.setdefault("source_path", target_path)
        normalized.setdefault("dest_path", target_path)
        normalized.setdefault("media_type", media_type or "auto")
        normalized.setdefault("scrape_mode", "scrape_and_rename")
        normalized.setdefault("rename_mode", "move")
        normalized.setdefault("generate_nfo", True)
        normalized.setdefault("download_images", True)
        normalized.setdefault("force_overwrite", False)
        normalized.setdefault("max_threads", 1)
        normalized.setdefault("enable_secondary_category", True)

        if normalized["scrape_mode"] not in {"only_scrape", "scrape_and_rename", "only_rename"}:
            normalized["scrape_mode"] = "scrape_and_rename"
        if normalized["rename_mode"] not in {"move", "copy", "hardlink", "softlink"}:
            normalized["rename_mode"] = "move"
        if normalized["media_type"] not in {"auto", "movie", "tv"}:
            normalized["media_type"] = "auto"

        normalized["source_path"] = validate_path(normalized["source_path"], "source_path")
        normalized["dest_path"] = validate_path(normalized["dest_path"], "dest_path")

        return normalized

    def _scan_directory(self, path: str) -> List[str]:
        media_extensions = {".mp4", ".mkv", ".avi", ".mov", ".strm"}
        files: List[str] = []
        if not os.path.exists(path):
            return files
        for root, _dirs, filenames in os.walk(path):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in media_extensions:
                    files.append(os.path.join(root, filename))
        files.sort()
        return files

    def _hydrate_item_from_parser(
        self,
        item: ScrapeItem,
        info: Dict[str, Any],
        requested_media_type: str,
    ) -> None:
        media_type = "movie"
        if requested_media_type == "tv":
            media_type = "tv"
        elif requested_media_type == "movie":
            media_type = "movie"
        elif info.get("season") is not None or info.get("episode") is not None:
            media_type = "tv"

        item.media_type = media_type
        item.title = info.get("title") or os.path.splitext(item.file_name)[0]
        item.original_title = info.get("original_title") or item.title
        item.year = info.get("year")
        item.season = info.get("season")
        item.episode = info.get("episode")
        item.confidence = float(info.get("confidence") or 0.5)

    async def _scrape_single_item(
        self,
        item: ScrapeItem,
        options: Dict[str, Any],
    ) -> Tuple[bool, Optional[Dict[str, str]]]:
        """Identify metadata and generate NFO/images when enabled."""
        try:
            info = MediaParser.parse(item.file_name)
            self._hydrate_item_from_parser(item, info, options.get("media_type", "auto"))

            metadata = await self._lookup_tmdb_metadata(item, info)
            if metadata:
                item.tmdb_id = metadata.get("tmdb_id")
                item.title = metadata.get("title") or item.title
                item.original_title = metadata.get("original_title") or item.original_title
                item.year = metadata.get("year") or item.year
                item.season = metadata.get("season") or item.season
                item.episode = metadata.get("episode") or item.episode
                item.confidence = float(metadata.get("confidence") or item.confidence or 0.5)

            file_dir = os.path.dirname(item.file_path)
            base_name = os.path.splitext(item.file_name)[0]

            # 验证文件目录是否在允许范围内
            try:
                validate_file_path(file_dir)
            except PathSecurityError as e:
                logger.error(f"Path security error for file_dir: {file_dir}, error: {e}")
                return False, self._standardize_error(
                    "PATH_SECURITY_ERROR",
                    "File directory is outside of allowed directories",
                    str(e),
                )

            if options.get("generate_nfo", True):
                nfo_content = self._build_simple_nfo(item)
                nfo_path = os.path.join(file_dir, f"{base_name}.nfo")
                if options.get("force_overwrite") or not os.path.exists(nfo_path):
                    try:
                        with safe_open(nfo_path, "w", encoding="utf-8") as nfo_fp:
                            nfo_fp.write(nfo_content)
                    except PathSecurityError as e:
                        logger.error(f"Path security error writing NFO: {e}")
                        return False, self._standardize_error(
                            "PATH_SECURITY_ERROR",
                            "Cannot write NFO file outside of allowed directories",
                            str(e),
                        )
                item.nfo_path = nfo_path

            if options.get("download_images", True):
                poster_url = metadata.get("poster_url") if metadata else None
                fanart_url = metadata.get("fanart_url") if metadata else None
                if poster_url:
                    poster_path = os.path.join(file_dir, f"{base_name}-poster.jpg")
                    if await self._download_image(poster_url, poster_path):
                        item.poster_path = poster_path
                if fanart_url:
                    fanart_path = os.path.join(file_dir, f"{base_name}-fanart.jpg")
                    if await self._download_image(fanart_url, fanart_path):
                        item.fanart_path = fanart_path

            item.error_message = None
            return True, None
        except Exception as exc:
            logger.exception("Scrape failed for %s", item.file_name)
            return False, self._standardize_error(
                "SCRAPE_ITEM_FAILED",
                "Failed to scrape item",
                str(exc),
            )

    async def _lookup_tmdb_metadata(
        self,
        item: ScrapeItem,
        info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Best-effort TMDB lookup. Returns parser fallback if TMDB is unavailable."""
        metadata: Dict[str, Any] = {
            "title": item.title,
            "original_title": item.original_title,
            "year": item.year,
            "season": item.season,
            "episode": item.episode,
            "confidence": 0.55,
        }

        tmdb = self.tmdb_service
        if not tmdb:
            from app.core.config_manager import ConfigManager
            from app.services.cache_service import get_cache_service

            cfg = ConfigManager()
            api_key = cfg.get("api_keys.tmdb_api_key") or cfg.get("tmdb.api_key")
            if api_key:
                tmdb = get_tmdb_service(api_key=api_key, cache_service=get_cache_service())
                self.tmdb_service = tmdb

        if not tmdb:
            return metadata

        try:
            if item.media_type == "movie":
                search_result = await tmdb.search_movie(info["title"], year=info.get("year"))
                if not search_result.results:
                    search_result = await tmdb.search_movie(info["title"])
                if not search_result.results:
                    return metadata
                match = search_result.results[0]
                metadata.update(
                    {
                        "tmdb_id": match.id,
                        "title": match.title,
                        "original_title": match.original_title,
                        "year": int(match.release_date[:4]) if match.release_date else metadata.get("year"),
                        "poster_url": tmdb.get_poster_url(match.poster_path) if match.poster_path else None,
                        "fanart_url": tmdb.get_backdrop_url(match.backdrop_path) if match.backdrop_path else None,
                        "confidence": 0.9,
                    }
                )
            else:
                search_result = await tmdb.search_tv(
                    info["title"],
                    first_air_date_year=info.get("year"),
                )
                if not search_result.results:
                    search_result = await tmdb.search_tv(info["title"])
                if not search_result.results:
                    return metadata
                show = search_result.results[0]
                metadata.update(
                    {
                        "tmdb_id": show.id,
                        "title": show.name,
                        "original_title": show.original_name,
                        "year": int(show.first_air_date[:4]) if show.first_air_date else metadata.get("year"),
                        "poster_url": tmdb.get_poster_url(show.poster_path) if show.poster_path else None,
                        "fanart_url": tmdb.get_backdrop_url(show.backdrop_path) if show.backdrop_path else None,
                        "confidence": 0.88,
                    }
                )
                if info.get("season") and info.get("episode"):
                    episode = await tmdb.get_tv_episode(show.id, info["season"], info["episode"])
                    metadata["episode"] = episode.episode_number
                    metadata["season"] = episode.season_number
                    if episode.name:
                        metadata["title"] = episode.name
                    if episode.still_path:
                        metadata["poster_url"] = tmdb.get_poster_url(episode.still_path)
        except Exception as exc:
            logger.warning("TMDB lookup failed for %s: %s", item.file_name, exc)
        return metadata

    def _build_simple_nfo(self, item: ScrapeItem) -> str:
        title = item.title or os.path.splitext(item.file_name)[0]
        # 对所有字段进行 XML 转义，防止注入攻击
        escaped_title = self._xml_escape(str(title))
        year_tag = f"<year>{self._xml_escape(str(item.year))}</year>" if item.year else ""
        tmdb_tag = f"<tmdbid>{self._xml_escape(str(item.tmdb_id))}</tmdbid>" if item.tmdb_id else ""

        if item.media_type == "tv":
            season_tag = f"<season>{self._xml_escape(str(item.season))}</season>" if item.season is not None else ""
            episode_tag = f"<episode>{self._xml_escape(str(item.episode))}</episode>" if item.episode is not None else ""
            return (
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                "<episodedetails>\n"
                f"  <title>{escaped_title}</title>\n"
                f"  {season_tag}\n"
                f"  {episode_tag}\n"
                f"  {tmdb_tag}\n"
                "</episodedetails>\n"
            )

        return (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<movie>\n"
            f"  <title>{escaped_title}</title>\n"
            f"  {year_tag}\n"
            f"  {tmdb_tag}\n"
            "</movie>\n"
        )

    def _organize_item(
        self,
        item: ScrapeItem,
        options: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, str]]]:
        source_file = item.file_path
        if not os.path.exists(source_file):
            return (
                False,
                None,
                self._standardize_error("SOURCE_FILE_MISSING", "Source file not found", source_file),
            )

        dest_root = options.get("dest_path") or os.path.dirname(source_file)
        target_root = dest_root
        if options.get("enable_secondary_category", True):
            strategy = self._get_category_strategy()
            if strategy["enabled"]:
                category_key = self._resolve_category_key(item, source_file, strategy)
                category_folder = strategy["folder_names"].get(category_key) or DEFAULT_CATEGORY_FOLDERS[category_key]
                target_root = os.path.join(dest_root, category_folder)
        
        # 使用安全的目录创建
        try:
            safe_makedirs(target_root, exist_ok=True)
        except PathSecurityError as e:
            return (
                False,
                None,
                self._standardize_error("PATH_SECURITY_ERROR", "Target directory is outside of allowed directories", str(e)),
            )

        target_name = self._build_target_filename(item, source_file)
        target_path = os.path.join(target_root, target_name)

        # 验证源文件和目标路径
        try:
            validate_file_path(source_file, check_exists=True)
            validate_file_path(target_path)
        except PathSecurityError as e:
            return (
                False,
                None,
                self._standardize_error("PATH_SECURITY_ERROR", "File path is outside of allowed directories", str(e)),
            )

        if os.path.abspath(source_file) == os.path.abspath(target_path):
            return True, target_path, None

        if os.path.exists(target_path):
            if options.get("force_overwrite"):
                os.remove(target_path)
            else:
                target_path = self._next_available_path(target_path)

        mode = options.get("rename_mode", "move")
        try:
            if mode == "move":
                safe_rename(source_file, target_path)
            elif mode == "copy":
                # 复制操作使用 shutil，但需要先验证路径
                validate_file_path(source_file, check_exists=True)
                validate_file_path(target_path)
                shutil.copy2(source_file, target_path)
            elif mode == "hardlink":
                safe_hardlink(source_file, target_path)
            elif mode == "softlink":
                safe_symlink(source_file, target_path)
            else:
                return (
                    False,
                    None,
                    self._standardize_error("INVALID_RENAME_MODE", "Unsupported rename mode", mode),
                )
        except PathSecurityError as e:
            return (
                False,
                None,
                self._standardize_error("PATH_SECURITY_ERROR", "File operation blocked for security reasons", str(e)),
            )
        except Exception as exc:
            return (
                False,
                None,
                self._standardize_error("RENAME_IO_ERROR", "Failed to organize media file", str(exc)),
            )

        return True, target_path, None

    def _build_target_filename(self, item: ScrapeItem, source_file: str) -> str:
        source_name = os.path.basename(source_file)
        _base, ext = os.path.splitext(source_name)

        if item.media_type == "tv":
            if item.season is not None and item.episode is not None:
                stem = f"{item.title or 'Unknown'} - S{int(item.season):02d}E{int(item.episode):02d}"
            else:
                stem = item.title or "Unknown"
        else:
            if item.year:
                stem = f"{item.title or 'Unknown'} ({item.year})"
            else:
                stem = item.title or "Unknown"

        stem = self._sanitize_filename(stem)
        return f"{stem}{ext}"

    def _get_category_strategy(self) -> Dict[str, Any]:
        db = self.db_session_factory()
        try:
            strategy = db.query(CategoryStrategy).order_by(CategoryStrategy.id.asc()).first()
            if not strategy:
                return {
                    "enabled": True,
                    "anime_keywords": DEFAULT_ANIME_KEYWORDS,
                    "folder_names": DEFAULT_CATEGORY_FOLDERS,
                }
            anime_keywords = strategy.anime_keywords or DEFAULT_ANIME_KEYWORDS
            folder_names = dict(DEFAULT_CATEGORY_FOLDERS)
            if isinstance(strategy.folder_names, dict):
                folder_names.update(strategy.folder_names)
            return {
                "enabled": bool(strategy.enabled),
                "anime_keywords": [str(keyword).lower() for keyword in anime_keywords],
                "folder_names": folder_names,
            }
        finally:
            db.close()

    def _resolve_category_key(
        self,
        item: ScrapeItem,
        source_file: str,
        strategy: Dict[str, Any],
    ) -> str:
        text = f"{item.title or ''} {item.file_name or ''} {source_file}".lower()
        for keyword in strategy.get("anime_keywords", []):
            if keyword and keyword.lower() in text:
                return "anime"
        if item.media_type == "movie":
            return "movie"
        return "tv"

    def _sanitize_filename(self, value: str) -> str:
        cleaned = re.sub(r'[<>:"/\\\\|?*]+', " ", value)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or "Unknown"

    def _next_available_path(self, target_path: str) -> str:
        directory = os.path.dirname(target_path)
        filename = os.path.basename(target_path)
        stem, ext = os.path.splitext(filename)
        index = 1
        candidate = target_path
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{stem}_{index}{ext}")
            index += 1
        return candidate

    @retry_on_transient()
    async def _download_image(self, url: str, save_path: str) -> bool:
        if not url:
            return False
        try:
            # 配置超时：连接超时10秒，总超时30秒
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status in {408, 429} or resp.status >= 500:
                        raise TransientError(f"Download transient error: {resp.status}")
                    if resp.status == 200:
                        content = await resp.read()
                        with open(save_path, "wb") as image_fp:
                            image_fp.write(content)
                        return True
        except asyncio.TimeoutError:
            logger.warning("Timeout downloading image from %s", url)
        except TransientError:
            raise
        except Exception as exc:
            logger.warning("Failed to download image %s: %s", url, exc)
        return False

    async def _safe_notify(self, notify_type: NotificationType, title: str, content: str) -> None:
        try:
            await self.notification_service.send_notification(
                type=notify_type,
                title=title,
                content=content,
            )
        except Exception as exc:
            logger.warning("Notification failed: %s", exc)

    def _standardize_error(self, code: str, message: str, detail: Optional[str] = None) -> Dict[str, str]:
        payload = {"code": code, "message": message}
        if detail:
            payload["detail"] = detail
        return payload

    def _xml_escape(self, value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )


def get_scrape_service() -> ScrapeService:
    return ScrapeService.get_instance()

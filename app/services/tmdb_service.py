"""
TMDB API 服务模块

提供TMDB API调用功能:
- 电影/电视剧搜索
- 详细信息获取
- 图片URL生成
- 限流和重试机制
- 缓存支持
- 代理支持

优化:
- 使用全局 HTTP 连接池，实现连接复用
- 降低 TCP 握手开销，减少延迟

参考: QMediaSync TMDB实现
"""

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.http_pool import ClientType, get_http_pool
from app.core.logging import get_logger
from app.core.retry import retry_on_tmdb
from app.services.cache_service import CacheService


logger = get_logger(__name__)


@dataclass
class TMDBMovie:
    """TMDB电影信息"""

    id: int
    title: str
    original_title: str
    release_date: str | None = None
    overview: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    vote_average: float | None = None
    popularity: float | None = None


@dataclass
class TMDBTVShow:
    """TMDB电视剧信息"""

    id: int
    name: str
    original_name: str
    first_air_date: str | None = None
    overview: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    vote_average: float | None = None
    popularity: float | None = None


@dataclass
class TMDBSearchResult:
    """TMDB搜索结果"""

    results: list[Any]
    total_results: int
    total_pages: int
    page: int


@dataclass
class TMDBGenre:
    """TMDB类型"""

    id: int
    name: str


@dataclass
class TMDBMovieDetail:
    """TMDB电影详情"""

    id: int
    title: str
    original_title: str
    release_date: str | None
    overview: str | None
    poster_path: str | None
    backdrop_path: str | None
    runtime: int | None
    status: str | None
    genres: list[TMDBGenre]
    vote_average: float | None
    vote_count: int | None
    imdb_id: str | None


@dataclass
class TMDBTVDetail:
    """TMDB电视剧详情"""

    id: int
    name: str
    original_name: str
    first_air_date: str | None
    overview: str | None
    poster_path: str | None
    backdrop_path: str | None
    number_of_seasons: int
    number_of_episodes: int
    status: str | None
    genres: list[TMDBGenre]
    vote_average: float | None
    vote_count: int | None


@dataclass
class TMDBEpisode:
    """TMDB剧集信息"""

    id: int
    name: str
    episode_number: int
    season_number: int
    air_date: str | None
    overview: str | None
    still_path: str | None
    vote_average: float | None


class TMDBRateLimiter:
    """TMDB API限流器"""

    def __init__(self, max_requests: int = 40, time_window: int = 10):
        """
        初始化限流器

        Args:
            max_requests: 时间窗口内最大请求数
            time_window: 时间窗口(秒)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self._requests: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self):
        """获取请求许可"""
        async with self._lock:
            now = asyncio.get_event_loop().time()

            # 清理过期请求
            self._requests = [req_time for req_time in self._requests if now - req_time < self.time_window]

            # 检查是否超限
            if len(self._requests) >= self.max_requests:
                # 计算需要等待的时间
                oldest = self._requests[0]
                wait_time = self.time_window - (now - oldest)
                if wait_time > 0:
                    logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    return await self.acquire()

            self._requests.append(now)


class TMDBService:
    """
    TMDB API服务

    参考: QMediaSync的TMDB实现

    优化: 使用全局 HTTP 连接池
    """

    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

    def __init__(
        self,
        api_key: str,
        language: str = "zh-CN",
        proxy_url: str | None = None,
        cache_service: CacheService | None = None,
        cache_ttl: int = 3600,
    ):
        """
        初始化TMDB服务

        Args:
            api_key: TMDB API密钥
            language: 语言(默认中文)
            proxy_url: 代理URL（暂不支持，保留兼容性）
            cache_service: 缓存服务
            cache_ttl: 缓存TTL(秒)
        """
        self.api_key = api_key
        self.language = language
        self.proxy_url = proxy_url  # 保留字段，但连接池暂不支持代理
        self.cache_service = cache_service
        self.cache_ttl = cache_ttl

        # 限流器 (TMDB限制: 40请求/10秒)
        self.rate_limiter = TMDBRateLimiter(max_requests=40, time_window=10)

        # 连接池客户端
        self._pool = None
        self._httpx_client: httpx.AsyncClient | None = None

        logger.info(f"TMDBService initialized: language={language}")

    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端（来自连接池）"""
        if self._httpx_client is None or self._httpx_client.is_closed:
            if self._pool is None:
                self._pool = await get_http_pool()
            self._httpx_client = await self._pool.get_client(ClientType.TMDB)
        return self._httpx_client

    async def close(self):
        """关闭服务"""
        # 连接池统一管理客户端生命周期，这里只清理引用
        self._httpx_client = None

    @retry_on_tmdb()
    async def _request(self, method: str, endpoint: str, params: dict | None = None) -> dict[str, Any]:
        """
        发送HTTP请求(带重试)

        Args:
            method: HTTP方法
            endpoint: API端点
            params: 查询参数

        Returns:
            响应JSON
        """
        # 限流
        await self.rate_limiter.acquire()

        url = f"{self.BASE_URL}{endpoint}"
        params = params or {}
        params["api_key"] = self.api_key
        params["language"] = self.language

        client = await self._get_client()

        try:
            if method.upper() == "GET":
                response = await client.get(url, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, params=params)
            else:
                response = await client.request(method, url, params=params)

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"TMDB API error: {e}")
            raise
        except httpx.RequestError as e:
            logger.error(f"TMDB API error: {e}")
            raise

    async def _cached_request(
        self, cache_key: str, method: str, endpoint: str, params: dict | None = None
    ) -> dict[str, Any]:
        """带缓存的请求"""
        # 尝试从缓存获取
        if self.cache_service:
            cached = await self.cache_service.get(cache_key)
            if cached is not None:
                logger.debug(f"TMDB cache hit: {cache_key}")
                return cached

        # 发送请求
        result = await self._request(method, endpoint, params)

        # 缓存结果
        if self.cache_service:
            await self.cache_service.set(cache_key, result, self.cache_ttl)

        return result

    async def search_movie(self, query: str, year: int | None = None, page: int = 1) -> TMDBSearchResult:
        """
        搜索电影

        Args:
            query: 搜索关键词
            year: 年份(可选)
            page: 页码

        Returns:
            搜索结果
        """
        cache_key = f"tmdb:search:movie:{query}:{year}:{page}"

        params = {"query": query, "page": page}
        if year:
            params["year"] = year

        data = await self._cached_request(cache_key, "GET", "/search/movie", params)

        results = [
            TMDBMovie(
                id=item["id"],
                title=item.get("title", ""),
                original_title=item.get("original_title", ""),
                release_date=item.get("release_date"),
                overview=item.get("overview"),
                poster_path=item.get("poster_path"),
                backdrop_path=item.get("backdrop_path"),
                vote_average=item.get("vote_average"),
                popularity=item.get("popularity"),
            )
            for item in data.get("results", [])
        ]

        return TMDBSearchResult(
            results=results,
            total_results=data.get("total_results", 0),
            total_pages=data.get("total_pages", 0),
            page=data.get("page", 1),
        )

    async def search_tv(self, query: str, first_air_date_year: int | None = None, page: int = 1) -> TMDBSearchResult:
        """
        搜索电视剧

        Args:
            query: 搜索关键词
            first_air_date_year: 首播年份(可选)
            page: 页码

        Returns:
            搜索结果
        """
        cache_key = f"tmdb:search:tv:{query}:{first_air_date_year}:{page}"

        params = {"query": query, "page": page}
        if first_air_date_year:
            params["first_air_date_year"] = first_air_date_year

        data = await self._cached_request(cache_key, "GET", "/search/tv", params)

        results = [
            TMDBTVShow(
                id=item["id"],
                name=item.get("name", ""),
                original_name=item.get("original_name", ""),
                first_air_date=item.get("first_air_date"),
                overview=item.get("overview"),
                poster_path=item.get("poster_path"),
                backdrop_path=item.get("backdrop_path"),
                vote_average=item.get("vote_average"),
                popularity=item.get("popularity"),
            )
            for item in data.get("results", [])
        ]

        return TMDBSearchResult(
            results=results,
            total_results=data.get("total_results", 0),
            total_pages=data.get("total_pages", 0),
            page=data.get("page", 1),
        )

    async def get_movie_detail(self, movie_id: int) -> TMDBMovieDetail:
        """
        获取电影详情

        Args:
            movie_id: 电影ID

        Returns:
            电影详情
        """
        cache_key = f"tmdb:movie:{movie_id}"

        data = await self._cached_request(cache_key, "GET", f"/movie/{movie_id}")

        genres = [TMDBGenre(id=g["id"], name=g["name"]) for g in data.get("genres", [])]

        return TMDBMovieDetail(
            id=data["id"],
            title=data.get("title", ""),
            original_title=data.get("original_title", ""),
            release_date=data.get("release_date"),
            overview=data.get("overview"),
            poster_path=data.get("poster_path"),
            backdrop_path=data.get("backdrop_path"),
            runtime=data.get("runtime"),
            status=data.get("status"),
            genres=genres,
            vote_average=data.get("vote_average"),
            vote_count=data.get("vote_count"),
            imdb_id=data.get("imdb_id"),
        )

    async def get_tv_detail(self, tv_id: int) -> TMDBTVDetail:
        """
        获取电视剧详情

        Args:
            tv_id: 电视剧ID

        Returns:
            电视剧详情
        """
        cache_key = f"tmdb:tv:{tv_id}"

        data = await self._cached_request(cache_key, "GET", f"/tv/{tv_id}")

        genres = [TMDBGenre(id=g["id"], name=g["name"]) for g in data.get("genres", [])]

        return TMDBTVDetail(
            id=data["id"],
            name=data.get("name", ""),
            original_name=data.get("original_name", ""),
            first_air_date=data.get("first_air_date"),
            overview=data.get("overview"),
            poster_path=data.get("poster_path"),
            backdrop_path=data.get("backdrop_path"),
            number_of_seasons=data.get("number_of_seasons", 0),
            number_of_episodes=data.get("number_of_episodes", 0),
            status=data.get("status"),
            genres=genres,
            vote_average=data.get("vote_average"),
            vote_count=data.get("vote_count"),
        )

    async def get_tv_episode(self, tv_id: int, season_number: int, episode_number: int) -> TMDBEpisode:
        """
        获取电视剧集详情

        Args:
            tv_id: 电视剧ID
            season_number: 季号
            episode_number: 集号

        Returns:
            剧集详情
        """
        cache_key = f"tmdb:tv:{tv_id}:s{season_number}e{episode_number}"

        data = await self._cached_request(
            cache_key, "GET", f"/tv/{tv_id}/season/{season_number}/episode/{episode_number}"
        )

        return TMDBEpisode(
            id=data["id"],
            name=data.get("name", ""),
            episode_number=data.get("episode_number", 0),
            season_number=data.get("season_number", 0),
            air_date=data.get("air_date"),
            overview=data.get("overview"),
            still_path=data.get("still_path"),
            vote_average=data.get("vote_average"),
        )

    def get_image_url(self, path: str, size: str = "original") -> str:
        """
        获取图片URL

        Args:
            path: 图片路径
            size: 尺寸 (w92, w154, w185, w342, w500, w780, original)

        Returns:
            完整图片URL
        """
        if not path:
            return ""
        return f"{self.IMAGE_BASE_URL}/{size}{path}"

    def get_poster_url(self, path: str, width: int = 500) -> str:
        """
        获取海报URL

        Args:
            path: 海报路径
            width: 宽度 (92, 154, 185, 342, 500, 780, 0=original)

        Returns:
            海报URL
        """
        size_map = {92: "w92", 154: "w154", 185: "w185", 342: "w342", 500: "w500", 780: "w780", 0: "original"}
        size = size_map.get(width, "w500")
        return self.get_image_url(path, size)

    def get_backdrop_url(self, path: str, width: int = 1280) -> str:
        """
        获取背景图URL

        Args:
            path: 背景图路径
            width: 宽度 (300, 780, 1280, 0=original)

        Returns:
            背景图URL
        """
        size_map = {300: "w300", 780: "w780", 1280: "w1280", 0: "original"}
        size = size_map.get(width, "w1280")
        return self.get_image_url(path, size)


# 全局TMDB服务实例
_global_tmdb_service: TMDBService | None = None


def get_tmdb_service(api_key: str, language: str = "zh-CN", cache_service: CacheService | None = None) -> TMDBService:
    """获取全局TMDB服务实例"""
    global _global_tmdb_service

    if _global_tmdb_service is None:
        _global_tmdb_service = TMDBService(api_key=api_key, language=language, cache_service=cache_service)

    return _global_tmdb_service

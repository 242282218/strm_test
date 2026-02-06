# -*- coding: utf-8 -*-
"""
TMDB API路由

提供TMDB搜索和查询接口
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
from pydantic import BaseModel, Field
from app.services.tmdb_service import (
    get_tmdb_service,
    TMDBMovie,
    TMDBTVShow,
    TMDBMovieDetail,
    TMDBTVDetail,
    TMDBEpisode
)
from app.services.cache_service import get_cache_service
from app.core.config_manager import ConfigManager
from app.core.logging import get_logger
from app.core.dependencies import require_api_key

logger = get_logger(__name__)
router = APIRouter(prefix="/api/tmdb", tags=["tmdb"])


# Pydantic模型
class MovieSearchResponse(BaseModel):
    """电影搜索响应"""
    id: int
    title: str
    original_title: str
    release_date: Optional[str] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    vote_average: Optional[float] = None
    popularity: Optional[float] = None


class TVSearchResponse(BaseModel):
    """电视剧搜索响应"""
    id: int
    name: str
    original_name: str
    first_air_date: Optional[str] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    vote_average: Optional[float] = None
    popularity: Optional[float] = None


class SearchResultResponse(BaseModel):
    """搜索结果响应"""
    results: List[dict]
    total_results: int
    total_pages: int
    page: int


class GenreResponse(BaseModel):
    """类型响应"""
    id: int
    name: str


class MovieDetailResponse(BaseModel):
    """电影详情响应"""
    id: int
    title: str
    original_title: str
    release_date: Optional[str]
    overview: Optional[str]
    poster_path: Optional[str]
    backdrop_path: Optional[str]
    runtime: Optional[int]
    status: Optional[str]
    genres: List[GenreResponse]
    vote_average: Optional[float]
    vote_count: Optional[int]
    imdb_id: Optional[str]
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None


class TVDetailResponse(BaseModel):
    """电视剧详情响应"""
    id: int
    name: str
    original_name: str
    first_air_date: Optional[str]
    overview: Optional[str]
    poster_path: Optional[str]
    backdrop_path: Optional[str]
    number_of_seasons: int
    number_of_episodes: int
    status: Optional[str]
    genres: List[GenreResponse]
    vote_average: Optional[float]
    vote_count: Optional[int]
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None


class EpisodeResponse(BaseModel):
    """剧集响应"""
    id: int
    name: str
    episode_number: int
    season_number: int
    air_date: Optional[str]
    overview: Optional[str]
    still_path: Optional[str]
    vote_average: Optional[float]
    still_url: Optional[str] = None


def _get_tmdb_service():
    """获取TMDB服务实例"""
    config_manager = ConfigManager()
    api_key = config_manager.get("api_keys.tmdb_api_key") or config_manager.get("tmdb.api_key")
    
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="TMDB API key not configured"
        )
    
    cache_service = get_cache_service()
    
    return get_tmdb_service(
        api_key=api_key,
        language="zh-CN",
        cache_service=cache_service
    )


@router.get("/search/movie", response_model=SearchResultResponse)
async def search_movie(
    query: str = Query(..., description="搜索关键词"),
    year: Optional[int] = Query(None, description="年份"),
    page: int = Query(1, ge=1, description="页码")
):
    """
    搜索电影
    
    Args:
        query: 搜索关键词
        year: 年份(可选)
        page: 页码
    
    Returns:
        搜索结果
    """
    try:
        tmdb_service = _get_tmdb_service()
        result = await tmdb_service.search_movie(query, year, page)
        
        return SearchResultResponse(
            results=[
                {
                    "id": movie.id,
                    "title": movie.title,
                    "original_title": movie.original_title,
                    "release_date": movie.release_date,
                    "overview": movie.overview,
                    "poster_path": movie.poster_path,
                    "backdrop_path": movie.backdrop_path,
                    "vote_average": movie.vote_average,
                    "popularity": movie.popularity,
                    "poster_url": tmdb_service.get_poster_url(movie.poster_path) if movie.poster_path else None
                }
                for movie in result.results
            ],
            total_results=result.total_results,
            total_pages=result.total_pages,
            page=result.page
        )
    except Exception as e:
        logger.error(f"Failed to search movie: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/tv", response_model=SearchResultResponse)
async def search_tv(
    query: str = Query(..., description="搜索关键词"),
    first_air_date_year: Optional[int] = Query(None, description="首播年份"),
    page: int = Query(1, ge=1, description="页码")
):
    """
    搜索电视剧
    
    Args:
        query: 搜索关键词
        first_air_date_year: 首播年份(可选)
        page: 页码
    
    Returns:
        搜索结果
    """
    try:
        tmdb_service = _get_tmdb_service()
        result = await tmdb_service.search_tv(query, first_air_date_year, page)
        
        return SearchResultResponse(
            results=[
                {
                    "id": tv.id,
                    "name": tv.name,
                    "original_name": tv.original_name,
                    "first_air_date": tv.first_air_date,
                    "overview": tv.overview,
                    "poster_path": tv.poster_path,
                    "backdrop_path": tv.backdrop_path,
                    "vote_average": tv.vote_average,
                    "popularity": tv.popularity,
                    "poster_url": tmdb_service.get_poster_url(tv.poster_path) if tv.poster_path else None
                }
                for tv in result.results
            ],
            total_results=result.total_results,
            total_pages=result.total_pages,
            page=result.page
        )
    except Exception as e:
        logger.error(f"Failed to search TV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/movie/{movie_id}", response_model=MovieDetailResponse)
async def get_movie_detail(movie_id: int):
    """
    获取电影详情
    
    Args:
        movie_id: 电影ID
    
    Returns:
        电影详情
    """
    try:
        tmdb_service = _get_tmdb_service()
        detail = await tmdb_service.get_movie_detail(movie_id)
        
        return MovieDetailResponse(
            id=detail.id,
            title=detail.title,
            original_title=detail.original_title,
            release_date=detail.release_date,
            overview=detail.overview,
            poster_path=detail.poster_path,
            backdrop_path=detail.backdrop_path,
            runtime=detail.runtime,
            status=detail.status,
            genres=[
                GenreResponse(id=g.id, name=g.name)
                for g in detail.genres
            ],
            vote_average=detail.vote_average,
            vote_count=detail.vote_count,
            imdb_id=detail.imdb_id,
            poster_url=tmdb_service.get_poster_url(detail.poster_path) if detail.poster_path else None,
            backdrop_url=tmdb_service.get_backdrop_url(detail.backdrop_path) if detail.backdrop_path else None
        )
    except Exception as e:
        logger.error(f"Failed to get movie detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tv/{tv_id}", response_model=TVDetailResponse)
async def get_tv_detail(tv_id: int):
    """
    获取电视剧详情
    
    Args:
        tv_id: 电视剧ID
    
    Returns:
        电视剧详情
    """
    try:
        tmdb_service = _get_tmdb_service()
        detail = await tmdb_service.get_tv_detail(tv_id)
        
        return TVDetailResponse(
            id=detail.id,
            name=detail.name,
            original_name=detail.original_name,
            first_air_date=detail.first_air_date,
            overview=detail.overview,
            poster_path=detail.poster_path,
            backdrop_path=detail.backdrop_path,
            number_of_seasons=detail.number_of_seasons,
            number_of_episodes=detail.number_of_episodes,
            status=detail.status,
            genres=[
                GenreResponse(id=g.id, name=g.name)
                for g in detail.genres
            ],
            vote_average=detail.vote_average,
            vote_count=detail.vote_count,
            poster_url=tmdb_service.get_poster_url(detail.poster_path) if detail.poster_path else None,
            backdrop_url=tmdb_service.get_backdrop_url(detail.backdrop_path) if detail.backdrop_path else None
        )
    except Exception as e:
        logger.error(f"Failed to get TV detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tv/{tv_id}/season/{season_number}/episode/{episode_number}", response_model=EpisodeResponse)
async def get_episode_detail(
    tv_id: int,
    season_number: int,
    episode_number: int
):
    """
    获取剧集详情
    
    Args:
        tv_id: 电视剧ID
        season_number: 季号
        episode_number: 集号
    
    Returns:
        剧集详情
    """
    try:
        tmdb_service = _get_tmdb_service()
        episode = await tmdb_service.get_tv_episode(
            tv_id,
            season_number,
            episode_number
        )
        
        return EpisodeResponse(
            id=episode.id,
            name=episode.name,
            episode_number=episode.episode_number,
            season_number=episode.season_number,
            air_date=episode.air_date,
            overview=episode.overview,
            still_path=episode.still_path,
            vote_average=episode.vote_average,
            still_url=tmdb_service.get_image_url(episode.still_path, "w300") if episode.still_path else None
        )
    except Exception as e:
        logger.error(f"Failed to get episode detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats")
async def get_cache_stats():
    """获取缓存统计信息"""
    try:
        cache_service = get_cache_service()
        return cache_service.get_stats()
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache(_auth: None = Depends(require_api_key)):
    """清空缓存"""
    try:
        cache_service = get_cache_service()
        await cache_service.clear()
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

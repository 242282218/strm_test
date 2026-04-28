"""
Prometheus 指标暴露端点

提供 /metrics 端点供 Prometheus 服务器抓取
"""

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.logging import get_logger
from app.core.prometheus_metrics import REGISTRY


logger = get_logger(__name__)

router = APIRouter(tags=["prometheus"])


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """
    Prometheus 指标端点

    返回 Prometheus 格式的指标数据，供 Prometheus 服务器抓取。

    Returns:
        PlainTextResponse: Prometheus 格式的指标数据
    """
    try:
        # 生成 Prometheus 格式的指标输出
        output = generate_latest(REGISTRY)
        return Response(
            content=output,
            media_type=CONTENT_TYPE_LATEST,
            headers={
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate Prometheus metrics: {e}")
        return Response(content="# Error generating metrics\n", media_type=CONTENT_TYPE_LATEST, status_code=500)


@router.get("/metrics/health")
async def metrics_health():
    """
    指标服务健康检查

    Returns:
        dict: 健康状态
    """
    return {"status": "healthy", "service": "prometheus-metrics", "registry": "quark_strm"}

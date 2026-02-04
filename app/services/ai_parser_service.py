import aiohttp
import asyncio
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass
from app.core.config_manager import ConfigManager
from app.core.logging import get_logger
from app.core.retry import retry_on_transient, TransientError

logger = get_logger(__name__)

@dataclass
class AIParseResult:
    """AI解析结果"""
    title: str
    original_title: Optional[str] = None
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    media_type: str = "movie"  # movie/tv/anime
    confidence: float = 0.0

class AIParserService:
    """AI辅助解析服务 (Zhipu AI)"""
    
    SYSTEM_PROMPT = """你是一个专业的媒体文件名解析JSON生成器。

【重要约束】
1. 只返回纯JSON，不要任何其他文字
2. 严禁使用markdown代码块标记（如 ```json）
3. 如果无法识别，返回 {"title": "[原始文件名]", "media_type": "unknown"}
4. 确保输出可以被 json.loads() 直接解析

【字段说明】
- title: 中文标题（必填，如果原名是英文且翻译不明确，保留原名）
- original_title: 英文或原始语言标题
- year: 年份（4位数字）
- media_type: "movie" 或 "tv" 或 "anime"
- season: 季数（仅电视剧/动漫，数字，如1）
- episode: 集数（仅电视剧/动漫，数字，如15）

【示例】
输入: The.Wandering.Earth.2.2023.BluRay.1080p.mkv
输出: {"title":"流浪地球2","original_title":"The Wandering Earth 2","year":2023,"media_type":"movie","season":null,"episode":null}

输入: 三体.Three-Body.S01E15.2023.WEB-DL.4K.mp4
输出: {"title":"三体","original_title":"Three-Body","year":2023,"media_type":"tv","season":1,"episode":15}

输入: [动漫国字幕组]进击的巨人 第四季 第28集[1080P].mp4
输出: {"title":"进击的巨人","original_title":"Attack on Titan","year":2020,"media_type":"anime","season":4,"episode":28}
"""

    _instance = None
    _semaphore = None

    def __init__(self):
        config = ConfigManager()
        # 优先读取配置中的密钥，不再使用硬编码
        self.api_key = (
            config.get("zhipu.api_key")
            or config.get("api_keys.ai_api_key")
            or config.get("ai.api_key", "")
        )
        self.model = config.get("ai.model", "glm-4.7-flash")
        self.base_url = config.get("ai.base_url", "https://open.bigmodel.cn/api/paas/v4")
        self.timeout = config.get("ai.timeout", 30)
        
        # 并发控制：最多 5 个并发请求
        if AIParserService._semaphore is None:
            AIParserService._semaphore = asyncio.Semaphore(5)
            
    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = AIParserService()
        return cls._instance
        
    @retry_on_transient()
    async def _post_request(self, url: str, headers: dict, payload: dict) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as resp:
                if resp.status in {408, 429} or resp.status >= 500:
                    raise TransientError(f"AI API transient error: {resp.status}")
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"AI API error: {resp.status} - {text}")
                    return {}
                return await resp.json()

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """
        从 AI 响应内容中提取 JSON 对象
        """
        import re
        
        # 1. 预处理：移除所有的 markdown 代码块标记
        cleaned = re.sub(r'```(?:json)?\s*', '', content)
        cleaned = cleaned.replace('```', '').strip()
        
        # 2. 尝试直接解析
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
            
        # 3. 正则提取第一个 { ... } 结构
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            json_str = match.group()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Extracted JSON string is invalid: {e}")
                
        return None

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """
        验证解析结果的有效性
        
        用途: 验证 AI 解析结果是否符合基本要求
        输入:
            - result (Dict[str, Any]): AI 解析的 JSON 结果
        输出:
            - bool: 是否有效
        副作用: 无
        """
        if not result or not isinstance(result, dict):
            return False
            
        # 必须有标题
        if not result.get("title"):
            return False
            
        # 媒体类型必须合法
        if result.get("media_type") not in ["movie", "tv", "anime", "unknown"]:
            result["media_type"] = "unknown"
            
        return True

    async def parse_filename(self, filename: str) -> Optional[AIParseResult]:
        """使用AI解析文件名 (带并发控制)"""
        if not self.api_key:
            logger.warning("AI API key not configured")
            return None
            
        # 使用信号量控制并发
        async with self._semaphore:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"请解析这个文件名: {filename}"}
                ],
                "max_tokens": 512,
                "temperature": 0.1,
                "stream": False
            }
            
            try:
                data = await self._post_request(url, headers, payload)
                if not data or "choices" not in data or not data["choices"]:
                    return None

                content = data["choices"][0]["message"]["content"]
                
                # 使用增强的提取逻辑
                result = self._extract_json(content)
                
                if self._validate_result(result):
                    return AIParseResult(
                        title=result.get("title", ""),
                        original_title=result.get("original_title"),
                        year=result.get("year"),
                        season=result.get("season"),
                        episode=result.get("episode"),
                        media_type=result.get("media_type", "movie"),
                        confidence=0.95
                    )
                else:
                    logger.error(f"AI response validation failed for '{filename}': {content[:200]}")
                    return None
                    
            except Exception as e:
                logger.error(f"AI parse error for {filename}: {e}")
                return None


def get_ai_parser_service() -> AIParserService:
    return AIParserService.get_instance()

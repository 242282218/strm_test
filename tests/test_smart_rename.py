import pytest
import asyncio
import os
import sys

# 添加项目根目录到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_parser_service import AIParserService
from app.utils.media_parser import MediaParser

# 测试数据
MOVIE_TESTS = [
    ("流浪地球2.2023.1080p.BluRay.mp4", {"title": "流浪地球2", "year": 2023}),
    ("The.Wandering.Earth.2.2023.BluRay.1080p.mkv", {"title": "The Wandering Earth 2", "year": 2023}),
    ("满江红 (2023) 1080p.mp4", {"title": "满江红", "year": 2023}),
    ("Oppenheimer.2023.2160p.WEB-DL.x265.mkv", {"title": "Oppenheimer", "year": 2023}),
]

TV_TESTS = [
    ("三体.Three-Body.S01E15.2023.WEB-DL.mp4", {"title": "三体", "season": 1, "episode": 15}),
    ("庆余年.S02E01.2024.mp4", {"title": "庆余年", "season": 2, "episode": 1}),
    ("狂飙.第01集.mp4", {"title": "狂飙", "episode": 1}),
    ("漫长的季节.EP01.mp4", {"title": "漫长的季节", "episode": 1}),
    ("三体.S01E01E02.mp4", {"title": "三体", "season": 1, "episode": 1}),
]

ANIME_TESTS = [
    ("[动漫国字幕组]进击的巨人 第四季 第28集[1080P].mp4", {"title": "进击的巨人", "episode": 28}),
    ("咒术回战.第2季.01话.mp4", {"title": "咒术回战", "episode": 1}),
    ("葬送的芙莉莲.Frieren.S01E01.mp4", {"title": "葬送的芙莉莲", "season": 1, "episode": 1}),
    ("咒术回战.EP01.EP02.mp4", {"title": "咒术回战", "episode": 1}),
]

EDGE_TESTS = [
    ("未知文件名.mp4", {"title": "未知文件名"}),
    ("123456.mp4", {"title": "123456"}),
    ("Movie.Name.2023.1080p.BluRay.REMUX.DTS-HD.mkv", {"title": "Movie Name", "year": 2023}),
    ("[字幕组] 标题 [1080p] [x265] [DTS].mp4", {"title": "标题"}),
]

@pytest.mark.parametrize("filename,expected", MOVIE_TESTS + TV_TESTS + ANIME_TESTS)
def test_regex_parse(filename, expected):
    """测试正则解析器"""
    result = MediaParser.parse(filename)
    assert result["title"] != filename
    assert result["title"] is not None
    
    # 验证提取的标题 (模糊匹配，忽略大小写和空格)
    assert expected["title"].lower() in result["title"].lower() or result["title"].lower() in expected["title"].lower()
    
    if "year" in expected:
        assert result["year"] == expected["year"]
    if "season" in expected:
        assert result["season"] == expected["season"]
    if "episode" in expected:
        assert result["episode"] == expected["episode"]

@pytest.mark.parametrize("filename,expected", EDGE_TESTS)
def test_edge_cases(filename, expected):
    """测试边界情况"""
    result = MediaParser.parse(filename)
    assert result["title"] is not None
    
    # 验证提取的标题 (模糊匹配)
    assert expected["title"].lower() in result["title"].lower() or result["title"].lower() in expected["title"].lower()
    
    if "year" in expected:
        assert result["year"] == expected["year"]

@pytest.mark.asyncio
async def test_ai_parse_robustness():
    """测试 AI 解析器的鲁棒性 (解析不同格式的 JSON)"""
    service = AIParserService.get_instance()
    
    # 模拟各种可能的响应内容
    test_contents = [
        '{"title": "测试电影", "year": 2024, "media_type": "movie"}',
        '```json\n{"title": "测试电影", "year": 2024, "media_type": "movie"}\n```',
        '这里是解析结果：{"title": "测试电影", "year": 2024, "media_type": "movie"}，请查收。',
        '{\n  "title": "测试电影",\n  "year": 2024,\n  "media_type": "movie"\n}'
    ]
    
    for content in test_contents:
        result = service._extract_json(content)
        assert result is not None
        assert result["title"] == "测试电影"
        assert result["year"] == 2024

def test_title_post_processing():
    """测试标题后处理逻辑"""
    test_cases = [
        ("Movie.Name.2023.1080p.BluRay", "Movie Name"),
        ("三体.Three-Body.S01E15", "三体 Three-Body"),
        ("[字幕组] 进击的巨人 [1080p]", "进击的巨人"),
        ("Movie.Name.2023.1080p.BluRay.REMUX.DTS-HD", "Movie Name"),
        ("[字幕组] 标题 [1080p] [x265] [DTS]", "标题"),
    ]
    
    for raw, expected in test_cases:
        processed = MediaParser._post_process_title(raw)
        assert processed == expected, f"Expected '{expected}', got '{processed}' for '{raw}'"

def test_performance():
    """测试解析性能"""
    import time
    
    test_files = MOVIE_TESTS + TV_TESTS + ANIME_TESTS + EDGE_TESTS
    filenames = [f[0] for f in test_files]
    
    # 测试正则解析性能
    start = time.time()
    for filename in filenames * 100:  # 重复100次
        MediaParser.parse(filename)
    elapsed = time.time() - start
    
    # 平均每次解析应该小于 10ms
    avg_time = elapsed / (len(filenames) * 100)
    assert avg_time < 0.01, f"正则解析平均时间 {avg_time*1000:.2f}ms 超过 10ms"
    
    # 测试缓存效果 - 清除缓存后重新运行
    MediaParser._parse_internal.cache_clear()
    start = time.time()
    for filename in filenames * 100:
        MediaParser.parse(filename)
    elapsed_no_cache = time.time() - start
    
    # 再次运行，应该使用缓存
    cache_before = MediaParser._parse_internal.cache_info()
    start = time.time()
    for filename in filenames * 100:
        MediaParser.parse(filename)
    elapsed_cached = time.time() - start
    cache_after = MediaParser._parse_internal.cache_info()
    
    # 缓存命中数应该增长；时间在不同环境中波动较大，仅做上限校验
    assert cache_after.hits > cache_before.hits, "缓存未命中"
    assert elapsed_cached < 0.5, f"缓存性能异常: 有缓存 {elapsed_cached*1000:.2f}ms"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

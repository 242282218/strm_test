#!/usr/bin/env python3
"""测试统一 AI 配置"""

import asyncio
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.unified_ai_service import get_unified_ai_service


async def main():
    service = get_unified_ai_service()

    print("=== 测试 AI 配置 ===\n")
    print(f"可用 providers: {len(service._get_providers())}")

    for p in service._get_providers():
        status = "✓" if p.api_key else "✗"
        print(f"{status} {p.name} (priority: {p.priority})")

    print("\n=== 测试文件名解析 ===\n")
    test_files = [
        "The.Matrix.1999.1080p.BluRay.x264.mkv",
        "Friends.S01E01.1080p.WEB-DL.mkv",
    ]

    for filename in test_files:
        print(f"解析: {filename}")
        result = await service.parse_filename(filename)
        print(f"  标题: {result.title}")
        print(f"  类型: {result.media_type}")
        if result.year:
            print(f"  年份: {result.year}")
        if result.season:
            print(f"  季: S{result.season:02d}")
        if result.episode:
            print(f"  集: E{result.episode:02d}")
        print()


if __name__ == "__main__":
    asyncio.run(main())

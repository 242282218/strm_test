"""
测试 STRM 生成，查看 base_url 处理
"""
import asyncio
import sys
sys.path.insert(0, 'c:\\Users\\24228\\Desktop\\smart_media\\quark_strm')

from app.services.strm_generator import STRMGenerator
from app.core.config_manager import ConfigManager

async def test_strm_generation():
    config = ConfigManager()
    cookie = config.get("quark.cookie", "")

    if not cookie:
        print("错误: 未配置 Cookie")
        return

    # 测试不同的 base_url
    test_urls = [
        "http://192.168.100.101:8000",
        "http://192.168.100.101:8000/",
    ]

    file_id = "2c84d515a8c545e3b1aece4a5b1c7e01"
    remote_path = "test_video.mkv"

    print("=" * 80)
    print("测试 STRM 生成 - base_url 处理")
    print("=" * 80)

    for base_url in test_urls:
        print(f"\n输入 base_url: {base_url}")

        generator = STRMGenerator(
            cookie=cookie,
            output_dir="./strm_test",
            base_url=base_url,
            strm_url_mode="redirect"
        )

        print(f"处理后 base_url: {generator.base_url}")

        # 生成视频 URL
        video_url = await generator._generate_video_url(file_id, remote_path)
        print(f"生成的 URL: {video_url}")

        await generator.close()

    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(test_strm_generation())

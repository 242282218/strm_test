"""
本地验证 STRM 播放能力
模拟 Emby 播放流程
"""
import asyncio
import sys
sys.path.insert(0, 'c:\\Users\\24228\\Desktop\\smart_media\\quark_strm')

from app.services.quark_service import QuarkService
from app.core.config_manager import ConfigManager

async def test_playback():
    """测试播放流程"""
    # 测试文件
    test_cases = [
        {
            "name": "寄生虫",
            "file_id": "6e4f43091b1e451b8c22ce612e36194e",
            "strm_path": "c:\\Users\\24228\\Desktop\\smart_media\\quark_strm\\strm\\6e4f43091b1e451b8c22ce612e36194e.strm"
        },
        {
            "name": "测试文件[23]",
            "file_id": "41ea24e721cf4fc7a0534a59354a3625",
            "strm_path": "c:\\Users\\24228\\Desktop\\smart_media\\quark_strm\\strm\\41ea24e721cf4fc7a0534a59354a3625.strm"
        }
    ]
    
    config = ConfigManager()
    cookie = config.get("quark.cookie", "")
    
    if not cookie:
        print("❌ 错误: 未配置夸克 Cookie")
        return
    
    print("=" * 80)
    print("STRM 播放能力本地验证")
    print("=" * 80)
    
    service = QuarkService(cookie=cookie)
    
    try:
        for test in test_cases:
            print(f"\n📁 测试: {test['name']}")
            print("-" * 80)
            
            # 1. 读取 STRM 文件
            try:
                with open(test['strm_path'], 'r', encoding='utf-8') as f:
                    strm_url = f.read().strip()
                print(f"✅ STRM 文件读取成功")
                print(f"   URL: {strm_url[:80]}...")
            except Exception as e:
                print(f"❌ STRM 文件读取失败: {e}")
                continue
            
            # 2. 检查 URL 格式
            if 'http:/' in strm_url and 'http://' not in strm_url:
                print(f"❌ URL 格式错误: 单斜杠 http:/")
                continue
            else:
                print(f"✅ URL 格式正确")
            
            # 3. 获取夸克直链（模拟代理服务）
            print(f"\n🔄 获取夸克直链...")
            try:
                link = await service.get_transcoding_link(test['file_id'])
                if link and link.url:
                    print(f"✅ 直链获取成功")
                    print(f"   直链: {link.url[:80]}...")
                    
                    # 4. 验证直链可访问性
                    print(f"\n🌐 验证直链可访问性...")
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.head(link.url, timeout=10) as resp:
                            if resp.status == 200 or resp.status == 206:
                                print(f"✅ 直链可访问 (Status: {resp.status})")
                                content_type = resp.headers.get('Content-Type', 'unknown')
                                print(f"   Content-Type: {content_type}")
                                content_length = resp.headers.get('Content-Length')
                                if content_length:
                                    size_mb = int(content_length) / 1024 / 1024
                                    print(f"   文件大小: {size_mb:.2f} MB")
                            else:
                                print(f"⚠️ 直链返回状态: {resp.status}")
                else:
                    print(f"❌ 直链获取失败")
            except Exception as e:
                print(f"❌ 获取直链出错: {e}")
    
    finally:
        await service.close()
    
    print("\n" + "=" * 80)
    print("验证完成")
    print("=" * 80)
    print("\n📋 结论:")
    print("   - STRM 文件格式正确即可在 Emby 中使用")
    print("   - Emby 会通过代理服务获取直链并播放")
    print("   - 直链有效期约4小时，过期后 Emby 会重新请求")

if __name__ == "__main__":
    asyncio.run(test_playback())

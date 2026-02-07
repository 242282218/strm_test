"""
测试获取文件信息
"""
import asyncio
import sys
sys.path.insert(0, 'c:\\Users\\24228\\Desktop\\smart_media\\quark_strm')

from app.services.quark_service import QuarkService
from app.core.config_manager import ConfigManager

async def test_file_info():
    # 测试文件ID
    file_id = "2c84d515a8c545e3b1aece4a5b1c7e01"
    
    config = ConfigManager()
    cookie = config.get("quark.cookie", "")
    
    if not cookie:
        print("错误: 未配置 Cookie")
        return
    
    print("=" * 80)
    print("测试获取文件信息")
    print("=" * 80)
    print(f"文件ID: {file_id}")
    print()
    
    service = QuarkService(cookie=cookie)
    
    try:
        # 通过ID获取文件信息
        print("通过 get_file_info 获取...")
        info = await service.client.get_file_info(file_id)
        print(f"返回结果: {info}")
        
        if info:
            print(f"\n文件信息:")
            print(f"  fid: {info.get('fid')}")
            print(f"  file_name: {info.get('file_name')}")
            print(f"  file_type: {info.get('file_type')} (0=文件夹, 1=文件)")
            print(f"  is_dir: {info.get('file_type') == 0}")
            print(f"  pdir_fid: {info.get('pdir_fid')}")
        else:
            print("✗ 未获取到文件信息")
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.close()

if __name__ == "__main__":
    asyncio.run(test_file_info())

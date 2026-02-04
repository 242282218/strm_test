import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(os.path.abspath("."))

from app.services.strm_generator import STRMGenerator
from app.core.config_manager import get_config

async def test_generation():
    config = get_config()
    cookie = config.get_quark_cookie()
    
    if not cookie:
        print("❌ 错误: 未在 config.yaml 中配置夸克 Cookie")
        return

    # 初始化生成器
    # 目标：古见同学有交流障碍症 第一季
    target_fid = "b2b648097fcb4eec897fd7eb3b063591"
    output_dir = "./strm_test"
    
    print(f"🚀 开始测试 STRM 生成...")
    print(f"📁 目标 FID: {target_fid}")
    print(f"📍 输出目录: {output_dir}")
    
    generator = STRMGenerator(
        cookie=cookie,
        output_dir=output_dir,
        base_url="http://localhost:8000",
        strm_url_mode="redirect"
    )

    try:
        # 生成文件（限制5个进行测试）
        stats = await generator.generate_strm_files(
            root_id=target_fid,
            only_video=True,
            max_files=5
        )
        
        print("\n📊 生成统计:")
        print(f"  - 总计发现: {stats['total_files']}")
        print(f"  - 成功生成: {stats['generated_files']}")
        print(f"  - 跳过文件: {stats['skipped_files']}")
        print(f"  - 失败情况: {stats['failed_files']}")
        
        if stats['errors']:
            print("\n❌ 错误详情:")
            for err in stats['errors']:
                print(f"  - {err}")

        # 验证生成的文件
        print("\n🔍 检查生成的文件内容:")
        strm_files = list(Path(output_dir).rglob("*.strm"))
        if not strm_files:
            print("  - 未找到生成的 .strm 文件")
        else:
            for strm in strm_files[:3]:
                with open(strm, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                print(f"  - 文件: {strm.name}")
                print(f"    内容: {content}")
                
                if "?path=" in content:
                    print("    ✅ 包含 path 参数 (WebDAV 兜底支持已就绪)")
                else:
                    print("    ❌ 缺少 path 参数")
                
    finally:
        await generator.close()

if __name__ == "__main__":
    asyncio.run(test_generation())

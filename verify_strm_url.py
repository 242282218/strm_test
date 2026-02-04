"""验证 STRM 文件中的 URL 是否能正确 302 重定向"""
import requests

# 从 STRM 文件读取 URL
strm_file = r"strm_test\SPs\[Menu01].mkv.strm"
with open(strm_file, 'r', encoding='utf-8') as f:
    url = f.read().strip()

print(f"📄 STRM 文件: {strm_file}")
print(f"🔗 URL: {url}\n")

try:
    # 测试 302 重定向
    response = requests.get(url, allow_redirects=False, timeout=10)
    
    print(f"✅ 状态码: {response.status_code}")
    
    if response.status_code == 302:
        location = response.headers.get("Location", "")
        print(f"✅ 302 重定向成功!")
        print(f"🎯 目标地址: {location[:150]}...")
        print(f"\n✅ 完整流程验证通过！")
        print("   夸克网盘 → STRM 文件 → 302 代理 → 夸克直链")
    else:
        print(f"❌ 预期 302，实际 {response.status_code}")
        
except Exception as e:
    print(f"❌ 错误: {e}")

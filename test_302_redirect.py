"""测试 302 重定向功能"""
import requests

file_id = "3bc172a4f0ed469abc0b88bba441aee9"
url = f"http://localhost:8000/api/proxy/redirect/{file_id}"

print(f"Testing 302 redirect for file_id: {file_id}")
print(f"URL: {url}\n")

try:
    # 不自动跟随重定向
    response = requests.get(url, allow_redirects=False, timeout=30)
    
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    
    if response.status_code == 302:
        location = response.headers.get("Location", "")
        print(f"\n✅ 302 Redirect successful!")
        print(f"Location: {location[:150]}...")
    else:
        print(f"\n❌ Expected 302, got {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")

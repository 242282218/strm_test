"""
测试 URL 格式问题
"""

# 测试 base_url 处理
def test_base_url_processing():
    test_cases = [
        "http://192.168.100.101:8000",
        "http://192.168.100.101:8000/",
        "http://localhost:8000",
        "http://localhost:8000/",
    ]

    print("测试 base_url 处理:")
    print("=" * 80)

    for url in test_cases:
        # 原来的处理方式（有问题）
        old_result = url.rstrip("/")

        # 新的处理方式
        new_result = url.rstrip("/") if not url.endswith(":/") else url

        print(f"\n原始 URL: {url}")
        print(f"旧处理方式: {old_result}")
        print(f"新处理方式: {new_result}")

        # 测试拼接后的 URL
        file_id = "2c84d515a8c545e3b1aece4a5b1c7e01"
        old_full = f"{old_result}/api/proxy/redirect/{file_id}"
        new_full = f"{new_result}/api/proxy/redirect/{file_id}"
        print(f"旧拼接 URL: {old_full}")
        print(f"新拼接 URL: {new_full}")


if __name__ == "__main__":
    test_base_url_processing()

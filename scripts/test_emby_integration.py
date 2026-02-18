
import asyncio
import os
import sys
import logging

# Add project root to path
sys.path.append(os.getcwd())

from app.main import init_app
from app.services.emby_service import get_emby_service
from app.services.config_service import get_config_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestEmby")

async def test_emby():
    print(">>> 1. Initializing Emby Service...")
    init_app()
    
    # Check Config
    config_service = get_config_service()
    config = config_service.get_config()
    
    print(f"Emby Enabled: {config.emby.enabled}")
    if config.emby.enabled:
        print(f"Emby URL: {config.emby.url}")
        print(f"Emby API Key: {config.emby.api_key[:5]}...")
    
    service = get_emby_service()
    
    # 2. Test Connection
    print("\n>>> 2. Testing Connection...")
    result = await service.test_connection()
    if result["success"]:
        server_info = result["server_info"]
        print(f"✅ Connection successful!")
        print(f"   Server Name: {server_info.get('server_name')}")
        print(f"   Version: {server_info.get('version')}")
        print(f"   OS: {server_info.get('operating_system')}")
    else:
        print(f"❌ Connection failed: {result['message']}")
        return

    # 3. Get Libraries
    print("\n>>> 3. Fetching Libraries...")
    try:
        # Debug: Print raw response
        settings = service._get_effective_settings()
        raw_data = await service._request_json(
            "GET",
            "/Library/MediaFolders",
            url=settings["url"],
            api_key=settings["api_key"],
            timeout=10
        )
        print(f"   [DEBUG] Raw /Library/MediaFolders response: {raw_data}")
        
        libraries = await service.get_libraries()
        print(f"✅ Found {len(libraries)} libraries:")
        for lib in libraries:
            print(f"   - [{lib['id']}] {lib['name']} ({lib.get('collection_type', 'Unknown')})")
    except Exception as e:
        print(f"❌ Failed to fetch libraries: {e}")
        
    # 4. Dry Run Refresh (Optional - try one library if present)
    # We won't trigger full refresh to avoid load, just check if method works fundamentally.
    # Actually, we can just verify the service is configured correctly.
    
    print("\n>>> 4. Emby Integration Status: READY")

if __name__ == "__main__":
    asyncio.run(test_emby())

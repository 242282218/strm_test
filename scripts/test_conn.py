
import asyncio
import os
import sys
import logging

# Add project root to path
sys.path.append(os.getcwd())

from app.main import init_app
from app.services.config_service import get_config_service
from app.services.quark_service import QuarkService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestConn")

async def test_conn():
    print(">>> Initializing App...")
    init_app()
    
    config_service = get_config_service()
    config = config_service.get_config()
    quark_cookie = config.quark.cookie
    
    if not quark_cookie:
        print("❌ Error: Quark Cookie not configured")
        return

    print(f"Cookie found: {quark_cookie[:20]}...")
    
    qs = QuarkService(cookie=quark_cookie)
    try:
        print("Listing root (fid=0)...")
        files = await qs.get_files(parent="0", page_size=10)
        print(f"✅ Success. Found {len(files)} items in root.")
        for f in files:
            print(f" - {f.file_name} [{'File' if f.file else 'Dir'}] ({f.fid})")
            
        # Try to find Test_Flow_Auto
        found = False
        for f in files:
            if f.file_name == "Test_Flow_Auto":
                print(f"Found target dir: {f.fid}")
                found = True
        
        if not found:
            print("Target dir 'Test_Flow_Auto' not found in root.")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    finally:
        await qs.close()

if __name__ == "__main__":
    asyncio.run(test_conn())

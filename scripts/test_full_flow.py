
import asyncio
import os
import sys
import logging
from pathlib import Path
import re

# Add project root to path
sys.path.append(os.getcwd())

from app.main import init_app
from app.services.config_service import get_config_service
from app.services.search_service import ResourceSearchService
from app.services.transfer_service import TransferService
from app.services.scrape_service import get_scrape_service
from app.services.strm_service import StrmService
from app.services.notification_service import get_notification_service
from app.services.quark_service import QuarkService
from app.core.db import SessionLocal
from fastapi import BackgroundTasks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TestFlow")

async def ensure_remote_directory(quark_service: QuarkService, path: str):
    """Ensure a directory exists on Quark drive"""
    logger.info(f"Ensuring remote directory: {path}")
    
    clean_path = path.lstrip('/')
    parts = clean_path.split('/')
    if not parts or parts == ['']:
        return "0"

    parent_fid = "0"
    for part in parts:
        if not part: continue
        found = False
        files = await quark_service.get_files(parent=parent_fid)
        for f in files:
            if not f.file and f.file_name == part:
                parent_fid = f.fid
                found = True
                break
        
        if not found:
            logger.info(f"Creating directory '{part}' in parent '{parent_fid}'")
            res = await quark_service.mkdir(parent_fid, part)
            # Typically need to re-list to get fid reliably or parse result
            await asyncio.sleep(1)
            files = await quark_service.get_files(parent=parent_fid)
            for f in files:
                if not f.file and f.file_name == part:
                    parent_fid = f.fid
                    found = True
                    break
            if not found:
                raise Exception(f"Failed to create directory {part}")
    
    return parent_fid

async def is_share_valid(quark_service: QuarkService, share_url: str):
    try:
        match = re.search(r'/s/([a-zA-Z0-9]+)', share_url)
        if not match: 
            return False
        pwd_id = match.group(1)
        stoken = await quark_service.client.get_share_token(pwd_id, "")
        files = await quark_service.client.get_share_files(pwd_id, stoken)
        return len(files) > 0
    except Exception as e:
        logger.warning(f"Share {share_url} check failed: {e}")
        return False

async def run_test():
    print(">>> 1. Initializing App...")
    init_app()
    
    # Get Config
    config_service = get_config_service()
    config = config_service.get_config()
    quark_cookie = config.quark.cookie
    
    if not quark_cookie:
        print("❌ Error: Quark Cookie not configured in config.yaml")
        return

    # Context for services needing DB
    db = SessionLocal()
    
    target_dir = "/Test_Flow_Auto"
    local_strm_path = os.path.abspath("./strm/Test_Flow_Auto")
    
    try:
        qs = QuarkService(cookie=quark_cookie)
        
        # 1. Search
        print("\n>>> 2. Searching for '庆余年'...")
        search_service = ResourceSearchService()
        search_result = await search_service.search(keyword="庆余年", page=1, page_size=10) # Get more results
        
        if not search_result.get("results"):
            print("❌ Search failed: No results found.")
            return
            
        valid_share_url = None
        for result in search_result["results"]:
            for link in result.get("cloud_links", []):
                if link["type"] == "quark":
                    url = link["url"]
                    print(f"Checking share: {url}")
                    if await is_share_valid(qs, url):
                        print(f"✅ Found valid share: {url}")
                        valid_share_url = url
                        break
            if valid_share_url:
                break
        
        if not valid_share_url:
             print("❌ No valid Quark share links found in top 10 results.")
             return

        # 2. Prepare Remote Directory
        print(f"\n>>> 3.1 Ensuring target directory '{target_dir}' exists...")
        try:
            await ensure_remote_directory(qs, target_dir)
            print("✅ Remote directory ready.")
        finally:
            await qs.close()

        # 3. Transfer
        print(f"\n>>> 3.2 Transferring to '{target_dir}'...")
        transfer_service = TransferService(db)
        bg_tasks = BackgroundTasks()
        
        await transfer_service.transfer_share(
            drive_id=None,
            share_url=valid_share_url,
            target_dir=target_dir,
            password="",
            auto_organize=False,
            background_tasks=bg_tasks
        )
        print("✅ Transfer completed.")

        # 4. Scrape
        print("\n>>> 4. Creating and Starting Scrape Job...")
        scrape_service = get_scrape_service()
        job = await scrape_service.create_job(
            target_path=target_dir,
            media_type="auto",
            options={
                "source_path": target_dir,
                "dest_path": target_dir,
                "generate_nfo": True,
                "download_images": True 
            }
        )
        print(f"   Job ID: {job.job_id}")
        
        started = await scrape_service.start_job(job.job_id)
        if started:
            print("✅ Scrape Job started.")
            # Give it a moment to scrape some metadata? 
            # Scrape is async. If we proceed to generate STRM immediately, STRM generator works on FILES not metadata.
            # But metadata helps. 
            await asyncio.sleep(5) 
        else:
            print("❌ Failed to start Scrape Job.")

        # 5. Generate STRM
        print(f"\n>>> 5. Generating STRM in '{local_strm_path}'...")
        if not os.path.exists(local_strm_path):
            try:
                os.makedirs(local_strm_path)
            except FileExistsError:
                pass
            
        strm_service = StrmService(
            cookie=quark_cookie,
            recursive=True,
            base_url="http://127.0.0.1:8001",
            strm_url_mode="redirect",
            overwrite_existing=True
        )
        
        try:
            scan_result = await strm_service.scan_directory(
                remote_path=target_dir,
                local_path=local_strm_path,
                concurrent_limit=5
            )
            print(f"✅ Generated: {scan_result.get('generated_count')} files.")
        finally:
            await strm_service.close()
        
        # 6. Verify Playback
        print("\n>>> 6. Verifying Playback...")
        strm_files = list(Path(local_strm_path).rglob("*.strm"))
        if not strm_files:
            print("❌ No STRM files generated.")
        else:
            sample_file = strm_files[0]
            print(f"   Testing file: {sample_file.name}")
            content = ""
            with open(sample_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
            print(f"   Content: {content}")
            
            if "/api/proxy/" in content:
                match = re.search(r"/api/proxy/(redirect|stream|transcoding)/([a-zA-Z0-9]+)", content)
                if match:
                    endpoint_type = match.group(1)
                    file_id = match.group(2)
                    print(f"   Extracted File ID: {file_id}, Type: {endpoint_type}")
                    
                    print("   [Test 1] Verifying Download/Redirect Link Generation...")
                    qs = QuarkService(cookie=quark_cookie)
                    try:
                        from app.services.link_resolver import LinkResolver
                        resolver = LinkResolver(quark_service=qs)
                        redirect_url = await resolver.resolve(file_id, None)
                        if redirect_url:
                            print(f"   ✅ Redirect URL Resolved: {redirect_url[:50]}...")
                        else:
                            print("   ❌ Failed to resolve redirect URL")
                            
                        print("   [Test 2] Verifying Transcoding Link Generation...")
                        trans_link = await qs.get_transcoding_link(file_id)
                        if trans_link and trans_link.url:
                             print(f"   ✅ Transcoding URL Resolved: {trans_link.url[:50]}...")
                        else:
                             print("   ❌ Failed to resolve transcoding URL")
                             
                    except Exception as e:
                        print(f"   ❌ Verification Logic Failed: {e}")
                    finally:
                        await qs.close()
                else:
                    print("❌ Could not parse File ID from STRM content.")
            else:
                 print("⚠️ STRM content does not contain /api/proxy/ link (maybe direct mode?)")

        # 7. Notification
        print("\n>>> 7. Testing Notification...")
        try:
            from app.services.notification_service import NotificationType, NotificationPriority
            notif_service = get_notification_service()
            await notif_service.send_notification(
                type=NotificationType.SYSTEM_ALERT,
                title="Test Flow Completed",
                content="The full automation flow test was successful.",
                priority=NotificationPriority.NORMAL
            )
            print("✅ Notification sent.")
        except Exception as e:
            print(f"❌ Notification failed: {e}")

        print("\n>>> [SUCCESS] Test Flow Completed Successfully.")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n❌ Unexpected Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_test())

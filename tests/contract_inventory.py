PHASE3_DOC_SNAPSHOT_DATE = "2026-04-21"

API_CONFIG_MANAGER_GETTER_INVENTORY = ("app/api/quark.py",)

SERVICE_CORE_CONFIG_MANAGER_COMPAT_INVENTORY = (
    "app/services/integrations/emby.py",
    "app/services/media/organize.py",
    "app/services/media/rename.py",
    "app/services/media/smart_rename.py",
    "app/services/media/strm_generator.py",
    "app/services/unified_ai_service.py",
)

PHASE3_CONFIG_MANAGER_INVENTORY_HINTS = (
    *API_CONFIG_MANAGER_GETTER_INVENTORY,
    *SERVICE_CORE_CONFIG_MANAGER_COMPAT_INVENTORY,
)

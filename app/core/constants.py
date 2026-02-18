"""
Constants
"""

REQUEST_ID_HEADER = "X-Request-ID"

# Input limits
MAX_PATH_LENGTH = 512
MAX_URL_LENGTH = 2048
MAX_ID_LENGTH = 128

MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 50
DEFAULT_BATCH_SIZE = 10

MIN_CONCURRENT_LIMIT = 1
MAX_CONCURRENT_LIMIT = 50

MIN_TIMEOUT_SECONDS = 1
MAX_TIMEOUT_SECONDS = 120

MAX_FILES_LIMIT = 1000

# Retry policy
RETRY_MAX_ATTEMPTS = 3
RETRY_MIN_SECONDS = 0.5
RETRY_MAX_SECONDS = 8
RETRY_MULTIPLIER = 0.5

# Sensitive field names (for masking)
SENSITIVE_FIELD_NAMES = {
    "password",
    "passwd",
    "token",
    "api_key",
    "apikey",
    "secret",
    "cookie",
    "authorization",
    "auth",
    "key",
}

SCRAPE_MODES = {
    "only_scrape": {
        "name": "仅刮削",
        "description": "只从TMDB获取元数据信息，不进行文件重命名和整理",
    },
    "scrape_and_rename": {
        "name": "刮削并重命名",
        "description": "从TMDB获取元数据，并按照Emby/Plex标准重命名文件",
    },
    "only_rename": {
        "name": "仅重命名",
        "description": "不刮削元数据，仅根据文件名智能识别并重命名",
    },
}

RENAME_MODES = {
    "move": {
        "name": "移动",
        "description": "将文件移动到目标目录，源目录文件会消失",
    },
    "copy": {
        "name": "复制",
        "description": "复制文件到目标目录，保留源目录原文件",
    },
    "hardlink": {
        "name": "硬链接",
        "description": "创建硬链接，不占用额外空间，要求同一磁盘分区",
    },
    "softlink": {
        "name": "软链接",
        "description": "创建符号链接，可跨磁盘分区，但依赖源文件路径",
    },
}

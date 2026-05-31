import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration from environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "")
ADMINS = []
if ADMIN_IDS_STR:
    ADMINS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip().isdigit()]

# Worker IDs from environment (optional)
WORKERS_STR = os.environ.get("WORKER_IDS", "")
WORKERS = []
if WORKERS_STR:
    WORKERS = [int(x.strip()) for x in WORKERS_STR.split(",") if x.strip().isdigit()]

# AI configuration
AI_PROVIDER = os.environ.get("AI_PROVIDER", "groq").lower()
AI_API_KEY = os.environ.get("AI_API_KEY", "")

# Debug output on startup
logger.info("=" * 50)
logger.info("CONFIG LOADED:")
logger.info(f"TOKEN set: {bool(TOKEN)} (length: {len(TOKEN)})")
logger.info(f"ADMINS: {ADMINS}")
logger.info(f"WORKERS: {WORKERS}")
logger.info(f"AI_PROVIDER: {AI_PROVIDER}")
logger.info(f"AI_API_KEY set: {bool(AI_API_KEY)}")
logger.info("=" * 50)

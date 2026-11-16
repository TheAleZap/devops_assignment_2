import os

PORT = int(os.environ.get("PORT", "8001"))
DATA_DIR = os.environ.get("DATA_DIR", "data")
DB_PATH = os.path.join(DATA_DIR, "scheduling.db")

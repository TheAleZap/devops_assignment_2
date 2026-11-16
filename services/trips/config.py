import os

PORT = int(os.environ.get("PORT", "8002"))
DATA_DIR = os.environ.get("DATA_DIR", "data")
DB_PATH = os.path.join(DATA_DIR, "trips.db")
SCHEDULING_URL = os.environ.get("SCHEDULING_URL", "http://localhost:8001")
SCHEDULING_TIMEOUT_S = float(os.environ.get("SCHEDULING_TIMEOUT_S", "2"))

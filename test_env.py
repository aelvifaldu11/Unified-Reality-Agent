import os
from dotenv import load_dotenv

load_dotenv()

print("SERVICE:", os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))

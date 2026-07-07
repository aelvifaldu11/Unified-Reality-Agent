import os
import sys
import json

# Ensures both the IDE and the runtime can resolve project-root packages
# (utils, agent, config, security …) regardless of the working directory.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.logger import log       # noqa: E402
from dotenv import load_dotenv     # noqa: E402

class SecretsLoader:
    """
    Loads API keys and config from .env file.
    Falls back to DEMO mode when keys are missing.
    """

    def __init__(self, mock_data_path="mock_data/"):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.mock_data_path = os.path.join(self.project_root, mock_data_path)
        self.mode = "demo"
        self.secrets = {}

        self.load_env()
        self.load_secrets()

    def load_env(self, filepath=".env"):
        env_path = os.path.join(self.project_root, filepath)

        if not os.path.exists(env_path):
            log(f"[SecretsLoader] .env file missing at {env_path} -> staying in DEMO mode")
            return

        load_dotenv(env_path)
        log("[SecretsLoader] Loaded .env successfully")

    def load_secrets(self):
        """Basic loader that checks environment variables."""
        required_keys = ["OPENAI_API_KEY"]
        found_any = False

        for key in required_keys:
            val = os.getenv(key)
            if val:
                found_any = True
                self.secrets[key] = val

        if found_any:
            self.mode = "real"
            log("[SecretsLoader] Environment keys found -> REAL mode")
        else:
            self.mode = "demo"
            log("[SecretsLoader] No environment keys found -> DEMO mode")
    
    def get_secret(self, key: str):
        return self.secrets.get(key)

    def load_mock_data(self, filename):
        path = os.path.join(self.mock_data_path, filename)
        
        if not os.path.exists(path):
            log(f"[SecretsLoader] Mock file not found: {path}")
            return {}

        with open(path, "r") as f:
            return json.load(f)
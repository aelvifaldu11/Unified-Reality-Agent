import os
import json
from typing import Any,Dict

SESSION_PATH = os.path.join("data", "session_store.json")

class SessionManager:
    def __init__(self, path: str=SESSION_PATH):
        self.path = path
        self._state: Dict[str, Any] = {}
        self._ensure_file()
        self.load()
        
    def _ensure_file(self):
        d = os.path.dirname(self.path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                json.dump({}, f)

    def load(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r") as f:
                self._state = json.load(f) or {}
        except Exception:
            self._state = {}
        return self._state

    def save(self) -> None:
        try:
            with open(self.path, "w") as f:
                json.dump(self._state, f, indent=2)
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self._state.get(key, default)

    def set(self, key: str, value) -> None:
        self._state[key] = value
        self.save()

    def add_to_history(self, user_input: str, agent_response: str) -> None:
        history = self.get("history", [])
        if not isinstance(history, list):
            history = []
        history.append({
            "user": user_input,
            "agent": agent_response
        })
        self.set("history", history)

    def clear(self) -> None:
        self._state = {}
        self.save()    


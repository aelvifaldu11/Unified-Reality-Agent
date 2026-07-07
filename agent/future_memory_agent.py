import os
import json
from datetime import datetime
from typing import Dict, Any

from utils.logger import log

class FutureMemoryAgent:
    """
    FutureMemoryAgent:
    Manages long-term event history, user preferences, and generates cognitive alerts (sleep / focus tips).
    """
    def __init__(self, secrets_loader):
        self.secrets = secrets_loader
        self.project_root = getattr(secrets_loader, "project_root", os.getcwd())
        self.memory_path = os.path.join(self.project_root, "data", "memory.json")
        self._ensure_file()

    def _ensure_file(self):
        d = os.path.dirname(self.memory_path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        if not os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "w") as f:
                    json.dump({"preferences": {}, "event_history": []}, f, indent=2)
            except Exception as e:
                log(f"FutureMemoryAgent: failed to create memory.json: {e}")

    def load_memory(self) -> Dict[str, Any]:
        try:
            with open(self.memory_path, "r") as f:
                return json.load(f)
        except Exception:
            return {"preferences": {}, "event_history": []}

    def save_memory(self, data: Dict[str, Any]):
        try:
            with open(self.memory_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log(f"FutureMemoryAgent: failed to save memory: {e}")

    def record_event(self, event_title: str, event_type: str, time_iso: str) -> Dict[str, Any]:
        mem = self.load_memory()
        history = mem.setdefault("event_history", [])
        
        # Prevent duplicates
        for h in history:
            if (h.get("title", "").lower().strip() == event_title.lower().strip() and
                h.get("time_iso", "").lower().strip() == time_iso.lower().strip()):
                return {"status": "already_recorded", "title": event_title}

        entry = {
            "title": event_title,
            "type": event_type,
            "time_iso": time_iso,
            "recorded_at": datetime.utcnow().isoformat()
        }
        history.append(entry)
        self.save_memory(mem)
        log(f"FutureMemoryAgent: recorded event {entry}")
        return {"status": "recorded", "entry": entry}

    def query_habits(self, event_type: str) -> Dict[str, Any]:
        """
        Generate cognitive sleep suggestions and preparation advice based on event type.
        """
        evt_type = (event_type or "").lower().strip()

        if evt_type in ["viva", "exam", "test", "quiz", "midterm", "final"]:
            return {
                "sleep_recommendation": "winding down by 10:30 PM tonight to get a solid 8 hours of sleep",
                "focus_tip": "Review your dynamic study notes recommendations and stay hydrated."
            }
        elif evt_type in ["meeting", "presentation", "discussion"]:
            return {
                "sleep_recommendation": "getting at least 7-8 hours of sleep to stay sharp during your discussions",
                "focus_tip": "Prepare your agenda and materials beforehand."
            }
        elif evt_type in ["interview", "pitch"]:
            return {
                "sleep_recommendation": "resting well tonight to maintain peak cognitive readiness and confidence",
                "focus_tip": "Take deep breaths and review your interview answers."
            }
        elif evt_type in ["flight", "trip", "travel"]:
            return {
                "sleep_recommendation": "ensuring you sleep early to avoid travel fatigue",
                "focus_tip": "Double-check your tickets, documents, and packing list."
            }
        else:
            return {
                "sleep_recommendation": "getting a full night's sleep to maintain your daily productivity",
                "focus_tip": "Arrive early and take notes if needed."
            }

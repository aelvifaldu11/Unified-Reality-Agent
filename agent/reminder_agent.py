import os
import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any

from utils.logger import log

REMINDERS_PATH = os.path.join("data","reminders.json")

class ReminderAgent:
    """
    Simple reminder agent:
    - Stores reminders in data/reminders.json
    - evaluate(ctx) returns list of due/near reminders
    - dispatch(reminders) prints/logs notifications
    """

    def __init__(self, secrets_loader):
        # Store secrets loader (kept for consistency with other agents)
        self.secrets = secrets_loader
        self._ensure_file()

    def _ensure_file(self):
        """
        Makes sure reminders.json exists.
        If not, create the 'data' folder and an empty reminders.json file.
        """
        d = os.path.dirname(REMINDERS_PATH)

        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)      

        if not os.path.exists(REMINDERS_PATH):
            with open(REMINDERS_PATH, "w") as f:
                json.dump([], f)

    def _load_all(self) -> List[Dict[str, Any]]:
        """
        Loads all reminders from the file.
        Returns an empty list if file missing / corrupted.
        """
        try:
            with open(REMINDERS_PATH, "r") as f:
                return json.load(f) or []
        except Exception:
            return []

    def _save_all(self, items: List[Dict[str, Any]]):
        """
        Saves the updated list of reminders to the file.
        """
        try:
            with open(REMINDERS_PATH, "w") as f:
                json.dump(items, f, indent=2)
        except Exception as e:
            log(f"reminder_agent: failed to save reminders: {e}")     

    def add_reminder(self, title: str, time_iso: str, meta: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Adds a new reminder entry.
        - title: Reminder title
        - time_iso: ISO-formatted date string
        - meta: Additional metadata 
        """
        items = self._load_all()

        rid = f"r{len(items)+1}"

        r = {
            "id": rid,
            "title": title,
            "time_iso": time_iso,               
            "meta": meta or {},
            "created": datetime.utcnow().isoformat()
        }
        items.append(r)
        self._save_all(items)
        log(f"reminder_agent: added {r}")
        return r

    def update_reminder(self, reminder_id: str, title: str = None, time_iso: str = None, meta: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Updates an existing reminder by its ID.
        """
        items = self._load_all()
        updated_r = None
        for r in items:
            if r.get("id") == reminder_id:
                if title is not None:
                    r["title"] = title
                if time_iso is not None:
                    r["time_iso"] = time_iso
                if meta is not None:
                    r["meta"] = meta
                updated_r = r
                break
        if updated_r:
            self._save_all(items)
            log(f"reminder_agent: updated {updated_r}")
        return updated_r

    def remove_reminder(self, reminder_id: str) -> bool:
        """
        Removes a reminder by its ID.
        Returns True if removed and False if ID not found.
        """
        items = self._load_all()

        n = [i for i in items if i.get("id") != reminder_id]

        changed = len(n) != len(items)
        if changed:
            self._save_all(n)
            log(f"reminder_agent: removed {reminder_id}")
        return changed

    def normalize_title(self, title: str) -> str:
        if not title:
            return ""
        s = title.lower()
        s = re.sub(r'[^a-zA-Z0-9\s]', ' ', s)
        return " ".join(s.split())

    def find_matching_reminders(self, query: str, include_completed: bool = False) -> List[Dict[str, Any]]:
        reminders = self.list_reminders(include_completed=include_completed)
        target = self.normalize_title(query)
        if not target:
            return []
            
        exact_matches = []
        for r in reminders:
            if self.normalize_title(r.get("title", "")) == target:
                exact_matches.append(r)
                
        if exact_matches:
            return exact_matches
            
        # 2. Look for partial matches (substring and word subset match)
        partial_matches = []
        t_words = set(target.split())
        for r in reminders:
            r_title = r.get("title", "")
            r_norm = self.normalize_title(r_title)
            
            # Substring check
            if target in r_norm or r_norm in target:
                partial_matches.append(r)
                continue
                
            # Word subset check
            r_words = set(r_norm.split())
            if t_words.issubset(r_words) or r_words.issubset(t_words):
                partial_matches.append(r)
                
        return partial_matches

    def mark_completed(self, reminder_id: str) -> bool:
        """
        Marks a reminder as completed by its ID.
        Returns True if updated and False if ID not found.
        """
        items = self._load_all()
        updated = False
        for r in items:
            if r.get("id") == reminder_id:
                r["completed"] = True
                updated = True
                break
        if updated:
            self._save_all(items)
            log(f"reminder_agent: marked completed {reminder_id}")
        return updated

    def list_reminders(self, include_completed: bool = False) -> List[Dict[str, Any]]:
        """
        Returns reminders that are currently stored.
        """
        items = self._load_all()
        if not include_completed:
            items = [i for i in items if not i.get("completed")]
        return items

    def evaluate(self, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Returns reminders that are due soon or match context rules.
        - due within next 30 minutes -> 'due'
        - weather-based suggestions -> 'weather' type
        """
        out = []
        now = datetime.now(timezone.utc)
        items = self._load_all()

        for r in items:
            if r.get("completed"):
                continue
            try:
                t = datetime.fromisoformat(r.get("time_iso"))
                t = t if t.tzinfo else t.replace(tzinfo=timezone.utc)

                delta_min = (t - now).total_seconds() / 60

                # Check if reminder is due in next 30 mins (or slightly late)
                if delta_min <= 30 and delta_min >= -5:
                    out.append({
                        "type": "due",
                        "msg" : f"Reminder '{r.get('title')}' at {r.get('time_iso')}",
                        "id": r.get("id")
                    })
            except Exception:
                continue
        
        weather = ctx.get("weather", {}) or {}
        cond = (weather.get("condition") or "").lower()
        if "rain" in cond:
            out.append({"type": "weather" , 
                        "msg": "Rain expected soon - consider taking an umbrella."
                    })

        seen = set()
        final = []
        for r in out:
            key = (r.get("type"), r.get("msg"))
            if key in seen:
                continue
            seen.add(key)
            final.append(r)
        return final

    def dispatch(self, reminders: List[Dict[str, Any]]):
        for r in reminders:
            try:
                msg = r.get("msg")
                print(f"[REMINDER] {msg}")
                log(f"reminder_agemt: dispatched -> {msg}")
            except Exception as e:
                log(f"reminder_agent: dispatch error {e}")


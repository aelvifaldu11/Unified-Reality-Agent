import os
import json
from datetime import datetime
from typing import List, Dict, Any

from utils.logger import log

try:
    from google.oauth2 import service_account 
    from googleapiclient.discovery import build       # for accessing Google Calendar API
except Exception:
    service_account = None                            # fallback if Google modules not installed
    build = None

CAL_PATH = os.path.join("data" , "calendar.json")
 
class CalendarAgent:
    """
    CalendarAgnet:
    - Demo Mode : local JSON calendar file
    - Real Mode : Google Calendar using Service Account Credentials 
    """
    def __init__(self,secrets_loader):
        self.secrets = secrets_loader
        self.mode = secrets_loader.mode
        self._ensure_file()
        self.service = self._connect_service_account() if self.mode == "real" else None 

    #Demo Mode
    def _ensure_file(self):

        d = os.path.dirname(CAL_PATH) 

        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        
        if not os.path.exists(CAL_PATH):
            # if file missing, try loading mock/demo data
            try:
                mock = self.secrets.load_mock_data("calendar.json")
                if mock:
                    with open(CAL_PATH, "w") as f:
                        json.dump(mock, f, indent=2)
                    return
            except Exception:
                pass
            with open(CAL_PATH, "w") as f:
                json.dump([] , f)

    def _load(self):
        try:
            with open(CAL_PATH, "r") as f:
                return json.load(f) or []
        except Exception:
            return []

    def _save(self, arr):
        try:
            with open(CAL_PATH, "w") as f:
                json.dump(arr, f, indent=2) 
                
        except Exception as e:
            log(f"calendar_agent: save failed: {e}")

    #Real Mode
    def _connect_service_account(self):
        try:
            filename = self.secrets.get_secret("GOOGLE_SERVICE_ACCOUNT_JSON")

            if not filename:
                log("calendar_agent: GOOGLE_SERVICE_ACCOUNT_JSON missing in .env")
                self.mode = "demo"
                return None

            key_file = filename
            if not os.path.isabs(key_file):
                key_file = os.path.join(self.secrets.project_root, "config", filename)

            if not os.path.exists(key_file):
                log(f"calendar_agent: service account file missing at {key_file}, switching to demo mode")
                self.mode = "demo"
                return None

            creds = service_account.Credentials.from_service_account_file(
               key_file,
               scopes=["https://www.googleapis.com/auth/calendar"]
        )

            service = build("calendar", "v3", credentials=creds)
            return service

        except Exception as e:
            log(f"calendar_agent: service account connection failed: {e}")
            self.mode = "demo"
            return None

    def get_upcoming(self, within_hours=24) -> List[Dict[str, Any]]:
        if self.mode == "real" and self.service:
            return self._real_get_upcoming(within_hours)
        events = self._demo_get_upcoming(within_hours)
        seen = set()
        out = []
        for e in events:
            key = (
                (e.get("title") or "").lower().strip(),
                (e.get("time_iso") or "").lower().strip(),
                (e.get("location") or "").lower().strip()
            )
            if key not in seen:
                seen.add(key)
                out.append(e)
        return out

    def add_event(self, title, time_iso, location=None) -> Dict[str, Any]:
        return self._real_add_event(title, time_iso, location) if self.mode == "real" and self.service else self._demo_add_event(title, time_iso, location)

    def delete_event(self, event_id) -> bool:
        return self._real_delete_event(event_id) if self.mode == "real" and self.service else self._demo_delete_event(event_id)

    def update_event(self, event_id, title=None, time_iso=None, location=None) -> Dict[str, Any]:
        return self._real_update_event(event_id, title, time_iso, location) if self.mode == "real" and self.service else self._demo_update_event(event_id, title, time_iso, location)

    def list_all(self) -> List[Dict[str, Any]]:
        if self.mode == "real" and self.service:
            return self._real_list_all()
        events = self._load()
        seen = set()
        out = []
        for e in events:
            key = (
                (e.get("title") or "").lower().strip(),
                (e.get("time_iso") or "").lower().strip(),
                (e.get("location") or "").lower().strip()
            )
            if key not in seen:
                seen.add(key)
                out.append(e)
        return out

    #Demo Implementation
 
    def _demo_get_upcoming(self, within_hours):
        now = datetime.utcnow()
        out = []
        for e in self._load():
            try:
                t = datetime.fromisoformat(e.get("time_iso").replace("Z", "+00:00"))
                # Handle tz aware if needed
                if t.tzinfo is not None:
                    from datetime import timezone
                    now_tz = datetime.now(timezone.utc)
                    delta = (t - now_tz).total_seconds()
                else:
                    delta = (t - now).total_seconds()
                if 0 <= delta <= within_hours * 3600:
                    out.append(e)
            except Exception:
                continue
        return out

    def _demo_add_event(self, title, time_iso, location):
        items = self._load()
        # Prevent duplicates (case-insensitive comparison)
        for item in items:
            if (item.get("title", "").lower().strip() == (title or "").lower().strip() and
                    item.get("time_iso", "").lower().strip() == (time_iso or "").lower().strip() and
                    item.get("location", "").lower().strip() == (location or "").lower().strip()):
                return item

        eid = f"evt{len(items)+1}"
        ev = {"id": eid, 
              "title": title, 
              "time_iso": time_iso, 
              "location": location
        }
        items.append(ev)
        self._save(items)
        log(f"demo added event: {ev}")
        return ev

    def _demo_delete_event(self, event_id):
        items = self._load()
        new = [e for e in items if e["id"] != event_id]
        if len(new) == len(items):
            return False
        self._save(new)
        log(f"demo deleted event: {event_id}")
        return True 

    def _demo_update_event(self, event_id, title=None, time_iso=None, location=None):
        items = self._load()
        updated_ev = None
        for item in items:
            if item.get("id") == event_id:
                if title is not None:
                    item["title"] = title
                if time_iso is not None:
                    item["time_iso"] = time_iso
                if location is not None:
                    item["location"] = location
                updated_ev = item
                break
        if updated_ev:
            self._save(items)
            log(f"demo updated event: {updated_ev}")
        return updated_ev 

    #Real Implementation
    def _real_get_upcoming(self, within_hours):
        try:
            now = datetime.utcnow().isoformat() + "Z"              # Google requires Z suffix , fetches request or API response in UTC 
            events = (
                self.service.events()
                .list(calendarId="primary", timeMin=now, maxResults=10, singleEvents=True , orderBy="startTime")
                .execute()
            )
            return events.get("items", [])
        except Exception as e:
            log(f"real get_upcoming failed: {e}")
            return []

    def _real_add_event(self, title, time_iso, location):
        try:
            event = {
                "summary": title,
                "location": location,
                "start": {"dateTime": time_iso},
                "end": {"dateTime": time_iso}
            }

            created = self.service.events().insert(calendarId="primary", body=event).execute()
            return created

        except Exception as e:
            log(f"real add_event failed: {e}")
            return {}

    def _real_delete_event(self, event_id):
        try:
            self.service.events().delete(calendarId="primary", eventId=event_id).execute()
            return True
        except Exception:
            return False

    def _real_list_all(self):
        try:
            events = self.service.events().list(calendarId="primary", maxResults=50).execute()
            return events.get("items",[])
        except Exception:
            return []

    def _real_update_event(self, event_id, title=None, time_iso=None, location=None):
        try:
            event = self.service.events().get(calendarId="primary", eventId=event_id).execute()
            if title is not None:
                event["summary"] = title
            if location is not None:
                event["location"] = location
            if time_iso is not None:
                event["start"] = {"dateTime": time_iso}
                event["end"] = {"dateTime": time_iso}
            updated = self.service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
            return updated
        except Exception as e:
            log(f"real update_event failed: {e}")
            return {}
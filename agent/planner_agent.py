from config.secrets_loader import SecretsLoader
from agent.openai_runtime import OpenAIRuntime
import json
import re

def generate_reminder_message(title: str) -> str:
    if not title:
        return "Prepare for the event"
    t = title.lower()
    if "party" in t:
        return "Get ready for the party"
    elif "birthday" in t or "bday" in t:
        match = re.search(r'([a-zA-Z0-9]+)\'s\s+birthday', title, re.IGNORECASE)
        if match:
            return f"Wish {match.group(1)}"
        return "Leave for the birthday celebration"
    elif "trip" in t or "vacation" in t or "pack" in t or "travel" in t or "tour" in t:
        return "Pack essentials"
    elif "flight" in t or "airport" in t or "plane" in t:
        return "Leave for the airport"
    elif "movie" in t or "theatre" in t or "cinema" in t or "show" in t:
        return "Leave for the theatre"
    elif "dinner" in t or "lunch" in t or "restaurant" in t or "food" in t or "breakfast" in t or "brunch" in t:
        for meal in ["dinner", "lunch", "breakfast", "brunch"]:
            if meal in t:
                return f"Leave for {meal}"
        return "Leave for dinner"
    elif "wedding" in t or "marriage" in t:
        return "Get ready for the wedding"
    elif "shopping" in t:
        return "Leave for shopping"
    elif "concert" in t or "gig" in t:
        return "Leave for the concert"
    elif "sports" in t or "match" in t or "game" in t:
        return "Leave for the game"
    elif "railway" in t or "station" in t or "train" in t:
        return "Leave for the railway station"
    elif "appointment" in t or "doctor" in t or "dentist" in t or "checkup" in t:
        if "doctor" in t:
            return "Leave for the doctor appointment"
        elif "dentist" in t:
            return "Leave for the dentist appointment"
        return "Leave for the appointment"
    else:
        return f"Prepare for {title}"

class PlannerAgent:
    """
    PlannerAgent:
    Converts user queries into structured plans dynamically.
    - Demo mode: keyword and regex-based dynamic intent/entity parser.
    - Real mode: calls OpenAI GPT to produce a structured JSON plan with extracted entities.
    """

    def __init__(self, secrets: SecretsLoader):
        self.secrets = secrets
        self.mode = secrets.mode
        self.runtime = OpenAIRuntime(secrets) if self.mode == "real" else None
    def plan(self, user_query: str) -> dict:
        """
        Main entry point – returns a structured plan dict:
            {
                "extracted_info": {
                    "event_title": "...",
                    "event_type": "...",
                    "date": "...",
                    "time": "...",
                    "location": "...",
                    "subject": "...",
                    "priority": "..."
                },
                "steps": [ {"action": "...", ...}, ... ]
            }
        """
        if self.mode == "demo":
            return self._demo_plan(user_query)

        print("[PlannerAgent] REAL MODE: Calling OpenAI")
        prompt = f"""
You are the Unified Reality Agent Planner.
Convert the user request into a structured JSON plan, identifying the intent and extracting dynamic entities.

USER INPUT:
"{user_query}"

STAGE 1: EXTRACT ENTITIES (extract directly from USER INPUT)
Identify:
- event_title: The name of the event (e.g. "AI Viva", "Data Mining Exam", "Meeting with client").
- event_type: Classification of the event. Must be one of: "viva", "exam", "meeting", "interview", "trip", "flight", "deadline", "birthday", "personal", "reminder", "general".
- date: Mentioned date or relative date (e.g., "Tomorrow", "5 July", "Next Monday").
- time: Mentioned time (e.g., "11 AM", "2 PM", "4 PM").
- location: Mentioned location (e.g., "College Lab", "Office", "Mumbai") if any.
- subject: The academic/work subject (e.g., "AI", "Data Mining") if applicable.
- priority: "High", "Medium", or "Low".

STAGE 2: CREATE DYNAMIC PLAN
Decide on steps dynamically. Do not use static hardcoded templates.
Possible actions:
- {{"action": "add_calendar_event", "title": "<title>", "time": "<date/time string>", "location": "<location>"}}
- {{"action": "set_reminder", "message": "<message>", "time": "<date/time string>"}}
- {{"action": "recommend_notes", "subject": "<subject>", "title": "<title>"}}
- {{"action": "cognitive_prep", "event_type": "<type>"}}
- {{"action": "check_weather", "location": "<location>"}}
- {{"action": "query_calendar"}}
- {{"action": "query_reminders"}}

Rules for Plan generation:
- If scheduling an exam/viva/test: add_calendar_event, set_reminder (for study today at 6 PM), set_reminder (morning prep tomorrow at 8 AM), recommend_notes, cognitive_prep, check_weather, and record_event.
- If scheduling a meeting: add_calendar_event, check_weather, set_reminder (for umbrella), cognitive_prep, and record_event.
- If scheduling a general personal event (party, birthday, trip, flight, movie, dinner, wedding, vacation, appointment): add_calendar_event, and set_reminder (with a logically generated message).
- If querying weather: check_weather.
- If listing reminders: query_reminders.
- If querying calendar: query_calendar.

You MUST respond ONLY with a valid JSON object matching this structure:
{{
  "extracted_info": {{
    "event_title": "<event_title or null>",
    "event_type": "<event_type or null>",
    "date": "<date or null>",
    "time": "<time or null>",
    "location": "<location or null>",
    "subject": "<subject or null>",
    "priority": "<priority or null>"
  }},
  "steps": [
    {{ "action": "add_calendar_event", "title": "...", "time": "...", "location": "..." }},
    ...
  ]
}}
"""
        result = self.runtime.generate_text(prompt)

        print("=== RAW LLM OUTPUT START ===")
        print(result)
        print("=== RAW LLM OUTPUT END ===")

        # Safely coerce LLM output to a dict
        plan = {}
        if isinstance(result, dict):
            if "raw_response" in result:
                try:
                    plan = json.loads(result["raw_response"])
                except Exception:
                    plan = {}
            elif "error" in result:
                plan = {}
            else:
                plan = result
        elif isinstance(result, str):
            try:
                plan = json.loads(result)
            except Exception:
                plan = {}

        # Fallback if parsing failed or structure is incomplete
        if not isinstance(plan, dict) or "steps" not in plan:
            # Fall back to demo parser for resilience
            return self._demo_plan(user_query)

        if "extracted_info" not in plan:
            plan["extracted_info"] = self._parse_query_dynamics(user_query)

        return plan

    def _classify_reminder_intent(self, q: str) -> str | None:
        """
        Returns the reminder-specific intent if the query is about managing
        existing reminders, or None if it is unrelated.

        Priority order (checked before event-type routing):
          'list_reminders'   – show / list / view / my reminders
          'delete_reminder'  – delete / remove / cancel / clear reminder
          'complete_reminder'– mark / done / complete reminder
          'create_reminder'  – remind me to … / set a reminder …
        """
        q_l = q.lower()

        # ── Management operations (must come before create check) ──────────────
        update_kws = ["update", "change", "modify", "reschedule", "edit", "postpone", "shift"]
        list_kws   = ["show", "list", "view", "what are", "display", "see"]
        delete_kws = ["delete", "remove", "cancel", "clear", "erase"]
        done_kws   = ["mark", "complete", "done", "finish", "check off"]
        reminder_nouns = ["reminder", "reminders"]

        has_reminder_noun = any(n in q_l for n in reminder_nouns)

        if any(k in q_l for k in update_kws) and (has_reminder_noun or "remind" in q_l):
            return "update_reminder"
        if any(k in q_l for k in delete_kws) and has_reminder_noun:
            return "delete_reminder"
        if any(k in q_l for k in done_kws) and has_reminder_noun:
            return "complete_reminder"
        if any(k in q_l for k in list_kws) and has_reminder_noun:
            return "list_reminders"
        if has_reminder_noun and any(p in q_l for p in ["my reminder", "all reminder", "all my reminder"]):
            return "list_reminders"

        create_kws = ["remind me to", "remind me about", "set a reminder",
                      "set reminder", "create a reminder", "add a reminder"]
        if any(k in q_l for k in create_kws):
            return "create_reminder"

        return None

    def _extract_city(self, q: str) -> str:
        """Try to extract a city name from the query."""
        city_map = [
            "mumbai", "delhi", "bangalore", "chennai", "kolkata",
            "hyderabad", "pune", "jaipur", "ahmedabad", "surat",
            "london", "new york", "paris", "tokyo", "dubai",
            "singapore", "sydney", "berlin", "toronto", "seattle"
        ]
        for tok in city_map:
            if tok in q.lower():
                return tok.title()
        return "Mumbai"

    def _parse_query_dynamics(self, q: str) -> dict:
        q_work = q.strip()
        q_lower = q.lower()

        reminder_intent = self._classify_reminder_intent(q)
        if reminder_intent in ("list_reminders", "delete_reminder", "complete_reminder"):
            return {
                "event_title": None,
                "event_type": reminder_intent,
                "date": None,
                "time": None,
                "location": None,
                "subject": None,
                "priority": "Low"
            }

        event_type = "general"
        viva_kws      = ["viva", "presentation", "defense"]
        exam_kws      = ["exam", "test", "quiz", "midterm", "final"]
        meeting_kws   = ["meeting", "conference", "discussion", "client", "sync"]
        interview_kws = ["interview", "pitch", "recruit"]
        trip_kws      = ["trip", "travel", "flight", "tour", "vacation", "journey"]
        deadline_kws  = ["deadline", "due", "submit", "submission"]
        birthday_kws  = ["birthday", "bday", "anniversary"]

        # ── Informational intents: weather (must come before planning checks) ───
        weather_kws  = ["weather", "temp", "temperature", "rain", "raining",
                        "forecast", "climate", "hot", "cold", "degrees", "humid",
                        "wind", "sunny", "cloudy", "drizzle", "storm"]
        # planning indicators that can co-occur with weather words (e.g. "meeting weather")
        planning_kws = viva_kws + exam_kws + meeting_kws + interview_kws + trip_kws + deadline_kws + birthday_kws
        if (any(k in q_lower for k in weather_kws)
                and not any(k in q_lower for k in planning_kws)
                and not any(k in q_lower for k in ["remind me", "set a reminder", "schedule"])):
            event_type = "weather"

        elif any(p in q_lower for p in [
                "show my calendar", "show calendar", "view calendar",
                "list calendar", "upcoming events", "list upcoming",
                "what's on my schedule", "whats on my schedule",
                "my schedule", "my events"]):
            event_type = "query_calendar"

        elif any(k in q_lower for k in viva_kws):
            event_type = "viva"
        elif any(k in q_lower for k in exam_kws):
            event_type = "exam"
        elif any(k in q_lower for k in meeting_kws):
            event_type = "meeting"
        elif any(k in q_lower for k in interview_kws):
            event_type = "interview"
        elif any(k in q_lower for k in trip_kws):
            event_type = "trip"
        elif any(k in q_lower for k in deadline_kws):
            event_type = "deadline"
        elif any(k in q_lower for k in birthday_kws):
            event_type = "birthday"
        elif any(k in q_lower for k in [
            "party", "wedding", "marriage", "function", "celebration", "dinner",
            "lunch", "movie", "shopping", "airport", "station", "vacation",
            "picnic", "concert", "sports", "gathering", "festival", "club",
            "hangout", "social", "appointment", "doctor", "dentist", "checkup"
        ]):
            event_type = "personal"
        elif reminder_intent == "create_reminder":
            event_type = "reminder"
        elif reminder_intent == "update_reminder":
            event_type = "update_reminder"

        time_str = None
        time_match = re.search(r'\b(?:at|for|to)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))\b', q_work)
        if time_match:
            time_str = time_match.group(1).strip()
            q_work = q_work.replace(time_match.group(0), "")
        else:
            time_match_colon = re.search(r'\b(?:at|for|to)?\s*(\d{1,2}:\d{2})\b', q_work)
            if time_match_colon:
                time_str = time_match_colon.group(1).strip()
                q_work = q_work.replace(time_match_colon.group(0), "")
        
        if not time_str:
            time_str = "10:00 AM"

        date_str = None
        relative_match = re.search(r'\b(tomorrow|today|next\s+monday|next\s+tuesday|next\s+wednesday|next\s+thursday|next\s+friday|next\s+saturday|next\s+sunday|next\s+week)\b', q_work, re.IGNORECASE)
        if relative_match:
            date_str = relative_match.group(1).title()
            q_work = q_work.replace(relative_match.group(0), "")
        else:
            date_match = re.search(r'\b(?:on\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+[a-zA-Z]+)\b', q_work, re.IGNORECASE)
            if date_match:
                date_str = date_match.group(1).strip()
                q_work = q_work.replace(date_match.group(0), "")
            else:
                date_match_rev = re.search(r'\b(?:on\s+)?([a-zA-Z]+\s+\d{1,2}(?:st|nd|rd|th)?)\b', q_work, re.IGNORECASE)
                if date_match_rev:
                    date_str = date_match_rev.group(1).strip()
                    q_work = q_work.replace(date_match_rev.group(0), "")

        if not date_str:
            if event_type == "update_reminder":
                date_str = "Today"
            else:
                date_str = "Tomorrow"

        location_str = None
        loc_match = re.search(r'\b(?:in|at)\s+(?:the\s+)?([a-zA-Z0-9\s]+?)(?=\s+(?:in|at|on|for)|$)', q_work, re.IGNORECASE)
        if loc_match:
            candidate_loc = loc_match.group(1).strip()
            if candidate_loc and len(candidate_loc) > 1:
                location_str = candidate_loc
                q_work = q_work.replace(loc_match.group(0), "")
        
        if not location_str:
            if event_type in ["exam", "viva"]:
                location_str = "College Lab"
            elif event_type in ["meeting"]:
                location_str = "Office"
            else:
                location_str = None

        title_temp = q_work
        title_temp = re.sub(r'(?i)^\s*(?:update\s+reminder\s+|update\s+|change\s+reminder\s+|change\s+|modify\s+reminder\s+|modify\s+|reschedule\s+reminder\s+|reschedule\s+|edit\s+reminder\s+|edit\s+|i\s+have\s+(?:\bmy\b|\ba\b|\ban\b)?\s*|schedule\s+(?:\bmy\b|\ba\b|\ban\b)?\s*|set\s+a\s+reminder\s+for\s*|remind\s+me\s+to\s*|remind\s+me\s+about\s*)', '', title_temp)
        title_temp = re.sub(r'\s+', ' ', title_temp).strip(" ,.!?")
        title_temp = title_temp.strip("'\"")
        
        if not title_temp:
            title_temp = f"{event_type.title()} Event"

        event_title = title_temp

        subject_str = event_title
        if event_type in ["exam", "viva"]:
            sub_match = re.search(r'^(.*?)\s+(?:exam|viva|test|quiz|presentation|defense)$', event_title, re.IGNORECASE)
            if sub_match:
                subject_str = sub_match.group(1).strip()

        # ── Informational intents must never produce a titled event ─────────────
        # Setting event_title=None here prevents _build_proactive_plan_dynamically
        # from generating any proactive plan card for these query types.
        _informational_types = (
            "weather", "query_calendar",
            "list_reminders", "delete_reminder", "complete_reminder"
        )
        if event_type in _informational_types:
            event_title = None

        extracted_info = {
            "event_title": event_title,
            "event_type": event_type,
            "date": date_str,
            "time": time_str,
            "location": location_str,
            "subject": subject_str,
            "priority": "High" if event_type in ["exam", "viva", "interview"] else "Medium"
        }
        
        return extracted_info

    def _demo_plan(self, user_query: str) -> dict:
        """
        Demo mode: Dynamic parsing and action steps generation.
        """
        info = self._parse_query_dynamics(user_query)
        etype = info["event_type"]
        title = info["event_title"]
        date = info["date"]
        time_val = info["time"]
        loc = info["location"]
        sub = info["subject"]

        time_label = f"{date} at {time_val}"
        steps = []

        if etype == "weather":
            city = info.get("location") or self._extract_city(user_query)
            return {
                "extracted_info": info,
                "steps": [{"action": "check_weather", "location": city}]
            }

        if etype == "query_calendar":
            return {
                "extracted_info": info,
                "steps": [{"action": "query_calendar"}]
            }

        # ── Reminder management: dispatch FIRST before event-type routing ──────
        reminder_intent = self._classify_reminder_intent(user_query)

        if reminder_intent == "list_reminders":
            return {
                "extracted_info": info,
                "steps": [{"action": "query_reminders"}]
            }

        if reminder_intent == "delete_reminder":
            return {
                "extracted_info": info,
                "steps": [{"action": "delete_reminder", "query": user_query}]
            }

        if reminder_intent == "complete_reminder":
            return {
                "extracted_info": info,
                "steps": [{"action": "mark_reminder_done", "query": user_query}]
            }

        if reminder_intent == "update_reminder":
            return {
                "extracted_info": info,
                "steps": [{
                    "action": "update_reminder",
                    "query": user_query,
                    "target_title": info.get("event_title"),
                    "new_time": time_label
                }]
            }

        if reminder_intent == "create_reminder":
            return {
                "extracted_info": info,
                "steps": [
                    {"action": "set_reminder", "message": title or user_query, "time": time_label},
                    {"action": "record_event", "title": title or user_query, "type": "reminder", "time": time_label}
                ]
            }

        if etype in ["viva", "exam", "test"]:
            steps.append({
                "action": "add_calendar_event",
                "title": title,
                "time": time_label,
                "location": loc
            })
            # Create study reminder (Today at 6:00 PM)
            steps.append({
                "action": "set_reminder",
                "message": f"📖 Study and prepare for {sub}",
                "time": "Today at 6:00 PM"
            })
            # Create morning prep reminder
            steps.append({
                "action": "set_reminder",
                "message": f"⏰ Morning prep: {title} today",
                "time": f"{date} at 8:00 AM"
            })
            steps.append({
                "action": "recommend_notes",
                "subject": sub,
                "title": title
            })
            steps.append({
                "action": "cognitive_prep",
                "event_type": etype
            })
            steps.append({
                "action": "check_weather",
                "location": loc or "Mumbai",
                "event_type": etype
            })
            steps.append({
                "action": "record_event",
                "title": title,
                "type": etype,
                "time": time_label
            })
        
        elif etype == "meeting":
            steps.append({
                "action": "add_calendar_event",
                "title": title,
                "time": time_label,
                "location": loc
            })
            steps.append({
                "action": "check_weather",
                "location": loc or "Mumbai",
                "event_type": etype
            })
            # Bring umbrella reminder
            steps.append({
                "action": "set_reminder",
                "message": f"☔ Bring umbrella to meeting at {time_val}",
                "time": time_label
            })
            steps.append({
                "action": "cognitive_prep",
                "event_type": etype
            })
            steps.append({
                "action": "record_event",
                "title": title,
                "type": etype,
                "time": time_label
            })

        elif etype in ["personal", "birthday", "trip", "travel", "appointment", "party", "celebration", "family event", "general"]:
            reminder_msg = generate_reminder_message(title or user_query)
            steps.append({
                "action": "add_calendar_event",
                "title": title or user_query,
                "time": time_label,
                "location": loc
            })
            steps.append({
                "action": "set_reminder",
                "message": reminder_msg,
                "time": time_label
            })
        else:
            steps.append({
                "action": "query_calendar"
            })

        return {
            "extracted_info": info,
            "steps": steps
        }
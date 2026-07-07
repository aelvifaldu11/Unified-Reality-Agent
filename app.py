"""
app.py — URA Local Web Server
Serves the UI at / and exposes POST /api/chat for agent interaction.
"""

import sys
import os
import time
import traceback
import re

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from flask import Flask, request, jsonify, render_template

from config.secrets_loader import SecretsLoader
from agent.planner_agent   import PlannerAgent
from agent.executor_agent  import ExecutorAgent
from agent.reminder_agent  import ReminderAgent
from agent.weather_agent   import WeatherAgent
from agent.calendar_agent  import CalendarAgent
from agent.session_manager import SessionManager
from agent.offline_mode    import OfflineModeController

app = Flask(__name__, template_folder="templates")

secrets  = SecretsLoader()
session  = SessionManager()
offline  = OfflineModeController()
planner  = PlannerAgent(secrets)
executor = ExecutorAgent(secrets)
reminder = ReminderAgent(secrets)
weather  = WeatherAgent(secrets)
calendar = CalendarAgent(secrets)


def _intent_wants_weather(query: str) -> bool:
    """Returns True if the user explicitly asked about weather/temperature."""
    weather_kw = ["weather", "temperature", "forecast", "rain", "sunny",
                  "humidity", "wind", "climate", "hot", "cold", "raining",
                  "temp", "degrees"]
    q = query.lower()
    return any(kw in q for kw in weather_kw)


def _is_internal_result(item: dict) -> bool:
    """
    Returns True for dicts that are internal agent results consumed by the
    proactive-plan builder and must never be shown raw in the chat UI.
    """
    if not isinstance(item, dict):
        return False
    # FutureMemoryAgent.record_event() result
    if "status" in item and "entry" in item:
        return True
    if item.get("status") in ("recorded", "already_recorded"):
        return True
    # FutureMemoryAgent.query_habits() result
    if "sleep_recommendation" in item:
        return True
    # NotesAgent.recommend_notes() result
    if "files" in item and "topics" in item:
        return True
    return False


def is_personal_event(event_type: str, event_title: str) -> bool:
    if not event_type:
        return True
    et = event_type.lower()
    if et in ("viva", "exam", "test", "meeting", "interview"):
        return False
    if et in ("weather", "query_calendar", "update_reminder", "delete_reminder", "list_reminders", "complete_reminder"):
        return False
    return True

def get_personal_confirmation_message(event_type: str, title: str) -> str:
    t = (title or "event").lower()
    et = (event_type or "").lower()
    
    if "birthday" in t or et == "birthday":
        return "I've scheduled the birthday event and created a reminder to wish them."
    elif "trip" in t or "travel" in t or "vacation" in t or et in ("trip", "travel"):
        return "Your trip has been scheduled successfully. I've also set a reminder to pack essentials!"
    elif "party" in t or et == "party":
        return "Everything is set for the party! I've scheduled it and set a reminder to get ready."
    elif "flight" in t or "airport" in t:
        return "I've scheduled your flight event and set a reminder to leave for the airport."
    elif "movie" in t:
        return "Your movie event is scheduled, and I've set a reminder to leave for the theatre."
    elif "dinner" in t or "lunch" in t or "breakfast" in t or "brunch" in t:
        return "I've scheduled your meal event and created a reminder to leave."
    elif "wedding" in t:
        return "Get ready for the wedding! I've scheduled the event and set a reminder."
    elif "appointment" in t or "doctor" in t or "dentist" in t or et == "appointment":
        if "doctor" in t:
            return "I've scheduled your doctor appointment and set a reminder."
        elif "dentist" in t:
            return "I've scheduled your dentist appointment and set a reminder."
        return "Your appointment has been scheduled successfully, and a reminder has been set."
    else:
        return "Your event has been scheduled successfully, and a reminder has been set."


def resolve_choice(user_msg: str, choices: list) -> dict | None:
    msg_clean = user_msg.strip().lower()
    
    num_match = re.search(r'\b(\d+)\b', msg_clean)
    if num_match:
        idx = int(num_match.group(1)) - 1
        if 0 <= idx < len(choices):
            return choices[idx]
            
    ordinals = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"]
    for i, ord_word in enumerate(ordinals):
        if ord_word in msg_clean:
            if i < len(choices):
                return choices[i]
                
    if "last" in msg_clean:
        return choices[-1]
        
    def _norm(title):
        if not title:
            return ""
        s = title.lower()
        s = re.sub(r'[^a-zA-Z0-9\s]', ' ', s)
        return " ".join(s.split())

    msg_norm = _norm(user_msg)
    if msg_norm:
        for choice in choices:
            if _norm(choice.get("title", "")) == msg_norm:
                return choice
        
        matching_choices = []
        for choice in choices:
            choice_norm = _norm(choice.get("title", ""))
            if msg_norm in choice_norm or choice_norm in msg_norm:
                matching_choices.append(choice)
        if len(matching_choices) == 1:
            return matching_choices[0]
            
    return None


def _format_result(step_results: list, include_weather: bool = True, proactive_plan: dict = None) -> dict:
    """
    Turn the flat list of executor results into a structured payload
    the UI can render as rich cards.

    Internal agent results (notes, cognitive, memory) are silently absorbed
    here — they are already consumed by _build_proactive_plan_dynamically and
    must never appear as raw strings in the chat response.

    include_weather: if False, weather data from results is suppressed.
    """
    weather_data  = None
    reminders_out = []
    events_out    = []
    messages      = []

    def _absorb(item):
        nonlocal weather_data
        if not isinstance(item, dict):
            if isinstance(item, str) and item.strip():
                messages.append(item)
            return
        # Silent-absorb internal agent results
        if _is_internal_result(item):
            return
        if "temperature" in item or "condition" in item:
            if include_weather:
                weather_data = item
        # Reminder card – has an "r…" id or a "created" timestamp
        elif item.get("id", "").startswith("r") or "created" in item:
            reminders_out.append(item)
        # Calendar event – has an "evt…" id or a "location" key
        elif item.get("id", "").startswith("evt") or "location" in item:
            events_out.append(item)
        # Known string-style payloads from executor (error/info text)
        elif isinstance(item.get("message"), str):
            messages.append(item["message"])
        # Fallback: only emit plain strings, never raw dicts
        # (anything that reaches here is an unknown internal result – drop it)

    for item in step_results:
        if isinstance(item, list):
            for sub_item in item:
                _absorb(sub_item)
        elif isinstance(item, str) and item.strip():
            messages.append(item)
        else:
            _absorb(item)

    # Deduplicate events based on title, time, and location (case-insensitive)
    seen_events = set()
    unique_events = []
    for ev in events_out:
        key = (
            (ev.get("title") or "").lower().strip(),
            (ev.get("time_iso") or "").lower().strip(),
            (ev.get("location") or "").lower().strip()
        )
        if key not in seen_events:
            seen_events.add(key)
            unique_events.append(ev)
    events_out = unique_events

    # Deduplicate reminders based on title and time (case-insensitive)
    seen_reminders = set()
    unique_reminders = []
    for r in reminders_out:
        key = (
            (r.get("title") or "").lower().strip(),
            (r.get("time_iso") or "").lower().strip()
        )
        if key not in seen_reminders:
            seen_reminders.add(key)
            unique_reminders.append(r)
    reminders_out = unique_reminders

    return {
        "weather":   weather_data,
        "reminders": reminders_out,
        "events":    events_out,
        "messages":  messages,
        "proactive_plan": proactive_plan,
    }


def _build_proactive_plan_dynamically(extracted_info: dict, step_results: list) -> dict:
    """
    Constructs a proactive plan dynamically from planner extraction and execution results.
    """
    if not extracted_info or not extracted_info.get("event_title"):
        return None
    if extracted_info.get("event_type") in ("update_reminder", "delete_reminder", "list_reminders", "complete_reminder"):
        return None

    title = extracted_info.get("event_title")
    etype = extracted_info.get("event_type", "general")
    date_val = extracted_info.get("date") or "Tomorrow"
    time_val = extracted_info.get("time") or "10:00 AM"
    loc = extracted_info.get("location") or "Scheduled Location"
    subject = extracted_info.get("subject") or title

    header_date_time = f"{date_val.lower()} at {time_val}" if "tomorrow" in date_val.lower() or "today" in date_val.lower() else f"on {date_val} at {time_val}"
    
    if etype in ["viva", "exam", "test", "interview"]:
        header = f"Here's your proactive plan to help you ace your {title.lower()} {header_date_time}:"
    else:
        header = f"Here's your proactive plan for your {title.lower()} {header_date_time}:"

    items = []

    items.append({
        "type": "calendar",
        "title": "Calendar",
        "text": f"You have your {title.lower()} scheduled {header_date_time} in the {loc}."
    })

    weather_info = None
    notes_info = None
    cognitive_info = None
    reminders_set = []

    for item in step_results:
        if isinstance(item, dict):
            if "temperature" in item or "condition" in item:
                weather_info = item
            elif "files" in item and "topics" in item:
                notes_info = item
            elif "sleep_recommendation" in item:
                cognitive_info = item
            elif item.get("id", "").startswith("r") or "created" in item:
                reminders_set.append(item)
        elif isinstance(item, list):
            for sub_item in item:
                if isinstance(sub_item, dict):
                    if "temperature" in sub_item or "condition" in sub_item:
                        weather_info = sub_item
                    elif "files" in sub_item and "topics" in sub_item:
                        notes_info = sub_item
                    elif "sleep_recommendation" in sub_item:
                        cognitive_info = sub_item
                    elif sub_item.get("id", "").startswith("r") or "created" in sub_item:
                        reminders_set.append(sub_item)

    if notes_info:
        items.append({
            "type": "notes",
            "title": "Notes Recommendation",
            "text": notes_info.get("message") or f"Recommended reviewing materials for {subject}."
        })

    if cognitive_info:
        items.append({
            "type": "cognitive",
            "title": "Cognitive Prep",
            "text": f"For peak cognitive performance, URA suggests {cognitive_info.get('sleep_recommendation') or 'resting well tonight'}."
        })

    if weather_info:
        cond = (weather_info.get("condition") or "").lower()
        temp = weather_info.get("temperature") or weather_info.get("temp_c") or ""
        temp_str = f" ({temp})" if temp else ""
        
        if "rain" in cond or "shower" in cond or "drizzle" in cond:
            weather_text = f"Heavy rain is predicted for {date_val.lower()}{temp_str}. URA suggests carrying an umbrella!"
            items.append({
                "type": "weather",
                "title": "Weather Alert",
                "text": weather_text
            })
        else:
            items.append({
                "type": "weather",
                "title": "Weather Outlook",
                "text": f"Weather is predicted to be {weather_info.get('condition', 'Sunny')}{temp_str} on {date_val.lower()}."
            })

    if reminders_set:
        reminder_titles = [f"'{r.get('title')}'" for r in reminders_set]
        items.append({
            "type": "reminder",
            "title": "Reminders Set",
            "text": f"Created reminders: {', '.join(reminder_titles)}."
        })

    return {
        "header": header,
        "items": items
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data       = request.get_json(force=True, silent=True) or {}
    user_msg   = (data.get("message") or "").strip()
    logs       = []
    start_time = time.time()

    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    try:
        logs.append({"agent": "System",   "msg": "Query received"})

        offline.refresh_status()
        is_online = offline.is_online()
        current_mode = secrets.mode if is_online else "demo"

        planner.mode = current_mode
        weather.secrets.mode = current_mode
        calendar.mode = current_mode

        # 1. Plan
        pending = session.load().get("pending_reminder_action")
        resolved_reminder = None
        plan = None
        
        if pending:
            resolved_reminder = resolve_choice(user_msg, pending["ambiguous_reminders"])
            if resolved_reminder:
                session.set("pending_reminder_action", None)
                plan = {
                    "extracted_info": {
                        "event_type": pending["action"],
                        "event_title": None,
                        "date": None,
                        "time": None,
                        "location": None,
                        "subject": None,
                        "priority": "Low"
                    },
                    "steps": [
                        {
                            "action": pending["action"],
                            "resolved_id": resolved_reminder["id"],
                            "query": pending["query"]
                        }
                    ]
                }
                logs.append({"agent": "Planner", "msg": f"Resolved pending choice: '{resolved_reminder.get('title')}'"})
            else:
                session.set("pending_reminder_action", None)

        if not plan:
            logs.append({"agent": "Planner",  "msg": f"Analysing intent ({'Online' if is_online else 'Offline'} Mode)…"})
            plan = planner.plan(user_msg)
            
        steps = plan.get("steps", [])
        if not pending or not resolved_reminder:
            logs.append({"agent": "Planner",
                         "msg": f"Plan built – {len(steps)} step(s): "
                                f"{[s.get('action') for s in steps]}"})

        # 2. Collect context
        logs.append({"agent": "Context",  "msg": "Loading session context…"})
        
        extracted = plan.get("extracted_info", {})
        etype = extracted.get("event_type")
        location = extracted.get("location")
        
        current_weather = weather.get_weather(location, event_type=etype)

        ctx = {
            "session": session.load(),
            "weather": current_weather,
        }

        # 3. Evaluate reminders
        logs.append({"agent": "Reminder", "msg": "Evaluating reminders…"})
        due_reminders = reminder.evaluate(ctx)

        # 4. Execute steps
        logs.append({"agent": "Executor", "msg": "Executing plan steps…"})
        raw_results = executor.execute(plan, ctx)

        # Check if the execution returned a pending reminder action
        # If so, save it to the session
        items_to_check = raw_results if isinstance(raw_results, list) else [raw_results]
        for item in items_to_check:
            if isinstance(item, dict) and "pending_reminder_action" in item:
                session.set("pending_reminder_action", item["pending_reminder_action"])
                break

        # Generate category-aware neutral confirmation message for general personal events
        if is_personal_event(extracted.get("event_type"), extracted.get("event_title")):
            msg = get_personal_confirmation_message(extracted.get("event_type"), extracted.get("event_title") or user_msg)
            if not isinstance(raw_results, list):
                raw_results = [raw_results]
            raw_results.insert(0, {"message": msg})

        # 5. Save to session history
        session.add_to_history(user_msg, str(raw_results))
        logs.append({"agent": "Memory",   "msg": "Session history updated"})

        # 6. Determine whether to include weather in the UI response
        user_wants_weather = _intent_wants_weather(user_msg)
        has_weather_step = any(s.get("action") == "check_weather" for s in steps)
        show_weather = user_wants_weather or has_weather_step

        # 7. Build Proactive Plan dynamically from execution results
        _no_plan_types = ("weather", "query_calendar",
                          "update_reminder", "delete_reminder",
                          "list_reminders", "complete_reminder")
        if is_personal_event(extracted.get("event_type"), extracted.get("event_title")):
            dynamic_proactive_plan = None
        elif extracted.get("event_type") in _no_plan_types:
            dynamic_proactive_plan = None
        else:
            dynamic_proactive_plan = _build_proactive_plan_dynamically(extracted, raw_results)

        # 8. Format payload
        formatted = _format_result(
            raw_results if isinstance(raw_results, list) else [raw_results],
            include_weather=show_weather,
            proactive_plan=dynamic_proactive_plan
        )

        elapsed      = round(time.time() - start_time, 2)
        confidence   = "High" if len(steps) > 0 and steps[0].get("action") != "none" else "Low"
        active_agent = steps[0].get("action", "none").replace("_", " ").title() if steps else "None"

        logs.append({"agent": "Response", "msg": "Response generated"})

        return jsonify({
            "result":        formatted,
            "logs":          logs,
            "due_reminders": due_reminders,
            "meta": {
                "execution_time": elapsed,
                "confidence":     confidence,
                "active_agent":   active_agent,
                "mode":           "offline" if not is_online else secrets.mode,
            }
        })

    except Exception as exc:
        tb = traceback.format_exc()
        logs.append({"agent": "System", "msg": f"Fatal error: {exc}"})
        return jsonify({"error": str(exc), "traceback": tb, "logs": logs}), 500


if __name__ == "__main__":
    print("\n🚀  URA Web UI starting at  http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000, use_reloader=False)

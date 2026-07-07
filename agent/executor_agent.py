import re

def extract_target_title(query: str) -> str:
    quoted_match = re.search(r'["\']([^"\']+)["\']', query)
    if quoted_match:
        return quoted_match.group(1).strip()
    
    q = query.strip()
    prefixes = [
        r'^(?:delete|remove|cancel|clear|erase|mark|complete|finish|check\s+off)\s+(?:the\s+|my\s+)?(?:reminder\s+to\s+|reminder\s+of\s+|reminder\s+for\s+|reminder\s+)?',
        r'^(?:delete|remove|cancel|clear|erase|mark|complete|finish|check\s+off)\s+'
    ]
    for pattern in prefixes:
        q_new = re.sub(pattern, '', q, flags=re.IGNORECASE)
        if q_new != q:
            q = q_new
            break
            
    suffixes = [
        r'\s+(?:as\s+)?done$',
        r'\s+(?:as\s+)?completed$',
        r'\s+complete$',
        r'\s+reminder$'
    ]
    for pattern in suffixes:
        q = re.sub(pattern, '', q, flags=re.IGNORECASE)
        
    return q.strip()

from agent.weather_agent import WeatherAgent
from agent.reminder_agent import ReminderAgent 
from agent.calendar_agent import CalendarAgent
from agent.notes_agent import NotesAgent
from agent.future_memory_agent import FutureMemoryAgent

def _clean_title(title: str) -> str:
    if not title:
        return ""
    t = title.lower().strip()
    # Strip emojis and common reminder prep prefixes
    t = t.replace("📖", "").replace("⏰", "").replace("☔", "")
    t = t.replace("study and prepare for", "")
    t = t.replace("morning prep:", "")
    t = t.replace("bring umbrella to", "")
    t = t.replace("today", "")
    t = t.replace("exam", "")
    t = t.replace("viva", "")
    t = t.replace("meeting", "")
    t = t.replace("test", "")
    t = t.replace("quiz", "")
    t = " ".join(t.split())
    return t

class ExecutorAgent:
    """
    ExecutorAgent:
    Executes each step created by PlannerAgent by dispatching to the relevant agent.
    """

    def __init__(self, secrets):
        self.secrets = secrets

        self.weather_agent = WeatherAgent(secrets)
        self.reminder_agent = ReminderAgent(secrets)
        self.calendar_agent = CalendarAgent(secrets)
        self.notes_agent = NotesAgent(secrets)
        self.future_memory_agent = FutureMemoryAgent(secrets)

    def execute(self, plan, ctx):
        if not plan:
            return ["invalid plan format received."]
        if isinstance(plan, dict) and "steps" in plan:
            return self.execute_plan(plan)
        return [self.execute_step(plan)]
    
    def execute_step(self, step: dict):
        """
        Execute a single action step.
        """
        if not isinstance(step, dict):
            return f"invalid step format: {step}"
            
        action = step.get("action")

        if action == "check_weather":
            location = step.get("location", "Mumbai")
            event_type = step.get("event_type")
            return self.weather_agent.get_weather(location, event_type=event_type)

        elif action == "set_reminder":
            time = step.get("time")
            message = step.get("message")
            return self.reminder_agent.add_reminder(title=message, time_iso=time)

        elif action == "query_calendar":
            return self.calendar_agent.list_all()

        elif action == "add_calendar_event":
            title = step.get("title", "Meeting")
            time = step.get("time")
            location = step.get("location", "Office")
            return self.calendar_agent.add_event(title, time, location)

        elif action == "query_reminders" or action == "list_reminders":
            return self.reminder_agent.list_reminders()

        elif action == "delete_reminder":
            resolved_id = step.get("resolved_id")
            if resolved_id:
                reminders = self.reminder_agent.list_reminders(include_completed=True)
                target = next((r for r in reminders if r["id"] == resolved_id), None)
            else:
                query_text = step.get("query", "")
                target_title = extract_target_title(query_text)
                matches = self.reminder_agent.find_matching_reminders(target_title)
                
                if not matches:
                    return {"message": f"No reminder matching \"{target_title}\" was found."}
                elif len(matches) > 1:
                    msg = f"I found multiple reminders matching \"{target_title}\":\n" + \
                          "\n".join(f"{i+1}. {r.get('title')}" for i, r in enumerate(matches)) + \
                          "\nWhich one did you mean?"
                    return {
                        "message": msg,
                        "pending_reminder_action": {
                            "action": "delete_reminder",
                            "ambiguous_reminders": matches,
                            "query": query_text
                        }
                    }
                else:
                    target = matches[0]

            if target:
                calendar_events = self.calendar_agent.list_all()
                best_ev, best_ev_score = None, 0
                reminder_clean = _clean_title(target.get("title", ""))
                
                if reminder_clean:
                    for ev in calendar_events:
                        ev_clean = _clean_title(ev.get("title", ""))
                        if ev_clean:
                            ev_words = set(ev_clean.split())
                            rem_words = set(reminder_clean.split())
                            overlap = len(ev_words & rem_words)
                            if overlap > best_ev_score:
                                best_ev, best_ev_score = ev, overlap
                
                if best_ev_score > 0 and best_ev:
                    self.calendar_agent.delete_event(best_ev["id"])

                removed = self.reminder_agent.remove_reminder(target["id"])
                if removed:
                    results = [{"message": f"✅ Reminder '{target.get('title')}' has been deleted."}]
                    results.extend(self.reminder_agent.list_reminders())
                    return results
            return {"message": "Could not delete the reminder. Please try again."}

        elif action == "mark_reminder_done":
            resolved_id = step.get("resolved_id")
            if resolved_id:
                reminders = self.reminder_agent.list_reminders(include_completed=True)
                target = next((r for r in reminders if r["id"] == resolved_id), None)
            else:
                query_text = step.get("query", "")
                target_title = extract_target_title(query_text)
                matches = self.reminder_agent.find_matching_reminders(target_title)
                
                if not matches:
                    return {"message": f"No reminder matching \"{target_title}\" was found."}
                elif len(matches) > 1:
                    msg = f"I found multiple reminders matching \"{target_title}\":\n" + \
                          "\n".join(f"{i+1}. {r.get('title')}" for i, r in enumerate(matches)) + \
                          "\nWhich one did you mean?"
                    return {
                        "message": msg,
                        "pending_reminder_action": {
                            "action": "mark_reminder_done",
                            "ambiguous_reminders": matches,
                            "query": query_text
                        }
                    }
                else:
                    target = matches[0]

            if target:
                marked = self.reminder_agent.mark_completed(target["id"])
                if marked:
                    results = [{"message": f"✅ Reminder '{target.get('title')}' marked as complete."}]
                    results.extend(self.reminder_agent.list_reminders())
                    return results
            return {"message": "Could not mark the reminder as done. Please try again."}

        elif action == "update_reminder":
            target_title = step.get("target_title", "")
            new_time = step.get("new_time")
            reminders = self.reminder_agent.list_reminders()
            if not reminders:
                return {"message": "You have no reminders to update."}
            
            # Fuzzy match target reminder
            best, best_score = None, 0
            target_words = {w for w in target_title.lower().split() if w not in {"reminder", "reminders", "the", "a", "an", "to", "for", "update", "change"}}
            
            for r in reminders:
                title_words = set((r.get("title") or "").lower().split())
                score = len(target_words & title_words)
                if score > best_score:
                    best, best_score = r, score
            
            target_reminder = best if best_score > 0 else reminders[-1]
            
            updated_reminder = self.reminder_agent.update_reminder(target_reminder["id"], time_iso=new_time)
            
            # Update linked calendar event if exists
            updated_event = None
            calendar_events = self.calendar_agent.list_all()
            
            best_ev, best_ev_score = None, 0
            reminder_clean = _clean_title(target_reminder.get("title", ""))
            
            if reminder_clean:
                for ev in calendar_events:
                    ev_clean = _clean_title(ev.get("title", ""))
                    if ev_clean:
                        ev_words = set(ev_clean.split())
                        rem_words = set(reminder_clean.split())
                        overlap = len(ev_words & rem_words)
                        if overlap > best_ev_score:
                            best_ev, best_ev_score = ev, overlap
            
            if best_ev_score > 0 and best_ev:
                updated_event = self.calendar_agent.update_event(best_ev["id"], time_iso=new_time)
            
            results = []
            results.append({"message": "✅ Reminder Updated"})
            if updated_reminder:
                results.append(updated_reminder)
            if updated_event:
                results.append(updated_event)
            return results

        elif action == "recommend_notes":
            subject = step.get("subject")
            title = step.get("title")
            return self.notes_agent.recommend_notes(subject, title)

        elif action == "cognitive_prep":
            event_type = step.get("event_type", "general")
            return self.future_memory_agent.query_habits(event_type)

        elif action == "record_event":
            title = step.get("title", "Event")
            event_type = step.get("type", "general")
            time = step.get("time")
            return self.future_memory_agent.record_event(title, event_type, time)

        elif action == "none":
            reason = step.get("message", "Unknown issue")
            return f"[Planner Error] {reason}"

        else:
            return f"Unknown action : {action}"

    def execute_plan(self, plan: dict):
        """
        Execute each step from planner.
        """
        if not plan or "steps" not in plan:
            return ["invalid plan format received."]

        results = []
        for step in plan["steps"]:
            results.append(self.execute_step(step))

        return results

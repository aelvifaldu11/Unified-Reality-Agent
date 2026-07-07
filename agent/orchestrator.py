import traceback
from typing import Any, Dict

from config.secrets_loader import SecretsLoader
from utils.logger import log
from agent.session_manager import SessionManager

#Attempt import for agents; Orchestrator is resilient, if agents not implemented yet, it will not lead to crashing

try:
    from agent.weather_agent import WeatherAgent
except Exception:
    WeatherAgent = None

try:
    from agent.calendar_agent import CalendarAgent
except Exception:
    CalendarAgent = None

try:
    from agent.reminder_agent import ReminderAgent
except Exception:
    ReminderAgent = None

try:
    from agent.planner_agent import PlannerAgent
except Exception:
    PlannerAgent = None

try:
    from agent.executor_agent import ExecutorAgent
except Exception:
    ExecutorAgent = None  

try:
    from agent.offline_mode import OfflineModeController
except Exception:
    OfflineModeController = None   



try:
    from agent.openai_runtime import OpenAIRuntime
except Exception:
    OpenAIRuntime = None


class Orchestrator:
    """
    Multi-agent orchestrator:
    1.Initializes the agents with a shared secrets loader and session manager
    2. Collects the context, asks planner for actions, executes them via executor
    3.Dispatches reminders
    """ 

    def __init__(self, mock_path: str="mock_path/"):
        self.secrets = SecretsLoader(mock_data_path= mock_path)
        self.session = SessionManager()
        self.offline = False

        self.weather_agent = WeatherAgent(self.secrets) if WeatherAgent else None
        self.calendar_agent = CalendarAgent(self.secrets) if CalendarAgent else None
        self.reminder_agent = ReminderAgent(self.secrets) if ReminderAgent else None
        self.planner_agent = PlannerAgent(self.secrets) if PlannerAgent else None
        self.executor_agent = ExecutorAgent(self.secrets) if ExecutorAgent else None
        self.offline_mode = OfflineModeController() if OfflineModeController else None

        self.openai_runtime = OpenAIRuntime(self.secrets) if (OpenAIRuntime and self.secrets.mode == "real") else None

    def collect_context(self) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {}


        try:
            if self.weather_agent:
                ctx["weather"] = self.weather_agent.get_weather()
            else:
                ctx["weather"] = self.secrets.load_mock_data("weather.json")
        except Exception:
            log("Orchestrator: weather collection failed")
            ctx["weather"] = {}
        

        try:
            if self.calendar_agent:
                ctx["calendar"] = self.calendar_agent.get_upcoming()
            else:
                ctx["calendar"] = self.secrets.load_mock_data("calendar.json")
        except Exception:
            log("Orchestrator: calendar collection failed")
            ctx["calendar"] = []


        ctx["session"] = self.session.load()
        return ctx
    

    
    def run_cycle(self, user_input: str) ->Dict[str, Any]:
        """
        Single Orchestrator Cycle:
        1. Collect context
        2. Compute reminders
        3. run planner
        4. execute actions
        5. return summary
        """

        try:
            


            self.session.add_to_history(user_input, "(awaiting response)")
            log("Orchestrator: starting of the cycle")
            ctx = self.collect_context()


            try:
                if self.offline_mode:
                    self.offline_mode.refresh_status()
                    self.offline = not self.offline_mode.is_online()
            except Exception:
                self.offline = False


            reminders = []
            try:
                if self.reminder_agent:
                    reminders = self.reminder_agent.evaluate(ctx)
                else:
                    reminders = []
            except Exception:
                log("Orchestrator: reminder evaluation failed")
                reminders = []

            #Planner: prefer vertex runtime and if not offline
            plan_actions = []
            
            try:
                if self.planner_agent:
                    plan = self.planner_agent.plan(user_input)
                    plan_actions = plan.get("steps", [])
                else:
                    plan_actions = []
            except Exception:
                log("Orchestrator: planner failed, falling back to empty actions")     
                plan_actions = []
                log(traceback.format_exc())


            executed = []
            try:
                if self.executor_agent:
                    for act in plan_actions:
                        try:
                            res_list = self.executor_agent.execute(act, ctx)      
                            res = res_list[0] if res_list else "No result"
                            executed.append({"Action": act ,"Result": res})  
                        except Exception as e:
                            executed.append({"Action": act, "Error": str(e)})
                else:
                    #no executer for planned actions
                    for act in plan_actions:
                        executed.append({"Action": act, "Result": "No execution of executor"})
            except Exception:
                log("Orchestrator: execution failed") 
            

            try:
                if self.reminder_agent and hasattr(self.reminder_agent, "dispatch"):
                   self.reminder_agent.dispatch(reminders)
            except Exception:
                log("Orchestrator: dispatch reminder failed")


            try:
                self.session.set("last_run_summary",{"reminders": reminders, "actions":plan_actions})
            except Exception:
                pass    
            log("Orchestrator cycle complete")
            return{"context": ctx, "reminders": reminders, "planned_actions": plan_actions, "executed": executed}

        except Exception as e:
            log(f"Orchestrator: fatal error {e}")
            log(traceback.format_exc())
            return{"error": str(e)}

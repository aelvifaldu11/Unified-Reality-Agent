"""
Unified Reality Agent - Starting point of the Agent
"""

from agent.offline_mode import OfflineModeController
from agent.planner_agent import PlannerAgent
from agent.executor_agent import ExecutorAgent
from agent.reminder_agent import ReminderAgent
from agent.weather_agent import WeatherAgent
from agent.calendar_agent import CalendarAgent
from agent.session_manager import SessionManager
from agent.openai_runtime import OpenAIRuntime

from config.secrets_loader import SecretsLoader

from utils.logger import log

def initialize_system():
    print("Initializing the Unified Reality Agent")

    secrets = SecretsLoader()
    secrets.load_env()

    offline = OfflineModeController()

    session = SessionManager()

    planner = PlannerAgent(secrets)
    executor = ExecutorAgent(secrets)
    reminder_agent = ReminderAgent(secrets)
    weather_agent = WeatherAgent(secrets)
    calendar_agent = CalendarAgent(secrets)

    # LLM runtime using OpenAI (replaces VertexRuntime)
    openai_runtime = OpenAIRuntime(secrets) if secrets.mode == "real" else None

    print("System ready.\n")
    return {
        "secrets": secrets,
        "offline": offline,
        "session": session,
        "planner": planner,
        "executor": executor,
        "reminder": reminder_agent,
        "weather": weather_agent,
        "calendar": calendar_agent,
        "openai_runtime": openai_runtime
    }
    
def demo_loop(ctx):
    print("Unified Reality Agent Demo Mode Started")
    print("Type 'exit' to quit.\n")
    
    """
    Manual chatbot testing environment
    """

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() == "exit":
            print("\n Exiting. Goodbye!")
            break

        log(f"User said: {user_input}")

        plan = ctx["planner"].plan(user_input)

        result = ctx["executor"].execute(plan, ctx)

        print(f"Agent: {result}\n")


def main():
    ctx = initialize_system()
    demo_loop(ctx)

main()
    
from utils.network_utils import has_internet

class OfflineModeController:
    """
    Controller to manage online/offline mode.
    - Detects internet availability using has_internet()
    - Provides fallback behavior when the system is offline
    - Used to enable 'Air-Gap Mode' (local-only operation)
    """
    def __init__(self):
        self.online = has_internet()

    def refresh_status(self):
        """Check again if network is available."""
        self.online = has_internet()

    def is_online(self) -> bool:
        """Return True is system is currently online."""
        return self.online

    def get_mode(self) -> str:
        return "online" if self.online else "offline"

    def respond(self, query: str) -> str:
        """
        Fallback behavior when agent is in offline mode.
        """
        if self.online:
            return "System is online. Full features available."

        #Offline fallback mode(Air-Gap)
        return (
            "You are currently offline.\n"
            "Running in AIR-GAP MODE.\n"
            "Features available:\n"
            " - Local planning\n"
            " - Local reminders\n"
            " - Task structuring\n"
            " - File operation\n"
            "Cloud/LLM functions are disabled."
        )

    

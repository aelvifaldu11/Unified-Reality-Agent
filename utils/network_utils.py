import socket

def has_internet(timeout : int = 3) -> bool:
    """
    Checks if machine has internet connection.
    Tries connecting to a public DNS server (Google DNS).
    """
    try:
        socket.setdefaulttimeout(timeout)

        # Try connecting to a stable public DNS server (Google DNS)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))

        return True
        
    except Exception:
        return False


"""Global kill switch: when engaged, every automated/AI action refuses to run."""
import threading

class KillSwitchEngaged(RuntimeError):
    pass

class KillSwitch:
    def __init__(self):
        self._stopped = threading.Event()
    def engage(self):
        self._stopped.set()
    def release(self):
        self._stopped.clear()
    @property
    def engaged(self):
        return self._stopped.is_set()
    def check(self):
        if self.engaged:
            raise KillSwitchEngaged("تم إيقاف الموظف (Kill Switch)")

KILL_SWITCH = KillSwitch()

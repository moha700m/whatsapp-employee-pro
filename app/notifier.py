"""Native Windows notifications: listens to the engine's private event stream and shows a toast (app name + icon, click → opens the chat)
with a soft original chime at the owner's volume. Off Windows (tests/CI) it only logs what it would show."""
import json, os, subprocess, sys, tempfile, threading, time, urllib.request, wave
from pathlib import Path
from xml.sax.saxutils import escape

AUMID = "MohammedAlzhrani.WhatsAppEmployee"
SHOWN = []   # for tests

def sounds_dir():
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    for d in (Path(sys.executable).resolve().parent / "engine" / "public" / "sounds", base / "engine" / "public" / "sounds", Path(__file__).resolve().parents[1] / "engine" / "public" / "sounds"):
        if d.exists(): return d
    return None

_cache = {}
def scaled(kind, vol):
    """WAV at the owner's volume (winsound has no volume control)."""
    key = (kind, int(vol)); src = (sounds_dir() or Path(".")) / f"{kind}.wav"
    if key in _cache or not src.exists(): return _cache.get(key)
    import array
    with wave.open(str(src), "rb") as w: p = w.getparams(); a = array.array("h", w.readframes(p.nframes))
    g = max(0.0, min(1.0, vol / 100)) ** 1.6
    a = array.array("h", (int(x * g) for x in a)); out = Path(tempfile.gettempdir()) / f"wae-{kind}-{int(vol)}.wav"
    with wave.open(str(out), "wb") as w: w.setparams(p); w.writeframes(a.tobytes())
    _cache[key] = out; return out

def toast_xml(ev):
    launch = "wae://chat/" + ev.get("jid", "") if ev.get("jid") else "wae://open"
    return (f'<toast activationType="protocol" launch="{escape(launch)}"><visual><binding template="ToastGeneric">'
            f'<text>{escape(ev.get("title", ""))}</text><text>{escape(ev.get("body", ""))}</text></binding></visual><audio silent="true"/></toast>')

def show(ev, log=print):
    SHOWN.append(ev)
    if os.name != "nt": log(f"NOTIFY would show {ev.get('kind')} sound={ev.get('sound')} vol={ev.get('volume')}"); return
    try:
        ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
              "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null;"
              "$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml([Console]::In.ReadToEnd());"
              f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{AUMID}').Show([Windows.UI.Notifications.ToastNotification]::new($x))")
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps], input=toast_xml(ev).encode("utf-8"),
                       creationflags=0x08000000, timeout=15, capture_output=True)
    except Exception as e: log(f"NOTIFY toast failed: {type(e).__name__}")
    if ev.get("sound"):
        try:
            import winsound; f = scaled(ev.get("kind", "msg"), ev.get("volume", 70))
            if f: winsound.PlaySound(str(f), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e: log(f"NOTIFY sound failed: {type(e).__name__}")

class Notifier:
    def __init__(self, url, key, log=print):
        self.url, self.key, self.log, self.stop_ = url.rstrip("/") + "/internal/notify-events", key, log, False
    def start(self): threading.Thread(target=self._run, daemon=True).start(); return self
    def stop(self): self.stop_ = True
    def _run(self):
        while not self.stop_:
            try:
                req = urllib.request.Request(self.url, headers={"x-notify-key": self.key})
                with urllib.request.urlopen(req, timeout=60) as r:
                    ev_type = None
                    for raw in r:
                        if self.stop_: return
                        line = raw.decode("utf-8", "replace").rstrip("\n")
                        if line.startswith("event:"): ev_type = line[6:].strip()
                        elif line.startswith("data:") and ev_type == "notify":
                            try: threading.Thread(target=show, args=(json.loads(line[5:]), self.log), daemon=True).start()
                            except Exception: pass
                        elif not line: ev_type = None
            except Exception: time.sleep(2)   # engine restarting → reconnect

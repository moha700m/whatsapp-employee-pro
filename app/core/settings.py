"""Typed auto-reply settings stored in the settings table."""
from dataclasses import dataclass, fields

@dataclass
class AutoReplySettings:
    auto_reply_enabled: bool = False      # employee ON/OFF: reads new messages and drafts replies (OFF by default)
    send_mode: str = "approval"           # "approval" = every reply waits for the user's click (only mode in the UI)
    min_delay: float = 8.0                # seconds before replying
    max_delay: float = 25.0
    typing_delay_ms: int = 60             # per character
    chat_cooldown: float = 120.0          # seconds between replies in one chat
    max_per_chat_hour: int = 4
    global_hour_cap: int = 40
    skip_groups: bool = True
    provider: str = "offline"             # offline (built-in brain) | auto/ollama (only if already running locally) | chatgpt_web (experimental)
    chatgpt_experimental: bool = False    # chatgpt_web is experimental and OFF unless explicitly enabled
    after_hours_auto: bool = False        # outside working hours: auto-send ONLY safe intents (greeting/thanks/delivery FAQ/...)
    retention_days: int = 0               # 0 = keep forever; else delete messages/replies older than N days
    backup_daily: bool = True
    poll_interval: float = 5.0
    show_browser: bool = False            # Chrome window visible or parked off-screen (never headless)
    opt_out_words: str = "لا ترسل,وقف,stop,الغاء الاشتراك,لا تراسلني,لا تتواصل"
    holding_reply: str = "أبشر، بيتواصل معك الزميل المختص قريب"

    @classmethod
    def load(cls, repo):
        s = cls()
        for f in fields(cls):
            raw = repo.get_setting("ar." + f.name, None)
            if raw is None:
                continue
            if f.type in (bool, "bool"):
                val = raw in ("1", "True", "true")
            elif f.type in (int, "int"):
                val = int(float(raw))
            elif f.type in (float, "float"):
                val = float(raw)
            else:
                val = raw
            setattr(s, f.name, val)
        if s.max_delay < s.min_delay:
            s.max_delay = s.min_delay
        return s

    def save(self, repo):
        for f in fields(self):
            v = getattr(self, f.name)
            repo.set_setting("ar." + f.name, int(v) if isinstance(v, bool) else v)

    @property
    def opt_out_list(self):
        return [w.strip() for w in self.opt_out_words.split(",") if w.strip()]

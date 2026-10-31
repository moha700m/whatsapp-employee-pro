"""Parse pasted chat text or WhatsApp exported .txt files."""
import re
from dataclasses import dataclass

@dataclass
class Message:
    sender: str
    text: str
    timestamp: str = ""

# Android: 12/31/23, 9:15 PM - Name: text   | iOS: [31/12/2023, 21:15:03] Name: text
_ANDROID = re.compile(r"^\u200e?(\d{1,2}[/.]\d{1,2}[/.]\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?\s?(?:[AaPp][Mm]|ص|م)?)\s+[-–]\s+([^:]+?):\s(.*)$")
_IOS = re.compile(r"^\u200e?\[(\d{1,2}[/.]\d{1,2}[/.]\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?\s?(?:[AaPp][Mm]|ص|م)?)\]\s+([^:]+?):\s(.*)$")
_SIMPLE = re.compile(r"^([^:\n]{1,40}):\s(.+)$")
_SYSTEM_HINTS = ("end-to-end encrypted", "مشفرة", "<Media omitted>", "تم استبعاد الوسائط")

def parse_chat(text: str):
    msgs = []
    for raw in (text or "").splitlines():
        line = raw.strip().replace("\u202f", " ")
        if not line or any(h in line for h in _SYSTEM_HINTS):
            continue
        m = _ANDROID.match(line) or _IOS.match(line)
        if m:
            date, time, sender, body = m.groups()
            if any(h in body for h in _SYSTEM_HINTS):
                continue
            msgs.append(Message(sender.strip(), body.strip(), f"{date} {time}".strip()))
            continue
        m = _SIMPLE.match(line)
        if m and not line.startswith("http"):
            msgs.append(Message(m.group(1).strip(), m.group(2).strip()))
        elif msgs:  # continuation of multi-line message
            msgs[-1].text += "\n" + line
        else:
            msgs.append(Message("العميل", line))
    return msgs

def parse_file(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return parse_chat(f.read())

def guess_customer(msgs, me_names=("أنا", "me", "Me", "You", "أنت")):
    for m in msgs:
        if m.sender not in me_names:
            return m.sender
    return msgs[0].sender if msgs else "غير معروف"

_PHONE = re.compile(r"(?:\+|00)?9665\d{8}|05\d{8}|\+\d{10,14}")
def find_phone(msgs, customer=""):
    for s in [customer] + [m.text for m in msgs]:
        p = _PHONE.search(s.replace(" ", ""))
        if p:
            return p.group(0)
    return ""

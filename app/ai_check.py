"""v2.3 AI gate (CI + pytest): Saudi quality on fixed samples, latency per reply, RAM of the model process, and the fallback path.
Uses a made-up shop and made-up messages only (no real customer data)."""
import os, time
from app import brain_server as BS
from app.brain import ai as AI
from app.brain.llm import LocalLLM

SHOP = {"name": "ورد التجربة", "city": "الرياض", "location": "الرياض", "hours": "4:00 م - 12:00 ص", "delivery": "توصيل داخل الرياض 30 ريال"}
SAMPLES = ["السلام عليكم عندكم ورد جوري؟", "كم سعر بوكيه الجوري؟", "ابي ورد لزوجتي بمناسبة المولود وش تنصحوني", "غالي مره، فيه شي أرخص؟", "توصلون حي النرجس اليوم؟"]
SAUDI = ("هلا", "والله", "أبشر", "ابشر", "وش", "عندنا", "تبي", "تبغى", "حياك", "إيه", "ايه", "يا هلا", "أكيد", "زين", "عشان", "نوصل", "وين")

def run(max_ms=30000, need_ai=2):
    out = {"samples": [], "ok": True, "problems": []}
    llm = LocalLLM(); BS.LLM = llm; st = llm.status(); out["status0"] = st
    if not st["available"]: out["ok"] = False; out["problems"].append("model unavailable: " + st["reason"]); return out
    t0 = time.time(); llm.ensure(); out["load_s"] = round(time.time() - t0, 1)
    ai_n = 0
    for t in SAMPLES:
        t1 = time.time(); r = BS.do_think({"text": t, "ai": True, "shop": SHOP}); ms = int((time.time() - t1) * 1000)
        issues = AI.guard(BS.Brain(kb=BS.make_kb({"shop": SHOP})), r["reply"], None)
        saudi = any(w in r["reply"] for w in SAUDI)
        out["samples"].append({"q": t, "a": r["reply"], "engine": r["engine"], "ms": ms, "rejected": r.get("ai_rejected"), "saudi": saudi})
        ai_n += r["engine"] == "ai"
        if issues: out["problems"].append(f"bad reply for {t}: {issues}")
        if ms > max_ms: out["problems"].append(f"slow {ms} ms: {t}")
    if ai_n < need_ai: out["problems"].append(f"only {ai_n}/5 replies came from the model")
    # «اكتب بالذكاء» in Marketing must return model text on the installed build
    m = BS.do_mkt_draft({"ai": True, "goal": "متابعة عميل ما رد", "template": "هلا {الاسم} 🌷 حبينا نطمن عليك", "shop": SHOP})
    out["mkt"] = m
    if not m["text"] or m["text"] == "هلا {الاسم} 🌷 حبينا نطمن عليك" or m["engine"] not in ("ai", "library") or "model" in str(m.get("reason", "")): out["problems"].append(f"marketing draft returned nothing: {m.get('reason')}")
    if m["engine"] == "library" and "مطفي" in str(m.get("reason", "")): out["problems"].append("marketing draft did not reach the model: " + str(m.get("reason")))
    st = llm.status(); out["rss_mb"] = st["rss_mb"]; out["avg_ms"] = st["avg_ms"]
    # fallback: a small PC (4 GB) must never try the model and still answer with the rule brain
    os.environ["WAE_FAKE_RAM_GB"] = "4"
    try:
        small = LocalLLM(); BS.LLM = small; r = BS.do_think({"text": SAMPLES[1], "ai": True, "shop": SHOP})
        out["fallback"] = {"available": small.available()[0], "engine": r["engine"], "reply": r["reply"]}
        if small.available()[0] or r["engine"] != "rules" or not r["reply"]: out["problems"].append("fallback failed")
    finally: os.environ.pop("WAE_FAKE_RAM_GB", None); BS.LLM = llm
    # broken model process → rule reply, no crash
    llm.stop(); bad = LocalLLM(); bad.exe = bad.exe.parent / "missing-llama-server.exe" if bad.exe else None; bad.exe = None; BS.LLM = bad
    r = BS.do_think({"text": SAMPLES[0], "ai": True, "shop": SHOP}); out["missing_files_engine"] = r["engine"]
    if r["engine"] != "rules": out["problems"].append("missing-files fallback failed")
    out["ok"] = not out["problems"]; return out

def report(o):
    L = [f"AI TEST {'OK' if o['ok'] else 'FAILED'} load={o.get('load_s')}s avg={o.get('avg_ms')}ms rss={o.get('rss_mb')}MB ram={o['status0'].get('ram_gb')}GB threads={o['status0'].get('threads')}"]
    for s in o["samples"]: L.append(f"  [{s['engine']} {s['ms']}ms] {s['q']} => {s['a']}" + (f"  (rejected: {s['rejected']})" if s.get("rejected") else ""))
    if "fallback" in o: L.append(f"  fallback(4GB): available={o['fallback']['available']} engine={o['fallback']['engine']} => {o['fallback']['reply']}")
    if "mkt" in o: L.append(f"  marketing draft [{o['mkt']['engine']}] {o['mkt']['text']}")
    L.append(f"  missing files → {o.get('missing_files_engine')}")
    L += ["  PROBLEM: " + p for p in o["problems"]]
    return "\n".join(L)

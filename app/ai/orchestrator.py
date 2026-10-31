import re
"""AI Orchestrator: understanding -> customer analysis -> reply -> classification ->
follow-up suggestion -> quality check. Each stage is a separate, testable method."""
from datetime import date, timedelta
from app.core.kill_switch import KILL_SWITCH
from app.ai import analyzer
from app.ai.replies import build_reply, PRICE_RE

FOLLOW_DAYS = {"Hot Lead": 1, "Interested": 2, "Follow-up": 3, "New Lead": 2, "Support": 1, "Existing Customer": 7}

class Orchestrator:
    def __init__(self, provider=None, kill_switch=KILL_SWITCH, workflow=None):
        self.provider = provider
        self.ks = kill_switch
        self.workflow = workflow   # dict from app.core.workflow; None = built-in defaults

    def understand(self, msgs, customer):
        texts = [m.text for m in msgs if m.sender == customer]
        return {"customer_texts": texts or [m.text for m in msgs]}

    def analyze_customer(self, ctx, business_info):
        cls, scores = analyzer.classify(ctx["customer_texts"])
        matched = analyzer.match_business(ctx["customer_texts"], business_info)
        if cls == "New Lead" and matched:
            cls = "Interested"
        need = analyzer.extract_need(ctx["customer_texts"], matched)
        asked_price = bool(re.search(r"(سعر|بكم|كم تكلف|تكلفه|price|cost)", analyzer._norm(" ".join(ctx["customer_texts"]))))
        return {"classification": cls, "scores": scores, "matched": matched, "need": need, "asked_price": asked_price}

    def suggest_follow_up(self, classification):
        if classification == "Complaint":
            return None
        return (date.today() + timedelta(days=FOLLOW_DAYS.get(classification, 3))).isoformat()

    def quality_check(self, reply, business_info, recent=()):
        issues = []
        allowed = " ".join(f"{b.get('price','')} {b.get('content','')}" for b in business_info)
        for p in PRICE_RE.findall(reply):
            if p not in allowed:
                issues.append(f"سعر غير معتمد: {p}")
        max_len = (self.workflow or {}).get("tone", {}).get("max_len", 300) or 300
        if len(reply) > max_len + 20:
            issues.append("الرد طويل")
        if reply in set(recent):
            issues.append("رد مكرر")
        return issues

    def brain_for(self, business_info):
        """Built-in knowledge brain, with the owner's approved business_info prices merged into the price table."""
        from app.brain.engine import Brain
        from app.brain.knowledge import load_kb
        kb = load_kb(self.repo) if getattr(self, "repo", None) is not None else load_kb()
        own = [b for b in business_info or [] if b.get("title")]
        if own:   # the owner's approved items replace the default flower table
            kb["products"] = [p for p in kb["products"] if p["category"] in ("خدمات", "إضافات") and False]
        for b in own:
            m = re.search(r"\d+(?:\.\d+)?", str(b.get("price") or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
            if b.get("title"):
                kb["products"].append({"name": b["title"], "aliases": [], "price": float(m.group(0)) if m else None,
                                       "price_text": str(b.get("price") or ""), "unit": "بوكيه", "category": b.get("kind") or "منتج"})
        return Brain(kb=kb)

    def run(self, msgs, customer, business_info, recent_replies=(), rng=None):
        self.ks.check()
        ctx = self.understand(msgs, customer)
        self.ks.check()
        info = self.analyze_customer(ctx, business_info)
        cls = info["classification"]
        handoff, reason = analyzer.detect_handoff(ctx["customer_texts"], cls)
        reply = build_reply(customer, cls, info["matched"], info["asked_price"], recent_replies, rng)
        provider = "heuristic"
        brain = None; used_brain = False
        try:
            from app.brain.engine import think
            b = self.brain_for(business_info)
            brain = think("\n".join(ctx["customer_texts"][-3:]), customer, kb=b.kb, rng=rng)
            if brain["kind"] not in ("fallback", "guarded") and brain["reply"] not in set(recent_replies):
                reply, used_brain = brain["reply"], True
            if brain["kind"] == "handoff" and not handoff:
                handoff, reason = True, "شكوى أو طلب موظف"
        except Exception:
            brain = None
        from app.core.safety import is_injection, clean_reply
        injected = any(is_injection(t) for t in ctx["customer_texts"])
        if injected:   # customer text tried to give the AI orders: never pass it to the model, flag it for the owner
            handoff, reason = True, "رسالة فيها محاولة توجيه للبوت — راجعها بنفسك"
        if self.provider is not None and self.provider.available() and not injected:
            try:
                reply = clean_reply(self.provider.complete(self.build_prompt(msgs, customer, business_info))) or reply
                provider = self.provider.name
            except Exception:
                pass
        issues = self.quality_check(reply, business_info, recent_replies)
        if used_brain and provider == "heuristic":   # brain prices are checked against its own approved price table instead
            issues = [i for i in issues if not i.startswith("سعر غير معتمد")] + self.brain_for(business_info).guard(reply, brain["entities"])
        elif brain is not None and provider != "heuristic":
            issues += self.brain_for(business_info).guard(reply, brain["entities"])
        if issues:  # fall back to the safe heuristic reply
            reply = build_reply(customer, cls, info["matched"], info["asked_price"], recent_replies, rng)
            provider = "heuristic"
        if self.workflow:
            from app.core.workflow import apply_tone
            reply = apply_tone(reply, self.workflow)
        self.ks.check()
        return {"summary": analyzer.summarize(msgs, customer, cls), "need": info["need"],
                "classification": cls, "handoff": handoff, "handoff_reason": reason,
                "reply": reply, "follow_up": self.suggest_follow_up(cls), "provider": provider,
                "quality_issues": issues, "brain": brain, "engine": "brain" if used_brain and provider == "heuristic" else provider,
                "missing_price": info["asked_price"] and not any(b.get("price") for b in info["matched"])}

    def build_prompt(self, msgs, customer, business_info):
        from app.core.workflow import DEFAULT_PROMPT
        wf = self.workflow or {}
        tone = wf.get("tone", {"dialect": "السعودية", "max_len": 300, "emoji": True})
        biz = "\n".join(f"- {b['title']}: {b['content']} {b.get('price','')}".rstrip() for b in business_info) or "لا يوجد"
        from app.core.safety import wrap_customer, sanitize
        chat = wrap_customer("\n".join(f"{sanitize(m.sender, 60)}: {m.text}" for m in msgs[-20:]))
        vals = {"business": biz, "chat": chat, "customer": customer, "dialect": tone["dialect"],
                "max_len": tone["max_len"], "business_name": wf.get("business", {}).get("name") or "النشاط",
                "emoji_rule": "" if tone["emoji"] else "لا تستخدم أي إيموجي."}
        out = wf.get("chatgpt_prompt") or DEFAULT_PROMPT
        for k, v in vals.items():
            out = out.replace("{" + k + "}", str(v))
        if "{chat}" not in (wf.get("chatgpt_prompt") or DEFAULT_PROMPT):
            out += "\n\nالمحادثة:\n" + chat
        return out

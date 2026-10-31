"""Application service glue between UI, DB and AI (UI-independent, testable)."""
from app.core.parser import parse_chat, guess_customer, find_phone
from app.core.logger import log_activity
from app.ai.orchestrator import Orchestrator

class EmployeeService:
    def __init__(self, repo, orchestrator=None):
        self.repo = repo
        self.orch = orchestrator or Orchestrator()

    def analyze_text(self, text, customer=None, source="paste", title=""):
        msgs = parse_chat(text)
        if not msgs:
            raise ValueError("لا توجد رسائل قابلة للتحليل")
        customer = customer or guess_customer(msgs)
        recent = [r["text"] for r in self.repo.recent_replies()]
        res = self.orch.run(msgs, customer, self.repo.business_info(), recent)
        cid = self.repo.upsert_customer(customer, find_phone(msgs, customer))
        self.repo.update_customer(cid, classification=res["classification"], stage=res["classification"]
                                  if res["classification"] in ("New Lead","Interested","Hot Lead","Existing Customer") else None,
                                  need=res["need"], follow_up_date=res["follow_up"])
        conv = self.repo.add_conversation(cid, msgs, title or customer, source)
        aid = self.repo.save_analysis(conv, res, res["provider"])
        if res["follow_up"]:
            self.repo.add_follow_up(cid, res["follow_up"], "")
        log_activity(self.repo.db, "analyze", f"{customer}: {res['classification']} handoff={res['handoff']}")
        res.update(customer_id=cid, conversation_id=conv, analysis_id=aid, customer=customer)
        return res

"""Saudi flower-shop AI layer on top of the rule brain.
The rule brain decides WHAT to do (intent, handoff, prices from the owner's list); the local model only says it naturally in Saudi dialect.
Every model output passes guards (prices, forbidden words, Arabic, length) or we fall back to the rule reply."""
import json, re
from app.brain.normalize import norm, fuzzy_in, tokens, sar
from app.brain.knowledge import CARE_TIPS, FLOWER_MEANINGS

DEFAULT_TEACH = {
    "persona": "موظفة مبيعات سعودية في محل ورد، ودودة ومحترفة وتحب الورد",
    "tone": "سعودي عامي خفيف، جمل قصيرة، إيموجي ورد واحد بالكثير",
    "dos": ["رحّب بالعميل باسمه إذا تعرفه", "اسأل عن المناسبة واليوم والحي إذا ناقصة", "اقترح شي يكمل الهدية (بطاقة، شوكولاتة، بالون) بدون إلحاح",
            "خلك مختصر: سطرين بالكثير"],
    "donts": ["لا تعطي سعر مو موجود بقائمة الأسعار", "لا تأكد طلب أو دفع — هذا شغل صاحب المحل", "لا توعد بموعد توصيل أكيد", "لا تتكلم بالسياسة أو الدين أو أي موضوع برا المحل",
              "لا تطلب بيانات بنكية"],
    "faq": [], "examples": [
        {"q": "السلام عليكم عندكم ورد جوري؟", "a": "وعليكم السلام ورحمة الله، هلا والله 🌹 إيه عندنا جوري أحمر وأبيض ووردي، لأي مناسبة تبيه؟"},
        {"q": "غالي شوي", "a": "أفهمك والله، عندنا خيارات أوفر وبرضو شكلها يفتح النفس 🌷 وش ميزانيتك تقريباً وأختار لك الأنسب؟"},
        {"q": "متى توصلون؟", "a": "نوصل داخل المدينة، وإذا طلبت بدري نقدر نوصله نفس اليوم إن شاء الله. وين الحي؟"}],
    "forbidden": ["سياسة", "دين", "قرض", "حساب بنكي"],
    "handoff": ["طلب مؤكد", "دفع", "شكوى", "استرجاع", "خصم خاص", "طلبات كبيرة للشركات"],
}

def merged_teach(t):
    t = t if isinstance(t, dict) else {}
    out = {k: (t.get(k) if t.get(k) not in (None, "") else v) for k, v in DEFAULT_TEACH.items()}
    for k in ("dos", "donts", "forbidden", "handoff"): out[k] = [str(x)[:200] for x in (out[k] or []) if str(x).strip()][:30]
    for k in ("faq", "examples"): out[k] = [{"q": str(x.get("q", ""))[:300], "a": str(x.get("a", ""))[:500]} for x in (out[k] or []) if isinstance(x, dict) and x.get("q") and x.get("a")][:60]
    return out

def _overlap(a, b):
    ta, tb = set(tokens(a)), set(tokens(b))
    return len(ta & tb) / (len(ta) or 1)

def faq_answer(teach, text, threshold=0.5):
    """Owner-written FAQ: a close match is answered word-for-word (works with or without the model)."""
    best, score = None, 0.0
    for f in merged_teach(teach)["faq"]:
        s = max(_overlap(f["q"], text), 1.0 if norm(f["q"]) in norm(text) and len(norm(f["q"])) > 6 else 0)
        if s > score: best, score = f, s
    return best["a"] if best and score >= threshold else None

def handoff_hit(teach, text):
    return next((h for h in merged_teach(teach)["handoff"] if len(h) > 2 and fuzzy_in(h, text, 0.88)), None)

def forbidden_hit(teach, text):
    """Whole-word match (so «دين» does not hit «المدينة»); phrases match as a substring."""
    t = norm(text); words = set(tokens(text))
    for w in merged_teach(teach)["forbidden"]:
        n = norm(w)
        if len(n) < 2: continue
        if (" " in n and n in t) or n in words or any(x in words for x in ("ال" + n, "و" + n, "بال" + n, "لل" + n)): return w
    return None

def knowledge(kb, text, teach, k=6):
    """Small RAG: only the facts relevant to this message (keeps the prompt — and the CPU work — small)."""
    t = merged_teach(teach); lines = []
    prods = [p for p in kb["products"] if p.get("price")]
    hit = [p for p in prods if any(fuzzy_in(a, text, 0.86) for a in [p["name"], *p.get("aliases", [])])]
    show = (hit + [p for p in prods if p not in hit])[:k]
    if show: lines.append("الأسعار (لا تذكر غيرها): " + "، ".join(f"{p['name']} {sar(p['price'])}" for p in show))
    s = kb.get("shop", {})
    lines.append(f"المحل: {s.get('name','')}، {s.get('location') or s.get('city','')}. الدوام: {s.get('hours','')}.")
    if s.get("delivery"): lines.append("التوصيل: " + s["delivery"])
    if s.get("about"): lines.append("عن المحل: " + s["about"])
    faqs = sorted(t["faq"] + [{"q": " ".join(f["q"]), "a": f["a"]} for f in kb.get("faq", [])], key=lambda f: -_overlap(f["q"], text))[:3]
    for f in faqs:
        if _overlap(f["q"], text) > 0.2: lines.append(f"سؤال شائع: {f['q']} ← {f['a']}".replace("{location}", s.get("location", "")).replace("{hours}", s.get("hours", "")))
    for f, m in FLOWER_MEANINGS.items():
        if fuzzy_in(f.split()[0], text, 0.9): lines.append(f"معنى {f}: {m}")
    if any(w in norm(text) for w in ("يذبل", "ذبل", "احافظ", "اسقي", "يعيش", "عنايه")): lines.append("عناية: " + " ".join(CARE_TIPS[:3]))
    occ = [o for o, v in kb["occasions"].items() if any(fuzzy_in(a, text, 0.88) for a in [o, *v.get("aliases", [])])]
    for o in occ[:1]: lines.append(f"مناسبة {o}: ألوان {kb['occasions'][o].get('colors','')}، نقترح {('، '.join(kb['occasions'][o].get('suggest', [])))}")
    return "\n".join(lines)

def system_prompt(kb, teach, facts):
    t = merged_teach(teach)
    return (f"أنت {t['persona']}. أسلوبك: {t['tone']}.\n"
            "تكلم باللهجة السعودية فقط (مثل: هلا والله، أبشر، وش، ليش، الحين، زين، إن شاء الله). لا تستخدم الفصحى الرسمية ولا الإنجليزي.\n"
            "سوّ: " + "؛ ".join(t["dos"]) + ".\n"
            "لا تسوي: " + "؛ ".join(t["donts"]) + ".\n"
            "إذا ما تعرف المعلومة قل إن صاحب المحل بيرد عليه، ولا تألف.\n"
            "اكتب الرد فقط بدون شرح، سطر أو سطرين.\n"
            "معلومات المحل:\n" + facts)

def few_shot(teach, text, n=3):
    ex = sorted(merged_teach(teach)["examples"], key=lambda e: -_overlap(e["q"], text))[:n]
    out = []
    for e in ex: out += [{"role": "user", "content": e["q"]}, {"role": "assistant", "content": e["a"]}]
    return out

AR = re.compile(r"[\u0600-\u06FF]")
FUSHA = ["سوف", "لدينا", "يمكنكم", "نود", "حضرتك", "عزيزي العميل", "نحن سعداء"]
def clean(reply):
    r = (reply or "").strip().strip('"').strip()
    r = re.sub(r"^(الرد|رد|الموظف|assistant)\s*[:：]\s*", "", r)
    r = re.sub(r"\n{2,}", "\n", r)
    # keep only shop-friendly emoji (a small model sometimes throws in random ones), at most two
    EMO = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]\uFE0F?")
    ok = set("🌹🌷🌸💐🌺🌼🌻🤍❤🙏😊🎁🎈✨👌💚")
    seen = [0]
    def keep(m):
        ch = m.group(0)[0]
        if ch in ok and seen[0] < 2: seen[0] += 1; return m.group(0)
        return ""
    r = EMO.sub(keep, r)
    r = re.sub(r"\s+([؟?!.،])", r"\1", re.sub(r"[ \t]{2,}", " ", r)).strip()
    return r[:420]

def guard(brain, reply, teach, e=None):
    issues = list(brain.guard(reply, e))
    if not AR.search(reply or ""): issues.append("ليس عربي")
    if re.search(r"[A-Za-z]{4,}", reply or ""): issues.append("فيه إنجليزي")
    if forbidden_hit(teach, reply): issues.append("كلمة ممنوعة")
    if re.search(r"(تم تاكيد|تم تأكيد|اكدنا طلبك|أكدنا طلبك)", reply or ""): issues.append("تأكيد طلب")
    if len(reply or "") > 230: issues.append("طويل")
    if len(re.findall(r"\d+\s*(?:ر\.?س|ريال)", reply or "")) > 2: issues.append("سرد أسعار كثير")
    if MSA.search(reply or ""): issues.append("فصحى مو سعودي")
    return issues

# Phrases a small model produces when it slips into formal Arabic; any of them → use the rule reply instead.
MSA = re.compile(r"(عذرا|عذراً|دعني|أنا ب|انا ب|إذا كان|اذا كان|لاحظ|يرجى|نود|يمكنك|سوف |لديك|لدينا|حسنا|حسناً|عزيزي العميل|نعم،|ماذا|لماذا|هل تريد|الذي|التي|😘|أنا أعرف|انا اعرف|هل |يبلغ|تجدون|يمكن|هنالك|هناك|علماً|علما،|ما هي|أيضاً|ايضاً|أنتي|انتي|متأكد منك|مشكلة|بكل سرور|من فضلك|^نعم|أين |تعيش|هادا|عند الحين|أعتذر|اعتذر|أستطيع|استطيع|نموذج|ذكاء اصطناعي|كمساعد|مساعد افتراضي|لا يمكنني|عذراً)")

def history_msgs(messages, n=4):
    out = []
    for m in (messages or [])[-n:]:
        if m.get("text"): out.append({"role": "assistant" if m.get("fromMe") else "user", "content": str(m["text"])[:400]})
    return out

def ai_reply(llm, brain, kb, teach, text, history=None, rule_reply="", hint="", max_tokens=90, temperature=0.3, retry=True):
    facts = knowledge(kb, text, teach)
    sys_p = system_prompt(kb, teach, facts) + (f"\nفكرة الرد المقترحة (أعد صياغتها بأسلوبك ولا تغيّر الأسعار): {rule_reply}" if rule_reply else "") + (f"\n{hint}" if hint else "")
    msgs = [{"role": "system", "content": sys_p}] + few_shot(teach, text) + (history or []) + [{"role": "user", "content": text[:600]}]
    e = brain.extract(text)
    def one(temp):
        o = clean(llm.chat(msgs, max_tokens=max_tokens, temperature=temp)); iss = guard(brain, o, teach, e)
        if o.startswith("وعليكم السلام") and not re.search(r"السلام|سلام", text): iss.append("رد سلام بدون سلام")
        return o, iss
    out, issues = one(temperature)
    if issues and retry: out, issues = one(0.7)      # one more try with a different sample, then the caller falls back to the rule reply
    return out, issues

def ai_json(llm, prompt, text, max_tokens=200, wait=12):
    raw = llm.chat([{"role": "system", "content": prompt}, {"role": "user", "content": text[:2500]}], max_tokens=max_tokens, temperature=0.1, json_mode=True, wait=wait)
    try: return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except Exception: return {}

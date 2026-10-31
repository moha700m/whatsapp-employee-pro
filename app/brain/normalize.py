"""Arabic normalisation + fuzzy matching (alef, taa marbuta, yaa, diacritics, tatweel, Arabic digits)."""
import re
from difflib import SequenceMatcher

_DIAC = re.compile("[\u064B-\u0652\u0670\u0640]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

def norm(t):
    t = _DIAC.sub("", str(t or "")).translate(_DIGITS)
    t = re.sub("[إأآٱا]", "ا", t).replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    t = re.sub(r"(.)\1{2,}", r"\1", t)          # هلااااا -> هلا
    return re.sub(r"\s+", " ", t).strip().lower()

def tokens(t):
    return re.findall(r"[\w]+", norm(t))

def _strip_al(w):
    for p in ("وال", "بال", "فال", "لل", "ال"):
        if w.startswith(p) and len(w) - len(p) >= 2:
            return w[len(p):]
    return w

def fuzzy_in(term, text, threshold=0.84):
    """True if normalised term appears in text exactly or approximately (per token window)."""
    nt, nx = norm(term), norm(text)
    if not nt: return False
    if nt in nx: return True
    tt = [_strip_al(w) for w in nt.split()]
    xt = [_strip_al(w) for w in nx.split()]
    n = len(tt)
    for i in range(len(xt) - n + 1):
        cand = " ".join(xt[i:i+n]); want = " ".join(tt)
        if cand == want or (len(want) >= 6 and SequenceMatcher(None, cand, want).ratio() >= threshold):
            return True
    return False

def any_in(terms, text, threshold=0.84):
    return [t for t in terms if fuzzy_in(t, text, threshold)]

def phone966(raw):
    """Format Saudi mobile numbers as +9665XXXXXXXX; returns '' if not a Saudi mobile."""
    d = re.sub(r"\D", "", str(raw or "").translate(_DIGITS))
    if d.startswith("00966"): d = d[5:]
    elif d.startswith("966"): d = d[3:]
    elif d.startswith("0"): d = d[1:]
    return "+966" + d if re.fullmatch(r"5\d{8}", d) else ""

def sar(amount):
    a = float(amount)
    return (f"{int(a):,}" if a == int(a) else f"{a:,.2f}") + " ر.س"

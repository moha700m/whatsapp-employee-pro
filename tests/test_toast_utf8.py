import os, subprocess, base64, pytest
from app import notifier as n

AR = {"kind": "msg", "title": "موظف واتساب", "body": "لزالو: ابي بوكيه ورد أحمر بـ ١٥٠ ريال 🌹 <عاجل> & \"شكراً\"", "jid": "966500000000@s.whatsapp.net"}

def test_xml_escaped_and_rtl():
    x = n.toast_xml(AR)
    assert "&lt;عاجل&gt; &amp; &quot;شكراً&quot;" in x and "\u200f" in x and 'lang="ar-SA"' in x
    import xml.dom.minidom; xml.dom.minidom.parseString(x.encode("utf-8"))

def test_command_line_is_ascii():
    a = n.ps_args(n.ps_script(n.toast_xml(AR)))
    assert all(s.isascii() for s in a)
    assert base64.b64decode(a[-1]).decode("utf-16-le").isascii()

@pytest.mark.skipif(os.name != "nt", reason="needs Windows PowerShell")
def test_powershell_roundtrip_exact(tmp_path):
    x = n.toast_xml(AR); out = tmp_path / "out.xml"
    r = subprocess.run(n.ps_args(n.ps_script(x, dump=out)), capture_output=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert out.read_bytes().decode("utf-8") == x

@pytest.mark.skipif(os.name != "nt", reason="needs Windows")
def test_real_toast_shows():
    r = subprocess.run(n.ps_args(n.ps_script(n.toast_xml(AR))), capture_output=True, timeout=60)
    assert r.returncode == 0, r.stderr

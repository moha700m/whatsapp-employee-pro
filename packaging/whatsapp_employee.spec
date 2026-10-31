# PyInstaller spec (one-folder). Build on Windows:  pyinstaller packaging\whatsapp_employee.spec --noconfirm
# Output: dist\WhatsAppEmployee\WhatsAppEmployee.exe ; user data goes to data\ next to the exe.
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
datas = [(os.path.join(ROOT, "app", "web", "static"), os.path.join("app", "web", "static")),
         (os.path.join(ROOT, "README_AR.md"), ".")]
datas += collect_data_files("webview")
a = Analysis([os.path.join(ROOT, "main.py")], pathex=[ROOT], datas=datas,
             hiddenimports=collect_submodules("app") + collect_submodules("webview") + ["playwright.sync_api", "pystray._win32", "PIL.Image"],
             excludes=["tkinter", "pytest", "_pytest"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="WhatsAppEmployee", console=False,
          icon=os.path.join(ROOT, "app", "web", "static", "icon.ico"),
          version=os.path.join(SPECPATH, "version_info.txt"))
coll = COLLECT(exe, a.binaries, a.datas, name="WhatsAppEmployee")

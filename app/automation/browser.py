import time
"""One persistent Chrome profile (inside data/chrome-profile) shared by WhatsApp and ChatGPT tabs.
The user logs in himself (QR / ChatGPT login). We never read cookies or tokens."""
from app import config
from app.core.logger import get_logger

PROFILE_DIR = config.DATA_DIR / "chrome-profile"

class BrowserSession:
    def __init__(self, headless=False, visible=None):
        self.headless = headless          # never headless for WhatsApp (it may refuse); we move the window instead
        if visible is None:
            try:
                from app.db.database import Database
                from app.db.repository import Repository
                visible = Repository(Database()).get_setting("ar.show_browser", "0") in ("1", "True")
            except Exception:
                visible = False
        self.visible = visible
        self._pw = self.context = None

    def start(self):
        if self.context:
            return self.context
        from playwright.sync_api import sync_playwright
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        args = dict(user_data_dir=str(PROFILE_DIR), headless=self.headless, no_viewport=True,
                    args=self._window_args(), locale="ar-SA")
        try:
            self.context = self._pw.chromium.launch_persistent_context(channel="chrome", **args)
        except Exception as e:  # Chrome not installed -> bundled Chromium (playwright install chromium)
            get_logger().warning("Chrome channel failed (%s); trying Microsoft Edge", e)
            try:   # Edge ships with every Windows 10/11 PC -> no browser download needed for the .exe build
                self.context = self._pw.chromium.launch_persistent_context(channel="msedge", **args)
            except Exception as e2:
                get_logger().warning("Edge channel failed (%s); falling back to bundled Chromium", e2)
                self.context = self._pw.chromium.launch_persistent_context(**args)
        return self.context

    def _window_args(self):
        if self.visible:
            return ["--start-maximized"]
        # real (non-headless) window placed off-screen so it doesn't bother the user
        return ["--window-position=-32000,-32000", "--window-size=1280,900"]

    def set_visible(self, page, visible):
        """Show/hide the Chrome window via the DevTools window API (no restart)."""
        self.visible = visible
        try:
            cdp = page.context.new_cdp_session(page)
            wid = cdp.send("Browser.getWindowForTarget")["windowId"]
            if visible:
                cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"windowState": "normal"}})
                cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"left": 60, "top": 40, "width": 1280, "height": 860}})
                page.bring_to_front()
            else:
                cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"windowState": "normal"}})
                cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"left": -32000, "top": -32000}})
            return True
        except Exception as e:
            get_logger().warning("set_visible failed: %s", e)
            return False


    def _reset(self):
        try: self.close()
        except Exception: pass

    def page_for(self, url_prefix, url, _attempt=0):
        """Find/open a tab. Relaunches the persistent context if Chrome was closed; retries aborted navigations."""
        try:
            ctx = self.start()
            for p in ctx.pages:
                if not p.is_closed() and p.url.startswith(url_prefix):
                    return p
            blank = [p for p in ctx.pages if not p.is_closed() and p.url in ("about:blank", "")]
            page = blank[0] if blank else ctx.new_page()
            for i in range(3):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000); break
                except Exception as e:
                    if i == 2 or "closed" in str(e).lower(): raise
                    get_logger().warning("goto retry %s: %s", i + 1, e); time.sleep(1.5 * (i + 1))
                    if page.is_closed(): page = ctx.new_page()
            return page
        except Exception as e:
            if _attempt < 2 and ("closed" in str(e).lower() or "target" in str(e).lower() or "detached" in str(e).lower()):
                get_logger().warning("browser context lost (%s) — relaunching", e)
                self._reset(); time.sleep(1)
                return self.page_for(url_prefix, url, _attempt + 1)
            raise

    def close(self):
        try:
            if self.context: self.context.close()
        except Exception:
            pass
        finally:
            try:
                if self._pw: self._pw.stop()
            except Exception:
                pass
            self.context = self._pw = None

"""Ephemeral browser resolver for public Douyin pages.

The resolver lets Chromium execute the page's normal JavaScript and keeps the
result in memory only.  The downloader still fetches the media URL itself so
the browser is never used as a download surface.
"""

from __future__ import annotations

from threading import Event

from .capture import DouyinCapture
from .client import DouyinClient


def create_resolver(parent=None):
    """Create a GUI-owned resolver without importing Qt in headless tests."""
    from PySide6.QtCore import QObject, QEventLoop, QTimer, QThread, QUrl, Qt, Signal
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineSettings

    capture_script = r"""
(() => {
    if (window.__bili23_douyin_capture_installed) return;
    window.__bili23_douyin_capture_installed = true;
    window.__bili23_douyin_responses = [];
    const push = (body) => {
        if (typeof body === "string" && body.length > 0 && body.length <= 2 * 1024 * 1024) {
            window.__bili23_douyin_responses.push(body);
        }
    };
    const originalFetch = window.fetch;
    if (originalFetch) {
        window.fetch = (...args) => originalFetch(...args).then((response) => {
            const contentType = response.headers.get("content-type") || "";
            if (!contentType || contentType.includes("json")) {
                response.clone().text().then(push).catch(() => {});
            }
            return response;
        });
    }
    const originalOpen = XMLHttpRequest.prototype.open;
    const originalSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
        this.__bili23_douyin_url = url;
        return originalOpen.call(this, method, url, ...rest);
    };
    XMLHttpRequest.prototype.send = function(...args) {
        this.addEventListener("load", () => {
            const contentType = this.getResponseHeader("content-type") || "";
            if ((!contentType || contentType.includes("json")) && typeof this.responseText === "string") {
                push(this.responseText);
            }
        });
        return originalSend.apply(this, args);
    };
})();
"""

    class Resolver(QObject):
        request = Signal(str, object)

        def __init__(self):
            super().__init__(parent)
            self.profile = QWebEngineProfile(self)
            self.profile.setHttpUserAgent(DouyinClient.USER_AGENT)
            self.profile.settings().setAttribute(
                QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture,
                False,
            )
            self.page_script = QWebEngineScript()
            self.page_script.setSourceCode(capture_script)
            self.page_script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
            self.page_script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            self.page_script.setRunsOnSubFrames(False)
            self.profile.scripts().insert(self.page_script)
            self.request.connect(self._resolve_in_gui, Qt.ConnectionType.QueuedConnection)

        def fetch(self, page_url: str, aweme_id: str):
            if QThread.currentThread() == self.thread():
                return self._resolve(page_url, aweme_id)

            done = Event()
            box = {}
            self.request.emit(page_url, (aweme_id, done, box))

            if not done.wait(35):
                raise RuntimeError("浏览器解析抖音页面超时")

            if box.get("error"):
                raise box["error"]

            return box["value"]

        def _resolve_in_gui(self, page_url: str, request):
            aweme_id, done, box = request

            try:
                box["value"] = self._resolve(page_url, aweme_id)

            except Exception as error:
                box["error"] = error

            finally:
                done.set()

        def _resolve(self, page_url: str, aweme_id: str):
            page = QWebEnginePage(self.profile, self)
            loop = QEventLoop()
            poller = QTimer(page)
            timeout = QTimer(page)
            result = {}
            finished = False

            def finish(value=None, error=None):
                nonlocal finished

                if finished:
                    return

                finished = True
                poller.stop()
                timeout.stop()

                if error:
                    result["error"] = error
                else:
                    result["value"] = value

                loop.quit()

            def inspect_page():
                script = r"""
(() => {
    const video = document.querySelector("video");
    if (video && video.paused) video.play().catch(() => {});
    const resources = performance.getEntriesByType("resource")
        .filter((entry) => {
            if (entry.initiatorType === "video") return true;
            if (entry.initiatorType !== "fetch" && entry.initiatorType !== "xmlhttprequest") return false;
            return !/\.(?:js|css|png|jpe?g|svg|woff2?)(?:\?|$)/i.test(entry.name);
        })
        .map((entry) => entry.name)
        .filter((url) => /^https?:/i.test(url))
        .slice(-40);
    const candidates = [video && video.currentSrc, video && video.src, ...resources]
        .filter((url) => typeof url === "string" && /^https?:/i.test(url));
    return {
        responses: window.__bili23_douyin_responses || [],
        media_url: candidates[0] || "",
        title: document.title.replace(/\s+-\s+抖音\s*$/, ""),
        cover_url: video && video.poster || "",
        duration: video && Number.isFinite(video.duration) ? Math.floor(video.duration) : 0,
        width: video && video.videoWidth || 0,
        height: video && video.videoHeight || 0,
    };
})()
"""

                page.runJavaScript(script, lambda value: handle_snapshot(value))

            def handle_snapshot(snapshot):
                if not isinstance(snapshot, dict):
                    return

                responses = snapshot.get("responses") or []

                try:
                    if responses:
                        media = DouyinClient.normalize_captured_detail(
                            aweme_id,
                            responses,
                            page_url=page.url().toString() or page_url,
                        )
                        finish(media)
                        return

                except RuntimeError:
                    pass

                media_url = snapshot.get("media_url") or ""
                if media_url:
                    finish(
                        DouyinClient.normalize_browser_result(
                            aweme_id,
                            snapshot,
                            page_url=page.url().toString() or page_url,
                        )
                    )

            def on_loaded(ok):
                if not ok:
                    finish(error=RuntimeError("抖音公开页面加载失败"))
                    return

                inspect_page()

            page.loadFinished.connect(on_loaded)
            poller.timeout.connect(inspect_page)
            poller.start(500)
            timeout.timeout.connect(lambda: finish(error=RuntimeError("浏览器页面未返回抖音媒体地址")))
            timeout.setSingleShot(True)
            timeout.start(30_000)
            page.load(QUrl(page_url))
            loop.exec()
            page.deleteLater()

            if "error" in result:
                raise result["error"]

            return result["value"]

    instance = Resolver()

    if parent is not None:
        instance.setParent(parent)

    return instance

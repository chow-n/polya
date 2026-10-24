"""Pólya.app entry point: one process = uvicorn (API + built frontend) + a native WKWebView window.

Used by both builds (docs/specs/mac-app/SPEC.md):
- Stage A (`make app`): py2app alias bundle that runs this file from the repo with the repo venv.
- Stage B (`make bundle`): PyInstaller bundle; code and data live in sys._MEIPASS.

A frozen binary cannot run `python -c`, so the SymPy verifier re-invokes this executable with `--lh-verify`
and the code on stdin (backend/tools.py).
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


def run_verifier_from_stdin() -> None:
    code = sys.stdin.read()
    exec(compile(code, "<string>", "exec"), {"__name__": "__main__"})


def login_shell_path() -> str:
    """GUI apps start with a minimal PATH; borrow the user's login-shell PATH so `claude`, `rg` and $EDITOR resolve."""
    shell = os.environ.get("SHELL", "/bin/zsh")
    try:
        out = subprocess.run([shell, "-lc", 'printf "%s" "$PATH"'], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    parts = [p for p in (out.split(":") + os.environ.get("PATH", "").split(":") +
                         [str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]) if p]
    return ":".join(dict.fromkeys(parts))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def healthy(url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1) as r:
                if r.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.2)
    return False


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--lh-verify":
        run_verifier_from_stdin()
        return

    frozen = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")
    root = Path(sys._MEIPASS) if frozen else Path(__file__).resolve().parent.parent
    os.environ["POLYA_APP"] = "1"
    os.environ.setdefault("POLYA_ROOT", str(root))
    os.environ["PATH"] = login_shell_path()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from backend import config   # light import: paths only (env above must be set first)

    moved = None if config.HOME_OVERRIDDEN else config.migrate_legacy_home(config.HOME, config.LEGACY_HOME)
    home = config.HOME
    (home / "logs").mkdir(parents=True, exist_ok=True)
    log_path = home / "logs" / "app.log"
    if not sys.stdout.isatty():
        log = open(log_path, "a", buffering=1)
        sys.stdout = sys.stderr = log
    try:  # privacy prompts use the main bundle's Info.plist; it must be Pólya.app, not Python's
        from Foundation import NSBundle
        bundle_id = NSBundle.mainBundle().bundleIdentifier()
    except Exception:
        bundle_id = None
    print(f"\n=== Pólya launch {time.strftime('%Y-%m-%d %H:%M:%S')} root={root} frozen={frozen} "
          f"bundle={bundle_id}", flush=True)
    if moved:
        print(f"[polya] {moved}", flush=True)

    lock = home / ".lock"
    if lock.exists():
        try:
            other = int(lock.read_text().strip())
        except ValueError:
            other = 0
        if other and other != os.getpid() and pid_alive(other):
            print(f"another Pólya (pid {other}) is running; exiting", flush=True)
            return
    lock.write_text(str(os.getpid()))

    import uvicorn
    import webview
    from webview.menu import Menu, MenuAction, MenuSeparator

    from backend.main import app

    port = free_port()
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info", access_log=False))
    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()

    if healthy(url, 90):
        config.PORT_FILE.write_text(str(port))
        start_url = url + "/"
    else:
        tail = log_path.read_text(errors="replace").splitlines()[-30:] if log_path.exists() else []
        import html
        start_url = None
        error_html = ("<body style='background:#070a12;color:#f8fafc;font:14px system-ui;padding:24px'>"
                      "<h2>Pólya could not start its server</h2>"
                      f"<p>Log: {html.escape(str(log_path))}</p><pre style='color:#fda4af;white-space:pre-wrap'>"
                      + html.escape("\n".join(tail)) + "</pre></body>")

    workspace = config.WORKSPACE

    def open_path(p: Path, reveal: bool = False) -> None:
        subprocess.Popen(["open", "-R", str(p)] if reveal else ["open", str(p)])

    def edit_scratch() -> None:
        scratch = str(workspace / "scratch.tex").replace("'", "'\\''")
        script = f"tell application \"Terminal\" to do script \"${{EDITOR:-nvim}} '{scratch}'\""
        subprocess.Popen(["osascript", "-e", script, "-e", 'tell application "Terminal" to activate'])

    window = webview.create_window(
        "Pólya", url=start_url, html=None if start_url else error_html, width=1520, height=960,
        min_size=(1100, 700), background_color="#070a12", text_select=True)

    menu = [
        Menu("Workspace", [
            MenuAction("Open Workspace Folder", lambda: open_path(workspace)),
            MenuAction("Edit scratch.tex in Terminal", edit_scratch),
            MenuSeparator(),
            MenuAction("Reveal Data Folder", lambda: open_path(config.DB_PATH, reveal=True)),
            MenuAction("Show App Log", lambda: open_path(log_path)),
        ]),
        Menu("Window", [
            MenuAction("Reload", lambda: window.load_url(url + "/")),
            MenuAction("Open in Browser", lambda: webbrowser.open(url + "/")),
        ]),
    ]

    done = threading.Event()

    def shutdown() -> None:
        """Runs on window close and on Cmd+Q (Cocoa's terminate exits without unwinding Python frames)."""
        if done.is_set():
            return
        done.set()
        server.should_exit = True
        thread.join(timeout=8)
        for f in (config.PORT_FILE, lock):
            try:
                if f == lock and f.read_text().strip() != str(os.getpid()):
                    continue
                f.unlink()
            except OSError:
                pass
        print("=== Pólya quit", flush=True)

    window.events.closing += shutdown   # Cmd+Q: applicationShouldTerminate_ fires `closing`
    window.events.closed += shutdown
    try:
        webview.start(menu=menu, private_mode=False, storage_path=str(home / "webview"))
    finally:
        shutdown()


if __name__ == "__main__":
    main()

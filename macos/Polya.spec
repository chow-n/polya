# PyInstaller spec for the self-contained Pólya.app (Stage B, `make bundle`).
# Run from the repo root: pyinstaller macos/Polya.spec --distpath build/bundle --workpath build/pyinstaller
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

sys.path.insert(0, str(Path(SPECPATH).parent))
from macos.setup_app import PLIST  # single source of truth for bundle metadata and privacy strings

ROOT = Path(SPECPATH).parent

workspace_datas = [
    (str(p), str(Path("workspace") / p.relative_to(ROOT / "workspace").parent))
    for p in (ROOT / "workspace").rglob("*")
    if p.is_file() and not p.name.startswith("session_") and not p.name.startswith(".")
]

hiddenimports = (
    collect_submodules("backend")
    + collect_submodules("uvicorn")
    + collect_submodules("watchdog.observers")
    # the SymPy verifier imports these only inside child-process code strings, so analysis cannot see them
    + collect_submodules("sympy")
    + ["numpy", "scipy", "scipy.stats", "scipy.integrate", "scipy.linalg", "scipy.optimize", "scipy.special",
       "scipy.sparse"]
    + ["webview.platforms.cocoa", "Speech", "AVFoundation", "Foundation", "AppKit", "Quartz", "pypdf"]
)

# Optional private engines (backend/local_engines, git-ignored; docs/specs/chatgpt-engine B4) ship only in builds
# made where they exist, together with what they need.
extra_datas, extra_binaries = [], []
if (ROOT / "backend" / "local_engines").is_dir():
    from PyInstaller.utils.hooks import collect_all
    for pkg in ("playwright", "greenlet", "pyee"):
        try:
            d, b, h = collect_all(pkg)
        except Exception:
            continue
        extra_datas += d
        extra_binaries += b
        hiddenimports += h
hiddenimports = [m for m in hiddenimports if ".tests" not in m]

a = Analysis(
    [str(ROOT / "macos" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "frontend" / "dist"), "frontend/dist")] + workspace_datas + extra_datas,
    binaries=extra_binaries,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "PyQt5", "PySide6", "IPython", "pytest", "py2app", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Polya", console=False,
          argv_emulation=False, target_arch="arm64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Polya")
app = BUNDLE(
    coll,
    name="Pólya.app",
    icon=str(ROOT / "macos" / "Polya.icns"),
    bundle_identifier=PLIST["CFBundleIdentifier"],
    version=PLIST["CFBundleShortVersionString"],
    info_plist=PLIST,
)

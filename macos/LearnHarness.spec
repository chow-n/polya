# PyInstaller spec for the self-contained LearnHarness.app (Stage B, `make bundle`).
# Run from the repo root: pyinstaller macos/LearnHarness.spec --distpath build/bundle --workpath build/pyinstaller
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

a = Analysis(
    [str(ROOT / "macos" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "frontend" / "dist"), "frontend/dist")] + workspace_datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "PyQt5", "PySide6", "IPython", "pytest", "py2app", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LearnHarness", console=False,
          argv_emulation=False, target_arch="arm64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="LearnHarness")
app = BUNDLE(
    coll,
    name="LearnHarness.app",
    icon=str(ROOT / "macos" / "LearnHarness.icns"),
    bundle_identifier=PLIST["CFBundleIdentifier"],
    version=PLIST["CFBundleShortVersionString"],
    info_plist=PLIST,
)

# PyInstaller spec for the single-file Windows release.
# Build:  pyinstaller packaging/BurpReportGenerator.spec --distpath Releases
# (run from the project root, in an environment with requirements.txt + pyinstaller installed)
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
PKG = ROOT / "burp_report"

datas = [
    (str(PKG / "templates"), "burp_report/templates"),
    (str(PKG / "fonts"), "burp_report/fonts"),
    (str(PKG / "webui"), "burp_report/webui"),
    (str(ROOT / "samples" / "sample_burp_export.xml"), "samples"),
]
# python-docx ships its blank document template as package data.
import docx
datas.append((str(Path(docx.__file__).parent / "templates"), "docx/templates"))

a = Analysis(
    [str(ROOT / "generate_report.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=collect_submodules("rich"),   # rich loads some unicode tables dynamically
    excludes=["tkinter", "unittest", "pydoc", "PIL", "weasyprint"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="BurpReportGenerator-v1.0",
    console=True,            # the web UI server and the terminal wizard both use the console
    icon=str(Path(SPECPATH) / "icon.ico"),
    version=str(Path(SPECPATH) / "version_info.txt"),
    upx=False,
)

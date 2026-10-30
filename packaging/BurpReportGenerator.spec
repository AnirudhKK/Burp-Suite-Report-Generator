# PyInstaller spec for the single-file Windows release.
# Build:  pyinstaller packaging/BurpReportGenerator.spec
# (run from the project root, in an environment with requirements.txt + pyinstaller installed)
# The version comes from burp_report/__init__.py, so bumping __version__ is all a release needs.
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

ROOT = Path(SPECPATH).parent
PKG = ROOT / "burp_report"

VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', (PKG / "__init__.py").read_text("utf-8")).group(1)
NAME = f"BurpReportGenerator-v{VERSION}"
nums = (tuple(int(n) for n in re.findall(r"\d+", VERSION)) + (0, 0, 0, 0))[:4]   # e.g. (1, 0, 0, 0)

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=nums, prodvers=nums, mask=0x3F, flags=0x0, OS=0x40004,
                      fileType=0x1, subtype=0x0, date=(0, 0)),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("FileDescription", "Burp Suite Report Generator"),
            StringStruct("FileVersion", VERSION),
            StringStruct("InternalName", "BurpReportGenerator"),
            StringStruct("OriginalFilename", f"{NAME}.exe"),
            StringStruct("ProductName", "Burp Suite Report Generator"),
            StringStruct("ProductVersion", VERSION),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

datas = [
    (str(PKG / "templates"), "burp_report/templates"),
    (str(PKG / "fonts"), "burp_report/fonts"),
    (str(PKG / "webui"), "burp_report/webui"),
    (str(PKG / "samples"), "burp_report/samples"),
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
    name=NAME,
    console=True,            # the web UI server and the terminal wizard both use the console
    icon=str(Path(SPECPATH) / "icon.ico"),
    version=version_info,
    upx=False,
)

# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent.parent
datas = [(str(root / "assets"), "assets"), (str(root / "LICENSE"), ".")]
# Qt's font database needs its bundled font resources in frozen/windowed builds.
datas += collect_data_files("PySide6", includes=["Qt/lib/fonts/*", "Qt/resources/*"])
for name in ("plugins", "release"):
    source = root / name
    if source.exists(): datas.append((str(source), name))

a = Analysis([str(root / "main.py")], pathex=[str(root)], datas=datas,
             hiddenimports=["PySide6", "easyocr", "mss", "PIL.Image", "requests", "speech_recognition", "pyttsx3"],
             excludes=["pytest"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [], name="EchoDesk",
          icon=str(root / "assets" / "echodesk.ico"), console=False, debug=False,
          version=str(root / "release" / "version_info.txt"))

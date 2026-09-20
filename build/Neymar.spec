# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

raiz = Path.cwd()
datas = [(str(raiz / 'interface_qt'), 'interface_qt')]
binaries = []
ocultos = [
    'win32timezone', 'win32com.client', 'pythoncom', 'central_qt',
    'voz_processo', 'tkinter', 'PIL._tkinter_finder'
]

for pacote in ('PySide6', 'vosk', 'pyttsx3', 'edge_tts', 'av'):
    d, b, h = collect_all(pacote)
    datas += d
    binaries += b
    ocultos += h

a = Analysis(
    [str(raiz / 'assistente_local.py')],
    pathex=[str(raiz)],
    binaries=binaries,
    datas=datas,
    hiddenimports=ocultos,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)

principal = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='Neymar', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False, disable_windowed_traceback=False,
)

trabalhador = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='NeymarWorker', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=True,
)

coll = COLLECT(
    principal, trabalhador, a.binaries, a.datas,
    strip=False, upx=True, upx_exclude=[], name='Neymar',
)

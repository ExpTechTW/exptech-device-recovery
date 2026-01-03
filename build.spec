# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect esptool data files and submodules
esptool_datas = collect_data_files('esptool')
esptool_hiddenimports = collect_submodules('esptool')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=esptool_datas,
    hiddenimports=[
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'serial.tools.list_ports_common',
        'serial.tools.list_ports_posix',
        'serial.tools.list_ports_windows',
        'esptool',
        'esptool.cmds',
        'esptool.loader',
        'esptool.targets',
        'esptool.util',
        'readchar',
        'readchar.readchar',
    ] + esptool_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='exptech-device-recovery',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

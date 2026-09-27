# -*- mode: python ; coding: utf-8 -*-

import os
import uiautomator2

U2_ASSETS = os.path.join(os.path.dirname(uiautomator2.__file__), "assets")


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        (U2_ASSETS, 'uiautomator2/assets'),
    ],
    hiddenimports=[
        'uiautomator2',
        'uiautomator2.assets',
        'adbutils',
        'logzero',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\mail\\Documents\\PUGE\\设计文件\\8h7mr-6xq6z-001.ico'],
)
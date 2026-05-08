# -*- mode: python ; coding: utf-8 -*-
"""UNS Outlook Backup v3.1 - PyInstaller spec (pywebview)"""

import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

block_cipher = None

hidden = collect_submodules('win32com')
hidden += collect_submodules('webview')
hidden += [
    'win32com.client', 'win32com.gen_py',
    'pywintypes', 'pythoncom',
    'win32cred', 'win32crypt',
    'cryptography', 'cryptography.hazmat',
    'cryptography.hazmat.primitives.ciphers.aead',
    'cryptography.hazmat.primitives.kdf.pbkdf2',
    'cryptography.hazmat.primitives.hashes',
    'webview', 'webview.platforms.edgechromium',
    'clr_loader',
    'api', 'i18n', 'config',
    'outlook_client', 'backup_engine',
    'import_engine', 'pst_inspector',
    'history_manager', 'scheduler',
    'account_inventory', 'cache_backup',
]

datas = [
    (os.path.join(ROOT, 'src', 'web'), 'web'),
    (os.path.join(ROOT, 'assets', '*.ico'), 'assets'),
]
datas += collect_data_files('webview', include_py_files=False)

a = Analysis(
    [os.path.join(ROOT, 'src', 'main.py')],
    pathex=[os.path.join(ROOT, 'src')],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'pandas', 'scipy',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'IPython', 'jupyter', 'notebook',
        'pytest', 'unittest',
    ],
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
    name='UNS-Outlook-Backup',
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
    icon=os.path.join(ROOT, 'assets', 'icon.ico'),
    version=os.path.join(ROOT, 'build', 'version_info.txt'),
)

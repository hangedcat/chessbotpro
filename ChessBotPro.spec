# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['chessbot_full.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('app_logo.ico', '.'),
    ],
    hiddenimports=[
        'torch',
        'torchvision',
        'torchvision.transforms',
        'chess',
        'chess.engine',
        'chess.polyglot',
        'mss',
        'cv2',
        'keyboard',
        'numpy',
        'PIL',
        'PIL.Image',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ChessBotPro',
    debug=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    icon='app_logo.ico',
)

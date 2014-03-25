# -*- mode: python -*-
a = Analysis(['src\\pydio\\main.py'],
             pathex=['src', 'D:\\projekty\\pydio\\pydio-sync'],
             hiddenimports=['pydio'],
             hookspath=['pyi_hooks'],
             runtime_hooks=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='pydio.exe',
          debug=True,
          strip=None,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=None,
               upx=True,
               name='pydio')

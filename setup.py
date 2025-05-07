from setuptools import setup

APP = ['main.py']
DATA_FILES = [
    'FitCSVTool.jar',  # your Java splitter tool
    # 'libsync.so' will be generated in CI and bundled automatically
]
OPTIONS = {
    'argv_emulation': True,
    'includes': [
        'gui', 'sync', 'divider',
        'parser_fit', 'parser_kdf', 'writer_fit'
    ],
    'packages': [
        'fitparse', 'fitdecode', 'fit_tool', 'numpy'
    ],
    'plist': {
        'CFBundleName': 'PolarGarminSyncSplit',
        'CFBundleShortVersionString': '1.0',
        'CFBundleIdentifier': 'com.yourcompany.polargarmin',
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

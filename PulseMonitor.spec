# -*- mode: python ; coding: utf-8 -*-
# PulseMonitor PyInstaller spec — clean windowed app, no AV-triggering UPX
# Rebuild: pyinstaller PulseMonitor.spec --noconfirm --clean
#
# This Python 3.11 installation is missing 102 .py source files across stdlib
# and site-packages (only .pyc bytecodes exist). All are bundled under
# stdlib_pyc/ and loaded by the runtime hook's _FrozenStdlibFinder.
# The finder maps module.name -> stdlib_pyc/package/path/stem.cpython-311.pyc

_PYLIB = r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib'
_SP    = r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages'

_missing_stdlib_pycs = [
    # ── Top-level stdlib ──────────────────────────────────────────────────
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\__pycache__\bz2.cpython-311.pyc',         'stdlib_pyc'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\__pycache__\cmd.cpython-311.pyc',         'stdlib_pyc'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\__pycache__\difflib.cpython-311.pyc',     'stdlib_pyc'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\__pycache__\fileinput.cpython-311.pyc',   'stdlib_pyc'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\__pycache__\heapq.cpython-311.pyc',       'stdlib_pyc'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\__pycache__\optparse.cpython-311.pyc',    'stdlib_pyc'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\__pycache__\queue.cpython-311.pyc',       'stdlib_pyc'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\__pycache__\selectors.cpython-311.pyc',   'stdlib_pyc'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\__pycache__\string.cpython-311.pyc',      'stdlib_pyc'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\__pycache__\textwrap.cpython-311.pyc',    'stdlib_pyc'),
    # ── Sub-packages ─────────────────────────────────────────────────────
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\asyncio\__pycache__\transports.cpython-311.pyc',      'stdlib_pyc/asyncio'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\email\__pycache__\_parseaddr.cpython-311.pyc',        'stdlib_pyc/email'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\multiprocessing\__pycache__\process.cpython-311.pyc', 'stdlib_pyc/multiprocessing'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\tomllib\__pycache__\_parser.cpython-311.pyc',         'stdlib_pyc/tomllib'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\unittest\__pycache__\suite.cpython-311.pyc',          'stdlib_pyc/unittest'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\xml\dom\__pycache__\minidom.cpython-311.pyc',         'stdlib_pyc/xml/dom'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\xml\etree\__pycache__\ElementPath.cpython-311.pyc',   'stdlib_pyc/xml/etree'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\xml\sax\__pycache__\handler.cpython-311.pyc',         'stdlib_pyc/xml/sax'),
    # ── encodings (55 files — same finder, unified tree) ─────────────────
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp037.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp1006.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp1026.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp1125.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp1250.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp1252.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp1253.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp1254.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp1255.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp1256.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp1257.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp1258.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp273.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp437.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp500.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp720.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp737.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp775.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp850.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp855.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp857.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp858.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp860.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp861.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp862.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp863.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp864.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp865.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp869.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp874.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\cp875.cpython-311.pyc',       'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\hp_roman8.cpython-311.pyc',   'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_10.cpython-311.pyc',  'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_13.cpython-311.pyc',  'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_14.cpython-311.pyc',  'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_15.cpython-311.pyc',  'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_16.cpython-311.pyc',  'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_2.cpython-311.pyc',   'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_3.cpython-311.pyc',   'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_4.cpython-311.pyc',   'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_5.cpython-311.pyc',   'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_6.cpython-311.pyc',   'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_7.cpython-311.pyc',   'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_8.cpython-311.pyc',   'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\iso8859_9.cpython-311.pyc',   'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\koi8_r.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\koi8_t.cpython-311.pyc',      'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\mac_cyrillic.cpython-311.pyc','stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\mac_greek.cpython-311.pyc',   'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\mac_iceland.cpython-311.pyc', 'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\mac_latin2.cpython-311.pyc',  'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\mac_roman.cpython-311.pyc',   'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\mac_turkish.cpython-311.pyc', 'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\ptcp154.cpython-311.pyc',     'stdlib_pyc/encodings'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\encodings\__pycache__\tis_620.cpython-311.pyc',     'stdlib_pyc/encodings'),
    # ── site-packages: six ────────────────────────────────────────────────
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\__pycache__\six.cpython-311.pyc',    'stdlib_pyc'),
    # ── site-packages: colorama ───────────────────────────────────────────
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\colorama\__pycache__\ansitowin32.cpython-311.pyc',                              'stdlib_pyc/colorama'),
    # ── site-packages: packaging ──────────────────────────────────────────
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\packaging\__pycache__\_parser.cpython-311.pyc',                                 'stdlib_pyc/packaging'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\packaging\__pycache__\markers.cpython-311.pyc',                                 'stdlib_pyc/packaging'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\packaging\__pycache__\metadata.cpython-311.pyc',                                'stdlib_pyc/packaging'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\packaging\__pycache__\pylock.cpython-311.pyc',                                  'stdlib_pyc/packaging'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\packaging\__pycache__\tags.cpython-311.pyc',                                    'stdlib_pyc/packaging'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\packaging\licenses\__pycache__\_spdx.cpython-311.pyc',                         'stdlib_pyc/packaging/licenses'),
    # ── site-packages: pkg_resources vendor ──────────────────────────────
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\pkg_resources\_vendor\__pycache__\appdirs.cpython-311.pyc',                     'stdlib_pyc/pkg_resources/_vendor'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\pkg_resources\_vendor\packaging\__pycache__\_manylinux.cpython-311.pyc',        'stdlib_pyc/pkg_resources/_vendor/packaging'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\pkg_resources\_vendor\packaging\__pycache__\version.cpython-311.pyc',           'stdlib_pyc/pkg_resources/_vendor/packaging'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\pkg_resources\_vendor\pyparsing\__pycache__\results.cpython-311.pyc',           'stdlib_pyc/pkg_resources/_vendor/pyparsing'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\pkg_resources\_vendor\pyparsing\__pycache__\unicode.cpython-311.pyc',           'stdlib_pyc/pkg_resources/_vendor/pyparsing'),
    # ── site-packages: pyparsing ──────────────────────────────────────────
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\pyparsing\__pycache__\common.cpython-311.pyc',                                  'stdlib_pyc/pyparsing'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\pyparsing\__pycache__\helpers.cpython-311.pyc',                                 'stdlib_pyc/pyparsing'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\pyparsing\__pycache__\results.cpython-311.pyc',                                 'stdlib_pyc/pyparsing'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\pyparsing\__pycache__\testing.cpython-311.pyc',                                 'stdlib_pyc/pyparsing'),
    # ── site-packages: setuptools + vendors ───────────────────────────────
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\setuptools\__pycache__\sandbox.cpython-311.pyc',                                'stdlib_pyc/setuptools'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\setuptools\_vendor\__pycache__\ordered_set.cpython-311.pyc',                    'stdlib_pyc/setuptools/_vendor'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\setuptools\_vendor\more_itertools\__pycache__\recipes.cpython-311.pyc',         'stdlib_pyc/setuptools/_vendor/more_itertools'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\setuptools\_vendor\packaging\__pycache__\_manylinux.cpython-311.pyc',           'stdlib_pyc/setuptools/_vendor/packaging'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\setuptools\_vendor\packaging\__pycache__\specifiers.cpython-311.pyc',           'stdlib_pyc/setuptools/_vendor/packaging'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\setuptools\_vendor\packaging\__pycache__\tags.cpython-311.pyc',                 'stdlib_pyc/setuptools/_vendor/packaging'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\setuptools\_vendor\packaging\__pycache__\version.cpython-311.pyc',              'stdlib_pyc/setuptools/_vendor/packaging'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\setuptools\_vendor\pyparsing\__pycache__\common.cpython-311.pyc',               'stdlib_pyc/setuptools/_vendor/pyparsing'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\setuptools\_vendor\pyparsing\__pycache__\core.cpython-311.pyc',                 'stdlib_pyc/setuptools/_vendor/pyparsing'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\setuptools\_vendor\pyparsing\__pycache__\helpers.cpython-311.pyc',              'stdlib_pyc/setuptools/_vendor/pyparsing'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\setuptools\_vendor\pyparsing\__pycache__\testing.cpython-311.pyc',              'stdlib_pyc/setuptools/_vendor/pyparsing'),
    # ── site-packages: rich ───────────────────────────────────────────────
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\rich\__pycache__\_emoji_codes.cpython-311.pyc',                                 'stdlib_pyc/rich'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\rich\__pycache__\_spinners.cpython-311.pyc',                                    'stdlib_pyc/rich'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\rich\__pycache__\color.cpython-311.pyc',                                        'stdlib_pyc/rich'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\rich\__pycache__\panel.cpython-311.pyc',                                        'stdlib_pyc/rich'),
    (r'C:\Users\Josh\AppData\Local\Programs\Python\Python311\Lib\site-packages\rich\__pycache__\style.cpython-311.pyc',                                        'stdlib_pyc/rich'),
]

a = Analysis(
    ['pulsemonitor.py'],
    pathex=[],
    binaries=[],
    datas=[
        *_missing_stdlib_pycs,
    ],
    hiddenimports=[
        # Encodings with .py source present — frozen normally
        'encodings', 'encodings.aliases',
        'encodings.ascii', 'encodings.utf_8', 'encodings.utf_8_sig',
        'encodings.utf_16', 'encodings.utf_16_le', 'encodings.utf_16_be',
        'encodings.utf_32', 'encodings.utf_32_le', 'encodings.utf_32_be',
        'encodings.utf_7', 'encodings.latin_1', 'encodings.idna',
        'encodings.punycode', 'encodings.mbcs', 'encodings.oem',
        'encodings.base64_codec', 'encodings.hex_codec', 'encodings.rot_13',
        'encodings.raw_unicode_escape', 'encodings.unicode_escape',
        'encodings.undefined', 'encodings.charmap',
        'encodings.cp852', 'encodings.cp856', 'encodings.cp866',
        'encodings.koi8_u',
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[
        'hooks/rthook_fix_encodings.py',
    ],
    excludes=[
        'sitecustomize',
        'pyqtgraph',
        'matplotlib',
        'multiprocessing',
        'tkinter',
        'clr',
        'pythonnet',
        'LibreHardwareMonitor',
        'GPUtil',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PulseMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PulseMonitor',
)

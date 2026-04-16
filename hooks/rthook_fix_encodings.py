# PyInstaller runtime hook — runs before pulsemonitor.py starts.
#
# This Python 3.11 installation is missing 73 stdlib .py source files
# (they exist only as .pyc bytecodes). sitecustomize.py patches this at
# runtime, but its path logic is invalid inside a frozen PyInstaller bundle.
#
# Fix:
#   1. Remove the broken _PycFallbackFinder and _pyc_codec_search installed
#      by sitecustomize so they don't interfere with normal import machinery.
#   2. Install a single _FrozenStdlibFinder that loads any missing module
#      from the .pyc files bundled under stdlib_pyc/ in _MEIPASS.
#      Covers: string, heapq, bz2, queue, selectors, textwrap, difflib,
#              asyncio.transports, encodings.cp437, xml.dom.minidom, etc.
#   3. Pre-import all common encodings to populate the codec registry.

import sys
import os
import importlib
import importlib.util

# ── Locate the bundled .pyc tree ─────────────────────────────────────────────
_MEIPASS = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
_STDLIB_PYC = os.path.join(_MEIPASS, 'stdlib_pyc')

# ── 1. Remove broken finders/searchers installed by sitecustomize ────────────
sys.meta_path[:] = [
    f for f in sys.meta_path
    if type(f).__name__ != '_PycFallbackFinder'
]

# ── 2. General finder for all .pyc-only stdlib modules ───────────────────────
class _FrozenStdlibFinder:
    """
    Loads any stdlib/site-package module whose .py source is absent from the
    frozen bundle. Looks up .cpython-311.pyc files under stdlib_pyc/.

    Examples:
      string                          -> stdlib_pyc/string.cpython-311.pyc
      encodings.cp437                 -> stdlib_pyc/encodings/cp437.cpython-311.pyc
      asyncio.transports              -> stdlib_pyc/asyncio/transports.cpython-311.pyc
      pkg_resources._vendor.appdirs   -> stdlib_pyc/pkg_resources/_vendor/appdirs.cpython-311.pyc
      setuptools._vendor.pyparsing    -> stdlib_pyc/setuptools/_vendor/pyparsing/__init__.cpython-311.pyc
    """
    def find_spec(self, fullname, path, target=None):
        if not os.path.isdir(_STDLIB_PYC):
            return None
        parts = fullname.split('.')
        pyc_name = f'{parts[-1]}.cpython-311.pyc'
        if len(parts) == 1:
            pyc      = os.path.join(_STDLIB_PYC, pyc_name)
            init_pyc = os.path.join(_STDLIB_PYC, parts[-1], '__init__.cpython-311.pyc')
        else:
            pyc      = os.path.join(_STDLIB_PYC, *parts[:-1], pyc_name)
            init_pyc = os.path.join(_STDLIB_PYC, *parts, '__init__.cpython-311.pyc')
        # Regular module
        if os.path.isfile(pyc):
            return importlib.util.spec_from_file_location(fullname, pyc)
        # Package __init__
        if os.path.isfile(init_pyc):
            pkg_dir = os.path.dirname(init_pyc)
            return importlib.util.spec_from_file_location(
                fullname, init_pyc,
                submodule_search_locations=[pkg_dir],
            )
        return None


if os.path.isdir(_STDLIB_PYC):
    # Insert after index 0 (the frozen importer runs first; we catch misses)
    sys.meta_path.insert(1, _FrozenStdlibFinder())

# ── 3. Pre-import common encodings to populate codec registry ────────────────
_ENCODINGS = [
    'ascii', 'utf_8', 'utf_8_sig', 'utf_16', 'utf_16_le', 'utf_16_be',
    'utf_32', 'utf_32_le', 'utf_32_be', 'utf_7',
    'latin_1',
    'cp437', 'cp850', 'cp852', 'cp855', 'cp866',
    'cp1250', 'cp1251', 'cp1252', 'cp1253', 'cp1254', 'cp1255',
    'cp1256', 'cp1257', 'cp1258',
    'mbcs', 'oem',
    'idna', 'punycode',
    'base64_codec', 'hex_codec', 'rot_13',
    'raw_unicode_escape', 'unicode_escape', 'undefined',
]
for _enc in _ENCODINGS:
    try:
        importlib.import_module(f'encodings.{_enc}')
    except Exception:
        pass

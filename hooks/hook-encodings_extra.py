# PyInstaller hook — bundles encoding .pyc files that are missing their .py source.
#
# This Python installation has ~55 encoding modules where only the .pyc bytecode
# exists (the .py source is absent). PyInstaller's standard hook-encodings.py
# only picks up modules that have a .py source, so those codecs get left out of
# the frozen bundle. This hook finds them and adds the .pyc files as data files
# so the runtime hook's finder can load them.

import os
import glob

_PYTHON_LIB = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Programs", "Python", "Python311", "Lib"
)
_ENC_DIR    = os.path.join(_PYTHON_LIB, "encodings")
_ENC_CACHE  = os.path.join(_ENC_DIR, "__pycache__")

datas = []

if os.path.isdir(_ENC_CACHE):
    for pyc in glob.glob(os.path.join(_ENC_CACHE, "*.cpython-311.pyc")):
        stem = os.path.basename(pyc).split(".cpython-311")[0]
        py   = os.path.join(_ENC_DIR, stem + ".py")
        if not os.path.exists(py):
            # Source is missing — bundle the .pyc so our runtime hook can load it
            datas.append((pyc, "encodings_pyc"))

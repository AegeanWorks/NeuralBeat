"""Conftest: deterministic import environment for the whole test suite.

Each test module mocks heavy dependencies with the pattern
``if mod_name not in sys.modules: sys.modules[mod_name] = mock``. Without this
conftest the outcome depended on pytest's collection order:

- a module importing real ``matplotlib`` while ``tkinter`` is a mock broke
  collection (matplotlib imports tkinter submodules over the mock);
- ``test_dsp_generators`` re-installed ``sys.modules['tkinter']`` without a
  guard, desynchronizing ``SourceCode.tk`` from what later tests expected.

UI/audio/output mocks are therefore pre-installed exactly once here; numpy and
scipy stay REAL (the DSP tests rely on them), which makes every import order
equivalent. Per-file blocks keep their guarded installs so files still run
standalone via ``python tests/test_<name>.py``.
"""

import sys
from unittest.mock import MagicMock

MOCK_MODULES = {
    'tkinter': MagicMock(),
    'tkinter.ttk': MagicMock(),
    'tkinter.messagebox': MagicMock(),
    'tkinter.simpledialog': MagicMock(),
    'tkinter.filedialog': MagicMock(),
    'ttkbootstrap': MagicMock(),
    'sounddevice': MagicMock(),
    'matplotlib': MagicMock(),
    'matplotlib.figure': MagicMock(),
    'matplotlib.backends': MagicMock(),
    'matplotlib.backends.backend_tkagg': MagicMock(),
}
for mod_name, mock_obj in MOCK_MODULES.items():
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mock_obj

# Tk constants compared literally by tests: with tkinter mocked, tk.END must
# behave like the real one ('end') instead of a MagicMock.
if isinstance(sys.modules.get('tkinter'), MagicMock):
    sys.modules['tkinter'].END = 'end'
    sys.modules['tkinter'].TclError = Exception

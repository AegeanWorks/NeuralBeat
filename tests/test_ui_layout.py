"""Comportamiento de configuracion de la UI en SourceCode.

Cubre la sincronizacion de las variables de estado de los menus
(tema y paleta del osciloscopio) introducidas con el arreglo de layout;
la geometria real de ventanas no es verificable con el patron de mocks
(tkinter simulado) y se cubre con dumps de winfo en la verificacion UI.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

import visual

# Mocks de dependencias pesadas (mismo patron que test_visual_mode.py).
mock_scipy = MagicMock()
mock_scipy.io = MagicMock()
mock_scipy.signal = MagicMock()

MOCK_MODULES = {
    'numpy': MagicMock(),
    'scipy': mock_scipy,
    'scipy.io': mock_scipy.io,
    'scipy.signal': mock_scipy.signal,
    'sounddevice': MagicMock(),
    'tkinter': MagicMock(),
    'tkinter.ttk': MagicMock(),
    'ttkbootstrap': MagicMock(),
    'matplotlib': MagicMock(),
    'matplotlib.figure': MagicMock(),
    'matplotlib.backends': MagicMock(),
    'matplotlib.backends.backend_tkagg': MagicMock(),
}
for mod_name, mock_obj in MOCK_MODULES.items():
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mock_obj

import SourceCode  # noqa: E402  (visual ya está importado como módulo real)


class TestSetThemeMenuVar(unittest.TestCase):
    """set_theme guarda el tema y refleja la eleccion en el menu Theme."""

    def setUp(self):
        self._config = SourceCode.config
        self._var = SourceCode.theme_menu_var
        SourceCode.config = {"theme": "darkly"}
        self.addCleanup(setattr, SourceCode, 'config', self._config)
        self.addCleanup(setattr, SourceCode, 'theme_menu_var', self._var)

    @patch.object(SourceCode, 'save_config')
    @patch('SourceCode.messagebox')
    def test_set_theme_actualiza_la_var_del_menu(self, _mb, save_mock):
        with patch.object(SourceCode, 'root') as root_mock, \
                patch.object(SourceCode, 'theme_menu_var') as var_mock:
            root_mock.style.theme_use.return_value = "superhero"
            SourceCode.set_theme("superhero")
        root_mock.style.theme_use.assert_called_once_with("superhero")
        var_mock.set.assert_called_once_with("superhero")
        self.assertEqual(SourceCode.config["theme"], "superhero")
        save_mock.assert_called_once_with(SourceCode.config)

    @patch.object(SourceCode, 'save_config')
    @patch('SourceCode.messagebox')
    def test_set_theme_error_no_toca_la_var(self, mb, save_mock):
        with patch.object(SourceCode, 'root') as root_mock, \
                patch.object(SourceCode, 'theme_menu_var') as var_mock:
            root_mock.style.theme_use.side_effect = RuntimeError("boom")
            SourceCode.set_theme("flatly")
        var_mock.set.assert_not_called()
        mb.showerror.assert_called_once()
        # El tema previo persiste en config (no se aplico "flatly").
        self.assertEqual(SourceCode.config["theme"], "darkly")


class TestSetOscPaletteVar(unittest.TestCase):
    """set_osc_colors guarda la paleta y refleja la eleccion en el menu."""

    def setUp(self):
        self._config = SourceCode.config
        self._var = SourceCode.osc_palette_var
        SourceCode.config = {}
        self.addCleanup(setattr, SourceCode, 'config', self._config)
        self.addCleanup(setattr, SourceCode, 'osc_palette_var', self._var)

    @patch.object(SourceCode, 'save_config')
    def test_set_osc_colors_actualiza_la_var_del_menu(self, save_mock):
        palette_name = next(iter(SourceCode.OSC_COLOR_PALETTES))
        with patch.object(SourceCode, 'osc_palette_var') as var_mock:
            SourceCode.set_osc_colors(palette_name)
        var_mock.set.assert_called_once_with(palette_name)
        self.assertEqual(SourceCode.config["osc_colors"], palette_name)
        save_mock.assert_called_once_with(SourceCode.config)


if __name__ == '__main__':
    unittest.main()

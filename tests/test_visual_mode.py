"""SourceCode-dependent tests for the visual strobe module.

Covers the UI-side resolution of the requested rhythm
(`get_visual_rate_request`) and the start-up gate of the visual mode
(`start_visual_mode` + `visual_mode_active`). These classes are ported
from the MoriNo23 fork (commit b3ac91d) and land together with the
SourceCode wiring; the pure-visual tests live in
`test_visual_capability.py`.

Test names and comments are kept in Spanish, as in the fork.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

import visual

# ---------------------------------------------------------------------------
# 10. Resolving the rhythm requested from the UI (SourceCode)
# ---------------------------------------------------------------------------

# Mocks of heavy dependencies (same pattern as test_ui_logic.py).
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

import SourceCode  # noqa: E402  (visual is already imported as a real module)


def patch_visual_ui_globals(func):
    """Parchea las variables de UI que lee get_visual_rate_request.

    Sin `new` explicito: @patch inyecta los mocks como argumentos en orden
    inverso al de decoracion (lo que el test desempaquetan).
    """
    @patch('SourceCode.beat_type_var')
    @patch('SourceCode.ramp_enabled_var')
    @patch('SourceCode.left_frequency_entry')
    @patch('SourceCode.right_frequency_entry')
    @patch('SourceCode.start_beat_entry')
    @patch('SourceCode.end_beat_entry')
    @patch('SourceCode.ramp_minutes_entry')
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


class TestRateRequest(unittest.TestCase):

    @patch_visual_ui_globals
    def test_binaural_modulo_canal(self, *mocks):
        (ramp_minutes_entry, end_beat_entry, start_beat_entry,
         right_frequency_entry, left_frequency_entry,
         ramp_enabled_var, beat_type_var) = mocks
        ramp_enabled_var.get.return_value = False
        beat_type_var.get.return_value = "binaural"
        left_frequency_entry.get.return_value = "427"
        right_frequency_entry.get.return_value = "437"
        req = SourceCode.get_visual_rate_request()
        self.assertEqual(req["mode"], "manual")
        self.assertAlmostEqual(req["rate_hz"], 10.0)

    @patch_visual_ui_globals
    def test_binaural_orden_invertido(self, *mocks):
        (ramp_minutes_entry, end_beat_entry, start_beat_entry,
         right_frequency_entry, left_frequency_entry,
         ramp_enabled_var, beat_type_var) = mocks
        ramp_enabled_var.get.return_value = False
        beat_type_var.get.return_value = "binaural"
        left_frequency_entry.get.return_value = "448"
        right_frequency_entry.get.return_value = "418"
        req = SourceCode.get_visual_rate_request()
        self.assertAlmostEqual(req["rate_hz"], 30.0)

    @patch_visual_ui_globals
    def test_isocronico_usa_pulse(self, *mocks):
        (ramp_minutes_entry, end_beat_entry, start_beat_entry,
         right_frequency_entry, left_frequency_entry,
         ramp_enabled_var, beat_type_var) = mocks
        ramp_enabled_var.get.return_value = False
        beat_type_var.get.return_value = "isochronic"
        left_frequency_entry.get.return_value = "10"
        right_frequency_entry.get.return_value = "432"
        req = SourceCode.get_visual_rate_request()
        self.assertAlmostEqual(req["rate_hz"], 10.0)
        self.assertEqual(req["beat_type"], "isochronic")

    @patch_visual_ui_globals
    def test_rampa_usa_peor_punto(self, *mocks):
        (ramp_minutes_entry, end_beat_entry, start_beat_entry,
         right_frequency_entry, left_frequency_entry,
         ramp_enabled_var, beat_type_var) = mocks
        ramp_enabled_var.get.return_value = True
        beat_type_var.get.return_value = "binaural"
        start_beat_entry.get.return_value = "3"
        end_beat_entry.get.return_value = "40"
        ramp_minutes_entry.get.return_value = "30"
        left_frequency_entry.get.return_value = "412"
        right_frequency_entry.get.return_value = "452"
        req = SourceCode.get_visual_rate_request()
        self.assertEqual(req["mode"], "ramp")
        self.assertAlmostEqual(req["rate_hz"], 40.0)  # peor punto, no el inicial
        self.assertAlmostEqual(req["start_hz"], 3.0)
        self.assertAlmostEqual(req["end_hz"], 40.0)
        self.assertAlmostEqual(req["ramp_s"], 1800.0)

    @patch_visual_ui_globals
    def test_rampa_descendente(self, *mocks):
        (ramp_minutes_entry, end_beat_entry, start_beat_entry,
         right_frequency_entry, left_frequency_entry,
         ramp_enabled_var, beat_type_var) = mocks
        ramp_enabled_var.get.return_value = True
        beat_type_var.get.return_value = "binaural"
        start_beat_entry.get.return_value = "20"
        end_beat_entry.get.return_value = "3"
        ramp_minutes_entry.get.return_value = "10"
        req = SourceCode.get_visual_rate_request()
        self.assertAlmostEqual(req["rate_hz"], 20.0)

    @patch_visual_ui_globals
    def test_valores_no_numericos(self, *mocks):
        (ramp_minutes_entry, end_beat_entry, start_beat_entry,
         right_frequency_entry, left_frequency_entry,
         ramp_enabled_var, beat_type_var) = mocks
        ramp_enabled_var.get.return_value = False
        beat_type_var.get.return_value = "binaural"
        left_frequency_entry.get.return_value = "abc"
        right_frequency_entry.get.return_value = "437"
        with self.assertRaises(ValueError):
            SourceCode.get_visual_rate_request()


# ---------------------------------------------------------------------------
# 11. Arranque del modo visual en la app y refresco del sistema
# ---------------------------------------------------------------------------

class TestSystemRefreshProbe(unittest.TestCase):
    """Nominal system refresh when calibration is not reliable."""

    XRANDR = (
        "Screen 0: minimum 320 x 200, current 1366 x 768, maximum 8192 x 8192\n"
        "eDP-1 connected primary 1366x768+0+0 (normal left inverted right x axis y axis) 344mm x 194mm\n"
        "   1366x768      59.80*+\n"
        "   1024x768      59.92  \n"
    )

    def test_lee_el_modo_marcado_como_actual(self):
        self.assertAlmostEqual(visual.parse_xrandr_refresh_hz(self.XRANDR), 59.80)

    def test_sin_modo_actual_devuelve_none(self):
        self.assertIsNone(visual.parse_xrandr_refresh_hz("Screen 0: minimum 320 x 200\n"))
        self.assertIsNone(visual.parse_xrandr_refresh_hz(""))


class TestVisualModeStart(unittest.TestCase):
    """Regression: start_visual_mode must start the scheduler.

    Without scheduler.start(), poll() returns None and visual_poll() closed
    the mode instantly ("the audio is not advancing"), so the strobe never
    became visible.
    """

    def setUp(self):
        self._config = SourceCode.config
        # `root` solo existe tras main(); en test se inyecta el mock de Tk.
        self._had_root = hasattr(SourceCode, "root")
        self._root = getattr(SourceCode, "root", None)
        SourceCode.root = MagicMock()
        SourceCode.config = {
            "visual": {"photosensitive_consent": True, "refresh_hz": 60.0,
                       "intensity": "comoda", "harmonics_enabled": False}}
        self.gen = MagicMock()
        self.gen.samples_generated = 0
        self.gen.is_finished = False
        cfg = MagicMock()
        cfg.sample_rate = 44100
        SourceCode.audio_engine.generator = self.gen
        SourceCode.audio_engine.current_config = cfg
        SourceCode.audio_engine.is_playing = True
        self.req = {"mode": "manual", "beat_type": "isochronic",
                    "rate_hz": 16.0, "ramp_s": None}
        self.cap = visual.visual_capability(16.0, 60.0, False)

    def tearDown(self):
        if SourceCode.visual_mode_active:
            SourceCode.close_visual_mode()
        SourceCode.audio_engine.generator = None
        SourceCode.audio_engine.current_config = None
        SourceCode.audio_engine.is_playing = False
        SourceCode.config = self._config
        if self._had_root:
            SourceCode.root = self._root
        else:
            del SourceCode.root

    def test_scheduler_arrancado_y_modo_activo(self):
        SourceCode.start_visual_mode(self.cap, self.req)
        self.assertTrue(SourceCode.visual_scheduler.started)
        self.assertTrue(SourceCode.visual_mode_active)

    def test_modo_sigue_activo_tras_el_segundo_poll(self):
        SourceCode.start_visual_mode(self.cap, self.req)
        SourceCode.visual_poll()
        self.assertTrue(SourceCode.visual_mode_active)


class TestWindowsProbeDispatch(unittest.TestCase):
    """El sondeo nominal del sistema despacha por plataforma (PRINCIPLE-003).

    En Windows nunca puede depender de xrandr: usa la API de pantalla.
    """

    XRANDR = (
        "Screen 0: minimum 320 x 200, current 1366 x 768, maximum 8192 x 8192\n"
        "eDP-1 connected primary 1366x768+0+0 (normal left inverted right x axis y axis) 344mm x 194mm\n"
        "   1366x768      59.80*+\n"
        "   1024x768      59.92  \n"
    )

    def test_en_windows_usa_el_helper_y_no_lanza_xrandr(self):
        with patch('os.name', 'nt'), \
                patch.object(SourceCode, '_windows_nominal_refresh_hz',
                             return_value=59.94) as helper, \
                patch('SourceCode.subprocess.run') as run_mock, \
                patch.object(SourceCode, 'config', {}):
            self.assertAlmostEqual(SourceCode.probe_system_refresh_hz(), 59.94)
        helper.assert_called_once_with()
        run_mock.assert_not_called()

    def test_en_no_windows_sigue_usando_xrandr(self):
        with patch('os.name', 'posix'), \
                patch('SourceCode.subprocess') as sub, \
                patch.object(SourceCode, 'config', {}):
            sub.run.return_value.stdout = self.XRANDR
            self.assertAlmostEqual(SourceCode.probe_system_refresh_hz(), 59.80)
        sub.run.assert_called_once()


class TestRevokeConsent(unittest.TestCase):
    """El consentimiento fotosensible se puede revocar (auditoria, fix c)."""

    def setUp(self):
        self._config = SourceCode.config
        SourceCode.config = {}
        self.addCleanup(setattr, SourceCode, 'config', self._config)

    def test_sin_consentimiento_guardado_no_pide_nada(self):
        with patch.object(SourceCode, 'get_visual_settings', return_value={
                'photosensitive_consent': False}), \
                patch.object(SourceCode, 'save_config') as save_mock, \
                patch('SourceCode.messagebox') as mb, \
                patch.object(SourceCode, 'update_visual_button'):
            SourceCode.revoke_photosensitive_consent()
        save_mock.assert_not_called()
        mb.askyesno.assert_not_called()
        self.assertEqual(mb.showinfo.call_count, 1)

    def test_con_consentimiento_confirma_y_guarda_false(self):
        with patch.object(SourceCode, 'get_visual_settings', return_value={
                'photosensitive_consent': True}), \
                patch.object(SourceCode, 'save_config') as save_mock, \
                patch('SourceCode.messagebox') as mb, \
                patch.object(SourceCode, 'update_visual_button'):
            mb.askyesno.return_value = True
            SourceCode.revoke_photosensitive_consent()
        mb.askyesno.assert_called_once()
        self.assertIs(SourceCode.config['visual']['photosensitive_consent'],
                      False)
        save_mock.assert_called_once_with(SourceCode.config)

    def test_con_consentimiento_cancelado_no_guarda_nada(self):
        with patch.object(SourceCode, 'get_visual_settings', return_value={
                'photosensitive_consent': True}), \
                patch.object(SourceCode, 'save_config') as save_mock, \
                patch('SourceCode.messagebox') as mb, \
                patch.object(SourceCode, 'update_visual_button'):
            mb.askyesno.return_value = False
            SourceCode.revoke_photosensitive_consent()
        save_mock.assert_not_called()


class TestZeroRateGuidance(unittest.TestCase):
    """Entradas frescas 432/432: guia neutra, no estado de error (fix d)."""

    @patch_visual_ui_globals
    def test_432_432_sin_arranque_muestra_guia_neutra(self, *mocks):
        (ramp_minutes_entry, end_beat_entry, start_beat_entry,
         right_frequency_entry, left_frequency_entry,
         ramp_enabled_var, beat_type_var) = mocks
        ramp_enabled_var.get.return_value = False
        beat_type_var.get.return_value = "binaural"
        left_frequency_entry.get.return_value = "432"
        right_frequency_entry.get.return_value = "432"
        start_beat_entry.get.return_value = ""
        end_beat_entry.get.return_value = ""
        with patch.object(SourceCode, 'config', {}), \
                patch.object(SourceCode, 'save_config'), \
                patch.object(SourceCode, 'visual_toggle_button') as vtb, \
                patch.object(SourceCode, 'visual_status_label') as vsl:
            SourceCode.update_visual_button()
        label_text = ' '.join(str(c.kwargs.get('text', ''))
                              for c in vsl.config.call_args_list)
        self.assertIn('enter a beat frequency', label_text)
        self.assertNotIn('invalid', label_text.lower())
        for call in vtb.config.call_args_list:
            self.assertNotIn('bootstyle', call.kwargs)


if __name__ == '__main__':
    unittest.main()

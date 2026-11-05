"""Regression tests for verify/analyze fixes (export routing, pulse continuity, config)."""
import os
import sys
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import numpy as np
import SourceCode as sc


class TestExportRouting(unittest.TestCase):
    def _make_cfg(self, beat_type):
        return sc.AudioConfig(
            sample_rate=44100,
            left_volume=0.5,
            right_volume=0.5,
            left_waveform="Sine",
            right_waveform="Sine",
            noise_type="None",
            noise_volume=0.0,
            use_ramp=False,
            left_frequency=10.0 if beat_type == "isochronic" else 432.0,
            right_frequency=432.0,
            carrier_hz=432.0,
            start_beat_hz=0.0,
            end_beat_hz=0.0,
            ramp_duration_s=0.0,
            beat_type=beat_type,
        )

    def test_export_uses_isochronic_generator(self):
        cfg = self._make_cfg("isochronic")
        captured = {}
        real_iso = sc.IsochronicGenerator

        class SpyIso(real_iso):
            def __init__(self, c):
                captured["used"] = "isochronic"
                super().__init__(c)

        with patch.object(sc, "IsochronicGenerator", SpyIso), \
             patch.object(sc, "BinauralGenerator", side_effect=AssertionError("wrong generator")), \
             patch.object(sc.wavfile, "write", return_value=None), \
             patch.object(sc, "root", MagicMock()):
            win = MagicMock()
            win.winfo_exists.return_value = True
            bar = MagicMock()
            label = MagicMock()
            sc._run_export_thread(cfg, "dummy.wav", 0.05, win, bar, label,
                                  lambda f: None, lambda e: (_ for _ in ()).throw(e))
        self.assertEqual(captured.get("used"), "isochronic")

    def test_export_uses_binaural_generator(self):
        cfg = self._make_cfg("binaural")
        captured = {}
        real_bin = sc.BinauralGenerator

        class SpyBin(real_bin):
            def __init__(self, c):
                captured["used"] = "binaural"
                super().__init__(c)

        with patch.object(sc, "BinauralGenerator", SpyBin), \
             patch.object(sc, "IsochronicGenerator", side_effect=AssertionError("wrong generator")), \
             patch.object(sc.wavfile, "write", return_value=None), \
             patch.object(sc, "root", MagicMock()):
            win = MagicMock()
            win.winfo_exists.return_value = True
            sc._run_export_thread(cfg, "dummy.wav", 0.05, win, MagicMock(), MagicMock(),
                                  lambda f: None, lambda e: (_ for _ in ()).throw(e))
        self.assertEqual(captured.get("used"), "binaural")


class TestIsochronicPulseContinuity(unittest.TestCase):
    def test_ramp_pulse_phase_continuous(self):
        cfg = sc.AudioConfig(
            sample_rate=44100, left_volume=0.8, right_volume=0.8,
            left_waveform="Sine", right_waveform="Sine",
            noise_type="None", noise_volume=0.0, use_ramp=True,
            left_frequency=0.0, right_frequency=0.0, carrier_hz=432.0,
            start_beat_hz=8.0, end_beat_hz=12.0, ramp_duration_s=10.0,
            beat_type="isochronic",
        )
        gen = sc.IsochronicGenerator(cfg)
        b1 = gen.generate_block(4410)
        p1 = gen.pulse_phase
        b2 = gen.generate_block(4410)
        # Phase advanced and blocks differ but stay bounded
        self.assertNotEqual(p1, 0.0)
        self.assertEqual(b1.shape, (4410, 2))
        self.assertEqual(b2.shape, (4410, 2))
        # Channels identical (dual-mono)
        self.assertTrue(np.allclose(b1[:, 0], b1[:, 1]))
        # Has both sound and silence due to gating (after fade-in)
        gen2 = sc.IsochronicGenerator(cfg)
        gen2.samples_generated = 5000
        blk = gen2.generate_block(44100)
        self.assertTrue(np.any(np.abs(blk) > 1e-3))
        # At least some near-zero gated samples
        self.assertTrue(np.any(np.abs(blk) < 1e-4))


class TestConfigRobustness(unittest.TestCase):
    def test_load_config_rejects_list_root(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as h:
            json.dump([1, 2, 3], h)
            path = h.name
        self.addCleanup(os.unlink, path)
        with patch.object(sc, "CONFIG_PATH", MagicMock()) as mp:
            # Emulate Path API used by load_config
            from pathlib import Path as RealPath
            mp.exists.return_value = True
            mp.read_text.return_value = RealPath(path).read_text(encoding="utf-8")
            self.assertEqual(sc.load_config(), {})

    def test_import_rejects_bad_theme(self):
        payload = {"theme": "not-a-theme", "user_presets": {"Monaural": [], "Binaural": [], "Isochronic": []}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as h:
            json.dump(payload, h)
            path = h.name
        self.addCleanup(os.unlink, path)
        with patch.object(sc.filedialog, "askopenfilename", return_value=path), \
             patch.object(sc, "save_config"), \
             patch.object(sc, "build_preset_buttons"), \
             patch.object(sc, "root", MagicMock()), \
             patch.object(sc.messagebox, "showinfo"):
            sc.import_config_json()
        self.assertNotEqual(sc.config.get("theme"), "not-a-theme")


if __name__ == "__main__":
    unittest.main()

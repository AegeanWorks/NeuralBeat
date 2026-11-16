"""Regression tests for verify/analyze fixes (export routing, pulse continuity, config)."""
import os
import sys
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
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
             patch.object(sc, "_StreamingWavWriter"), \
             patch.object(sc, "root", MagicMock()):
            tmpdir = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
            win = MagicMock()
            win.winfo_exists.return_value = True
            bar = MagicMock()
            label = MagicMock()
            sc._run_export_thread(cfg, os.path.join(tmpdir, "dummy.wav"), 0.05, win, bar, label,
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
             patch.object(sc, "_StreamingWavWriter"), \
             patch.object(sc, "root", MagicMock()):
            tmpdir = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
            win = MagicMock()
            win.winfo_exists.return_value = True
            sc._run_export_thread(cfg, os.path.join(tmpdir, "dummy.wav"), 0.05, win, MagicMock(), MagicMock(),
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


class TestCombinedLabelHelper(unittest.TestCase):
    def test_combined_label_helper(self):
        self.assertTrue(sc.is_combined_beat_label("Binaural Beat / Monaural Beat"))
        self.assertTrue(sc.is_combined_beat_label(" binaural / monaural "))
        self.assertFalse(sc.is_combined_beat_label("Binaural"))
        self.assertFalse(sc.is_combined_beat_label("Monaural Beat"))
        self.assertFalse(sc.is_combined_beat_label("Isochronic Tone"))
        self.assertFalse(sc.is_combined_beat_label(""))

    def test_export_duration_constants_shared(self):
        self.assertEqual(sc.EXPORT_MIN_DURATION_S, 1.0)
        self.assertEqual(sc.EXPORT_MAX_DURATION_S, 3600.0)


class TestExportCancellation(unittest.TestCase):
    def test_cancelled_export_writes_nothing(self):
        cfg = sc.AudioConfig(
            sample_rate=44100, left_volume=0.5, right_volume=0.5,
            left_waveform="Sine", right_waveform="Sine",
            noise_type="None", noise_volume=0.0, use_ramp=False,
            left_frequency=10.0, right_frequency=432.0, carrier_hz=432.0,
            start_beat_hz=0.0, end_beat_hz=0.0, ramp_duration_s=0.0,
            beat_type="binaural",
        )
        cancel = threading.Event()
        cancel.set()
        with patch.object(sc, "root", MagicMock()), \
             patch.object(sc, "_StreamingWavWriter") as writer_cls:
            sc._run_export_thread(cfg, "dummy.wav", 0.05, MagicMock(),
                                  MagicMock(), MagicMock(),
                                  lambda f: None, lambda e: None,
                                  cancel_event=cancel)
        # Cancelled before the first block: no writer, hence no file.
        self.assertEqual(writer_cls.call_count, 0)

    def test_uncancelled_export_writes_file(self):
        cfg = sc.AudioConfig(
            sample_rate=44100, left_volume=0.5, right_volume=0.5,
            left_waveform="Sine", right_waveform="Sine",
            noise_type="None", noise_volume=0.0, use_ramp=False,
            left_frequency=10.0, right_frequency=432.0, carrier_hz=432.0,
            start_beat_hz=0.0, end_beat_hz=0.0, ramp_duration_s=0.0,
            beat_type="binaural",
        )
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        out_path = os.path.join(tmpdir, "out.wav")
        with patch.object(sc, "root", MagicMock()), \
             patch.object(sc, "_StreamingWavWriter") as writer_cls:
            sc._run_export_thread(cfg, out_path, 0.05, MagicMock(),
                                  MagicMock(), MagicMock(),
                                  lambda f: None, lambda e: None)
        self.assertEqual(writer_cls.call_count, 1)
        self.assertTrue(writer_cls.return_value.write.called)
        writer_cls.return_value.flush_and_sync.assert_called_once()


class TestConfigQuarantine(unittest.TestCase):
    def test_corrupt_config_is_quarantined(self):
        from pathlib import Path as RealPath
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = RealPath(tmp) / "config.json"
            cfg_path.write_text("{ this is not json", encoding="utf-8")
            with patch.object(sc, "CONFIG_PATH", cfg_path):
                self.assertEqual(sc.load_config(), {})
            self.assertFalse(cfg_path.exists(), "corrupt config must not be left in place")
            quarantined = list(RealPath(tmp).glob("config.json.corrupt*"))
            self.assertEqual(len(quarantined), 1)
            self.assertEqual(quarantined[0].read_text(encoding="utf-8"), "{ this is not json")

    def test_valid_config_is_not_quarantined(self):
        from pathlib import Path as RealPath
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = RealPath(tmp) / "config.json"
            cfg_path.write_text('{"theme": "darkly"}', encoding="utf-8")
            with patch.object(sc, "CONFIG_PATH", cfg_path):
                self.assertEqual(sc.load_config(), {"theme": "darkly"})
            self.assertTrue(cfg_path.exists())
            self.assertEqual(list(RealPath(tmp).glob("config.json.corrupt*")), [])


class TestStreamingExport(unittest.TestCase):
    def _cfg(self):
        return sc.AudioConfig(
            sample_rate=44100, left_volume=0.5, right_volume=0.5,
            left_waveform="Sine", right_waveform="Sine",
            noise_type="None", noise_volume=0.0, use_ramp=False,
            left_frequency=10.0, right_frequency=432.0, carrier_hz=432.0,
            start_beat_hz=0.0, end_beat_hz=0.0, ramp_duration_s=0.0,
            beat_type="binaural",
        )

    def _run(self, out_path, duration):
        sc._run_export_thread(self._cfg(), str(out_path), duration,
                              MagicMock(), MagicMock(), MagicMock(),
                              lambda f: None,
                              lambda e: (_ for _ in ()).throw(e))

    def _expected_frames(self, total_frames, fade_len):
        """Reference render: one deterministic generator run plus the tail fade."""
        full = sc.BinauralGenerator(self._cfg()).generate_block(total_frames)
        expected = full.copy()
        ramp = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
        expected[-fade_len:] *= ramp[:, np.newaxis]
        return full, expected

    def test_export_produces_f32_wav_matching_reference(self):
        from scipy.io import wavfile as real_wavfile
        out_path = Path(tempfile.mkdtemp()) / "export.wav"
        self.addCleanup(shutil.rmtree, str(out_path.parent), ignore_errors=True)
        total = 44100  # 1s (min clamp): blocks 4096 x10 + 2760, fade in the tail
        fade_len = int(0.02 * 44100)
        with patch.object(sc, "root", MagicMock()):
            self._run(out_path, 1.0)
        rate, data = real_wavfile.read(str(out_path))
        self.assertEqual(rate, 44100)
        self.assertEqual(data.shape, (total, 2))
        _, expected = self._expected_frames(total, fade_len)
        self.assertTrue(np.allclose(data, expected, atol=1e-4))

    def test_export_pre_fade_region_matches_reference(self):
        from scipy.io import wavfile as real_wavfile
        out_path = Path(tempfile.mkdtemp()) / "export.wav"
        self.addCleanup(shutil.rmtree, str(out_path.parent), ignore_errors=True)
        total = 44100
        fade_len = int(0.02 * 44100)
        with patch.object(sc, "root", MagicMock()):
            self._run(out_path, 1.0)
        rate, data = real_wavfile.read(str(out_path))
        full, _ = self._expected_frames(total, fade_len)
        # Pre-fade region matches the untouched reference render.
        self.assertTrue(np.allclose(data[:-fade_len], full[:-fade_len], atol=1e-4))

    def test_cancelled_after_generation_removes_no_file_on_success_path(self):
        # Sanity: normal run leaves exactly one valid file behind.
        out_path = Path(tempfile.mkdtemp()) / "export.wav"
        self.addCleanup(shutil.rmtree, str(out_path.parent), ignore_errors=True)
        with patch.object(sc, "root", MagicMock()):
            self._run(out_path, 1.0)
        self.assertTrue(out_path.exists())

    def test_writer_uses_fsync_and_discards_partial(self):
        out_path = Path(tempfile.mkdtemp()) / "export.wav"
        self.addCleanup(shutil.rmtree, str(out_path.parent), ignore_errors=True)
        with open(out_path, "wb") as fh:
            w = sc._StreamingWavWriter(fh, 44100, 10)
            w.write(np.zeros((10, 2), dtype=np.float32))
            w.flush_and_sync()
        data = np.fromfile(str(out_path), dtype=np.uint8)
        self.assertEqual(len(data), 44 + 10 * 8)  # 44-byte header + 10 stereo f32 frames
        # A partially-written export is removed wholesale, not left behind.
        self.assertTrue(out_path.exists())
        sc._discard_partial_export_file(str(out_path))
        self.assertFalse(out_path.exists())
        # Discarding a missing file is a no-op, not an error.
        sc._discard_partial_export_file(str(out_path))



if __name__ == "__main__":
    unittest.main()

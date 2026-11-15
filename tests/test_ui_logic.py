"""Test UI logic functions from SourceCode.py that don't require a live UI."""

import unittest
from unittest.mock import patch, MagicMock
from contextlib import ExitStack
from functools import wraps
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Mock heavy dependencies before importing SourceCode; numpy and scipy stay
# real, UI/output mocks come from tests/conftest.py.
MOCK_MODULES = {
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

import SourceCode


# UI globals patched for every logic test, in decoration order.
UI_GLOBAL_NAMES = (
    'left_frequency_entry',
    'right_frequency_entry',
    'left_volume_entry',
    'right_volume_entry',
    'noise_volume_entry',
    'left_waveform_var',
    'right_waveform_var',
    'noise_type_var',
    'ramp_enabled_var',
    'beat_type_var',
    'carrier_entry',
    'start_beat_entry',
    'end_beat_entry',
    'ramp_minutes_entry',
)


def patch_ui_globals(func):
    """Patch every UI global and pass the mocks in the order the tests unpack them."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        mocks = {name: MagicMock() for name in UI_GLOBAL_NAMES}
        with ExitStack() as stack:
            for name in UI_GLOBAL_NAMES:
                stack.enter_context(patch(f'SourceCode.{name}', mocks[name]))
            ordered = [mocks[name] for name in reversed(UI_GLOBAL_NAMES)]
            return func(*args, *ordered, **kwargs)

    return wrapper


class TestUiLogic(unittest.TestCase):
    """Test UI-related logic functions."""

    @patch_ui_globals
    def test_get_audio_config_manual_mode(self, *mocks):
        """Test get_audio_config_from_ui in manual mode."""
        # The mocks are passed in reverse order of decoration
        (
            ramp_minutes_entry, end_beat_entry, start_beat_entry, carrier_entry,
            beat_type_var, ramp_enabled_var, noise_type_var, right_waveform_var,
            left_waveform_var, noise_volume_entry, right_volume_entry, left_volume_entry,
            right_frequency_entry, left_frequency_entry
        ) = mocks

        ramp_enabled_var.get.return_value = False
        left_frequency_entry.get.return_value = "432.0"
        right_frequency_entry.get.return_value = "442.0"
        left_volume_entry.get.return_value = "50"
        right_volume_entry.get.return_value = "50"
        noise_volume_entry.get.return_value = "10"
        left_waveform_var.get.return_value = "Sine"
        right_waveform_var.get.return_value = "Square"
        noise_type_var.get.return_value = "Pink"
        beat_type_var.get.return_value = "binaural"

        cfg = SourceCode.get_audio_config_from_ui()

        self.assertFalse(cfg.use_ramp)
        self.assertEqual(cfg.left_frequency, 432.0)
        self.assertEqual(cfg.right_frequency, 442.0)
        self.assertAlmostEqual(cfg.left_volume, 0.5)
        self.assertEqual(cfg.left_waveform, "Sine")
        self.assertEqual(cfg.right_waveform, "Square")
        self.assertEqual(cfg.noise_type, "Pink")
        self.assertAlmostEqual(cfg.noise_volume, 0.1)
        self.assertEqual(cfg.beat_type, "binaural")

    @patch_ui_globals
    def test_get_audio_config_ramp_mode(self, *mocks):
        """Test get_audio_config_from_ui in ramp mode."""
        (
            ramp_minutes_entry, end_beat_entry, start_beat_entry, carrier_entry,
            beat_type_var, ramp_enabled_var, noise_type_var, right_waveform_var,
            left_waveform_var, noise_volume_entry, right_volume_entry, left_volume_entry,
            right_frequency_entry, left_frequency_entry
        ) = mocks

        ramp_enabled_var.get.return_value = True
        carrier_entry.get.return_value = "528"
        start_beat_entry.get.return_value = "20"
        end_beat_entry.get.return_value = "8"
        ramp_minutes_entry.get.return_value = "15"
        left_volume_entry.get.return_value = "60"
        right_volume_entry.get.return_value = "60"
        noise_volume_entry.get.return_value = "0"
        left_waveform_var.get.return_value = "Sine"
        right_waveform_var.get.return_value = "Sine"
        noise_type_var.get.return_value = "None"
        beat_type_var.get.return_value = "binaural"

        cfg = SourceCode.get_audio_config_from_ui()

        self.assertTrue(cfg.use_ramp)
        self.assertEqual(cfg.carrier_hz, 528.0)
        self.assertEqual(cfg.start_beat_hz, 20.0)
        self.assertEqual(cfg.end_beat_hz, 8.0)
        self.assertEqual(cfg.ramp_duration_s, 15 * 60.0)
        self.assertAlmostEqual(cfg.left_volume, 0.6)

    @patch_ui_globals
    def test_get_audio_config_invalid_input(self, *mocks):
        """Test get_audio_config_from_ui with invalid text input."""
        (
            ramp_minutes_entry, end_beat_entry, start_beat_entry, carrier_entry,
            beat_type_var, ramp_enabled_var, noise_type_var, right_waveform_var,
            left_waveform_var, noise_volume_entry, right_volume_entry, left_volume_entry,
            right_frequency_entry, left_frequency_entry
        ) = mocks

        ramp_enabled_var.get.return_value = False
        left_frequency_entry.get.return_value = "not-a-number"
        right_frequency_entry.get.return_value = "442.0"
        left_volume_entry.get.return_value = "50"
        right_volume_entry.get.return_value = "50"
        noise_volume_entry.get.return_value = "10"

        with self.assertRaisesRegex(ValueError, "Please enter valid numeric values for frequencies."):
            SourceCode.get_audio_config_from_ui()

    @patch_ui_globals
    def test_get_audio_config_out_of_range(self, *mocks):
        """Test get_audio_config_from_ui with out-of-range frequency."""
        (
            ramp_minutes_entry, end_beat_entry, start_beat_entry, carrier_entry,
            beat_type_var, ramp_enabled_var, noise_type_var, right_waveform_var,
            left_waveform_var, noise_volume_entry, right_volume_entry, left_volume_entry,
            right_frequency_entry, left_frequency_entry
        ) = mocks

        ramp_enabled_var.get.return_value = False
        left_frequency_entry.get.return_value = "10.0"  # Below 20Hz
        right_frequency_entry.get.return_value = "442.0"
        left_volume_entry.get.return_value = "50"
        right_volume_entry.get.return_value = "50"
        noise_volume_entry.get.return_value = "10"
        beat_type_var.get.return_value = "binaural"

        with self.assertRaisesRegex(ValueError, "Frequency must be between 20 Hz and 20000 Hz."):
            SourceCode.get_audio_config_from_ui()

    @patch('SourceCode.apply_preset')
    def test_build_preset_buttons(self, mock_apply_preset):
        """Test that preset buttons are created with the correct commands."""
        mock_binaural_frame = MagicMock()
        mock_isochronic_frame = MagicMock()

        with patch('SourceCode.binaural_monaural_frame', mock_binaural_frame), \
                patch('SourceCode.isochronic_beats_frame', mock_isochronic_frame), \
                patch('SourceCode.get_all_presets') as mock_get_presets:
            mock_get_presets.return_value = {
                "Monaural": [],
                "Binaural": [{"label": "Test Binaural", "left_hz": 400, "right_hz": 410}],
                "Isochronic": [{"label": "Test Iso", "carrier_hz": 200, "pulse_hz": 10}],
            }

            with patch('SourceCode.ttk.Button') as mock_button:
                SourceCode.build_preset_buttons()

                self.assertGreaterEqual(len(mock_button.call_args_list), 2)

                binaural_call_args = mock_button.call_args_list[0]
                binaural_command = binaural_call_args[1]['command']
                binaural_command()
                mock_apply_preset.assert_called_with(400, 410, "Binaural")

                isochronic_call_args = mock_button.call_args_list[1]
                isochronic_command = isochronic_call_args[1]['command']
                isochronic_command()
                mock_apply_preset.assert_called_with(0, 0, "Isochronic", carrier_hz=200, pulse_hz=10)

    def test_apply_preset(self):
        """Test that apply_preset correctly updates the UI entries."""
        mock_left_entry = MagicMock()
        mock_right_entry = MagicMock()
        mock_beat_type_var = MagicMock()
        mock_carrier_entry = MagicMock()

        with patch('SourceCode.left_frequency_entry', mock_left_entry), \
                patch('SourceCode.right_frequency_entry', mock_right_entry), \
                patch('SourceCode.beat_type_var', mock_beat_type_var), \
                patch('SourceCode.carrier_entry', mock_carrier_entry):
            SourceCode.apply_preset(left_hz=432.0, right_hz=440.0, category="Binaural")
            mock_left_entry.delete.assert_called_with(0, 'end')
            mock_left_entry.insert.assert_called_with(0, '432.0')
            mock_right_entry.delete.assert_called_with(0, 'end')
            mock_right_entry.insert.assert_called_with(0, '440.0')
            mock_beat_type_var.set.assert_called_with("binaural")

            SourceCode.apply_preset(category="Isochronic", pulse_hz=10.0, carrier_hz=200.0)
            mock_left_entry.insert.assert_called_with(0, '10.0')
            mock_right_entry.insert.assert_called_with(0, '200.0')
            mock_carrier_entry.insert.assert_called_with(0, '200.0')
            mock_beat_type_var.set.assert_called_with("isochronic")


class TestRampAndNoiseBoundaries(unittest.TestCase):
    """Boundary coverage for the ramp and noise validation rules."""

    def _assert_ramp_error(self, *mocks, ramp_minutes, carrier="528",
                           start="20", end="8", beat_type="binaural",
                           noise="0", pattern):
        (
            ramp_minutes_entry, end_beat_entry, start_beat_entry, carrier_entry,
            beat_type_var, ramp_enabled_var, noise_type_var, right_waveform_var,
            left_waveform_var, noise_volume_entry, right_volume_entry, left_volume_entry,
            right_frequency_entry, left_frequency_entry
        ) = mocks

        ramp_enabled_var.get.return_value = True
        carrier_entry.get.return_value = carrier
        start_beat_entry.get.return_value = start
        end_beat_entry.get.return_value = end
        ramp_minutes_entry.get.return_value = ramp_minutes
        left_volume_entry.get.return_value = "50"
        right_volume_entry.get.return_value = "50"
        noise_volume_entry.get.return_value = noise
        left_waveform_var.get.return_value = "Sine"
        right_waveform_var.get.return_value = "Sine"
        noise_type_var.get.return_value = "None"
        beat_type_var.get.return_value = beat_type

        with self.assertRaisesRegex(ValueError, pattern):
            SourceCode.get_audio_config_from_ui()

    @patch_ui_globals
    def test_ramp_duration_below_minimum_rejected(self, *mocks):
        self._assert_ramp_error(*mocks, ramp_minutes="0.4",
                                pattern="Ramp duration must be between 0.5 and 120 minutes.")

    @patch_ui_globals
    def test_ramp_duration_above_maximum_rejected(self, *mocks):
        self._assert_ramp_error(*mocks, ramp_minutes="120.5",
                                pattern="Ramp duration must be between 0.5 and 120 minutes.")

    @patch_ui_globals
    def test_ramp_carrier_audibility_below_bound_rejected(self, *mocks):
        # carrier 29 Hz, beat 20 Hz: left channel = 29 - 10 = 19 Hz < 20 Hz
        self._assert_ramp_error(*mocks, ramp_minutes="10", carrier="29.0",
                                start="20", end="20",
                                pattern="left channel stays audible")

    @patch_ui_globals
    def test_ramp_carrier_audibility_at_bound_accepted(self, *mocks):
        (
            ramp_minutes_entry, end_beat_entry, start_beat_entry, carrier_entry,
            beat_type_var, ramp_enabled_var, noise_type_var, right_waveform_var,
            left_waveform_var, noise_volume_entry, right_volume_entry, left_volume_entry,
            right_frequency_entry, left_frequency_entry
        ) = mocks

        ramp_enabled_var.get.return_value = True
        carrier_entry.get.return_value = "30.0"
        start_beat_entry.get.return_value = "20"
        end_beat_entry.get.return_value = "20"
        ramp_minutes_entry.get.return_value = "10"
        left_volume_entry.get.return_value = "50"
        right_volume_entry.get.return_value = "50"
        noise_volume_entry.get.return_value = "0"
        left_waveform_var.get.return_value = "Sine"
        right_waveform_var.get.return_value = "Sine"
        noise_type_var.get.return_value = "None"
        beat_type_var.get.return_value = "binaural"

        cfg = SourceCode.get_audio_config_from_ui()
        self.assertEqual(cfg.carrier_hz, 30.0)

    @patch_ui_globals
    def test_noise_volume_out_of_range_rejected(self, *mocks):
        self._assert_ramp_error(*mocks, ramp_minutes="10", noise="100.5",
                                pattern="Noise volume must be between 0% and 100%.")


class TestPresetAutoSplit(unittest.TestCase):
    def _patch_preset_entries(self, stack, label, category):
        for name in ('preset_category_var', 'preset_name_entry'):
            stack.enter_context(patch(f'SourceCode.{name}', MagicMock()))
        SourceCode.preset_name_entry.get.return_value = label
        SourceCode.preset_category_var.get.return_value = category

    @patch('SourceCode.messagebox.showinfo')
    @patch('SourceCode.build_preset_buttons')
    @patch('SourceCode.add_user_preset')
    def test_save_preset_auto_splits_combo_label(self, mock_add, *_):
        with ExitStack() as stack:
            self._patch_preset_entries(stack, " My Preset ", "Binaural Beat / Monaural Beat")
            left_entry = MagicMock()
            left_entry.get.return_value = "432.0"
            right_entry = MagicMock()
            right_entry.get.return_value = "431.5"
            stack.enter_context(patch('SourceCode.left_frequency_entry', left_entry))
            stack.enter_context(patch('SourceCode.right_frequency_entry', right_entry))
            SourceCode.save_current_as_preset()
        kwargs = mock_add.call_args.kwargs
        self.assertEqual(kwargs["category"], "Binaural")
        self.assertEqual(kwargs["label"], "My Preset")

    @patch('SourceCode.messagebox.showinfo')
    @patch('SourceCode.build_preset_buttons')
    @patch('SourceCode.add_user_preset')
    def test_save_preset_split_monaural_on_equal_frequencies(self, mock_add, *_):
        with ExitStack() as stack:
            self._patch_preset_entries(stack, "Mono Preset", "")
            left_entry = MagicMock()
            left_entry.get.return_value = "432.0"
            right_entry = MagicMock()
            right_entry.get.return_value = "432.0"
            stack.enter_context(patch('SourceCode.left_frequency_entry', left_entry))
            stack.enter_context(patch('SourceCode.right_frequency_entry', right_entry))
            SourceCode.save_current_as_preset()
        kwargs = mock_add.call_args.kwargs
        self.assertEqual(kwargs["category"], "Monaural")


if __name__ == '__main__':
    unittest.main()
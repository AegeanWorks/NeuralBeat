# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document catalogues Python modules, classes, and exported functions. See Map Coverage for any stack it does not index.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `22`
- **Total Classes**: `63`
- **Total Top-Level Functions**: `73`
- **Total Class Methods**: `264`
- **Total Source Lines**: `6992`

## 🧭 Map Coverage
- **Indexed**: python (`22` module(s))
- **Not indexed by this map**: none (no non-Python source files were found)

---

## 📦 Modules & Exported Symbols

### [`presets.py`](presets.py)
**Size**: `31` lines (`1438` bytes)

---

### [`run_tests.py`](run_tests.py)
> *NeuralBeat Test Runner*

**Size**: `46` lines (`886` bytes)

**Functions:**
- `def main()`

---

### [`SourceCode.py`](SourceCode.py)
**Size**: `2657` lines (`107562` bytes)

**Classes:**
- `class NoiseGenerator` - *Generates blocks of colored noise with state preservation using digital filters.*
  - Method `.__init__()`
  - Method `._normalize(noise)` - *Normalize noise to have RMS of 1.*
  - Method `.generate(noise_type, n_samples)`
- `class AudioConfig`
- `class BinauralGenerator` - *Generates binaural or monaural beats based on the provided AudioConfig.*
  - Method `.__init__(cfg)`
  - Method `.request_stop()` - *Signal the generator to start fading out.*
  - Method `.generate_block(frames)`
- `class IsochronicGenerator` - *Generates isochronic tones - rhythmic pulses of sound at a specific beat frequency.*
  - Method `.__init__(cfg)`
  - Method `.request_stop()`
  - Method `.generate_block(frames)`
- `class AudioEngine` - *Manages the audio playback stream using sounddevice.*
  - Method `.__init__()`
  - Method `.start(cfg)`
  - Method `.stop()` - *Stops audio gracefully with fade out.*
  - Method `.get_elapsed_time()`
  - Method `.get_last_block()`
- `class _StreamingWavWriter` - *Incremental float32 stereo WAV writer.*
  - Method `.__init__(fh, sample_rate, total_frames, channels)`
  - Method `.write(block)`
  - Method `.flush_and_sync()`

**Functions:**
- `def is_combined_beat_label(category)` - *True when the label carries both beat words (combined UI label).*
- `def _quarantine_corrupt_config()` - *Moves an unparsable config file aside so a later save can recreate it.*
- `def load_config()` - *Loads configuration from the JSON file.*
- `def save_config(cfg)` - *Saves the configuration dictionary to the JSON file.*
- `def _normalize_category(category)`
- `def get_user_presets()`
- `def add_user_preset(category, label, left_hz, right_hz)`
- `def remove_user_preset(category, label)`
- `def get_all_presets()`
- `def clamp(value, lo, hi)` - *Clamps a value between lo and hi.*
- `def validate_audio_params(freq_l, freq_r, vol_l, vol_r, duration)` - *Validates audio parameters (frequencies, volumes, duration).*
- `def _compute_ramped_beat_hz(elapsed_s, start_beat_hz, end_beat_hz, ramp_s)` - *Calculates the current beat frequency based on ramp progress.*
- `def get_audio_config_from_ui()` - *Reads values from UI entries and returns an AudioConfig object.*
- `def stop_audio()`
- `def get_visual_settings()` - *The visual section of config merged with defaults (backwards compatible).*
- `def save_visual_setting(key, value)` - *Persist one key of the visual section in ~/.neuralbeat/config.json.*
- `def get_visual_refresh_hz()` - *Calibrated screen refresh (conservative default when absent).*
- `def probe_system_refresh_hz()` - *Nominal refresh reported by the system. None when unavailable.*
- `def _windows_nominal_refresh_hz()` - *Nominal refresh (Hz) of the primary display via the Win32 API.*
- `def get_visual_rate_request()` - *Resolves the requested visual rhythm from the UI state.*
- `def get_visual_audio_time()` - *Audio time of the active stream (master clock: samples_generated).*
- `def compute_visual_capability()` - *(request, VisualCapability) from the UI state and current calibration.*
- `def update_visual_button()` - *Visible state of the Visual mode button: exact / approximate / harmonic*
- `def toggle_visual_mode()` - *Visual mode button action: gate + consent + start-up.*
- `def set_visual_intensity()` - *Comfy intensity (default) or bright (opt-in, with a warning).*
- `def revoke_photosensitive_consent()` - *Clear the stored photosensitive consent so the strobe asks again.*
- `def on_visual_harmonics_toggle()` - *Advanced flag of the experimental harmonic mode (off by default).*
- `def run_screen_calibration()` - *Measures the real screen refresh (~2s full-screen).*
- `def start_visual_mode(cap, req)` - *Opens the full-screen strobe anchored to the playing audio.*
- `def visual_poll()` - *Tk loop of the visual mode: deadline flips, audio watchdog and an*
- `def close_visual_mode(reason)` - *Closes the visual mode and restores the main window (focus included).*
- `def set_osc_merge_waves()` - *Saves the merge waves setting and updates the live plot's static elements.*
- `def set_osc_colors(palette_name)` - *Sets the oscilloscope color palette and saves to config.*
- `def toggle_oscilloscope_window()` - *Opens or closes the real-time oscilloscope window.*
- `def _discard_partial_export_file(filename)` - *Remove a partial export file (cancel / error path).*
- `def _run_export_thread(cfg, filename, duration, progress_win, progress_bar, progress_label, on_success, on_error, cancel_event)` - *Background thread function for exporting audio to a WAV file.*
- `def export_audio_file()` - *Initiates the audio export process with UI dialogs.*
- `def play_audio()` - *Starts audio playback based on current UI settings.*
- `def show_about()`
- `def set_theme(theme_name)`
- `def export_config_json()` - *Export the current in-memory config dict to a JSON file the user selects.*
- `def import_config_json()` - *Import config from a JSON file, persist it, and refresh UI (theme + presets).*
- `def apply_preset(left_hz, right_hz, category, carrier_hz, pulse_hz)`
- `def build_preset_buttons()`
- `def save_current_as_preset()`
- `def delete_preset()`
- `def update_live_status()` - *Updates the status bar with current frequencies and remaining time.*
- `def on_close()`
- `def create_frequency_control_frame(parent, title, column, waveform_options, default_freq, default_vol, default_waveform)`
- `def main()` - *Main application entry point. Initializes UI and starts the event loop.*

---

### [`tests/__init__.py`](tests/__init__.py)
**Size**: `0` lines (`0` bytes)

---

### [`tests/conftest.py`](tests/conftest.py)
> *Conftest: deterministic import environment for the whole test suite.*

**Size**: `42` lines (`1728` bytes)

---

### [`tests/test_audio_config.py`](tests/test_audio_config.py)
> *Test AudioConfig dataclass and utility functions.*

**Size**: `216` lines (`6612` bytes)

**Classes:**
- `class TestAudioConfig` - *Test AudioConfig dataclass.*
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.test_audio_config_defaults()` - *Test AudioConfig default values.*
  - Method `.test_audio_config_isochronic()` - *Test AudioConfig with isochronic beat type.*
- `class TestClampFunction` - *Test clamp utility function.*
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.test_clamp_basic()` - *Test basic clamping.*
  - Method `.test_clamp_edge_cases()` - *Test clamp edge cases.*
- `class TestRampCalculation` - *Test ramp computation function.*
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.test_ramp_no_ramp()` - *Test ramp calculation when ramp is disabled (returns end_beat_hz).*
  - Method `.test_ramp_linear()` - *Test linear ramp calculation.*
  - Method `.test_ramp_at_end()` - *Test ramp at end point.*
  - Method `.test_ramp_beyond_end()` - *Test ramp beyond duration.*
- `class TestValidation` - *Test validation functions.*
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.test_validate_valid_params()` - *Test validation with valid parameters.*
  - Method `.test_validate_invalid_left_freq()` - *Test validation with invalid left frequency.*
  - Method `.test_validate_invalid_volume()` - *Test validation with invalid volume.*

---

### [`tests/test_audio_engine.py`](tests/test_audio_engine.py)
> *Test the AudioEngine class from SourceCode.py.*

**Size**: `128` lines (`4112` bytes)

**Classes:**
- `class TestAudioEngine` - *Test the AudioEngine class.*
  - Method `.test_start_binaural(mock_binaural_gen, mock_sd)` - *Test starting the audio engine for binaural beats.*
  - Method `.test_start_isochronic(mock_isochronic_gen, mock_sd)` - *Test starting the audio engine for isochronic tones.*
  - Method `.test_stop(mock_binaural_gen, mock_sd)` - *Test stopping the audio engine.*
  - Method `.test_stop_when_not_playing(mock_sd)` - *Test that stop() does nothing if not playing.*
  - Method `.test_start_exception(mock_logger, mock_sd)` - *Test exception handling during start.*
  - Method `.test_get_elapsed_time()` - *Test elapsed time calculation.*

---

### [`tests/test_bootstyle_usage.py`](tests/test_bootstyle_usage.py)
> *Regression shield: ttkbootstrap-only keyword arguments must stay on ttkbootstrap widgets.*

**Size**: `51` lines (`1835` bytes)

**Classes:**
- `class TestBootstyleUsage`
  - Method `.test_bootstyle_only_on_ttkbootstrap_widgets()`

**Functions:**
- `def find_bootstyle_violations(source)`

---

### [`tests/test_config.py`](tests/test_config.py)
> *Test configuration management functions.*

**Size**: `191` lines (`7142` bytes)

**Classes:**
- `class TestConfig` - *Test configuration management functions.*
  - Method `.setUp()` - *Patch the config object for each test.*
  - Method `.tearDown()`
  - Method `.test_normalize_category()` - *Test _normalize_category function.*
  - Method `.test_get_user_presets_empty()` - *Test get_user_presets with an empty config.*
  - Method `.test_get_user_presets_populated()` - *Test get_user_presets with a populated config.*
  - Method `.test_add_user_preset()` - *Test adding a new user preset.*
  - Method `.test_add_user_preset_invalid_values()` - *Test adding a preset with invalid numeric values.*
  - Method `.test_add_user_preset_empty_label()` - *Test adding a preset with an empty label.*
  - Method `.test_remove_user_preset()` - *Test removing an existing user preset.*
  - Method `.test_remove_user_preset_not_found()` - *Test removing a preset that does not exist.*
  - Method `.test_save_config(mock_path)` - *Test the actual save_config function.*
  - Method `.test_load_config_exists(mock_path)` - *Test loading an existing config file.*
  - Method `.test_load_config_not_exists(mock_path)` - *Test loading when config file does not exist.*
  - Method `.test_load_config_error(mock_logger, mock_path)` - *Test loading a corrupt config file.*

---

### [`tests/test_config_presets.py`](tests/test_config_presets.py)
> *Test config and preset management functions.*

**Size**: `351` lines (`12306` bytes)

**Classes:**
- `class TestNormalizeCategory` - *Test _normalize_category function.*
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.test_normalize_binaural()` - *Test normalization of binaural.*
  - Method `.test_normalize_monaural()` - *Test normalization keeps monaural distinct.*
  - Method `.test_normalize_isochronic()` - *Test normalization of isochronic.*
  - Method `.test_normalize_invalid()` - *Test invalid category raises ValueError.*
- `class TestGetUserPresets` - *Test get_user_presets function.*
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.test_get_user_presets_empty()` - *Test get_user_presets with no config file.*
  - Method `.test_get_user_presets_with_data()` - *Test get_user_presets with user presets.*
- `class TestGetAllPresets` - *Test get_all_presets function.*
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.test_get_all_presets_structure()` - *Test get_all_presets returns correct keys.*
  - Method `.test_get_all_presets_includes_defaults()` - *Test get_all_presets includes default presets.*
  - Method `.test_get_all_presets_merges_user()` - *Test get_all_presets merges user presets.*
- `class TestAddUserPreset` - *Test add_user_preset function.*
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.test_add_user_preset_isochronic()` - *Test adding an isochronic preset stores pulse and carrier keys.*
  - Method `.test_add_user_preset_isochronic_roundtrip()` - *Test a saved isochronic preset survives get_all_presets unchanged.*
  - Method `.test_add_user_preset_binaural()` - *Test adding binaural preset.*
- `class TestRemoveUserPreset` - *Test remove_user_preset function.*
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.test_remove_existing_preset()` - *Test removing existing preset returns True.*
  - Method `.test_remove_nonexistent_preset()` - *Test removing nonexistent preset returns False.*
- `class TestImportConfigIsochronic` - *Test that profile import keeps isochronic presets.*
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.test_import_keeps_isochronic_presets()`
  - Method `.test_import_keeps_osc_settings()`

---

### [`tests/test_dsp_generators.py`](tests/test_dsp_generators.py)
> *Test the DSP generator classes (BinauralGenerator, IsochronicGenerator).*

**Size**: `191` lines (`7241` bytes)

**Classes:**
- `class TestBinauralGenerator` - *Tests for the BinauralGenerator class.*
  - Method `.setUp()` - *Set up a default AudioConfig for tests.*
  - Method `.test_block_generation()` - *Test that a block of audio is generated with the correct shape and type.*
  - Method `.test_fade_in()` - *Test that the signal fades in at the beginning.*
  - Method `.test_fade_out()` - *Test that the signal fades out and finishes when stop is requested.*
  - Method `.test_noise_mixing()` - *Test that noise is correctly added to the signal.*
  - Method `.test_ramp_mode()` - *Test that ramp mode runs without error and produces output.*
- `class TestIsochronicGenerator` - *Tests for the IsochronicGenerator class.*
  - Method `.setUp()` - *Set up a default AudioConfig for tests.*
  - Method `.test_block_generation()` - *Test that a block of isochronic tones is generated correctly.*

---

### [`tests/test_generators.py`](tests/test_generators.py)
> *Test generator classes.*

**Size**: `271` lines (`8062` bytes)

**Classes:**
- `class TestBinauralGenerator` - *Test BinauralGenerator class.*
  - Method `.setUpClass()`
  - Method `.test_generator_initialization()` - *Test BinauralGenerator initializes correctly.*
  - Method `.test_generator_creates_output()` - *Test BinauralGenerator creates audio output.*
  - Method `.test_generator_fade_in()` - *Test fade-in at start.*
  - Method `.test_request_stop()` - *Test request_stop sets stopping flag.*
- `class TestMonauralMode` - *Test monaural mode through the shared BinauralGenerator.*
  - Method `.setUpClass()`
  - Method `.test_generator_initialization()` - *Test the shared generator initializes correctly.*
  - Method `.test_generator_creates_output()` - *Test monaural mode produces identical left and right channels.*
- `class TestIsochronicGenerator` - *Test IsochronicGenerator class.*
  - Method `.setUpClass()`
  - Method `.test_generator_initialization()` - *Test IsochronicGenerator initializes correctly.*
  - Method `.test_generator_creates_output()` - *Test IsochronicGenerator creates audio output.*
  - Method `.test_generator_pulse_modulation()` - *Test IsochronicGenerator has pulsing.*
  - Method `.test_request_stop()` - *Test request_stop sets stopping flag.*
- `class TestGeneratorWaveforms` - *Test generator with different waveforms.*
  - Method `.setUpClass()`
  - Method `.test_generator_with_sine()` - *Test generator with Sine waveform.*
  - Method `.test_generator_with_ramp()` - *Test generator with ramp enabled.*

**Functions:**
- `def create_numpy_mock()` - *Create a more complete numpy mock.*

---

### [`tests/test_presets.py`](tests/test_presets.py)
> *Test presets module.*

**Size**: `69` lines (`2733` bytes)

**Classes:**
- `class TestPresets` - *Test preset data structures.*
  - Method `.test_monaural_presets_structure()` - *Test monaural presets have required fields.*
  - Method `.test_binaural_presets_structure()` - *Test binaural presets have required fields.*
  - Method `.test_isochronic_presets_structure()` - *Test isochronic presets have required fields.*
  - Method `.test_brainwave_ranges()` - *Test brainwave ranges are defined.*
  - Method `.test_frequency_ranges_valid()` - *Test brainwave frequency ranges are valid.*
  - Method `.test_presets_not_empty()` - *Test all preset lists are populated.*

---

### [`tests/test_ui_layout.py`](tests/test_ui_layout.py)
> *Comportamiento de configuracion de la UI en SourceCode.*

**Size**: `97` lines (`3868` bytes)

**Classes:**
- `class TestSetThemeMenuVar` - *set_theme guarda el tema y refleja la eleccion en el menu Theme.*
  - Method `.setUp()`
  - Method `.test_set_theme_actualiza_la_var_del_menu(_mb, save_mock)`
  - Method `.test_set_theme_error_no_toca_la_var(mb, save_mock)`
- `class TestSetOscPaletteVar` - *set_osc_colors guarda la paleta y refleja la eleccion en el menu.*
  - Method `.setUp()`
  - Method `.test_set_osc_colors_actualiza_la_var_del_menu(save_mock)`

---

### [`tests/test_ui_logic.py`](tests/test_ui_logic.py)
> *Test UI logic functions from SourceCode.py that don't require a live UI.*

**Size**: `350` lines (`15525` bytes)

**Classes:**
- `class TestUiLogic` - *Test UI-related logic functions.*
  - Method `.test_get_audio_config_manual_mode(*mocks)` - *Test get_audio_config_from_ui in manual mode.*
  - Method `.test_get_audio_config_ramp_mode(*mocks)` - *Test get_audio_config_from_ui in ramp mode.*
  - Method `.test_get_audio_config_invalid_input(*mocks)` - *Test get_audio_config_from_ui with invalid text input.*
  - Method `.test_get_audio_config_out_of_range(*mocks)` - *Test get_audio_config_from_ui with out-of-range frequency.*
  - Method `.test_build_preset_buttons(mock_apply_preset)` - *Test that preset buttons are created with the correct commands.*
  - Method `.test_apply_preset()` - *Test that apply_preset correctly updates the UI entries.*
- `class TestRampAndNoiseBoundaries` - *Boundary coverage for the ramp and noise validation rules.*
  - Method `._assert_ramp_error(*mocks, ramp_minutes, carrier, start, end, beat_type, noise, pattern)`
  - Method `.test_ramp_duration_below_minimum_rejected(*mocks)`
  - Method `.test_ramp_duration_above_maximum_rejected(*mocks)`
  - Method `.test_ramp_carrier_audibility_below_bound_rejected(*mocks)`
  - Method `.test_ramp_carrier_audibility_at_bound_accepted(*mocks)`
  - Method `.test_noise_volume_out_of_range_rejected(*mocks)`
- `class TestPresetAutoSplit`
  - Method `._patch_preset_entries(stack, label, category)`
  - Method `.test_save_preset_auto_splits_combo_label(mock_add, *_)`
  - Method `.test_save_preset_split_monaural_on_equal_frequencies(mock_add, *_)`

**Functions:**
- `def patch_ui_globals(func)` - *Patch every UI global and pass the mocks in the order the tests unpack them.*

---

### [`tests/test_utils.py`](tests/test_utils.py)
> *Test utility functions from SourceCode.py.*

**Size**: `103` lines (`4070` bytes)

**Classes:**
- `class TestUtils` - *Test utility functions.*
  - Method `.test_clamp()` - *Test the clamp function.*
  - Method `.test_validate_audio_params_valid()` - *Test validate_audio_params with valid inputs.*
  - Method `.test_validate_audio_params_invalid_freq()` - *Test validate_audio_params with invalid frequencies.*
  - Method `.test_validate_audio_params_invalid_vol()` - *Test validate_audio_params with invalid volumes.*
  - Method `.test_validate_audio_params_invalid_duration()` - *Test validate_audio_params with invalid duration.*
  - Method `.test_compute_ramped_beat_hz()` - *Test _compute_ramped_beat_hz calculation.*

---

### [`tests/test_verify_fixes.py`](tests/test_verify_fixes.py)
> *Regression tests for verify/analyze fixes (export routing, pulse continuity, config).*

**Size**: `303` lines (`13862` bytes)

**Classes:**
- `class TestExportRouting`
  - Method `._make_cfg(beat_type)`
  - Method `.test_export_uses_isochronic_generator()`
  - Method `.test_export_uses_binaural_generator()`
- `class TestIsochronicPulseContinuity`
  - Method `.test_ramp_pulse_phase_continuous()`
- `class TestConfigRobustness`
  - Method `.test_load_config_rejects_list_root()`
  - Method `.test_import_rejects_bad_theme()`
- `class TestCombinedLabelHelper`
  - Method `.test_combined_label_helper()`
  - Method `.test_export_duration_constants_shared()`
- `class TestExportCancellation`
  - Method `.test_cancelled_export_writes_nothing()`
  - Method `.test_uncancelled_export_writes_file()`
- `class TestConfigQuarantine`
  - Method `.test_corrupt_config_is_quarantined()`
  - Method `.test_valid_config_is_not_quarantined()`
- `class TestStreamingExport`
  - Method `._cfg()`
  - Method `._run(out_path, duration)`
  - Method `._expected_frames(total_frames, fade_len)` - *Reference render: one deterministic generator run plus the tail fade.*
  - Method `.test_export_produces_f32_wav_matching_reference()`
  - Method `.test_export_pre_fade_region_matches_reference()`
  - Method `.test_cancelled_after_generation_removes_no_file_on_success_path()`
  - Method `.test_writer_uses_fsync_and_discards_partial()`

---

### [`tests/test_visual_capability.py`](tests/test_visual_capability.py)
> *Tests del modo visual estroboscópico (change: modo-visual-estroboscopico).*

**Size**: `583` lines (`24267` bytes)

**Classes:**
- `class TestVisualCapabilityTable` - *Tabla de capacidad por refresco (tasks.md 1.1).*
  - Method `.test_299_exacto_on_598()`
  - Method `.test_10_exacto_on_598()`
  - Method `.test_16_aproximado_on_598()`
  - Method `.test_40_no_disponible_on_598()`
  - Method `.test_40_exacto_on_120()`
  - Method `.test_mejor_monitor_desbloquea_40()` - *Monitor 120 Hz recalibrado: 40 pasa a exacto sin cambios de código.*
- `class TestRawEmissionRejection` - *Rechazo de emisión cruda: f > refresh/2 nunca entrega exacto/aproximado*
  - Method `.test_sobre_nyquist_siempre_no_disponible()`
  - Method `.test_tolerancia_borde()`
  - Method `.test_entradas_invalidas()`
- `class TestPatterns`
  - Method `.test_exacto_duty_50_pares()`
  - Method `.test_aproximado_duty_y_ventana()`
  - Method `.test_armonico_patron_3_fotogramas_duty_1_3()`
  - Method `.test_relacion_coeficientes_armonico()` - *|c2|/|c1| del tren de pulsos con duty 1/3 es ~0.5 (design.md).*
- `class TestHarmonicAndSubstitute`
  - Method `.test_sin_flag_no_aparece_armonico()`
  - Method `.test_con_flag_40hz_usa_3_fotogramas()`
  - Method `.test_candidato_solo_si_existe_divisor()`
  - Method `.test_sustituto_maximo_exacto()`
- `class TestRampGate`
  - Method `.test_rampa_que_cruza_el_maximo_bloquea()` - *El gate se evalúa con el peor punto, no con el valor inicial.*
  - Method `.test_rampa_descendente_tambien_bloquea()`
  - Method `.test_rampa_soportable_no_bloquea()`
  - Method `.test_rampa_solo_exactos()`
- `class TestLabels`
  - Method `.test_etiqueta_exacto()`
  - Method `.test_etiqueta_exacto_reetiquetado()`
  - Method `.test_etiqueta_aproximado_con_jitter()`
  - Method `.test_etiqueta_no_disponible_con_razon()`
  - Method `.test_notas_intensidad()`
- `class TestRefreshStats`
  - Method `.test_pantalla_598()`
  - Method `.test_jitter_medido()`
  - Method `.test_marcas_insuficientes()`
  - Method `.test_validacion_plausibilidad()`
- `class TestVisualConfig`
  - Method `.test_config_sin_claves_no_rompe()`
  - Method `.test_config_parcial()`
  - Method `.test_valores_invalidos_a_defaults()`
  - Method `.test_roundtrip()`
  - Method `.test_refresh_fuera_de_banda_a_none()` - *Read-side plausibility: hostile/absurd stored refresh never flows*
- `class TestBeatClock`
  - Method `.test_constante()`
  - Method `.test_constante_siguiente_frontera()`
  - Method `.test_rampa_coincide_con_formula_del_motor()` - *rate_at reproduce _compute_ramped_beat_hz de SourceCode.py.*
  - Method `.test_rampa_frontera_cae_en_ciclo_entero()`
  - Method `.test_rechaza_frecuencia_invalida()`
- `class FakeClock`
  - Method `.__init__(t)`
  - Method `.__call__()`
- `class _Runner` - *Entorno con reloj falso y tiempo de audio derivable (con deriva opcional).*
  - Method `.__init__(rate, refresh, pattern, cpw, drift, reanchor, free_running, beat_clock, rebuild_fn)`
  - Method `.run(seconds, step, max_iters)`
  - Method `.on_sets()`
  - Method `.off_sets()`
- `class TestStrobeScheduler`
  - Method `.test_flips_exactos_ritmo_y_fase()`
  - Method `.test_flips_tardios_se_saltan_sin_rafa()`
  - Method `.test_reanclaje_absorbe_deriva_del_cristal()` - *Audio 0.5% más rápido que el reloj del sistema: con re-anclaje el*
  - Method `.test_sin_reanclaje_la_deriva_se_acumula()` - *Contraste: sin re-anclaje (intervalo enorme) la fase se desvía más.*
  - Method `.test_audio_detenido_sin_flips()`
  - Method `.test_rebuild_de_patron_en_reanclaje()` - *El scheduler puede cambiar de patrón en el re-anclaje (rampas).*
  - Method `.test_modo_libre_armonica_sin_jitter()` - *Armónico: patrón de 3 fotogramas a R/3 exacto, anclado al pulso.*
- `class TestLatenessMonitor`
  - Method `.test_umbral_de_aborto()`
  - Method `.test_ventana_desliza()`
  - Method `.test_pocas_muestras_no_abortan()`

---

### [`tests/test_visual_mode.py`](tests/test_visual_mode.py)
> *SourceCode-dependent tests for the visual strobe module.*

**Size**: `329` lines (`14053` bytes)

**Classes:**
- `class TestRateRequest`
  - Method `.test_binaural_modulo_canal(*mocks)`
  - Method `.test_binaural_orden_invertido(*mocks)`
  - Method `.test_isocronico_usa_pulse(*mocks)`
  - Method `.test_rampa_usa_peor_punto(*mocks)`
  - Method `.test_rampa_descendente(*mocks)`
  - Method `.test_valores_no_numericos(*mocks)`
- `class TestSystemRefreshProbe` - *Nominal system refresh when calibration is not reliable.*
  - Method `.test_lee_el_modo_marcado_como_actual()`
  - Method `.test_sin_modo_actual_devuelve_none()`
- `class TestVisualModeStart` - *Regression: start_visual_mode must start the scheduler.*
  - Method `.setUp()`
  - Method `.tearDown()`
  - Method `.test_scheduler_arrancado_y_modo_activo()`
  - Method `.test_modo_sigue_activo_tras_el_segundo_poll()`
- `class TestWindowsProbeDispatch` - *El sondeo nominal del sistema despacha por plataforma (PRINCIPLE-003).*
  - Method `.test_en_windows_usa_el_helper_y_no_lanza_xrandr()`
  - Method `.test_en_no_windows_sigue_usando_xrandr()`
- `class TestRevokeConsent` - *El consentimiento fotosensible se puede revocar (auditoria, fix c).*
  - Method `.setUp()`
  - Method `.test_sin_consentimiento_guardado_no_pide_nada()`
  - Method `.test_con_consentimiento_confirma_y_guarda_false()`
  - Method `.test_con_consentimiento_cancelado_no_guarda_nada()`
- `class TestZeroRateGuidance` - *Entradas frescas 432/432: guia neutra, no estado de error (fix d).*
  - Method `.test_432_432_sin_arranque_muestra_guia_neutra(*mocks)`

**Functions:**
- `def patch_visual_ui_globals(func)` - *Parchea las variables de UI que lee get_visual_rate_request.*

---

### [`tests/verify_dsp_ramp.py`](tests/verify_dsp_ramp.py)
**Size**: `122` lines (`4030` bytes)

**Classes:**
- `class FakeNumpy`
  - Method `.arange(*args, **kwargs)`
  - Method `.sin(x)`
  - Method `.tanh(x)`
  - Method `.clip(a, a_min, a_max)`
  - Method `.column_stack(tup)`
  - Method `.full(shape, fill_value, **kwargs)`
  - Method `.maximum(x1, x2)`
  - Method `.cumsum(a)`
  - Method `.concatenate(tup)`
  - Method `.sum(a)`
  - Method `.abs(a)`
  - Method `.max(a)`

---

### [`verification.py`](verification.py)
**Size**: `173` lines (`6480` bytes)

**Functions:**
- `def validate_signal(audio_data, sample_rate, expected_left_hz, expected_right_hz, duration_s, tolerance_hz)` - *Validates the generated audio signal for scientific accuracy.*
- `def validate_export(generator_class, config, duration_s)` - *Validates that the exported WAV file matches the in-memory generation.*

---

### [`visual.py`](visual.py)
**Size**: `688` lines (`27022` bytes)

**Classes:**
- `class VisualCapability` - *Gate result for a requested rate against a measured refresh.*
  - Property `.available`
- `class BeatClock` - *Accumulated cycles of the audio pulse as a function of audio time.*
  - Method `.__init__(rate_hz, start_hz, end_hz, ramp_s)`
  - Method `.rate_at(t)`
  - Method `.cycles(t)`
  - Method `.next_boundary(t)` - *Audio time of the next pulse boundary after t.*
- `class StrobeScheduler` - *Strobe scheduler anchored to the audio clock (samples_generated).*
  - Method `.__init__(pattern, refresh_hz, on_flip, clock, get_audio_time, beat_clock, cycles_per_window, free_running, reanchor_interval_s, rebuild_fn)`
  - Method `.start()` - *Starts aligned to the next audio pulse boundary.*
  - Method `.stop()`
  - Method `._snap(sys_now, audio_now)`
  - Method `._audio_est(sys_now)`
  - Method `._pos_frames(audio_t)` - *Position (float, in frames) inside the pattern window.*
  - Method `._state_at(audio_t)`
  - Method `._next_crossing(sys_now)` - *Deadline (clock time) of the next pattern state change.*
  - Method `.poll(now)` - *Processes due flips at `now`; returns the next deadline.*
- `class LatenessMonitor` - *Aborts when median lateness exceeds a threshold (fork design decision 7).*
  - Method `.__init__(frame_period_s, ratio, window_s, min_samples)`
  - Method `.record(now, lateness_s)`
  - Method `.should_abort()`

**Functions:**
- `def pulse_train_coefficient(k, duty)` - *Magnitude of the k-th coefficient of a rectangular pulse train of duty d.*
- `def harmonic_amplitude_ratio(duty, k)` - *|c_k| / |c_1| for a pulse train of the given duty (duty 1/3, k=2 -> 0.5).*
- `def _exact_pattern(n)` - *Pattern of n frames, ~50% duty, starting at the pulse onset.*
- `def _window_pattern(w_frames, cycles)` - *Periodic pattern of w_frames with `cycles` pulses (~50% duty).*
- `def _harmonic_pattern(n)` - *Pattern of n frames, ~1/3 duty (n=3 -> 1 on, 2 off).*
- `def harmonic_candidate(rate_hz, refresh_hz, tolerance_pct)` - *Finds n such that the 2nd harmonic of pulses at R/n (duty 1/3) approximates rate.*
- `def best_substitute(refresh_hz)` - *Highest exact rate supported (R/2, 2 frames, 50% duty).*
- `def visual_capability(rate_hz, refresh_hz, harmonics_enabled, tolerance_pct)` - *Classifies `rate_hz` on a screen of measured `refresh_hz`.*
- `def ramp_gate_capability(start_hz, end_hz, refresh_hz, harmonics_enabled, n_points, tolerance_pct)` - *Ramp gate: evaluated at the WORST point of the sweep (fork tasks 1.3).*
- `def capability_label(cap, requested_hz)` - *Status label for the button/UI (with power feedback).*
- `def intensity_note(intensity)` - *Power note for the chosen intensity (specs: feedback).*
- `def compute_refresh_stats(timestamps)` - *Refresh statistics from presentation timestamps.*
- `def _percentile(sortedable, pct)` - *Percentile by linear interpolation (equivalent to numpy p95).*
- `def validate_refresh_measurement(refresh_hz, jitter_ms)` - *Validates measurement plausibility. Returns (ok, confidence).*
- `def parse_xrandr_refresh_hz(text)` - *Refresh of the output marked as current (`*`) in `xrandr --current`.*
- `def merge_visual_config(cfg)` - *Merges the "visual" section of config with default values.*

---

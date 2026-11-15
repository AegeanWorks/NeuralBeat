"""Tests del modo visual estroboscópico (change: modo-visual-estroboscopico).

Cubre tasks.md 1.1-1.3 (capacidad, patrones, gate de rampa y rechazo de
emisión cruda), 2.1-2.2 (estadísticas de calibración con reloj falso y
compatibilidad de config), 3.2 (scheduler: deadlines absolutos, saltos de
flips tardíos, re-anclaje) y 4.3-4.4 (armónico opt-in y etiquetas).
"""

import math
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# visual.py es un módulo puro (solo stdlib): se importa real siempre.
import visual


# ---------------------------------------------------------------------------
# 1. Capacidad (tasks 1.1)
# ---------------------------------------------------------------------------

class TestVisualCapabilityTable(unittest.TestCase):
    """Tabla de capacidad por refresco (tasks.md 1.1)."""

    def test_299_exacto_on_598(self):
        cap = visual.visual_capability(29.9, 59.8)
        self.assertEqual(cap.state, visual.STATE_EXACTO)
        self.assertEqual(cap.frames_per_period, 2)
        self.assertAlmostEqual(cap.effective_hz, 29.9, delta=1e-6)
        self.assertEqual(cap.jitter_ms, 0.0)
        self.assertEqual(cap.pattern, [True, False])

    def test_10_exacto_on_598(self):
        cap = visual.visual_capability(10.0, 59.8)
        self.assertEqual(cap.state, visual.STATE_EXACTO)
        self.assertEqual(cap.frames_per_period, 6)
        # Frecuencia efectiva real: 59.8 / 6 = 9.9667 (re-etiquetada)
        self.assertAlmostEqual(cap.effective_hz, 59.8 / 6.0, delta=1e-6)
        self.assertLessEqual(cap.freq_error, 0.01)
        self.assertEqual(cap.jitter_ms, 0.0)
        self.assertEqual(len(cap.pattern), 6)

    def test_16_aproximado_on_598(self):
        cap = visual.visual_capability(16.0, 59.8)
        self.assertEqual(cap.state, visual.STATE_APROXIMADO)
        self.assertIsNotNone(cap.pattern)
        # Ventana periódica <= ~1 s
        self.assertLessEqual(len(cap.pattern) / 59.8, 1.0 + 1e-9)
        # Jitter esperado: un fotograma
        self.assertAlmostEqual(cap.jitter_ms, 1000.0 / 59.8, delta=1e-6)
        # Frecuencia efectiva cercana a la pedida
        self.assertIsNotNone(cap.effective_hz)
        self.assertLessEqual(abs(cap.effective_hz - 16.0) / 16.0, 0.02)
        self.assertGreaterEqual(cap.cycles_per_window, 1)

    def test_40_no_disponible_on_598(self):
        cap = visual.visual_capability(40.0, 59.8)
        self.assertEqual(cap.state, visual.STATE_NO_DISPONIBLE)
        self.assertFalse(cap.available)
        self.assertIn("29.9", cap.reason)

    def test_40_exacto_on_120(self):
        cap = visual.visual_capability(40.0, 120.0)
        self.assertEqual(cap.state, visual.STATE_EXACTO)
        self.assertEqual(cap.frames_per_period, 3)
        self.assertAlmostEqual(cap.effective_hz, 40.0, delta=1e-9)

    def test_mejor_monitor_desbloquea_40(self):
        """Monitor 120 Hz recalibrado: 40 pasa a exacto sin cambios de código."""
        cap = visual.visual_capability(40.0, 120.0)
        self.assertEqual(cap.state, visual.STATE_EXACTO)


class TestRawEmissionRejection(unittest.TestCase):
    """Rechazo de emisión cruda: f > refresh/2 nunca entrega exacto/aproximado
    (tasks.md 1.3)."""

    def test_sobre_nyquist_siempre_no_disponible(self):
        for f in (30.5, 31.0, 40.0, 45.0, 59.8, 80.0, 100.0):
            cap = visual.visual_capability(f, 59.8)
            self.assertEqual(
                cap.state, visual.STATE_NO_DISPONIBLE,
                msg=f"f={f} no debe ser exacto/aproximado en 59.8 Hz")
            self.assertNotIn(cap.state, (visual.STATE_EXACTO, visual.STATE_APROXIMADO))

    def test_tolerancia_borde(self):
        # 30.0 Hz en 59.8: dentro de tolerancia -> exacto re-etiquetado a 29.9
        cap = visual.visual_capability(30.0, 59.8)
        self.assertEqual(cap.state, visual.STATE_EXACTO)
        self.assertAlmostEqual(cap.effective_hz, 29.9, delta=1e-6)
        # 30.5: fuera de tolerancia -> no disponible
        cap = visual.visual_capability(30.5, 59.8)
        self.assertEqual(cap.state, visual.STATE_NO_DISPONIBLE)

    def test_entradas_invalidas(self):
        for rate, refresh in ((0.0, 59.8), (-3.0, 59.8), (10.0, 0.0), (10.0, None)):
            cap = visual.visual_capability(rate, refresh)
            self.assertEqual(cap.state, visual.STATE_NO_DISPONIBLE)
            self.assertIsNotNone(cap.reason)


# ---------------------------------------------------------------------------
# 2. Patrones (tasks 1.2)
# ---------------------------------------------------------------------------

class TestPatterns(unittest.TestCase):

    def test_exacto_duty_50_pares(self):
        for n in (2, 4, 6, 8):
            pattern = visual._exact_pattern(n)
            self.assertEqual(len(pattern), n)
            self.assertEqual(sum(pattern), n // 2)  # duty 50% exacto en n par
            self.assertTrue(pattern[0])  # arranca en el pulso

    def test_aproximado_duty_y_ventana(self):
        cap = visual.visual_capability(16.0, 59.8)
        pattern = cap.pattern
        duty = sum(pattern) / len(pattern)
        self.assertGreaterEqual(duty, 0.4)
        self.assertLessEqual(duty, 0.6)
        self.assertLessEqual(len(pattern) / 59.8, 1.0 + 1e-9)
        self.assertTrue(pattern[0])

    def test_armonico_patron_3_fotogramas_duty_1_3(self):
        cap = visual.visual_capability(40.0, 59.8, harmonics_enabled=True)
        self.assertEqual(cap.state, visual.STATE_ARMONICO)
        self.assertEqual(cap.frames_per_period, 3)
        self.assertEqual(cap.pattern, [True, False, False])
        self.assertAlmostEqual(sum(cap.pattern) / 3.0, 1.0 / 3.0, delta=1e-9)
        self.assertAlmostEqual(cap.effective_hz, 59.8 / 3.0, delta=1e-6)
        self.assertAlmostEqual(cap.harmonic_of_hz, 2.0 * 59.8 / 3.0, delta=1e-6)

    def test_relacion_coeficientes_armonico(self):
        """|c2|/|c1| del tren de pulsos con duty 1/3 es ~0.5 (design.md)."""
        ratio = visual.harmonic_amplitude_ratio(duty=1.0 / 3.0, k=2)
        self.assertAlmostEqual(ratio, 0.5, delta=1e-9)
        # El patrón de 3 fotogramas implementa duty 1/3
        self.assertAlmostEqual(sum([True, False, False]) / 3.0, 1.0 / 3.0)


# ---------------------------------------------------------------------------
# 3. Armónico opt-in (tasks 4.3) y sustituto (tasks 4.2)
# ---------------------------------------------------------------------------

class TestHarmonicAndSubstitute(unittest.TestCase):

    def test_sin_flag_no_aparece_armonico(self):
        cap = visual.visual_capability(40.0, 59.8, harmonics_enabled=False)
        self.assertEqual(cap.state, visual.STATE_NO_DISPONIBLE)

    def test_con_flag_40hz_usa_3_fotogramas(self):
        cap = visual.visual_capability(40.0, 59.8, harmonics_enabled=True)
        self.assertEqual(cap.state, visual.STATE_ARMONICO)
        self.assertEqual(cap.frames_per_period, 3)
        label = visual.capability_label(cap)
        self.assertIn("39.87", label)
        self.assertIn("harmonic", label)
        self.assertIn("experimental", label)

    def test_candidato_solo_si_existe_divisor(self):
        self.assertIsNotNone(visual.harmonic_candidate(40.0, 59.8))
        self.assertIsNone(visual.harmonic_candidate(35.0, 59.8))
        self.assertIsNone(visual.harmonic_candidate(100.0, 59.8))

    def test_sustituto_maximo_exacto(self):
        sub = visual.best_substitute(59.8)
        self.assertEqual(sub.state, visual.STATE_EXACTO)
        self.assertAlmostEqual(sub.effective_hz, 29.9, delta=1e-6)
        self.assertEqual(sub.frames_per_period, 2)
        self.assertEqual(sub.pattern, [True, False])
        # Etiquetado como frecuencia distinta a la pedida
        self.assertIsNone(sub.requested_hz)


# ---------------------------------------------------------------------------
# 4. Gate de rampa (tasks 1.3)
# ---------------------------------------------------------------------------

class TestRampGate(unittest.TestCase):

    def test_rampa_que_cruza_el_maximo_bloquea(self):
        """El gate se evalúa con el peor punto, no con el valor inicial."""
        cap = visual.ramp_gate_capability(3.0, 40.0, 59.8)
        self.assertEqual(cap.state, visual.STATE_NO_DISPONIBLE)

    def test_rampa_descendente_tambien_bloquea(self):
        cap = visual.ramp_gate_capability(40.0, 3.0, 59.8)
        self.assertEqual(cap.state, visual.STATE_NO_DISPONIBLE)

    def test_rampa_soportable_no_bloquea(self):
        cap = visual.ramp_gate_capability(20.0, 3.0, 59.8)
        self.assertIn(cap.state, (visual.STATE_EXACTO, visual.STATE_APROXIMADO))
        # El peor punto (7 Hz no divide el refresco) es aproximado
        self.assertEqual(cap.state, visual.STATE_APROXIMADO)

    def test_rampa_solo_exactos(self):
        cap = visual.ramp_gate_capability(29.9, 29.9, 59.8)
        self.assertEqual(cap.state, visual.STATE_EXACTO)


# ---------------------------------------------------------------------------
# 5. Etiquetas y feedback de potencia (tasks 4.4)
# ---------------------------------------------------------------------------

class TestLabels(unittest.TestCase):

    def test_etiqueta_exacto(self):
        cap = visual.visual_capability(29.9, 59.8)
        self.assertEqual(visual.capability_label(cap), "Exact")

    def test_etiqueta_exacto_reetiquetado(self):
        cap = visual.visual_capability(10.0, 59.8)
        label = visual.capability_label(cap)
        self.assertIn("9.97", label)

    def test_etiqueta_aproximado_con_jitter(self):
        cap = visual.visual_capability(16.0, 59.8)
        label = visual.capability_label(cap)
        self.assertIn("Approximate", label)
        self.assertIn("jitter", label)
        self.assertIn("ms", label)

    def test_etiqueta_no_disponible_con_razon(self):
        cap = visual.visual_capability(40.0, 59.8)
        label = visual.capability_label(cap)
        self.assertIn("Unavailable", label)
        self.assertIn("29.9", label)

    def test_notas_intensidad(self):
        self.assertIn("weaker visual response", visual.intensity_note("comoda"))
        self.assertIn("maximum contrast", visual.intensity_note("brillante"))


# ---------------------------------------------------------------------------
# 6. Calibración: estadísticas con reloj falso (tasks 2.1)
# ---------------------------------------------------------------------------

class TestRefreshStats(unittest.TestCase):

    def test_pantalla_598(self):
        stamps = [k / 59.8 for k in range(120)]
        refresh, jitter = visual.compute_refresh_stats(stamps)
        self.assertAlmostEqual(refresh, 59.8, delta=1e-4)
        self.assertLess(jitter, 0.5)

    def test_jitter_medido(self):
        import random
        rng = random.Random(7)  # determinista: ruido de media cero
        stamps = []
        t = 0.0
        for k in range(2000):
            stamps.append(t)
            t += 1.0 / 59.8 + rng.uniform(-0.002, 0.002)
        refresh, jitter = visual.compute_refresh_stats(stamps)
        # La mediana de ~2000 deltas ruidosos converge al periodo real
        self.assertAlmostEqual(refresh, 59.8, delta=0.3)
        self.assertGreater(jitter, 1.0)
        self.assertLess(jitter, 6.0)

    def test_marcas_insuficientes(self):
        with self.assertRaises(ValueError):
            visual.compute_refresh_stats([0.0, 0.1, 0.2])

    def test_validacion_plausibilidad(self):
        self.assertEqual(visual.validate_refresh_measurement(59.8, 0.5), (True, "high"))
        self.assertEqual(visual.validate_refresh_measurement(59.8, 4.0), (True, "medium"))
        self.assertEqual(visual.validate_refresh_measurement(5000.0, 0.1), (False, "low"))
        self.assertEqual(visual.validate_refresh_measurement(59.8, 9.0), (False, "low"))


# ---------------------------------------------------------------------------
# 7. Config persistente y compatibilidad (tasks 2.2)
# ---------------------------------------------------------------------------

class TestVisualConfig(unittest.TestCase):

    def test_config_sin_claves_no_rompe(self):
        v = visual.merge_visual_config({})
        self.assertIsNone(v["refresh_hz"])
        self.assertFalse(v["photosensitive_consent"])
        self.assertEqual(v["intensity"], "comoda")
        self.assertFalse(v["harmonics_enabled"])

    def test_config_parcial(self):
        v = visual.merge_visual_config({"visual": {"intensity": "brillante"}})
        self.assertEqual(v["intensity"], "brillante")
        self.assertFalse(v["photosensitive_consent"])

    def test_valores_invalidos_a_defaults(self):
        v = visual.merge_visual_config({
            "visual": {"intensity": "nada", "refresh_hz": "abc",
                       "photosensitive_consent": "si", "harmonics_enabled": 1}
        })
        self.assertEqual(v["intensity"], "comoda")
        self.assertIsNone(v["refresh_hz"])
        self.assertTrue(v["photosensitive_consent"])
        self.assertTrue(v["harmonics_enabled"])

    def test_roundtrip(self):
        raw = {"visual": {"refresh_hz": 59.8, "jitter_ms": 1.2,
                          "calibrated_at": "2026-10-19", "confidence": "high",
                          "photosensitive_consent": True,
                          "intensity": "brillante", "harmonics_enabled": True}}
        v = visual.merge_visual_config(raw)
        self.assertAlmostEqual(v["refresh_hz"], 59.8)
        self.assertEqual(v["calibrated_at"], "2026-10-19")
        self.assertTrue(v["photosensitive_consent"])


# ---------------------------------------------------------------------------
# 8. BeatClock (fase del pulso de audio, incl. rampa)
# ---------------------------------------------------------------------------

class TestBeatClock(unittest.TestCase):

    def test_constante(self):
        bc = visual.BeatClock(rate_hz=29.9)
        self.assertAlmostEqual(bc.cycles(1.0), 29.9)
        self.assertAlmostEqual(bc.rate_at(5.0), 29.9)
        b = bc.next_boundary(0.0)
        self.assertAlmostEqual(b, 1.0 / 29.9, delta=1e-6)
        self.assertAlmostEqual(bc.cycles(b), 1.0, delta=1e-6)

    def test_constante_siguiente_frontera(self):
        bc = visual.BeatClock(rate_hz=10.0)
        b = bc.next_boundary(0.13)  # cycles = 1.3 -> siguiente entero = 2
        self.assertAlmostEqual(b, 0.2, delta=1e-6)

    def test_rampa_coincide_con_formula_del_motor(self):
        """rate_at reproduce _compute_ramped_beat_hz de SourceCode.py."""
        f0, f1, T = 20.0, 3.0, 30.0
        bc = visual.BeatClock(start_hz=f0, end_hz=f1, ramp_s=T)
        for t in (0.0, 1.5, 7.5, 15.0, 29.0, 30.0, 45.0):
            expected = f0 + (f1 - f0) * (min(max(t / T, 0.0), 1.0))
            self.assertAlmostEqual(bc.rate_at(t), expected, delta=1e-9)
        # cycles(T) = promedio de frecuencias * T
        self.assertAlmostEqual(bc.cycles(T), (f0 + f1) / 2.0 * T, delta=1e-9)
        # tras la rampa avanza a f1
        self.assertAlmostEqual(bc.cycles(T + 10.0) - bc.cycles(T), 30.0, delta=1e-9)

    def test_rampa_frontera_cae_en_ciclo_entero(self):
        bc = visual.BeatClock(start_hz=20.0, end_hz=3.0, ramp_s=30.0)
        b = bc.next_boundary(1.0)
        self.assertGreater(b, 1.0)
        # La frontera cae en un ciclo entero (con el epsilon de bisección)
        c = bc.cycles(b)
        self.assertLess(abs(c - round(c)), 1e-6)

    def test_rechaza_frecuencia_invalida(self):
        with self.assertRaises(ValueError):
            visual.BeatClock(rate_hz=0.0)


# ---------------------------------------------------------------------------
# 9. Scheduler con reloj falso (tasks 3.2)
# ---------------------------------------------------------------------------

class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


class _Runner:
    """Entorno con reloj falso y tiempo de audio derivable (con deriva opcional)."""

    def __init__(self, rate=29.9, refresh=59.8, pattern=None, cpw=1,
                 drift=0.0, reanchor=1.0, free_running=False, beat_clock=None,
                 rebuild_fn=None):
        self.clock = FakeClock(0.0)
        self.drift = drift

        def get_audio_time():
            return (1.0 + drift) * self.clock.t

        self.beat_clock = beat_clock or visual.BeatClock(rate_hz=rate)
        cap_pattern = pattern if pattern is not None else [True, False]
        self.flips = []

        def on_flip(state):
            self.flips.append((self.clock.t, state))

        self.sched = visual.StrobeScheduler(
            cap_pattern, refresh, on_flip, self.clock,
            get_audio_time, self.beat_clock, cycles_per_window=cpw,
            free_running=free_running, reanchor_interval_s=reanchor,
            rebuild_fn=rebuild_fn)

    def run(self, seconds, step=0.001, max_iters=200000):
        d = self.sched.start()
        t = 0.0
        it = 0
        while t < seconds and it < max_iters:
            it += 1
            self.clock.t = t
            d = self.sched.poll(now=t)
            t += step
        return d

    def on_sets(self):
        return [t for t, s in self.flips if s]

    def off_sets(self):
        return [t for t, s in self.flips if not s]


class TestStrobeScheduler(unittest.TestCase):

    def test_flips_exactos_ritmo_y_fase(self):
        r = _Runner(rate=29.9, refresh=59.8)
        r.run(2.0)
        # Un flip de encendido por ciclo, en la frontera del pulso
        onsets = r.on_sets()
        self.assertGreaterEqual(len(onsets), 58)
        self.assertLessEqual(len(onsets), 61)
        for k, t in enumerate(onsets):
            self.assertAlmostEqual(t, k / 29.9, delta=0.0015)
        # Off a medio ciclo (fase 0.5)
        offs = r.off_sets()
        for k, t in enumerate(offs):
            self.assertAlmostEqual(t, (k + 0.5) / 29.9, delta=0.0015)
        # Duty ~50%
        on_time = sum(b - a for a, b in zip(onsets, offs))
        self.assertAlmostEqual(on_time / 2.0, 0.5, delta=0.03)

    def test_flips_tardios_se_saltan_sin_rafa(self):
        r = _Runner(rate=29.9, refresh=59.8)
        d = r.sched.start()  # flip ON en t=0
        self.assertEqual(len(r.flips), 1)
        # Llegamos MUY tarde (~15 flips perdidos): un solo salto al estado actual
        r.clock.t = 0.5
        d2 = r.sched.poll(now=0.5)
        self.assertEqual(len(r.flips), 2)
        self.assertEqual(r.flips[1], (0.5, False))  # fase 0.95 -> apagado
        self.assertIsNotNone(d2)
        self.assertGreater(d2, 0.5)
        # Sin acumulación de atraso: el próximo pulso sigue en la rejilla
        r.clock.t = d2
        r.sched.poll(now=d2)
        t_on = r.on_sets()[-1]
        self.assertAlmostEqual(t_on, 15.0 / 29.9, delta=0.0015)

    def test_reanclaje_absorbe_deriva_del_cristal(self):
        """Audio 0.5% más rápido que el reloj del sistema: con re-anclaje el
        pulso visual sigue enganchado al de audio (<= ~6 ms de error)."""
        r = _Runner(rate=29.9, refresh=59.8, drift=0.005, reanchor=1.0)
        r.run(3.0)
        onsets = r.on_sets()
        self.assertGreater(len(onsets), 85)
        expected = [k / (29.9 * 1.005) for k in range(len(onsets))]
        for got, exp in zip(onsets, expected):
            self.assertAlmostEqual(got, exp, delta=0.0065)

    def test_sin_reanclaje_la_deriva_se_acumula(self):
        """Contraste: sin re-anclaje (intervalo enorme) la fase se desvía más."""
        r = _Runner(rate=29.9, refresh=59.8, drift=0.005, reanchor=1e9)
        r.run(3.0)
        onsets = r.on_sets()
        # Sin corrección, tras 3 s la deriva es ~15 ms (media fase)
        self.assertGreater(abs(onsets[-1] - (len(onsets) - 1) / (29.9 * 1.005)), 0.008)

    def test_audio_detenido_sin_flips(self):
        clock = FakeClock(0.0)
        flips = []

        def on_flip(state):
            flips.append((clock.t, state))

        def frozen_audio():
            return 0.35  # audio congelado

        sched = visual.StrobeScheduler(
            [True, False], 59.8, on_flip, clock, frozen_audio,
            visual.BeatClock(rate_hz=29.9), cycles_per_window=1)
        d = sched.start()
        # Primer segundo: extrapolamos como si sonara (hasta el re-anclaje)
        t = 0.0
        while t < 1.2:
            clock.t = t
            d = sched.poll(now=t)
            if d is None:
                break
            t += 0.01
        n_after_stall = len(flips)
        # Tras detectar el estancamiento no hay más flips
        for t in (1.5, 2.0, 3.0):
            clock.t = t
            self.assertIsNone(sched.poll(now=t))
        self.assertEqual(len(flips), n_after_stall)

    def test_rebuild_de_patron_en_reanclaje(self):
        """El scheduler puede cambiar de patrón en el re-anclaje (rampas)."""
        r = _Runner(rate=16.0, refresh=59.8, pattern=[True, False] * 8,
                    cpw=8,
                    rebuild_fn=lambda rate: ([True, False, False, False], 2))
        self.assertEqual(r.sched.W, 16)
        r.run(1.2)
        self.assertEqual(r.sched.pattern, [True, False, False, False])
        self.assertEqual(r.sched.cpw, 2)

    def test_modo_libre_armonica_sin_jitter(self):
        """Armónico: patrón de 3 fotogramas a R/3 exacto, anclado al pulso."""
        clock = FakeClock(0.0)
        flips = []

        def on_flip(state):
            flips.append((clock.t, state))

        def get_audio():
            return clock.t

        sched = visual.StrobeScheduler(
            [True, False, False], 59.8, on_flip, clock, get_audio,
            visual.BeatClock(rate_hz=59.8 / 3.0), cycles_per_window=1,
            free_running=True)
        d = sched.start()
        t = 0.0
        while t < 2.0:
            clock.t = t
            d = sched.poll(now=t)
            if d is None:
                break
            t = max(t + 0.001, min(d, t + 0.005))
        onsets = [t for t, s in flips if s]
        # Fundamental exacta R/3 = 19.933 Hz
        self.assertAlmostEqual(len(onsets) / 2.0, 59.8 / 3.0, delta=0.4)
        # Cero jitter: espaciado constante de exactamente 3 fotogramas
        period = 3.0 / 59.8
        for a, b in zip(onsets, onsets[1:]):
            self.assertAlmostEqual(b - a, period, delta=0.0015)
        # Duración del pulso: exactamente 1 fotograma (duty 1/3)
        offs = [t for t, s in flips if not s]
        on_durations = [b - a for a, b in zip(onsets, offs)]
        for dur in on_durations:
            self.assertAlmostEqual(dur, 1.0 / 59.8, delta=0.0015)


class TestLatenessMonitor(unittest.TestCase):

    def test_umbral_de_aborto(self):
        mon = visual.LatenessMonitor(frame_period_s=1.0 / 59.8)
        now = 100.0
        for i in range(10):
            mon.record(now + i * 0.01, 0.001)  # lateness pequeña
        self.assertFalse(mon.should_abort())
        for i in range(10):
            mon.record(now + i * 0.01, 0.005)  # > 15% del período (2.5 ms)
        self.assertTrue(mon.should_abort())

    def test_ventana_desliza(self):
        mon = visual.LatenessMonitor(frame_period_s=1.0 / 59.8, window_s=0.5)
        for i in range(10):
            mon.record(10.0 + i * 0.01, 0.005)
        self.assertTrue(mon.should_abort())
        # Muestras nuevas (y pequeñas) expulsan a las viejas de la ventana
        for i in range(12):
            mon.record(20.0 + i * 0.01, 0.0005)
        self.assertFalse(mon.should_abort())

    def test_pocas_muestras_no_abortan(self):
        mon = visual.LatenessMonitor(frame_period_s=1.0 / 59.8)
        for i in range(3):
            mon.record(i * 0.01, 0.05)
        self.assertFalse(mon.should_abort())



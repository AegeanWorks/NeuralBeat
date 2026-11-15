# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.

<!-- Entry format:
### ADR-NNN: <decision in one line>
- **Date**: YYYY-MM-DD
- **Status**: Accepted
- **Context**: <what forced the decision>
- **Decision**: <what was decided>
- **Consequences**: <what follows, including what it costs>
-->

### ADR-001: Relicense NeuralBeat to AGPL-3.0
- **Date**: 2026-10-20
- **Status**: Accepted
- **Context**: NeuralBeat shipped under Apache-2.0 while the rest of the project portfolio moved to AGPL-3.0, so the repository, README and GitHub license badge disagreed with the portfolio contract.
- **Decision**: Replace the Apache-2.0 LICENSE with the canonical GNU Affero General Public License v3.0 text, update the README license section, and publish the change with the repository.
- **Consequences**:
  - *Positive*: One copyleft contract across the portfolio; GitHub detects AGPL-3.0; contributors and users see the same terms in LICENSE and README.
  - *Trade-offs*: NeuralBeat moves from a permissive license to a strong copyleft license; consumers who need Apache-2.0 terms must use an earlier commit or request a separate grant.
- Cross-principle check: PRINCIPLE-005 (README), PRINCIPLE-016 (ADR), PRINCIPLE-018 (commit and push).

## Licensing migration (agpl-final)

- New versions use the Aegean License 1.1 (AL-1.1); versions up to and including `agpl-final` remain under GNU AGPL-3.0.
- Rights holder: AegeanWorks; commercial use under ACL-1.0.
- Counsel review of the 1.1 texts remains pending.

## License notice cleanup (2026-10-26)

- The license-history notes were removed from README.md and COMMERCIAL.md: the project is offered only under the Aegean License 1.1 (AL-1.1), with commercial use under ACL-1.0.

### ADR-002: Keep isochronic presets and controls consistent with the mono generator
- **Date**: 2026-10-29
- **Status**: Accepted
- **Context**: Isochronic presets were saved as `left_hz`/`right_hz` while the preset list read `carrier_hz`/`pulse_hz`, so a saved preset applied 10 Hz at 200 Hz; the mono isochronic generator also left the right-ear volume and waveform controls active even though it uses only the left channel.
- **Decision**: Store isochronic user presets with `carrier_hz` and `pulse_hz`, validate pulse and carrier ranges separately, keep a `left_hz`/`right_hz` fallback for older records, and hide the right volume and waveform controls while isochronic mode is selected.
- **Consequences**:
  - *Positive*: Saved isochronic presets reproduce the values the user entered, and the UI no longer exposes controls that do nothing.
  - *Trade-offs*: The user-preset schema now differs by category; older isochronic records remain readable through the fallback.
- Cross-principle check: PRINCIPLE-016 (ADR), PRINCIPLE-018 (commit and push).

### ADR-003: Main-window keeper via PrintWindow; fullscreen grabs the wrong window
- **Date**: 2026-11-03
- **Status**: Accepted
- **Context**: No registered screenshots existed; the legacy root capture was unrecorded. Fullscreen ImageGrab framed the IDE because the Tk window never takes focus from a headless launcher.
- **Decision**: Register `2026-11-03-main.png` (`python SourceCode.py`, PrintWindow on `NeuralBeat 1.0.0`, 1125x655, commit `32c408a`) in `.aikit/media.json` and the README `aegean:screenshots` block. The single window is the whole UI, so one keeper is full coverage. No audio was generated (Generate never pressed).
- **Consequences**: README proves the current app. Reproduce with the launch plus PrintWindow script above.

### ADR-004: Preserve oscilloscope UI keys on profile import
- **Date**: 2026-11-03
- **Status**: Accepted
- **Context**: Profile import/export was introduced in wave 30 (`01c0274` v0.8.1). `export_config_json` writes the full in-memory config (including `osc_colors`, `osc_merge_waves`), but `import_config_json` rebuilt only `user_presets` plus `theme`, silently dropping the oscilloscope settings on every round-trip.
- **Decision**: Carry `osc_colors` through only when it names a palette in `OSC_COLOR_PALETTES`, and `osc_merge_waves` only when it is a `bool`; other keys remain excluded and invalid values are ignored without crashing.
- **Consequences**:
  - *Positive*: Export then import preserves the visualizer appearance; invalid profile values cannot corrupt the live config.
  - *Trade-offs*: Unknown future top-level keys are still dropped on import; they need an explicit allow-list entry.
- Cross-principle check: PRINCIPLE-016 (ADR), PRINCIPLE-013 (state atomicity via existing save path), PRINCIPLE-018 (commit and push).

### ADR-005: Refactor UI for aesthetic, sleek, minimalistic layout and modern design hierarchy
- **Date**: 2026-11-16
- **Status**: Accepted
- **Context**: The existing UI featured nested raw borders, ragged input alignments, cramped preset button rows, and cluttered layout per user request for an aesthetic, sleek, minimalistic interface
- **Decision**: Adopt uniform card containers, symmetrical 2x2 ramp parameters, sleek inverse status pill, prominent hero action buttons, and aligned preset manager while preserving all functional bindings
- **Consequences**: Improved visual hierarchy, uncluttered layout, zero test regressions, and full compatibility with existing audio engine and visual mode

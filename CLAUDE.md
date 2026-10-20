# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a **NOMAD dev distribution** — a uv workspace monorepo for developing [NOMAD Lab](https://nomad-lab.eu) and its plugins together in editable mode. It is a fork of [nomad-distro-dev](https://github.com/FAIRmat-NFDI/nomad-distro-dev), maintained at HZB (Helmholtz-Zentrum Berlin) for thin-film solar cell and energy materials research.

All packages under `packages/` are git submodules installed in editable mode via `uv` workspace.

The three actively developed plugins are:

- **`packages/nomad-baseclasses`** — reusable NOMAD schema base classes for HZB experiments
- **`packages/nomad-hysprint`** — Hysprint lab plugin for perovskite solar cells
- **`packages/nomad-tfsc-general`** — PERSEUS/TFSC general plugin for thin-film solar cells

## Common Commands

All commands run from the repo root. `uv run poe` is equivalent to `poe` if `poethepoet` is installed globally via `uv tool install poethepoet`.

```bash
# Initial setup (starts Docker, creates nomad.yaml if missing; no longer sets up the legacy GUI)
uv run poe setup

# Start NOMAD API app (development mode); also serves the new GUI
uv run poe start

# Legacy GUI only: one-time install, then start the yarn dev server
uv run poe gui-setup
uv run poe gui

# Linting (ruff check + format check)
uv run poe lint
uv run ruff check .
uv run ruff format . --check

# Run tests for a specific package
uv run --directory packages/nomad-tfsc-general pytest
uv run --directory packages/nomad-hysprint pytest
uv run --directory packages/nomad-baseclasses pytest

# Run a single test file
uv run --directory packages/nomad-tfsc-general pytest tests/test_foo.py

# Run tests in isolated venv (avoids cross-package interference)
uv run --exact --all-extras --package nomad-tfsc-general --directory packages/nomad-tfsc-general pytest

# Docker
docker compose up -d
docker compose down
```

The new GUI (the `nomad-gui` package) is served by the API at `http://localhost:8000/nomad-oasis/gui/v2/`. The legacy GUI runs at `http://localhost:3000/nomad-oasis/gui` only after `poe gui-setup`.

## Choosing Active Plugins

Which local plugins are active is controlled in two places, and they must agree:

1. Root `pyproject.toml`: the plugin must be listed in `[project] dependencies`, `[tool.uv.workspace] members`, and `[tool.uv.sources]` (`{ workspace = true }`). Commented-out lines mean the plugin is not installed. Run `uv sync` after changing them.
2. Root `nomad.yaml` (untracked, local): `plugins.entry_points.include` lists the entry points the running server loads. An installed plugin whose entry points are not listed is inactive.

**Parser overlap**: when nomad-hysprint and nomad-tfsc-general are both installed, the hysprint batch parser also matches tfsc-general's Excel test files, so tfsc-general tests fail unless hysprint's entry points are excluded. Run tfsc-general tests with a config that excludes them, for example a temp `nomad.yaml` passed via `NOMAD_CONFIG`:

```yaml
plugins:
  entry_points:
    exclude: ["nomad_hysprint.parsers:hysprint_parser", "nomad_hysprint.parsers:hysprint_experiment_parser"]
```

The same overlap applies in the server if both plugins' parsers are enabled in the root `nomad.yaml`.

**nomad-baseclasses tests**: its `nomad.yaml` uses the pre-entry-point plugin format (`plugins.include: 'schemas/baseclasses'`), which nomad-lab 1.4.4+ rejects. Use `plugins: {entry_points: {include: []}}` instead. Its only test (`tests/test_schema.py`) is a leftover from the plugin template and checks a schema that does not exist.

## NOMAD Plugin Architecture

NOMAD plugins are Python packages registered via `[project.entry-points.'nomad.plugin']` in `pyproject.toml`. Each entry point references a class in `schema_packages/`, `parsers/`, or `apps/` that implements the plugin interface.

### Schema System

All schema classes use NOMAD's **metainfo** system (`nomad.metainfo`). Key building blocks:

- **`Section`** — defines the schema for an entry type; `m_def = Section(...)` customizes ELN display
- **`Quantity`** — a typed field with optional unit, ontology links, and ELN widget config
- **`SubSection`** — nested section (composition)
- **`Reference`** — pointer to another entry in the NOMAD archive

ELN display is controlled via `a_eln` dict on Section and Quantity:

```python
m_def = Section(a_eln=dict(hide=['lab_id', 'users'], properties=dict(order=[...])))
quantity = Quantity(type=np.float64, unit='V', a_eln=dict(component='NumberEditQuantity', defaultDisplayUnit='mV'))
```

Ontology annotation uses `links=[...]` on Quantity with CHEBI/PATO/TFSCO URIs.

All concrete entry types inherit from `nomad.datamodel.data.EntryData` (makes them top-level NOMAD entries). Internal sections inherit from `ArchiveSection` or NOMAD base sections (`Entity`, `Process`, `Measurement`, `CompositeSystem`).

### `normalize()` Method

Every schema class can override `normalize(self, archive, logger)` to run post-processing on save. This is the main extension point for:

- Parsing raw data files referenced by a `data_file` quantity
- Auto-populating derived quantities (e.g. `add_solar_cell()` populates `Results`)
- Setting cross-references between entries

Always call `super().normalize(archive, logger)` first.

## Package: `nomad-baseclasses`

Source: `packages/nomad-baseclasses/src/baseclasses/`

This is the **domain library** for HZB experiments. It provides reusable base classes that nomad-hysprint and nomad-tfsc-general import and extend. It is not a NOMAD plugin itself but a Python package.

### Key Subpackages

| Subpackage | Contents |
| --- | --- |
| `solar_energy/` | `SolcarCellSample`, `JVMeasurement`, `EQEMeasurement`, `MPPTracking`, `Substrate`, PLimaging, UV-Vis, TRPL, SPV |
| `wet_chemical_deposition/` | `SpinCoating`, `BladeCoating`, `SlotDieCoating`, `InkjetPrinting`, `ScreenPrinting`, `GravurePrinting`, `WetChemicalDeposition` |
| `vapour_based_deposition/` | `AtomicLayerDeposition`, `Evaporations`, `Sputtering`, `CloseSpaceSublimation` |
| `material_processes_misc/` | `Cleaning` (+ subtypes), `LaserScribing`, `Lamination`, `Annealing`, `Quenching` |
| `chemical_energy/` | Electrochemistry: `CyclicVoltammetry`, `EIS`, potentiostat measurements, GC coupling |
| `helper/` | `add_solar_cell.py` (populates Results), `utilities.py` (archive manipulation), `solar_cell_batch_mapping.py`, `file_parser/`, `archive_builder/` |

The top-level `__init__.py` re-exports the most-used base classes: `BaseMeasurement`, `BaseProcess`, `Batch`, `LayerDeposition`, `ReadableIdentifiersCustom`.

### Helper Utilities

- `baseclasses.helper.utilities.set_sample_reference` — resolves and sets sample cross-references
- `baseclasses.helper.utilities.get_encoding(filepath)` — detects file encoding for raw data parsing
- `baseclasses.helper.add_solar_cell.add_solar_cell` — auto-populates `archive.results.properties.optoelectronic` from JV data
- `baseclasses.helper.add_solar_cell.add_band_gap` — populates band gap from EQE

## Package: `nomad-hysprint`

Source: `packages/nomad-hysprint/src/nomad_hysprint/`

Plugin for the **Hysprint lab** at HZB. Focused on perovskite solar cell high-throughput research with Excel-based batch workflows.

### Package Layout

```text
schema_packages/
  hysprint_package.py       # ~100 HySprint_* classes
  solai_package.py          # SOLAI high-throughput variant
  solartab_package.py       # Simulation data
  ink_recycling_package.py  # Ink recycling workflows
  file_parser/              # JV, MPP, EQE, PL, XRD, NMR parsers
parsers/
  parser.py                 # Batch/sample Excel parser
  experiment_parser.py      # Experimental plan parser
apps/
  voila.py                  # Voila notebooks + solar_cell_overview search
```

### Hysprint Class Naming Pattern

All public classes follow `HySprint_<BaseclassName>`, e.g.:

- `HySprint_Sample` extends `SolcarCellSample` + `EntryData`
- `HySprint_JVmeasurement` extends `JVMeasurement` + `EntryData`
- `HySprint_Cleaning` extends `Cleaning` + `EntryData`

Custom behavior is added via `normalize()` (calls file parsers) and `a_eln` UI overrides. The pattern is always: **inherit base class + EntryData, override `m_def` for ELN display, override `normalize()` to parse data files**.

### File Parsers (in `schema_packages/file_parser/`)

Each measurement class references a `data_file` quantity; `normalize()` reads it:

- `.jv.txt` → JV curve data with sign auto-correction
- `.csv` → MPP tracking with multi-pixel support and plotly visualizations
- `.eqe.txt` → EQE spectra
- `.abspl.txt`, `.trpl.txt` → Absolute and time-resolved photoluminescence

## Package: `nomad-tfsc-general`

Source: `packages/nomad-tfsc-general/src/nomad_tfsc_general/`

Plugin for the **PERSEUS project** at HZB. General-purpose thin-film solar cell ELN covering multiple deposition technologies (printing, vapor deposition, wet chemistry).

### TFSC Package Layout

```text
schema_packages/
  tfsc_general_package.py   # All TFSC_General_* classes (single file)
  file_parser/              # JV, MPP parsers; EQE parser reused from hysprint
parsers/
  parser.py                 # Excel batch parser
  experiment_parser.py      # Experimental plan parser  
apps/
  voila.py                  # Voila notebooks + Perseus search UIs
```

### TFSC Class Naming Pattern

All classes follow `TFSC_General_<BaseclassName>`:

- `TFSC_General_Sample`, `TFSC_General_Substrate`, `TFSC_General_Batch`
- `TFSC_General_JVmeasurement`, `TFSC_General_EQEmeasurement`, `TFSC_General_MPPTracking`
- Process classes: `TFSC_General_Cleaning`, `TFSC_General_SpinCoating`, `TFSC_General_SlotDieCoating`, `TFSC_General_AtomicLayerDeposition`, `TFSC_General_Sputtering`, `TFSC_General_Evaporations`, `TFSC_General_LaserScribing`, `TFSC_General_Lamination`

All classes are defined in the single file `tfsc_general_package.py`.

**Cross-package dependency**: `TFSC_General_EQEmeasurement.normalize()` imports the EQE file parser (`read_file`, `read_file_multiple`) from `nomad_hysprint`.

### Entry Points

| Entry Point | Purpose |
| --- | --- |
| `tfsc_general_parser` | Parses `.xlsx` batch files → creates sample/process entries |
| `tfsc_general_experiment_experiment_parser` | Parses experimental plan Excel files |
| `tfsc_general_package` | Registers all `TFSC_General_*` schema classes |
| `tfsc_perseus_search_app` | Perseus sample search UI in NOMAD GUI |
| `tfsc_perseus_layer_search_app` | Perseus layer search UI in NOMAD GUI |

## Dependency Hierarchy

```text
nomad-lab (core NOMAD framework)
    └── nomad-baseclasses (HZB domain base classes)
            ├── nomad-hysprint (Hysprint perovskite lab)
            └── nomad-tfsc-general (TFSC/PERSEUS lab)
                    └── imports EQE parser from nomad-hysprint at runtime
```

Both `nomad-hysprint` and `nomad-tfsc-general` declare `nomad-baseclasses` via git URL in `pyproject.toml`, but in this workspace the local `packages/nomad-baseclasses` takes precedence via `[tool.uv.sources]`.

## Adding a New Schema Class

1. In the target package's `schema_packages/<package>.py`, inherit from the appropriate baseclasses class + `EntryData`.
2. Set `m_def = Section(a_eln=dict(...))` to customize ELN display (hide unused fields, set field order).
3. Add a `data_file = Quantity(type=str, a_eln=dict(component='FileEditQuantity'))` if the entry parses raw data.
4. Override `normalize(self, archive, logger)`, call `super().normalize(archive, logger)` first, then add custom logic.
5. Register the class in the `SchemaPackage` at the bottom of the file: `m_package.__init_metainfo__()`.

## Workspace Management

```bash
# Sync environment after pyproject.toml changes
uv sync

# Add a dependency to a specific package
uv add --package nomad-tfsc-general pandas

# Add a new submodule plugin
git submodule add https://github.com/<org>/<repo>.git packages/<name>
uv add packages/<name>
```

### Updating the distro and nomad-FAIR

This repo is a **fork with local commits**. `origin` is `github.com/Dimi-G/nomad-distro-dev` and is usually behind; `upstream` is `FAIRmat-NFDI/nomad-distro-dev`. Use the `/update-distro` skill for the full procedure. The short version:

```bash
git fetch upstream
git merge upstream/main
git submodule update packages/nomad-FAIR   # only nomad-FAIR
uv sync
```

Do not:

- **Run `git pull` or `git pull --recurse-submodules`** in the superproject. Upstream's README advice assumes a plain clone. Here it pulls the stale fork, and with rebase enabled it replays every local commit onto it.
- **Run a blanket `git submodule update --init --recursive`**. It detaches nomad-baseclasses, nomad-hysprint, nomad-tfsc-general and the perovskite database from the branches they are developed on and resets them to old pinned commits. Update those repos inside their own directories, then commit the new pointers here with `git add packages/<name>`.
- **Commit large binaries** such as installers to the superproject. Check `git diff --stat origin/main..main` before pushing.

Pushing: `origin` uses HTTPS without stored credentials on this machine, but SSH works. Push with `git push git@github.com:Dimi-G/nomad-distro-dev.git main:main` or switch `origin` to the SSH URL.

### Infrastructure notes (nomad-lab 1.4.4.dev, October 2026)

- **Elasticsearch**: nomad-lab supports ES 7 and 9 via `elastic.version` in `nomad.yaml` (default `'7'`, deprecated, removed in v2.2.0). This dev distro's docker-compose still runs 7.17, which is fine for development. Production template 2.0.0 uses 9.5.
- **MongoDB**: the dev container runs 5.0, which the current pymongo driver supports. `upgrade_mongo.py` is FAIRmat's official 5→6→7→8 Oasis migration script (nomad-docs "Migrate to NOMAD 1.4.2"), not needed for dev.
- **Archives**: new uploads use the v3 archive format. Older archives are still readable; `nomad admin uploads convert` migrates them optionally.
- **pydantic**: nomad-baseclasses pins `pydantic<2.11`, which holds the whole environment on 2.10 although nomad-lab accepts newer.
- **Startup warnings** about "unsupported keys" (`MenuItemHistogram: unit`, `Axis: format`) come from the third-party `nomad_luqy_plugin` and are harmless.

## NOMAD 2.0, the new GUI, and HZB Oasis deployments

nomad-lab **2.0.0** and nomad-gui **2.0.0** were released on 2026-10-18, together with nomad-distro-template v2.0.0. This dev distro was still on the 1.4.4.dev264 develop pin, 39 commits behind 2.0.0, as of 2026-10-20.

- **Plugin code**: use the `/nomad-plugin-modernize` skill. Its audit script is `.claude/skills/nomad-plugin-modernize/scripts/audit_plugin.py`.
  - The biggest issue is the **115 legacy `a_plot` annotations**, 97 of them in baseclasses. The new GUI does not render them. Convert them to `PlotSection` plots before the old GUI is removed in v2.3.0.
  - Deprecated App fields in the hysprint and tfsc-general apps are the next issue.
  - For bulk mechanical changes, use the `nomad-plugin-modernizer` agent, one per package.
- **Oasis deployments** are separate `nomad-hzb/*-image` repos built from FAIRmat's template. Use the `/nomad-oasis-maintain` skill for updates, the 1.4 to 2.0 upgrade, Mongo and ES migrations, backups and security. perseus-image is on 2.0.0. Most others are still on 1.4.2 with ES7 and logtransfer.
- **URLs differ**:
  - dev distro: new GUI at `localhost:8000/nomad-oasis/gui/v2/`
  - Oasis on template 2.0: new GUI at `/`, old GUI at `/gui/`, API at `/backend/api/v1`
- **baseclasses is in every HZB Oasis image.** Changes there roll out everywhere, so test them here first.

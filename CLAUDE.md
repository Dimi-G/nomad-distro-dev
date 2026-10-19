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
# Initial setup (installs deps, starts Docker, configures GUI env)
uv run poe setup

# Start NOMAD API app (development mode)
uv run poe start

# Start GUI (yarn dev server)
uv run poe gui start

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

NOMAD instance runs at `http://localhost:3000/nomad-oasis/gui`, API at `http://localhost:8000`.

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

# Update all submodules
git pull --recurse-submodules
uv sync
```

# Opportunities for the HZB packages with NOMAD 2.x

These are ideas mapped to concrete code. They were not discussed or approved with the user. Propose them, don't just implement them.

## Must-do before the old GUI disappears (v2.3.0)

1. **Plots** (115 `a_plot`): baseclasses first, since hysprint and tfsc inherit from it.
   - Start with the classes people look at most: JV (`solar_energy/jvmeasurement.py`), EQE, MPP tracking, UV-vis, PL/TRPL, XRD.
   - Then the chemical-energy group, such as chronoamperometry, EIS and voltammetry. Their y values (`voltage_rhe_*`, `z_real`) also suit graph objects.
   - Recipe A covers most, since x is time, energy, wavelength or angle. Use Recipe B for the `jv_curve/:/...` and `eqe_data/:/...` cases.
2. **Apps** in hysprint (solar cell overview, voila) and tfsc-general (perseus search, layer search): rename deprecated fields and replace `filter_menus` with `menu`.
3. **Fix baseclasses tests**: config format, real tests, and drop the template leftover.
4. **Resolve the batch parser overlap**: add a distinguishing marker or use per-deployment include/exclude.

## Should-do

- **Raise `nomad-lab` floors** once 2.x-only APIs are used. Relax baseclasses' `pydantic<2.11` pin after checking why it was added (git blame) and re-running tests.
- **Example uploads**:
  - hysprint: a minimal batch with one JV, one EQE and one MPP file
  - tfsc-general: a minimal PERSEUS batch

  Each Oasis CI then processes them on every image build. This is the cheapest end-to-end guard against regressions from plugin or NOMAD updates.
- **Cookiecutter alignment**: run `cruft` against the cookiecutter, or copy its ruff config, test layout and docs layout, so all three repos share lint and CI conventions.
- **Datetime handling**: `hysprint_measurement_parser.py` and `tfsc_general_measurement_parser.py` call `datetime.now()`. Prefer `nomad.common.now()` (UTC), or the entry creation time when the value is a default.

## Could-do (new capabilities)

- **Dashboards**:
  - tfsc-general already has `upload_tracker` / `upload_qc` code paths (see the root `nomad.yaml` comments referring to `nomad_tfsc_general.apis:*`) and a `webapp` branch. In the new GUI these fit naturally as `DashboardEntryPoint`s: same-origin, logged-in user for free, opened from the Dashboards page.
  - A **JV batch overview** dashboard could query `results.properties.optoelectronic.solar_cell.*` via `/api/v1/entries/query` and plot PCE per batch and variation.
- **Voila notebooks to NORTH tool entry point**: hysprint's `voila` app uses `RowActionNorth(tool_name='voila')`. Define the voila tool as a `NORTHToolEntryPoint` in hysprint, or in a small `nomad-hzb-north` plugin, so every HZB Oasis gets the same tool definition. That replaces hand-written `north.tools` config. The HZB jupyter repos (`nomad-hysprint-jupyter-scripts`, `hzb-ce-*-jupyter`) are candidates for the image content.
- **Actions** for long jobs: batch re-fitting of JV parameters, external database lookups, or ML predictions (sol-ai). Triggered by an `ActionEditQuantity` button on a batch entry. Requires Temporal plus cpu-action workers in the Oasis.
- **Configurable entry points**: thresholds such as the JV fit range, the minimum illumination intensity, or the default unit system can become entry point fields, overridable per Oasis.
- **Projects** instead of datasets for publishing with DOIs. Dataset creation is removed in v2.3.0.

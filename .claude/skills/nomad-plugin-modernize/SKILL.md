---
name: nomad-plugin-modernize
description: Update and extend the HZB NOMAD plugins (nomad-baseclasses, nomad-hysprint, nomad-tfsc-general) for nomad-lab 2.x and the new GUI (nomad-gui 2.x). Use when the user wants to adapt plugin code to a new NOMAD version, make plots or ELN forms show up in the new GUI, replace deprecated annotations or app fields, add new entry point types (dashboards, actions, example uploads, APIs, NORTH tools), audit a plugin for compatibility, or asks "what changed in NOMAD 2" for plugin code.
---

# Modernize HZB plugins for NOMAD 2.x and the new GUI

Knowledge snapshot: nomad-lab **2.0.0** (tagged 2026-10-18), nomad-gui **2.0.0**, nomad-docs as of 2026-10-20. Verify against newer releases before asserting version-specific facts (see "Refreshing this knowledge" at the end).

The three packages live in `packages/` of this distro as git submodules on their own branches. Edit them inside their own directory. The distro only pins their commit.

## Workflow

1. **Audit first.** Run the bundled scanner on the package(s):
   ```bash
   python3 -I .claude/skills/nomad-plugin-modernize/scripts/audit_plugin.py packages/nomad-baseclasses packages/nomad-hysprint packages/nomad-tfsc-general
   # add --details for file:line of every hit
   ```
   It groups findings as BREAKS, NEW-GUI, DEPRECATED, and INFO. Fix BREAKS first, then NEW-GUI, then DEPRECATED.
2. **Work on a branch in the plugin repo**, never on the plugin's `main` directly. One concern per commit, such as "migrate a_plot in xrd.py".
3. **Apply the matching recipe** from the references below. Keep behaviour identical. The goal is that the same data shows in both GUIs.
4. **Run the package tests** after each file or group:
   ```bash
   (cd packages/nomad-hysprint && ../../.venv/bin/python -m pytest -q tests)
   ```
   For nomad-tfsc-general, exclude hysprint's parsers (see `references/testing.md`).
5. **Check it in the new GUI.** Run `uv run poe start`, open `http://localhost:8000/nomad-oasis/gui/v2/`, then create or upload an entry and confirm the plot or form renders. The old GUI is still at `http://localhost:3000/nomad-oasis/gui` after `uv run poe gui-setup`.
6. Report what changed, test results, and anything not verified in the GUI.

## What matters most for these packages (audit of 2026-10-20)

| Finding | baseclasses | hysprint | tfsc-general | Severity |
| --- | --- | --- | --- | --- |
| `a_plot=` legacy plot annotation | 97 in 21 files | 15 in 2 files | 3 in 1 file | NEW-GUI: invisible in new GUI |
| Deprecated App fields (`quantity=`, `nbins=`, `showinput=`, `filters=`, `filter_menus=`/`FilterMenu`) | none | ~60 | ~32 | DEPRECATED |
| `a_browser=dict(adaptor='RawFileAdaptor')` | 71 | 6 | 4 | harmless, ignored by new GUI |
| Test `nomad.yaml` in pre-entry-point format | yes | no | no | BREAKS tests |
| Template leftover test (`Hello Markus`) | yes | no | no | test always fails |
| `pydantic<2.11` pin | yes | no | no | caps the whole env |
| hysprint parser also matches tfsc-general Excel files | | cause | victim | tests fail when both installed |

Nothing in the three packages imports the removed `PlotAnnotation` class or the removed downloads module. Bare `from nomad.datamodel.metainfo.basesections import ...` still resolves to **v1** and keeps working.

## Key rules

- **Plots:** the new GUI only renders `PlotSection` figures. It does not read `a_plot` at all. Every class with `a_plot` must inherit `PlotSection` and declare `a_plotly_graph_object`, `a_plotly_express` or `a_plotly_subplots`, or build `PlotlyFigure` objects in `normalize()`. Recipes are in `references/plot-migration.md`.
- **Base sections:** stay on v1, the default import. v2 (`basesections.v2`) is a redesign that FAIRmat still hides from "Create from Schema". Do not migrate HZB classes to v2 unless FAIRmat announces it.
- **ELN components:** every `a_eln` component works in the new GUI except `UserEditQuantity`. Section `properties.order`/`hide`, `defaultDisplayUnit`, `label_quantity`, `display` and `template` annotations are supported. In 2.0.0, `display` annotations are validated: `visible`/`editable` must be filters on sections and booleans on quantities, and `order` is only allowed on sections.
- **Apps:** rename deprecated fields (`references/apps-migration.md`). Old names still load but log warnings, and FAIRmat removed them from its own apps in 2.0.0.
- **Datetimes:** use `nomad.common.now()` for "now" and `nomad.datamodel.metainfo.common.default_datetime(archive)` for defaults. Since 2.0.0 the v1 `BaseSection` and `ReadableIdentifiers` default `datetime` to the entry creation time, not processing time. This stops lab_id drift on reprocessing.
- **Secrets** in entry point config: `SecretStr`, read with `get_secret_value()` only at the boundary.
- **Don't** touch `packages/nomad-FAIR`. Upstream changes come through `/update-distro`.

## New capabilities worth using (details in `references/entry-points.md`)

| Entry point | Use at HZB |
| --- | --- |
| `DashboardEntryPoint` (new GUI only) | Turn browser-facing tools into dashboards: tfsc-general's upload tracker / upload QC, a JV overview page. FastAPI-hosted dashboards get NOMAD auth for free. |
| `ActionEntryPoint` (Temporal) | Long-running or external-API jobs triggered from an ELN button (`ActionEditQuantity`), such as batch re-analysis or fitting. Needs Temporal and CPU/GPU workers. |
| `ExampleUploadEntryPoint` | Ship a small HZB example batch. The Oasis CI (`test_example_uploads.py`) processes it and fails on any error, which is a free end-to-end test. |
| `NORTHToolEntryPoint` | Package the Voila/Jupyter analysis image as a plugin-defined NORTH tool instead of hand-written `north.tools` config. |
| `APIEntryPoint` | `prefix` is optional since 2.0.0 (default `apis/{id_url_safe}`). Use for JSON endpoints that scripts consume. |
| `get_plugin_entry_point()` + custom fields | Make thresholds and lab settings configurable per Oasis via `plugins.entry_points.options` in `nomad.yaml`. |

`references/hzb-opportunities.md` maps these to concrete HZB features.

## References

- `references/nomad-2-changes.md`: what changed in 1.4.3 and 2.0.0 for plugin code, plus the deprecation timeline.
- `references/new-gui.md`: what the new GUI renders, ignores, or adds, and its URL layout.
- `references/plot-migration.md`: `a_plot` to `PlotSection` recipes, including repeated subsections.
- `references/apps-migration.md`: deprecated App field map, before/after code, layouts.
- `references/entry-points.md`: minimal code for every entry point type, config access, include/exclude.
- `references/testing.md`: running tests, the parser overlap, nomad-plugin-tests in the Oasis CI, test config format.
- `references/hzb-opportunities.md`: concrete improvement ideas for the HZB packages.

For bulk mechanical work across many files, such as all `a_plot` in baseclasses, delegate per package to the `nomad-plugin-modernizer` agent.

## Refreshing this knowledge

Sources, in order of authority:

1. The `nomad-FAIR` code at the pinned tag: `git -C packages/nomad-FAIR show v2.0.0:CHANGELOG.md`, and `nomad/config/models/{plugins,ui}.py` and `nomad/datamodel/metainfo/annotations.py` at that tag.
2. nomad-docs: https://github.com/FAIRmat-NFDI/nomad-docs, under `docs/howto/plugins/types/*.md` and `docs/reference/annotations.md`.
3. nomad-gui: https://gitlab.mpcdf.mpg.de/nomad-lab/nomad-gui. The supported ELN components are in `src/components/values/utils/dynamicComponents.ts`, and plots are in `src/components/plot/`.
4. cookiecutter-nomad-plugin: https://github.com/FAIRmat-NFDI/cookiecutter-nomad-plugin. This is the current plugin layout. The old nomad-plugin-template now only points to it via `cruft create`.

Shallow-clone into the scratchpad, read, and update these references with the new date when versions move.

# The new NOMAD GUI (nomad-gui 2.x) from a plugin author's view

Facts below are from the nomad-gui source (develop branch, 2026-10-19) and the nomad-lab 2.0.0 code. They are marked "per source" where not visually confirmed.

## What it is

- A separate React/TypeScript app, distributed as the Python package **`nomad-gui`**. It is a NOMAD plugin that serves a production build. Repo: https://gitlab.mpcdf.mpg.de/nomad-lab/nomad-gui
- The new GUI reads two generated files:
  - `config.js`, a GUI-relevant subset of `nomad.yaml` including apps
  - `metainfo.js`, all registered schema definitions
- So **plugin schema and app changes reach the new GUI through the backend**. No JS build is needed for plugins.
- The old GUI is the React app in `nomad-FAIR/gui`. It is deprecated and **removed in v2.3.0**.

## URLs

| Setup | New GUI | Old GUI | API |
| --- | --- | --- | --- |
| nomad-distro-dev (this repo) | `http://localhost:8000/nomad-oasis/gui/v2/` | `http://localhost:3000/nomad-oasis/gui` after `poe gui-setup` and `poe gui` | `http://localhost:8000/nomad-oasis/api/v1` |
| Oasis from nomad-distro-template 2.0.0 | `http://<host>/` (root) | `http://<host>/gui/` | `http://<host>/backend/api/v1` |

In the template, nginx redirects old `/nomad-oasis/gui/...` links. A `/select-gui` page and a `nomad_gui_pref` cookie (`v1`/`v2`) decide which GUI a legacy link opens. `nomad-lab` itself still defaults `services.api_base_path` to `/nomad-oasis`, and the template's `configs/nomad.yaml` sets `/backend`.

## Schema features: supported vs not

| Feature | New GUI | Notes |
| --- | --- | --- |
| `a_eln` components | All except **`UserEditQuantity`** | Mapping in `src/components/values/utils/dynamicComponents.ts`. Unsupported ones show "Unsupported ELN component". `EnumEditQuantity` with `props.suggestions` on a `str` becomes an autocomplete that allows custom values. |
| `ActionEditQuantity` | yes | Triggers actions or normalize-driven buttons. |
| `FileEditQuantity` | yes | Rendered as a file reference. |
| `RichTextEditQuantity` | yes | |
| Section `a_eln=dict(hide=[...], properties=dict(order=[...]))` | yes | |
| `defaultDisplayUnit` | yes | |
| `a_display` / `SectionDisplayAnnotation` / `QuantityDisplayAnnotation` | yes | 2.0.0 validates shape: section `visible`/`editable` are `Filter`s, quantity ones are `bool`. `order` is section-only, `unit` quantity-only. |
| `label_quantity` | yes | |
| `a_template` | yes | |
| **`a_plot`** | **no** | Never read. Migrate to `PlotSection` (`plot-migration.md`). |
| `PlotSection` + `a_plotly_graph_object` / `a_plotly_express` / `a_plotly_subplots` | yes | Figures are built at processing time. Slices like `#sub/:/q` expand to one trace per subsection. |
| `PlotlyFigure` built in `normalize()` | yes | |
| `a_browser` (`RawFileAdaptor`, `render_value`) | ignored | Old archive-browser feature. Harmless. |
| `a_h5web` / HDF5 references | yes | There is an `HDF5Editor` component. |
| basesections v2 | hidden in "Create from Schema" | Use v1. |

## GUI-only features plugins can use

- **Dashboards** (`DashboardEntryPoint`) appear on the Dashboards page. They open embedded (iframe) or in a new tab, and can be pinned as widgets. The old GUI does not know them.
- **Apps** render in the new GUI with responsive layouts and a dashboard export/import dialog.
- **Projects** cover workflows and projects. 2.0.0 adds cross-project entry inclusion and recommends project DOIs over datasets, since dataset creation is removed in v2.3.0.
- **Notifications** endpoint; process status in archive metadata.

## Developing against the new GUI

- Normal plugin work needs no Node. Install the plugin, restart `uv run poe start`, and reload the new GUI.
- GUI development itself: clone nomad-gui and run `npm install && npm run start`, with `VITE_CONFIG_FILE_URL` and `VITE_METAINFO_FILE_URL` pointing to `http://localhost:8000/nomad-oasis/gui/v2/{config,metainfo}.js`.
- Dashboards with authentication must be tested same-origin through `:8000`, not via the GUI dev server on `:3000`, because cookies don't cross origins. For embedding from `:3000`, set `services.dashboard_frame_ancestors: ["'self'", 'http://localhost:3000']`.
- Dashboard styling: the GUI uses MUI CSS variables (`--mui-palette-*`) that an embedded same-origin dashboard can read from `window.parent`. The theme source is `src/components/theme/themeOptions.ts` in nomad-gui.

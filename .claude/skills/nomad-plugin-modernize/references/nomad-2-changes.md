# What changed for plugin code: nomad-lab 1.4.3 → 2.0.0

Compiled from `CHANGELOG.md` and code diffs in nomad-FAIR between 897f5e0 (April 2026), d1e3ae4 (2 October 2026, the distro-dev pin) and tag v2.0.0 (18 October 2026, d2838b0). The template release notes for v2.0.0 cover the deprecation timeline.

## Removed (code that relied on these breaks)

| Removed | Version | Impact on HZB |
| --- | --- | --- |
| `PlotAnnotation` class (`a_plot` model) | 2.0.0 | `a_plot` no longer validated or rendered by the new GUI; importing `PlotAnnotation` fails. HZB has 115 `a_plot` uses and no imports. |
| Many deprecated config options (`ui.apps`, `ui.north`, `archive.block_size`/`toc_depth`, example upload `path`/`url` → use `resources`) | 1.4.4/2.0.0 | None in HZB nomad.yaml files. |
| Legacy plugin config `plugins: {include: ..., options: {name: {python_package: ...}}}` | 1.4.4 | baseclasses `nomad.yaml` uses it, so its tests fail at config load. |
| Archive file download feature (`nomad.datamodel.metainfo.downloads`) | 1.4.3 | Not used. |
| Log transfer feature (logtransfer service) | 2.0.0 | Oasis compose files that still run `logtransfer` must drop it. |
| Materials index (`*_materials_v1`) | 2.0.0 | Only the entries index remains. |
| Federation scope on personal access tokens | 2.0.0 | |
| Batch child workflows (internal) | 1.4.3 | |

## Changed

- **Datetime defaults**: v1 `BaseSection.normalize` and `ReadableIdentifiers` set a missing `datetime` from the entry creation time (`default_datetime(archive)`) instead of `now()`. Lab IDs derived from datetime no longer drift on reprocessing. baseclasses' `ReadableIdentifiersCustom` inherits this.
- **API entry points**: `prefix` optional, default `apis/{id_url_safe}`. Dashboards mount at `{api_base_path}/dashboards/{id_url_safe}/`.
- **Archive storage**: new v3 msgpack format (1.4.3) and streaming reads (2.0.0). Old v1/v2 archives are still readable. Optional: `nomad admin uploads convert`.
- **Elasticsearch**: both ES7 and ES9 clients ship. `elastic.version: '7'|'9'` (env `NOMAD_ELASTIC_VERSION`). The code default is '7', and the template 2.0.0 uses 9. ES7 support is removed in **v2.2.0**.
- **Display annotations** are validated against the annotated definition (see new-gui.md).
- **`json_transformer`** gained an overwrite/extend flag. The **tabular parser** got fixes, including file paths with whitespace and pint API usage.
- **Plugin config mismatch handling**: options for entry points that are not installed are dropped with a warning instead of failing.
- **pint/s3fs API usage** updated (internal). `plotly_express` plots now work when `TableData` precedes `PlotSection` in the bases.

## Added (new capabilities)

- **Dashboard entry points** (1.4.3) and dashboard config fields (2.0.0).
- **Actions** with Temporal: asset upload, priority keys, access limits by user/group, human-in-the-loop signals, workflow streams.
- Upload and group **ownership transfer** APIs; **user notifications** endpoint.
- Projects can **include entries from other projects**.
- Graph API pagination and option to disable quantity fetching.
- `documentation.url` config, refactored NORTH hub API (`north.enable_new_hub_api: true`), OpenTelemetry tracing, worker health endpoints.
- Multiple annotations of the same kind on one definition.

## Deprecated, with removal dates (template v2.0.0 release notes)

| Deprecated | Removed in | Replacement |
| --- | --- | --- |
| Old GUI | **v2.3.0** | nomad-gui (new GUI) |
| Dataset creation | **v2.3.0** | DOIs on projects |
| Elasticsearch 7 support | **v2.2.0** | ES 9.5 (`howto/oasis/migrate/v2.0.md`) |
| `nomad admin run hub` | **v2.2.0** | new JupyterHub service + `north.enable_new_hub_api: true` |
| App fields `quantity`, `showinput`, `nbins`, `filters`, `filter_menus`, scatter `size`/`color` | not dated | see apps-migration.md |

## Version facts

- nomad-lab 2.0.0 requires Python >= 3.11 in the template (`requires-python = ">=3.11"`). The template CI uses Python 3.12 and uv 0.9.
- distro-dev upstream still pinned the 1.4.4.dev264 develop commit d1e3ae4 on 2026-10-20. It is 39 commits behind v2.0.0, and none of those touch HZB-used APIs except the datetime fix and annotation validation.
- The plugin cookiecutter now defaults to `nomad-lab>=1.4.3`. HZB packages declare `>=1.3.16` (hysprint, tfsc-general) and `>=1.4.0` (baseclasses). Raise the floor to what is actually tested once code depends on 2.x features, for example `nomad-lab>=2.0.0`.

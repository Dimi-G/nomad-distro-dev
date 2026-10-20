# App entry points: deprecated fields and the current model

Source of truth: `nomad/config/models/ui.py` at the pinned nomad-lab tag. Read it with `git -C packages/nomad-FAIR show v2.0.0:nomad/config/models/ui.py`. Docs: nomad-docs `docs/howto/plugins/types/apps.md`, with examples in `examples/plugins/*.py`.

Deprecated fields still load through backwards-compatibility validators and log deprecation warnings. In 2.0.0 FAIRmat removed them from all built-in apps, so treat them as due for removal.

## Field map

| Deprecated | Replacement | Where |
| --- | --- | --- |
| `Column(quantity=...)` | `Column(search_quantity=...)` | columns |
| `MenuItemTerms(quantity=...)`, `WidgetTerms(quantity=...)` | `search_quantity=` | menu items, widgets |
| `MenuItemHistogram(quantity=...)`, `WidgetHistogram(quantity=...)` | `x=Axis(search_quantity=...)` | histograms |
| histogram `scale=` | `y=AxisScale(scale=...)`, or `x=Axis(..., scale=...)` for the x axis | histograms |
| `nbins=` | `n_bins=` | histograms |
| `showinput=` | `show_input=` | terms, histograms |
| `WidgetScatterPlot(size=1000)` | `sample_size=1000` | scatter |
| `WidgetScatterPlot(color='q')` / `markers={'color': {'quantity': 'q'}}` | `markers=Markers(color=Axis(search_quantity='q', unit=...))` | scatter |
| widget `type='scatterplot'` (YAML) | `type='scatter_plot'` | YAML apps |
| `App(filters=Filters(include=[...]))` | `App(search_quantities=SearchQuantities(include=[...]))` | app |
| `App(filter_menus=FilterMenus(options={...}))` / `filter_menus={...}` | `App(menu=Menu(items=[...]))` | app |
| `RowActions(options=...)` | `RowActions(items=[...])` | rows |
| `ui.apps` in nomad.yaml | apps via plugins, or `plugins.entry_points.options` | config (removed) |

`FilterMenu` sections were named groups such as "material" or "solarcell" that NOMAD filled with built-in filters. With `Menu`, you list the items explicitly. To keep the same experience, build submenus with `Menu(title=..., items=[MenuItemTerms(...), MenuItemHistogram(...), MenuItemPeriodicTable(...)])`.

## Before / after (hysprint `solar_cell_overview.py`)

```python
# before
filters=Filters(include=[f'*#{schema}']),
columns=[Column(quantity='results.properties.optoelectronic.solar_cell.efficiency',
                selected=True, format={'decimals': 2, 'mode': 'standard'}, label='Efficiency (%)')],
filter_menus={'options': {'material': {'label': 'Materials'}, 'solarcell': {'label': 'Solar Cell Properties'}}},
WidgetScatterPlot(..., markers={'color': {'quantity': 'results.properties.optoelectronic.solar_cell.short_circuit_current_density',
                                          'unit': 'mA/cm^2'}}, size=1000)
```

```python
# after
from nomad.config.models.ui import (App, Axis, Column, Format, Markers, Menu, MenuItemHistogram,
                                    MenuItemPeriodicTable, MenuItemTerms, SearchQuantities, WidgetScatterPlot)

SC = 'results.properties.optoelectronic.solar_cell'
search_quantities=SearchQuantities(include=[f'*#{schema}']),
columns=[Column(search_quantity=f'{SC}.efficiency', selected=True,
                format=Format(decimals=2, mode='standard'), label='Efficiency (%)')],
menu=Menu(items=[
    Menu(title='Materials', items=[
        MenuItemPeriodicTable(search_quantity='results.material.elements'),
        MenuItemTerms(search_quantity='results.material.chemical_formula_hill', width=6, options=0),
    ]),
    Menu(title='Solar Cell Properties', items=[
        MenuItemHistogram(x=Axis(search_quantity=f'{SC}.efficiency')),
        MenuItemHistogram(x=Axis(search_quantity=f'{SC}.open_circuit_voltage', unit='V')),
        MenuItemTerms(search_quantity=f'{SC}.absorber'),
    ]),
    Menu(title='Electronic Lab Notebook', items=[
        MenuItemTerms(search_quantity='results.eln.lab_ids'),
        MenuItemTerms(search_quantity='results.eln.tags'),
    ]),
]),
WidgetScatterPlot(..., markers=Markers(color=Axis(search_quantity=f'{SC}.short_circuit_current_density',
                                                  unit='mA/cm^2')), sample_size=1000)
```

## Search quantities from custom schemas

- Syntax: `data.<path>#<python.qualified.SchemaName>`, for example `data.batch_id#nomad_tfsc_general.schema_packages.tfsc_general_package.TFSC_General_Sample`.
- Only **scalar** quantities are indexed automatically. Lists and arrays are not searchable.
- Repeated subsections: `data.my_repeated_section[*].myquantity#...` in columns.
- Lock the app to a schema with `filters_locked={'section_defs.definition_qualified_name': [schema]}`.
- `results.*` quantities, such as `results.properties.optoelectronic.solar_cell.*` filled by `add_solar_cell`, need no schema suffix.

## Layouts and responsive design (new GUI)

| Breakpoint | Grid width (px) | Columns |
| --- | --- | --- |
| `sm` | < 1065 | 12 |
| `md` | 1065–1420 | 18 |
| `lg` | 1420–1775 | 24 |
| `xl` | 1775–2130 | 30 |
| `xxl` | >= 2130 | 36 |

- Cells are square, so `h` and `w` share a unit. The minimum widget size is 3x3 unless you set `minW`/`minH`.
- A breakpoint without a layout copies the nearest larger breakpoint that has one, otherwise the nearest smaller. Defining only `lg` and `sm` is usually enough. HZB apps currently copy the same layout into all five, which can be simplified.
- Easiest workflow: arrange the widgets in the GUI, click **Dashboard export/import**, paste the YAML, then `Dashboard.parse_obj(yaml.safe_load(...))`.

## Row actions

- `RowActionNorth(tool_name='voila', filepath=...)` opens a file from the entry in a NORTH tool. The tool must exist, either from a `NORTHToolEntryPoint` in some plugin or from `north.tools.options` in nomad.yaml.
- `RowActionURL(path='data.url#Schema')` opens a URL stored in the entry.

## Validating an app

```python
from nomad_hysprint.apps import solar_cell_overview_entry_point as ep
assert ep.app.path  # pydantic validation already ran on import
```

The Oasis CI (`tests/test_app_entry_points.py` in the distro template) calls `GET /api/v1/apps/entry-points/<path>` for every installed app and fails on non-200. A broken app config fails the image build pipeline.

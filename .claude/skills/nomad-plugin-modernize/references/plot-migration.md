# Migrating `a_plot` to `PlotSection` (new GUI plots)

## Why

- `a_plot` was the old `PlotAnnotation`. The class was removed in nomad-lab 2.0.0 (commit 41158c6b1, "Removed deprecated PlotAnnotation class").
- The backend no longer validates `a_plot`. It keeps it as a raw annotation, so nothing errors and tests still pass.
- The old GUI still draws it: `ArchiveBrowser.js` and `SectionCard.js` read `m_annotations.plot`.
- The new GUI never reads `plot` annotations. It renders only the `figures` subsection of sections that inherit `nomad.datamodel.metainfo.plot.PlotSection`. The renderer is `PlotSectionFigure.tsx`.
- The old GUI will be removed in **v2.3.0**. Every `a_plot` chart disappears then, and is already invisible in the new GUI.

## How PlotSection works

- `PlotSection` adds a repeating subsection `figures: PlotlyFigure[]`, where each `PlotlyFigure` has `label`, `index`, `open` and `figure` (plotly JSON).
- `PlotSection.normalize()` reads the section's `plotly_graph_object`, `plotly_express` and `plotly_subplots` annotations and **writes figures at processing time**. Consequences:
  - Subclasses that override `normalize()` **must call `super().normalize(archive, logger)`**, or no figures are produced.
  - **Existing entries show the new plots only after reprocessing.** Use the GUI's reprocess action, or `nomad admin uploads process -- <ids>` in the Oasis.
- `#name` strings are references relative to the section that holds the figures.
  - In `plotly_graph_object` they are stored as references and resolved in the browser by the new GUI.
  - In `plotly_express` and `plotly_subplots` they are resolved on the server with `archive.m_resolve`.
- The new GUI supports these reference forms, per `usePlotSection.test.ts`:
  - `#runs/0/time`, `#runs/-1/time`
  - slices `#runs/:/time`, `#runs/0:2/time`, which become **one trace per repeated subsection**
  - nested `marker: {color: '#runs/2/time'}`
  - lists `['#a', '#b']`
- Datetime arrays are converted to ISO strings automatically.

## Mapping

| `a_plot` key | `a_plotly_graph_object` equivalent |
| --- | --- |
| `'x': 'angle'` | `'data': {'x': '#angle', ...}` |
| `'y': 'intensity'` | `'data': {..., 'y': '#intensity'}` |
| `'y': ['power', 'pressure']` (several lines) | a **list of graph objects**, one per y, or several traces: `'data': [{'x': '#time', 'y': '#power'}, {'x': '#time', 'y': '#pressure', 'yaxis': 'y2'}]` |
| `'x': 'jv_curve/:/voltage'` | `'x': '#jv_curve/:/voltage'` (slice supported, one trace per curve) |
| `'x': 'data/time'` (nested path) | `'x': '#data/time'` |
| `'layout': {...}` | `'layout': {...}` unchanged |
| `'config': {...}` | `'config': {...}` unchanged |
| `'label': ...` | `'label': ...` (figure tab label) |
| a_plot on a non-PlotSection class | add `PlotSection` to the class bases |

Notes:

- `a_plot` units: the old GUI applied units from the quantity definitions. With graph objects you get raw numbers in the stored unit. Put the unit in the axis title, for example `'xaxis': {'title': {'text': 'Voltage (V)'}}`. Alternatively build the figure in `normalize()` with converted values.
- Do **not** put `PlotSection` and the old `a_plot` on the same class long-term. During migration it is fine to keep both, so the old GUI keeps working for users who still use it. Then drop `a_plot` once the new GUI is the default for all HZB Oasis instances.

## Recipe A: simple x/y (most HZB cases)

Before (baseclasses `xrr.py`):

```python
class XRRData(ArchiveSection):
    m_def = Section(
        a_plot=[{
            'x': 'angle', 'y': 'intensity',
            'layout': {'yaxis': {'fixedrange': False, 'type': 'log'}, 'xaxis': {'fixedrange': False}},
            'config': {'scrollZoom': True, 'staticPlot': False},
        }],
    )
    angle = Quantity(type=np.float64, shape=['*'], unit='degree')
    intensity = Quantity(type=np.float64, shape=['*'])
```

After:

```python
from nomad.datamodel.metainfo.plot import PlotSection

class XRRData(PlotSection, ArchiveSection):
    m_def = Section(
        a_plotly_graph_object=[{
            'label': 'XRR',
            'data': {'x': '#angle', 'y': '#intensity', 'type': 'scatter', 'mode': 'lines'},
            'layout': {
                'xaxis': {'title': {'text': 'angle (deg)'}, 'fixedrange': False},
                'yaxis': {'title': {'text': 'intensity'}, 'type': 'log', 'fixedrange': False},
            },
            'config': {'scrollZoom': True},
        }],
    )
    angle = Quantity(type=np.float64, shape=['*'], unit='degree')
    intensity = Quantity(type=np.float64, shape=['*'])
```

`PlotSection.normalize()` calls `super().normalize()` first, so base order works either way, provided every `normalize()` in the chain also calls `super()`. HZB code already uses both orders, for example `PlotSection, ArchiveSection` and `BaseMeasurement, PlotSection`. If the class has its own `normalize`, make sure it calls `super().normalize(archive, logger)`.

## Recipe B: repeated subsections (JV, EQE, multi-pixel)

```python
class JVMeasurement(PlotSection, BaseMeasurement):
    m_def = Section(
        a_plotly_graph_object=[{
            'label': 'JV curves',
            'data': {'x': '#jv_curve/:/voltage', 'y': '#jv_curve/:/current_density',
                     'type': 'scatter', 'mode': 'lines'},
            'layout': {'xaxis': {'title': {'text': 'Voltage (V)'}},
                       'yaxis': {'title': {'text': 'Current density (mA/cm²)'}}},
        }],
    )
```

The new GUI names each trace after the subsection path. If you need custom names, colors, or reverse/forward scan styling, use Recipe C.

## Recipe C: build the figure in `normalize()` (full control)

Use this when values need unit conversion, derived curves, annotations or legends. Several HZB classes already do this, for example `XASWithSDD` in `characterizations/xas.py`. Follow their pattern:

```python
import plotly.graph_objects as go
from nomad.datamodel.metainfo.plot import PlotlyFigure, PlotSection

class HySprint_JVmeasurement(PlotSection, JVMeasurement, EntryData):
    def normalize(self, archive, logger):
        super().normalize(archive, logger)          # parses data, runs PlotSection.normalize
        fig = go.Figure()
        for curve in self.jv_curve or []:
            fig.add_trace(go.Scatter(
                x=curve.voltage.to('V').magnitude,
                y=curve.current_density.to('mA/cm^2').magnitude,
                name=curve.cell_name, mode='lines'))
        fig.update_layout(xaxis_title='Voltage (V)', yaxis_title='J (mA/cm²)', template='plotly_white')
        self.figures = [PlotlyFigure(label='JV', index=0, figure=fig.to_plotly_json())]
```

Notes:

- `PlotSection.normalize()` **clears `self.figures`** whenever its annotations produce at least one figure, then adds the annotation figures. Build code-made figures **after** `super().normalize()`.
- Assigning `self.figures = [...]` avoids duplicates on reprocessing, but it also drops annotation-made figures. If the class has both, append and de-duplicate by `label` instead.
- Figures are stored in the archive. Keep traces reasonable, for example downsample very long MPP time series before plotting.
- `figure_json['config'] = {...}` sets plotly config.

## Testing a migrated plot

```python
def test_xrr_has_figure(parsed_archive):
    sec = parsed_archive.data.<path to section>
    assert sec.figures, 'PlotSection produced no figures'
    fig = sec.figures[0].figure
    assert fig['data'][0]['x'] in ('#angle', ) or len(fig['data'][0]['x']) > 0
```

Then check visually in the new GUI. Figures render on the section card. An empty figure usually means a wrong `#` path or a missing `super().normalize()`.

## Bulk procedure for a package

1. List targets with `python3 -I .claude/skills/nomad-plugin-modernize/scripts/audit_plugin.py packages/<pkg> --details`. The output shows each `a_plot` with its enclosing class, and whether it is already a `PlotSection`.
2. Per file:
   1. Add the `PlotSection` import and base.
   2. Translate each `a_plot` dict with the mapping table.
   3. Keep or remove `a_plot` as decided for the transition.
3. Run the package tests, then reprocess one example upload and look at it in the new GUI.
4. Because figures are written at processing time, plan a reprocess of affected uploads on each Oasis after deploying.

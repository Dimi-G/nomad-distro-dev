#!/usr/bin/env python3
"""Audit NOMAD plugin packages for nomad-lab 2.x / new-GUI compatibility.

Usage:
    python3 -I audit_plugin.py <plugin-dir> [<plugin-dir> ...] [--details]

Each <plugin-dir> is a plugin repository root (with pyproject.toml and src/).
Only the standard library is used; nothing is imported from the plugin.

Findings are grouped by severity:
  BREAKS       fails or errors on nomad-lab 2.x
  NEW-GUI      still works, but is not shown or not usable in the new GUI (nomad-gui 2.x)
  DEPRECATED   still accepted, but warns and will be removed
  INFO         worth knowing; no action strictly required
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {'.git', '__pycache__', '.venv', 'venv', 'node_modules', 'build', 'dist'}

# (severity, key, regex, message)
PY_RULES = [
    (
        'BREAKS',
        'plot-annotation-class',
        re.compile(r'\bPlotAnnotation\b'),
        'PlotAnnotation class was removed in nomad-lab 2.0.0; importing it raises ImportError.',
    ),
    (
        'BREAKS',
        'downloads-module',
        re.compile(r'nomad\.datamodel\.metainfo\.downloads'),
        'The archive file-download feature was removed (nomad-lab 1.4.3); check usage of the downloads module.',
    ),
    (
        'NEW-GUI',
        'a_plot',
        re.compile(r'\ba_plot\s*='),
        'Legacy `a_plot` annotation: only the old GUI renders it (old GUI removed in v2.3.0). '
        'Migrate to PlotSection + a_plotly_graph_object / a_plotly_express, or build PlotlyFigure in normalize().',
    ),
    (
        'NEW-GUI',
        'UserEditQuantity',
        re.compile(r'\bUserEditQuantity\b'),
        'UserEditQuantity has no editor in the new GUI (shown as "Unsupported ELN component").',
    ),
    (
        'NEW-GUI',
        'a_browser',
        re.compile(r'\ba_browser\s*='),
        'a_browser (e.g. RawFileAdaptor) only affects the old GUI archive browser; ignored by the new GUI. Harmless.',
    ),
    (
        'INFO',
        'basesections-v2',
        re.compile(r'basesections\s*import\s*v2|basesections\.v2'),
        'Uses basesections v2 (redesign, hidden from "Create from Schema"); plain `basesections` import is v1.',
    ),
    (
        'INFO',
        'datetime-now',
        re.compile(r'datetime\.(?:datetime\.)?(?:now|utcnow)\('),
        'Direct datetime.now()/utcnow(): NOMAD prefers nomad.common.now() (UTC, mockable) or '
        'nomad.datamodel.metainfo.common.default_datetime(archive) for default timestamps.',
    ),
    (
        'INFO',
        'api-prefix',
        re.compile(r'APIEntryPoint\s*\('),
        'APIEntryPoint: since 2.0.0 `prefix` is optional and defaults to apis/{id_url_safe}. '
        'Consider a DashboardEntryPoint if the API mainly serves HTML for people.',
    ),
]

# Deprecated App / ui-config fields (nomad.config.models.ui, 2.0.0). Only applied to files
# that import from nomad.config.models.ui.
APP_RULES = [
    (re.compile(r'\bquantity\s*='), '`quantity=` -> `search_quantity=` (Column, MenuItem*, Widget*); for histograms use `x=Axis(search_quantity=...)`'),
    (re.compile(r'\bshowinput\s*='), '`showinput=` -> `show_input=`'),
    (re.compile(r'\bnbins\s*='), '`nbins=` -> `n_bins=`'),
    (re.compile(r'\bfilter_menus\s*='), '`filter_menus=` (FilterMenus) -> `menu=Menu(...)`'),
    (re.compile(r'\bfilters\s*=\s*Filters\('), '`filters=Filters(...)` -> `search_quantities=SearchQuantities(...)`'),
    (re.compile(r'\bFilterMenus?\b'), 'FilterMenu/FilterMenus are the deprecated menu system -> Menu + MenuItemTerms/Histogram/...'),
    (re.compile(r'''['"]quantity['"]\s*:'''), "dict key 'quantity' -> 'search_quantity' (e.g. markers={'color': {...}})"),
    (re.compile(r'\bsize\s*=\s*\d'), 'integer `size=` on WidgetScatterPlot -> `sample_size=` (Menu size="xl" strings are fine)'),
]

YAML_LEGACY_PLUGIN_FORMAT = re.compile(
    r'^plugins:\s*\n(?:\s*#.*\n)*\s+(include|options)\s*:', re.MULTILINE
)


def iter_files(root: Path, suffixes):
    for path in root.rglob('*'):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in suffixes:
            yield path


def enclosing_class(lines, idx):
    for j in range(idx, -1, -1):
        m = re.match(r'\s*class\s+(\w+)\s*(\(([^)]*)\))?', lines[j])
        if m:
            return m.group(1), (m.group(3) or '')
    return None, ''


def audit(root: Path):
    findings = defaultdict(list)  # severity -> list of (key, file, line, msg)
    src = root / 'src' if (root / 'src').is_dir() else root

    for path in iter_files(src, {'.py'}):
        text = path.read_text(errors='replace')
        lines = text.splitlines()
        rel = path.relative_to(root)
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith('#'):
                continue
            for sev, key, rx, msg in PY_RULES:
                if rx.search(line):
                    extra = ''
                    if key == 'a_plot':
                        cls, bases = enclosing_class(lines, i)
                        has_plot = 'PlotSection' in bases
                        extra = f' [class {cls}{" (already PlotSection)" if has_plot else ""}]'
                    findings[sev].append((key, str(rel), i + 1, msg + extra))
        if 'nomad.config.models.ui' in text:
            for i, line in enumerate(lines):
                if line.lstrip().startswith('#'):
                    continue
                for rx, msg in APP_RULES:
                    if rx.search(line):
                        findings['DEPRECATED'].append(('app-field', str(rel), i + 1, msg))

    # nomad.yaml files anywhere in the repo (tests often carry one)
    for path in iter_files(root, {'.yaml', '.yml'}):
        if path.name not in ('nomad.yaml', 'nomad.yml'):
            continue
        text = path.read_text(errors='replace')
        if YAML_LEGACY_PLUGIN_FORMAT.search(text) and 'entry_points' not in text:
            findings['BREAKS'].append(
                (
                    'legacy-plugin-config',
                    str(path.relative_to(root)),
                    1,
                    'Pre-entry-point plugin config (`plugins: include/options`) is rejected by nomad-lab >=1.4.4. '
                    'Use `plugins: {entry_points: {include: [...]}}` or `exclude: [...]`.',
                )
            )

    # template leftovers in tests
    tests = root / 'tests'
    if tests.is_dir():
        for path in iter_files(tests, {'.py'}):
            text = path.read_text(errors='replace')
            if 'Hello Markus' in text or 'nomadschemaexample' in text:
                findings['INFO'].append(
                    (
                        'template-test',
                        str(path.relative_to(root)),
                        1,
                        'Leftover plugin-template test (checks a schema that does not exist in this package).',
                    )
                )
    else:
        findings['INFO'].append(('no-tests', 'tests/', 0, 'No tests/ directory; nomad-plugin-tests in the Oasis CI will find nothing to run.'))

    # pyproject checks
    pp = root / 'pyproject.toml'
    if pp.is_file():
        text = pp.read_text(errors='replace')
        m = re.search(r'"nomad-lab(?:\[[^\]]*\])?\s*([<>=!~][^"]*)?"', text)
        if m:
            findings['INFO'].append(('nomad-lab-pin', 'pyproject.toml', 0, f'nomad-lab requirement: {m.group(0)}'))
        for pin in re.findall(r'["\'](pydantic\s*<[^"\']*)["\']', text):
            findings['INFO'].append(('pydantic-pin', 'pyproject.toml', 0, f'Pins {pin}; this caps the whole environment (nomad-lab accepts newer).'))
        if 'nomad.plugin' not in text:
            findings['INFO'].append(('no-entry-points', 'pyproject.toml', 0, 'No [project.entry-points."nomad.plugin"] table (library-only package).'))
        eps = re.findall(r'^\s*([\w-]+)\s*=\s*"([\w.]+):(\w+)"', text.split('nomad.plugin', 1)[-1], re.MULTILINE)
        kinds = defaultdict(int)
        for _, mod, _obj in eps:
            for k in ('parsers', 'schema_packages', 'apps', 'normalizers', 'apis', 'dashboards', 'actions', 'example_uploads', 'north_tools'):
                if f'.{k}' in mod:
                    kinds[k] += 1
        if kinds:
            findings['INFO'].append(('entry-points', 'pyproject.toml', 0, 'Entry points: ' + ', '.join(f'{k}={v}' for k, v in sorted(kinds.items()))))
    return findings


def main(argv):
    details = '--details' in argv
    roots = [Path(a) for a in argv if not a.startswith('--')]
    if not roots:
        print(__doc__)
        return 2
    order = ['BREAKS', 'NEW-GUI', 'DEPRECATED', 'INFO']
    for root in roots:
        f = audit(root.resolve())
        print(f'\n## {root.resolve().name}\n')
        for sev in order:
            items = f.get(sev, [])
            if not items:
                continue
            print(f'### {sev} ({len(items)})')
            grouped = defaultdict(list)
            for key, file, line, msg in items:
                base = msg.split(' [class ')[0]
                group = key if key != 'app-field' else f'{key}: {base.split(" ->")[0]}'
                grouped[group].append((file, line, msg))
            for key, occ in grouped.items():
                files = sorted({o[0] for o in occ})
                base_msg = occ[0][2].split(' [class ')[0]
                print(f'- **{key}** x{len(occ)} in {len(files)} file(s): {base_msg}')
                if details:
                    for file, line, msg in occ:
                        tail = msg[len(base_msg):]
                        print(f'    - {file}:{line}{tail}')
                else:
                    for file in files[:8]:
                        print(f'    - {file}')
                    if len(files) > 8:
                        print(f'    - ... {len(files) - 8} more (use --details)')
            print()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

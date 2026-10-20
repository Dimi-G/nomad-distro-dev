# Testing HZB plugins against new NOMAD versions

## Run tests in this distro

```bash
# hysprint (70 tests on 2026-10-20 with nomad-lab 1.4.4.dev264: all pass)
(cd packages/nomad-hysprint && ../../.venv/bin/python -m pytest -q tests)

# tfsc-general (23 tests: all pass ONLY with hysprint's parsers excluded)
cat > /tmp/tfsc-nomad.yaml <<'EOF'
plugins:
  entry_points:
    exclude: ["nomad_hysprint.parsers:hysprint_parser",
              "nomad_hysprint.parsers:hysprint_experiment_parser",
              "nomad_hysprint.parsers:solartab_sim_parser"]
EOF
(cd packages/nomad-tfsc-general && NOMAD_CONFIG=/tmp/tfsc-nomad.yaml ../../.venv/bin/python -m pytest -q tests)

# baseclasses: needs its nomad.yaml fixed first (see below)
(cd packages/nomad-baseclasses && ../../.venv/bin/python -m pytest -q tests)
```

Use the scratchpad instead of `/tmp` when running as Claude. If a package is not installed in the current workspace, install it temporarily with `uv pip install --no-deps -e packages/<name>`, then remove it afterwards with `uv pip uninstall <name>` and run `uv sync`.

## The parser overlap (hysprint vs tfsc-general)

Both batch parsers declare `mainfile_name_re='^(.+\.xlsx)$'`. Both `is_mainfile` checks look for the same "Experiment Info" / "Nomad ID" header, so a tfsc-general batch file also matches hysprint. With equal `matching_order` (default 0), ties go alphabetically by entry point id, so `nomad_hysprint...` wins. The tfsc-general tests then fail with "RawHySprintExperiment", `assert 3 == 5`, and similar errors.

Fix options, from best to quickest:

1. Make the formats distinguishable. Add a marker, such as a sheet name, a "Project" cell, or a filename convention like `*_perseus.xlsx`, and check it in `is_mainfile`, `mainfile_contents_dict` or `mainfile_name_re`.
2. Per deployment, enable only the relevant batch parser with `plugins.entry_points.include/exclude` in that Oasis' `nomad.yaml`. This is already effectively the case: the hysprint Oasis does not need tfsc's batch parser, and vice versa.
3. Set `matching_order` so the more specific parser is checked first.

This matters in the Oasis CI too, because `nomad-plugin-tests` installs the whole distro (see below).

## Test config format

nomad-lab >= 1.4.4 rejects the pre-entry-point format. baseclasses' `nomad.yaml` currently has:

```yaml
plugins:
  include: 'schemas/baseclasses'
  options:
    schemas/baseclasses:
      python_package: baseclasses
```

Replace it with:

```yaml
normalize:
  normalizers:
    include: [MetainfoNormalizer]
plugins:
  entry_points:
    include: []          # baseclasses has no entry points; load nothing else
```

Also replace `tests/test_schema.py`. It is a plugin-template leftover that parses `nomadschemaexample.ExampleSection` and asserts "Hello Markus!". baseclasses has no such schema, so the test fails on every version. Real baseclasses tests should instantiate key sections such as `JVMeasurement`, `SolcarCellSample` or `BaseProcess`, run `normalize_all` on small archives, and check `results` (for example `add_solar_cell`).

## Common test patterns (hysprint / tfsc-general)

```python
from nomad.client import normalize_all, parse

def test_parser(monkeypatch):
    archive = parse('tests/data/<file>')[0]
    normalize_all(archive)
    assert archive.data.<quantity> == pytest.approx(<value>, rel=1e-3)
```

- Fixtures copy test data into a temp dir. See each package's `tests/conftest.py`.
- Use the `nomad-test-writer` agent to write new tests from expected JSON.
- For plots migrated to `PlotSection`, assert `section.figures` is non-empty after `normalize_all`.

## Oasis CI: nomad-plugin-tests

The template's `docker-publish.yml` runs:

```bash
uv run --extra plugins --with nomad-plugin-tests nomad-plugin-tests --plugins-to-skip "$PLUGINS_STRING"
```

For every plugin in the distro's `plugins` extra (read from `uv.lock` or the requirements), it:

1. clones the plugin's **GitHub repo at the locked commit**, so plugins must be installed from git URLs;
2. creates a fresh venv;
3. installs the **whole distro** dependencies plus the plugin;
4. runs `python -m pytest -p no:warnings` on the plugin's tests.

Consequences:

- Tests must not depend on files outside the repo or on the distro-dev layout.
- Cross-plugin interference shows up here. tfsc-general tests fail in any image that also installs hysprint. Fix the overlap, or have tfsc-general's `tests/conftest.py` set an exclude config, for example `monkeypatch.setenv('NOMAD_CONFIG', ...)` before nomad loads, or pass a `nomad.yaml` in the repo.
- Skip a plugin with `PLUGIN_TESTS_PLUGINS_TO_SKIP` in the workflow env. Override test paths with `PLUGIN_TESTS_TESTS_TO_RUN_OVERRIDE='{"pkg": "tests/nomad"}'`.
- The CI also runs `tests/test_app_entry_points.py`, which needs every app to respond 200, and `tests/test_example_uploads.py`, which needs every example upload to process with no errors or warnings. Both run against the built image.

## Before declaring a migration done

- [ ] audit script shows no BREAKS and no new NEW-GUI items for the touched files
- [ ] package tests pass (tfsc-general with the exclude config)
- [ ] `uv run --no-sync python -c "from nomad.config import config; config.load_plugins()"` shows no new warnings from HZB plugins
- [ ] one reprocessed example shows plots and forms in the new GUI
- [ ] ruff check/format clean if the package uses ruff

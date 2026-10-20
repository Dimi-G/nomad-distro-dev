# Entry point cookbook (nomad-lab 2.0.0)

All entry points are registered in the plugin's `pyproject.toml`:

```toml
[project.entry-points.'nomad.plugin']
my_ep = "nomad_example.<module>:<instance>"
```

The entry point id is `<module>:<instance>`, for example `nomad_hysprint.parsers:hysprint_parser`. That id is what `plugins.entry_points.include/exclude/options` in `nomad.yaml` refers to.

For the current layout of a new plugin, run `cruft create https://github.com/FAIRmat-NFDI/cookiecutter-nomad-plugin`. It offers schema package, normalizer, parser, app, example uploads, action, API, NORTH tool, dashboard and CITATION.cff. The generated `pyproject.toml` uses:

- setuptools-scm
- `requires-python>=3.10`
- dependency `nomad-lab>=1.4.3`, plus `pydantic`/`temporalio` for actions and `fastapi` for APIs/dashboards
- ruff with rule sets E, F, UP, I, PL, single quotes, line length 88
- pytest and pytest-asyncio
- mkdocs docs
- `[tool.cruft] skip = [".github/*"]`

Run `cruft update` in a plugin to pull template improvements.

## Lazy loading pattern

Entry point objects are config. They are pydantic models, imported at startup. Heavy code is imported inside `load()`:

```python
from nomad.config.models.plugins import SchemaPackageEntryPoint

class HySprintPackageEntryPoint(SchemaPackageEntryPoint):
    def load(self):
        from nomad_hysprint.schema_packages.hysprint_package import m_package
        return m_package

hysprint_package = HySprintPackageEntryPoint(name='HySprint', description='...')
```

### Configurable parameters

Subclass the entry point and add pydantic fields. Admins override them per Oasis:

```python
class TFSCParserEntryPoint(ParserEntryPoint):
    max_rows: int = Field(5000, description='Rows read per sheet')
```

```yaml
# nomad.yaml
plugins:
  entry_points:
    options:
      nomad_tfsc_general.parsers:tfsc_general_parser:
        max_rows: 20000
```

```python
from nomad.config import config
ep = config.get_plugin_entry_point('nomad_tfsc_general.parsers:tfsc_general_parser')
ep.max_rows
```

Use `SecretStr` for secrets.

## Parser

- `ParserEntryPoint` matching fields:
  - `mainfile_name_re`, `mainfile_mime_re`, `mainfile_contents_re`
  - `mainfile_contents_dict` for Excel/JSON/HDF5 structure
  - `mainfile_binary_header(_re)`, `mainfile_alternative`, `supported_compressions`
  - `aliases=[...]`
- The `Parser` class implements `parse(mainfile, archive, logger, child_archives=None)`. `MatchingParser` is used for regex-based matching.
- **`matching_order`** (default 0) decides which parser claims a file. Lower values are checked first, ties go alphabetically by entry point id, and the first match wins.
- **`execution_order`** (default 0) decides when matched entries are processed within an upload. Lower values are processed first. Use it when a batch or experiment parser must run after the measurement entries exist.
- `level` is the **deprecated** name for `execution_order`. Both can be overridden per Oasis in `plugins.entry_points.options`.
- Parsers matching overly broad patterns, such as any `.xlsx`, steal files from other plugins. That is the hysprint and tfsc-general overlap. Make the batch parser match on something specific: a filename pattern, or `mainfile_contents_dict` for Excel sheets and columns.
- Run a parser locally: `nomad parse <file> --show-archive`, or from Python with `from nomad.client import parse, normalize_all`.

## Schema package

As in the lazy loading example above. The `load()` method returns the `SchemaPackage` (`m_package`). HZB schemas inherit baseclasses together with `EntryData`.

## App

`AppEntryPoint(name=..., description=..., app=App(...))`. There is no `load()`, because the whole app is config. See apps-migration.md.

## API (FastAPI)

```python
from nomad.config.models.plugins import APIEntryPoint

class UploadQCEntryPoint(APIEntryPoint):
    def load(self):
        from nomad_tfsc_general.apis.upload_qc import app
        return app

upload_qc = UploadQCEntryPoint(name='Upload QC', description='JSON endpoints for upload QC')
# mounted at {api_base_path}/apis/{id_url_safe} unless prefix='...' is given (2.0.0)
```

Auth inside routes:

```python
from typing import Annotated
from fastapi import Depends
from nomad.app.v1.routers.auth import get_current_user
from nomad.app.v1.models import User
from nomad.auth.scopes import Scope

@app.get('/mine')
async def mine(user: Annotated[User, Depends(get_current_user([Scope.USERS_READ], allow_anonymous=False))]):
    ...
```

## Dashboard (new GUI only)

```python
from nomad.config.models.plugins import DashboardEntryPoint

class UploadTrackerDashboard(DashboardEntryPoint):
    def load(self):
        from nomad_tfsc_general.dashboards.upload_tracker import app  # FastAPI app serving HTML/JS
        return app

upload_tracker = UploadTrackerDashboard(
    name='Upload tracker', description='Track PERSEUS batches',
    id_url_safe='upload-tracker', launch_modes=['embedded', 'tab'],
    icon='https://.../icon.svg',            # optional, absolute URL
)
# or external: DashboardEntryPoint(name=..., external_url='https://...', launch_modes=['tab'])
```

- The dashboard is mounted at `{api_base_path}/dashboards/{id_url_safe}/`. Set exactly one of `load()` or `external_url`.
- A FastAPI-hosted dashboard is same-origin, so the GUI's `Authorization` cookie arrives automatically. Use `fetch(apiBase + '/users/me', {credentials: 'same-origin'})`, deriving `apiBase` from `location.pathname`.
- For a single-page app, mount `/assets` with `StaticFiles` and add a catch-all route returning `index.html`. Include the built files as package data.
- The CSP `frame-ancestors` default is `'self'`. Configure it with `services.dashboard_frame_ancestors`.
- Cookiecutter test: assert `ep.external_url is None`, `set(ep.launch_modes) <= {'embedded','tab'}`, `isinstance(ep.load(), FastAPI)`.

## Action (Temporal workflows)

Layout: `actions/<name>/{__init__.py, activities.py, workflows.py, models.py}`.

```python
from nomad.actions import TaskQueue
from pydantic import Field
from temporalio import workflow
with workflow.unsafe.imports_passed_through():
    from nomad.config.models.plugins import ActionEntryPoint

class RefitEntryPoint(ActionEntryPoint):
    task_queue: str = Field(default=TaskQueue.CPU)
    def load(self):
        from nomad.actions import Action
        from .refit.activities import fit_batch
        from .refit.workflows import RefitWorkflow
        return Action(task_queue=self.task_queue, workflow=RefitWorkflow, activities=[fit_batch])

refit_action = RefitEntryPoint(name='Refit JV batch', description='...')
```

- Inputs and outputs are pydantic models. Inherit `BaseWorkflowInput(upload_id, user_id)`.
- Activities should be idempotent. Prefer sync functions, and use async only for async I/O.
- Trigger from an ELN with `start_action(action_name='<module>:<instance>', data=Input(...))`. Poll with `get_action_status(workflow_id)`. Wire both to `ActionEditQuantity` buttons in `normalize()`.
- Extra deps go in plugin extras `cpu-action = [...]` / `gpu-action = [...]`. The Oasis then needs the cpu/gpu worker images enabled (template README "Enabling NOMAD Actions").
- Run locally in distro-dev with `uv run poe cpuworker` / `uv run poe gpuworker`. The docker compose temporal service must be up.
- Prefer a normalizer or parser for anything short and deterministic. Use actions for long, external, or resource-heavy jobs.

## Example upload

```python
from nomad.config.models.plugins import ExampleUploadEntryPoint
hzb_example = ExampleUploadEntryPoint(
    title='HySprint example batch', category='HZB', description='...',
    resources=['example_uploads/hysprint_batch/*'],   # files shipped in the package; `path`/`url` are removed
)
```

The Oasis template CI (`tests/test_example_uploads.py`) uploads every example, processes it, and fails on any error or warning in the upload or entries. This is a cheap end-to-end regression test for parsers and normalizers.

## NORTH tool

```python
from nomad.config.models.north import NORTHTool
from nomad.config.models.plugins import NORTHToolEntryPoint
voila = NORTHToolEntryPoint(id='voila', north_tool=NORTHTool(
    image='ghcr.io/nomad-hzb/<image>/jupyter:main', display_name='Voila',
    file_extensions=['ipynb'], default_url='/voila', mount_path='/home/jovyan', with_path=True,
    icon='logo/jupyter.svg', maintainer=[{'name': '...', 'email': '...'}]))
```

- The `id` must match `RowActionNorth(tool_name=...)` used in apps.
- Images extend the Jupyter docker stacks. See nomad-docs `howto/plugins/types/north_tools.md` for the Dockerfile layout, tagging, and testing.
- The Oasis template already builds `ghcr.io/<owner>/<repo>/jupyter:main` with all plugins installed and configures `nomad_north_jupyter.north_tools:jupyter` to use it.

## Normalizer

`NormalizerEntryPoint` with `load()` returning a `Normalizer` subclass. Use it only for cross-schema post-processing. For a single schema, put the logic in its `normalize()`.

## Selecting entry points per deployment

```yaml
plugins:
  entry_points:
    include: ['nomad_hysprint.parsers:hysprint_parser', ...]   # whitelist; if set, others are off
    exclude: ['nomad_hysprint.parsers:hysprint_experiment_parser']
```

Every installed entry point is on by default. The Information page (`about/information`) lists the active entry points.

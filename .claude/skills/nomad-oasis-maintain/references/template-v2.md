# nomad-distro-template v2.0.0: anatomy

## Files

```text
.github/workflows/docker-publish.yml   # lock, plugin tests, build app/jupyter(/cpu-action/gpu-action), image tests
.github/workflows/initialize.yml       # runs once on repo creation: substitutes owner/repo names, then deletes itself
.github/dependabot.yml                 # enable in repo settings
Dockerfile                              # stages: base, builder (uv sync --extra plugins), docs, final, cpu/gpu_action_final, jupyter
pyproject.toml                          # nomad-lab[infrastructure]==2.0.0; extras: plugins, jupyter, cpu-action, gpu-action, dev
uv.lock                                 # committed; CI relocks on push
configs/nomad.yaml                      # baked into the image
configs/nginx_http.conf | nginx_https.conf   # server blocks (choose one in compose)
configs/nginx_base_conf | nginx_maps_conf    # shared routing (GUI at /, backend at /backend, legacy redirects)
configs/_temporal-sql.yaml              # temporal dynamic config
scripts/generate-env.sh                 # writes .env and .env.north with random secrets
scripts/backup-mongo.sh                 # mongodump of nomad_oasis_v1 into .volumes/mongo + backup.log
scripts/_setup_temporal.sh              # used by temporal admin one-off jobs
kubernetes/values.yaml                  # helm values (nomad/default chart)
tests/                                  # image tests: app entry points, example uploads, actions
.volumes/fs/{public,staging,tmp,north/users}   # raw + processed files (bind mount)
.volumes/mongo                          # mongodump target (mounted at /backup in mongo)
```

## pyproject (template defaults)

```toml
requires-python = ">=3.11"
dependencies = ["nomad-lab[infrastructure]==2.0.0"]
[project.optional-dependencies]
plugins = ["nomad-north-jupyter>=0.2.6", "nomad-gui==2.0.0"]   # add HZB plugins here
jupyter = ["jupyter-events"]                                     # extra packages in the jupyter image
gpu-action = []
cpu-action = []
dev = ["nomad-lab[infrastructure, dev]==2.0.0"]
[tool.uv]
extra-index-url = ["https://gitlab.mpcdf.mpg.de/api/v4/projects/2187/packages/pypi/simple"]
prerelease = "if-necessary-or-explicit"
```

Plugins can be PyPI names, `pkg @ git+https://...@<sha|tag>`, or `...#subdirectory=path`. **nomad-gui must stay in `plugins`**, because it provides the new GUI.

## Services (docker-compose.yaml)

| Service | Image (2.0.0) | Container | Notes |
| --- | --- | --- | --- |
| elastic | elasticsearch 9.5.0 | nomad_oasis_elastic_9 | volume `nomad_oasis_elastic_9`; `xpack.security.enabled=false` |
| mongo | mongo:8.0 | nomad_oasis_mongo | volume `nomad_oasis_mongo` (named!), `./.volumes/mongo:/backup` |
| postgresql | postgres:16 | nomad_oasis_postgresql | Temporal persistence; volume `nomad_oasis_postgresql` |
| temporal-setup-db, temporal-create-namespace | temporalio/admin-tools:1.31 | one-off | |
| temporal | temporalio/server:1.31 | nomad_oasis_temporal | |
| worker | `${APP_IMAGE}` | (replicas: 4, 4 CPU / 8 GB each) | `admin run action-internal-worker`, health :8080/health |
| cpu_worker / gpu_worker | `/cpu-action`, `/gpu-action` images | commented out | enable for Actions |
| app | `${APP_IMAGE}` | nomad_oasis_app | `admin run app --with-gui --gunicorn --host 0.0.0.0 --workers 2`, health :8000/-/health |
| north | ghcr.io/fairmat-nfdi/nomad-north:v2.0.0rc1 | nomad_oasis_north | JupyterHub; docker socket; `BASE_URL=/backend/north/` |
| jupyterlab_image | `${JUPYTER_IMAGE}` | (replicas 0) | only to pre-pull the jupyter image |
| proxy | nginx:1.31.1-alpine | nomad_oasis_proxy | ports 80/443; the only exposed service |

Image variables, with defaults from the init workflow:

- `APP_IMAGE` = `ghcr.io/<owner>/<repo>:${IMAGE_TAG:-main}`
- `JUPYTER_IMAGE` = `.../jupyter`
- `NOMAD_CPU_WORKER_IMAGE`, `NOMAD_GPU_WORKER_IMAGE`, `NOMAD_NORTH_IMAGE`, `TEMPORAL_VERSION`

Shared env: `NOMAD_ELASTIC_HOST=elastic`, `NOMAD_ELASTIC_VERSION=9`, `NOMAD_MONGO_HOST=mongo`, `NOMAD_TEMPORAL_HOST=temporal`, and `env_file: .env`.

## Secrets

- `.env`: `NOMAD_SERVICES_API_SECRET`, `NOMAD_NORTH_HUB_SERVICE_API_TOKEN`
- `.env.north`: `KEYCLOAK_URL` (central: `https://nomad-lab.eu/fairdi/keycloak/auth`), `KEYCLOAK_REALM` (`fairdi_nomad_prod`), `OAUTH_CLIENT_ID` (`nomad_public`), `OAUTH_CLIENT_SECRET`, `SERVICE_API_TOKEN` (= the hub token above), `JUPYTERHUB_CRYPT_KEY`
- Each is at least 64 hex characters (`openssl rand -hex 32`).

## configs/nomad.yaml (template)

```yaml
services: {api_host: "localhost", api_port: 80, api_base_path: "/backend"}
oasis: {is_oasis: true, uses_central_user_management: true}
plugins:
  entry_points:
    options:
      nomad_north_jupyter.north_tools:jupyter:
        north_tool: {image: ghcr.io/<owner>/<repo>/jupyter:main}   # set by init workflow
meta: {deployment: "oasis", maintainer_email: "me@my-oasis.org"}
logstash: {enabled: false}
temporal: {enabled: true}
mongo: {db_name: nomad_oasis_v1}
elastic: {entries_index: nomad_oasis_entries_v1}
north: {enabled: true, enable_new_hub_api: true}
```

For production, set `services.api_host` to the bare host name, `services.https: true`, and NORTH's `OAUTH_CALLBACK_URL=https://<host>/backend/north/hub/oauth_callback`.

## URL layout (2.0.0)

| Path | Serves |
| --- | --- |
| `/` | new GUI (internally `/backend/gui/v2/`) |
| `/gui/` | old GUI (removed in v2.3.0) |
| `/backend/api/v1` | API |
| `/backend/alive` | liveness |
| `/backend/north/` | JupyterHub |
| `/backend/dashboards/<id>/`, `/backend/apis/<id>/` | plugin dashboards and APIs |
| `/docs` | only if custom docs are built (`NOMAD_DOCS_REPO` + `NOMAD_DOCS_REPO_REF` in the workflow) |
| `/nomad-oasis/...` | legacy links, redirected; `/select-gui` with cookie `nomad_gui_pref=v1/v2` |

## CI (docker-publish.yml)

- Triggers: push and PR to `main`/`develop`, `v*.*.*` tags, and manual runs. Env: `UV_VERSION 0.9`, `PYTHON_VERSION 3.12`, `JUPYTER_VERSION 2025-04-14`.
- Job `update-lockfile` runs `uv lock` and commits `uv.lock` with `-o ci.skip`.
- Job `plugin_unit_tests` runs `nomad-plugin-tests` in 2 parallel groups. `PLUGIN_TESTS_PLUGINS_TO_SKIP` is a comma or newline list.
- Job `build` builds a matrix of app and jupyter images (plus cpu-action and gpu-action when enabled) and pushes them to ghcr.
- The image tests run the built image with `tests/docker-compose.yml` and `tests/nomad.yaml`. `test_app_entry_points` needs every app to return 200. `test_example_uploads` needs every example upload to process with no errors, warnings or ERROR logs.
- Make the GHCR package **public**, or use a PAT on servers. Otherwise the pull fails with `unauthorized`.

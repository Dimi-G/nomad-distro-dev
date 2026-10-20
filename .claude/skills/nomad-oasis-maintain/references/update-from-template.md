# Merging template updates into an HZB Oasis repo

Official procedure (template README, "Updating the distribution from the template"), with HZB specifics.

## Steps

```bash
cd <oasis-repo>                      # e.g. a clone of nomad-hzb/hzb-se-image-2
git switch -c template-v2.0.0        # work on a branch; PR into main
git remote add template https://github.com/FAIRmat-NFDI/nomad-distro-template   # once
git fetch template --tags
git merge template/main --allow-unrelated-histories   # or a release tag: git merge v2.0.0 ...
```

Conflict rules:

| File | Take | Then |
| --- | --- | --- |
| `Dockerfile` | **theirs** (`git checkout --theirs Dockerfile`) | Re-add HZB-specific build steps, if any, such as extra apt packages in the jupyter stage. |
| `.github/workflows/docker-publish.yml` | **theirs** | Re-set `PLUGIN_TESTS_PLUGINS_TO_SKIP`, `NOMAD_DOCS_REPO*`, and the enabled cpu/gpu build matrix. |
| `uv.lock` | **ours** (`git checkout --ours uv.lock`) | CI relocks on push. |
| `pyproject.toml` | merge by hand | Take theirs for `nomad-lab==X`, `nomad-gui==X`, `requires-python`, `[tool.uv]`, `dev`. Keep **ours** for the HZB `plugins` list and `jupyter` extras. Bump git pins of HZB plugins to commits tested against the new NOMAD. |
| `docker-compose.yaml` | usually start from **theirs** | Re-apply HZB deltas: host name in `OAUTH_CALLBACK_URL`, worker replicas and limits, HTTPS lines in `proxy`, the nomad.yaml mount, extra volumes. The image names were already rewritten by the init workflow; check `x-images`. |
| `configs/nomad.yaml` | merge by hand | Keep HZB: `services.api_host`, `https`, `meta.*`, `plugins.entry_points.include/exclude/options`, `ui.unit_systems`, `north.tools`. Take the template's new keys, such as `api_base_path`, `north.enable_new_hub_api`, and `temporal`. |
| `configs/nginx*` | **theirs** | Re-apply only HTTPS cert paths and `client_max_body_size` changes. |
| `README.md` | theirs, plus an HZB section | |
| `scripts/*`, `tests/*` | **theirs** | |

Finish:

```bash
git add -A && git commit -m "Update to nomad-distro-template vX.Y.Z"
git push -u origin template-v2.0.0     # open PR; CI builds and tests the image
```

- If `initialize.yml` reappears from the merge, delete it. It only runs once, on a new repo.
- Read the release notes of every skipped template version and the migration guide for the target NOMAD version **before** deploying (`upgrade-to-2.0.md`, `data-migrations.md`).

## Deploying the merged version

1. Back up first (`operations.md`).
2. Run the data migrations the release requires, such as Elasticsearch 7 to 9 for 2.0.
3. `docker compose pull && docker compose up -d`, then `docker compose ps` and `docker compose logs -f app worker`.
4. Smoke test: log in, open an app, open an existing entry, upload a small batch, and check plots in the new GUI.

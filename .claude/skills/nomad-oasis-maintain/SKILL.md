---
name: nomad-oasis-maintain
description: Maintain HZB NOMAD Oasis deployments built from FAIRmat's nomad-distro-template (perseus-image, hzb-se-image-2, sol-ai-image, hzb-pvcomb-image and the other nomad-hzb/*-image repos). Use when the user wants to set up, update, upgrade (e.g. 1.4.x to 2.0), back up, restore, migrate MongoDB or Elasticsearch, add plugins to an Oasis image, merge template updates, secure, tune, or troubleshoot an Oasis, or asks how the production template differs from this dev distro.
---

# Maintain an HZB NOMAD Oasis

Knowledge snapshot: nomad-distro-template **v2.0.0** (2026-10-18), with nomad-lab 2.0.0 and nomad-gui 2.0.0. FAIRmat versions the template in lockstep with nomad-lab: each NOMAD release has a matching template release.

An Oasis is a **separate repo per deployment**, created from the template. This repo (nomad-distro-dev) is only for development and is **never used in production**. Oasis repos live in the `nomad-hzb` GitHub org. `references/hzb-oasis-inventory.md` lists them and their state.

## Safety rules (production data)

- **Back up before anything that touches data or images.** That means a `mongodump` plus a copy of `.volumes/fs`. In template 2.0.0 the MongoDB data sits in a **named docker volume** (`nomad_oasis_mongo`), not in `.volumes`, so copying `.volumes` alone does **not** back up the database.
- **Never** run `docker volume rm`, `docker compose down -v`, `nomad admin reset`, `nomad admin uploads rm`, or ES index deletes without the user's explicit go-ahead. Run them only after verifying the replacement, such as matching document counts.
- Run commands on the Oasis server only when the user is operating there. Otherwise give them the exact commands. Ask before pushing to an Oasis repo's `main`, because that triggers an image build that the server pulls.
- Secrets (`.env`, `.env.north`) are never committed. Generate them with `bash scripts/generate-env.sh`.

## Common tasks

| Task | Where |
| --- | --- |
| Understand the 2.0.0 template (services, URLs, files, CI) | `references/template-v2.md` |
| Pull template changes into an Oasis repo | `references/update-from-template.md` |
| Upgrade an HZB Oasis from 1.4.x to 2.0.0 | `references/upgrade-to-2.0.md` |
| MongoDB 5→8, Elasticsearch 7→9, reindex, reprocess, archive convert | `references/data-migrations.md` |
| Backups, restore, admin CLI, auth/access control, security, performance, troubleshooting | `references/operations.md` |
| Which HZB Oasis repos exist and their versions | `references/hzb-oasis-inventory.md` |

## Routine update of a running Oasis (no version jump)

1. In the Oasis repo, edit `pyproject.toml` `[project.optional-dependencies] plugins`. Pin git plugins to a commit or tag, for example `"nomad-hysprint @ git+https://github.com/nomad-hzb/nomad-hysprint.git@<sha>"`.
2. Push to `main`. The GitHub workflow then:
   1. relocks `uv.lock` and commits it;
   2. runs every plugin's tests (`nomad-plugin-tests`);
   3. builds `ghcr.io/nomad-hzb/<repo>:main` plus `/jupyter`;
   4. runs app-entry-point and example-upload tests against the image.
3. Wait for a green pipeline. If plugin tests fail because of another plugin's parser, see the plugin skill's `testing.md`.
4. On the server:
   ```bash
   cd <oasis-dir>
   docker compose pull
   docker compose up -d          # recreates changed containers
   docker compose ps             # all healthy?
   curl -fsS localhost/backend/alive   # 2.0.0 layout; 1.4.x: localhost/nomad-oasis/alive
   docker image prune -a         # optional cleanup (ask first)
   ```
5. If parsers or schemas changed how data is stored or displayed, reprocess the affected uploads. Migrated `a_plot` plots, for example, only appear after reprocessing:
   ```bash
   docker exec -ti nomad_oasis_app python -m nomad.cli admin uploads process -- <upload_id> ...
   ```

## Plugins in an Oasis vs in this distro

- **Oasis:** plugins are installed from `pyproject.toml` into the image. Only what is installed exists. `configs/nomad.yaml` is **baked into the image**, unless the `./configs/nomad.yaml:/app/nomad.yaml` volume line in `x-nomad-base.volumes` is uncommented. Use `plugins.entry_points.include/exclude` there to activate per deployment, for example only tfsc-general's batch parser on Perseus.
- **This distro:** plugins are editable submodules plus `[tool.uv.workspace]`. See CLAUDE.md "Choosing Active Plugins".
- **Test in dev first.** Pin the same plugin commits in this distro, run the tests and look in the new GUI, then bump the Oasis repo.

## Refreshing this knowledge

- Template: https://github.com/FAIRmat-NFDI/nomad-distro-template. Read the README (update and migration sections), `docker-compose.yaml`, `configs/`, and `.github/workflows/docker-publish.yml`.
- Releases: https://github.com/FAIRmat-NFDI/nomad-distro-template/releases. These contain the deprecations and breaking URL changes.
- Docs: https://github.com/FAIRmat-NFDI/nomad-docs, under `docs/howto/oasis/*.md` and `docs/howto/oasis/migrate/*.md`. Note that `configure.md` still shows pre-2.0 paths (`/nomad-oasis`, rabbitmq). Trust the template over that page.

Shallow-clone into the scratchpad, diff against the references here, and update them with the date.

# Upgrading an HZB Oasis from 1.4.x to 2.0.0

Applies to hzb-se-image-2, sol-ai-image, hzb-pvcomb-image and the other `nomad-hzb/*-image` repos still on `nomad-lab==1.4.2` as of 2026-10-20. perseus-image was created directly on template v2.0.0.

## What changes for users

- **The new GUI is the default at `/`.** The old GUI moves to `/gui/` and is removed in v2.3.0.
- **The API moves to `/backend/api/v1`.** Old `/nomad-oasis/...` links redirect via `/select-gui`. Scripts and notebooks that hard-code `https://<host>/nomad-oasis/api/v1` must be updated to `/backend/api/v1`. This includes HZB jupyter scripts and `nomad-utility-workflows` users.
- **`a_plot` plots** from HZB plugins **do not show in the new GUI.** Ship migrated plugins (PlotSection) and reprocess, or tell users to use `/gui/` meanwhile.
- **Dataset creation is deprecated.** Use projects with DOIs.

## Checklist

1. **Back up** MongoDB (`bash scripts/backup-mongo.sh`) and `.volumes/fs`. Verify both.
2. **MongoDB is already on 8.0** in these images. Check with `docker compose exec mongo mongosh --eval 'db.version()'` and `featureCompatibilityVersion`. If it still shows 5.x, run the 5→8 migration first (`data-migrations.md`).
3. **Merge template v2.0.0** (`update-from-template.md`). This brings:
   - `nomad-lab[infrastructure]==2.0.0`, `nomad-gui==2.0.0` (replace pins like `nomad-gui==2.0.0a2.dev583`), and `requires-python>=3.11`
   - Elasticsearch **9.5.0** (`nomad_oasis_elastic_9` container and volume, `NOMAD_ELASTIC_VERSION=9`)
   - Temporal 1.31 (from 1.30)
   - north image `nomad-north:v2.0.0rc1`, with `north.enable_new_hub_api: true`
   - `services.api_base_path: "/backend"`; the split nginx configs (`nginx_base_conf`, `nginx_maps_conf`); and the `--with-gui` app command
   - removal of the **`logtransfer`** service and every `NOMAD_LOGSTASH_HOST: logtransfer` env line. The log transfer feature is gone in 2.0.0. Delete the service, `logstash.enabled` stays `false`.
4. **Update NORTH settings:**
   - `OAUTH_CALLBACK_URL=https://<host>/backend/north/hub/oauth_callback`
   - `NOMAD_API_URL=http://app:8000/backend/api/v1`
   - `BASE_URL=/backend/north/`
   - `.env.north` per `generate-env.sh`: `KEYCLOAK_*`, `OAUTH_CLIENT_ID=nomad_public`, `SERVICE_API_TOKEN` equal to `NOMAD_NORTH_HUB_SERVICE_API_TOKEN` in `.env`, and `JUPYTERHUB_CRYPT_KEY`
   - `nomad admin run hub` is deprecated and removed in v2.2.0.
5. **Bump HZB plugin pins** to commits tested on 2.0.0. Run the plugin skill audit and the tests in nomad-distro-dev first.
6. **Check the image reference.** Some HZB compose files still point `x-images`/`image:` at `ghcr.io/fairmat-nfdi/nomad-distro-template:main`. hzb-se-image-2 did on 2026-10-20. Make sure the server runs the HZB-built image, via `APP_IMAGE` in `.env` or the compose image line.
7. **Push, then wait for a green CI**, including plugin tests, app entry point tests, and example upload tests.
8. **On the server:**
   1. `docker compose down`
   2. Migrate Elasticsearch 7→9, Option 1 or 2 (`data-migrations.md`).
   3. `docker compose pull && docker compose up -d`
9. **Verify:**
   - `docker compose ps`, all healthy
   - `curl -fsS https://<host>/backend/alive`
   - the ES9 document count matches ES7
   - login works, apps load, existing entries open, NORTH launches, and an upload processes
10. **Reprocess** uploads whose plots or derived data depend on new plugin code: `nomad admin uploads process` with selection flags.
11. **Clean up** after a verification period. With the user's go-ahead, run `docker volume rm nomad_oasis_elastic` (the old ES7 volume) and prune old images.
12. **Tell users** about the URL changes and the new GUI. Keep `/gui/` available until plugins are migrated.

## Rollback

- Keep the ES7 volume and the previous image tag until verified.
- To roll back:
  1. Check out the previous Oasis repo commit.
  2. `docker compose down`.
  3. Restore the previous compose and `IMAGE_TAG`.
  4. `docker compose up -d`.
- The MongoDB data is untouched by the ES migration. If a reprocess ran on 2.0.0, restore the mongodump and `.volumes/fs` backup before going back.

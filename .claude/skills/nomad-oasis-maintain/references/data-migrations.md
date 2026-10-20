# Data migrations (verbatim from nomad-docs `howto/oasis/migrate/*`, 2026-10-20)

General rules:

- Back up first.
- Read the template release notes and the [NOMAD releases](https://github.com/FAIRmat-NFDI/nomad/releases).
- Verify container health after: `docker compose ps`, `docker compose logs`.
- The software and the data are independent. A new image does not migrate data.

## MongoDB 5.0.6 → 8.x (needed since template 1.4.2)

MongoDB must be upgraded through each major version in turn (5→6→7→8), setting `featureCompatibilityVersion` at each step. A 5.x data dir cannot be mounted into an 8.x container.

```bash
bash scripts/backup-mongo.sh && ls -lh .volumes/mongo && cat .volumes/mongo/backup.log
curl -O https://gitlab.mpcdf.mpg.de/nomad-lab/nomad-FAIR/-/snippets/188/raw/main/upgrade_mongo.py
python3 upgrade_mongo.py -c nomad_oasis_mongo -f docker-compose.yaml --from-version 5.0.6
docker compose exec mongo mongosh --eval 'db.version()'
docker compose exec mongo mongosh --eval 'db.adminCommand({getParameter: 1, featureCompatibilityVersion: 1})'
docker compose logs -f app worker
```

The `upgrade_mongo.py` at the root of this dev repo is this FAIRmat script. The dev distro's docker-compose still runs mongo 5.0.6 (upstream distro-dev on 2026-10-20). Only run the script against a dev database you can lose, or after a backup.

## Elasticsearch 7.17 → 9.5 (NOMAD 2.0)

- ES9 cannot read ES7 indices.
- The materials index (`nomad_oasis_materials_v1`) is dropped in 2.0. Only migrate the **entries** index (`nomad_oasis_entries_v1`).
- ES7 support in NOMAD is removed in **v2.2.0**.

### Option 1: remote reindex ES7 → ES9 (faster; no reprocessing)

1. Add a temporary `nomad_oasis_elastic_9` service and volume next to the running ES7 service. Configure it with:
   - image `docker.elastic.co/elasticsearch/elasticsearch:9.5.0`
   - `discovery.type=single-node`, `xpack.security.enabled=false`
   - `reindex.remote.whitelist=elastic:9200`
   - the disk watermarks
   - port `9201:9200`

   Then start it:
   ```bash
   docker compose up -d --wait --wait-timeout 180 nomad_oasis_elastic_9
   ```
2. Copy the settings and mapping, and create the index on ES9:
   ```bash
   set -o pipefail
   INDEX="$(docker compose exec -T app python -c 'from nomad.config import config; print(config.elastic.entries_index)')"
   docker compose exec -T elastic curl -fsS "http://localhost:9200/${INDEX}/_settings?flat_settings=false" > "/tmp/${INDEX}-settings.json"
   docker compose exec -T elastic curl -fsS "http://localhost:9200/${INDEX}/_mapping" > "/tmp/${INDEX}-mapping.json"
   jq -n --arg index "$INDEX" --slurpfile settings "/tmp/${INDEX}-settings.json" --slurpfile mapping "/tmp/${INDEX}-mapping.json" \
     '{settings: {number_of_replicas: 0, analysis: ($settings[0][$index].settings.index.analysis // {})}, mappings: $mapping[0][$index].mappings}' | \
     curl -sS --fail-with-body -X PUT "http://localhost:9201/${INDEX}" -H 'Content-Type: application/json' --data-binary @-
   ```
3. Reindex:
   ```bash
   jq -n --arg index "$INDEX" '{source: {remote: {host: "http://elastic:9200"}, index: $index, size: 100}, dest: {index: $index}}' | \
     curl -fsS -X POST "http://localhost:9201/_reindex?wait_for_completion=true&refresh=true" -H 'Content-Type: application/json' --data-binary @- | jq .
   ```
4. Verify the counts match:
   ```bash
   docker compose exec -T elastic curl -fsS "http://localhost:9200/${INDEX}/_count" | jq .
   curl -fsS "http://localhost:9201/${INDEX}/_count" | jq .
   ```
5. Finalize:
   1. `docker compose down`.
   2. Set the main `elastic` service to the ES 9.5.0 image, with `xpack.security.enabled=false` and the volume `nomad_oasis_elastic_9`.
   3. Set `NOMAD_ELASTIC_VERSION: 9` on app and workers.
   4. Remove the temporary service.
   5. `docker compose up -d`.
   6. Later, with the user's go-ahead, `docker volume rm nomad_oasis_elastic`.

### Option 2: fresh ES9 and reindex from MongoDB and files (simpler, slower)

1. Back up with `bash scripts/backup-mongo.sh` and keep `.volumes/fs` intact.
2. Change the compose file:
   - set the `elastic` image to ES 9.5.0 and add `xpack.security.enabled=false`
   - set `NOMAD_ELASTIC_VERSION: 9`
   - set the top-level `volumes: elastic: name: "nomad_oasis_elastic_9"`
3. Restart:
   ```bash
   docker compose down && docker compose up -d
   ```
4. Once app and elastic are healthy, reindex:
   ```bash
   docker compose exec app python -m nomad.cli admin uploads index --parallel 4   # add --print-progress 10
   ```
5. After verification, `docker volume rm nomad_oasis_elastic`. The old volume stays as a rollback until then.

## Reindex vs reprocess vs convert

| Command (inside `nomad_oasis_app`) | When |
| --- | --- |
| `nomad admin uploads index [--parallel N]` | The search index is lost or rebuilt, for example ES migration or a restore. Reads the existing archives and does not run parsers. |
| `nomad admin uploads process [-- ids]` | Plugin code changed (parsers, normalizers, `PlotSection` figures, results), uploads failed, or a migration requires it. Re-runs parsing and normalization. |
| `nomad admin uploads reset -- <id>` then `process` | Uploads stuck in processing. |
| `nomad admin uploads convert` | Optional: convert old v1/v2 msgpack archives to the v3 format, which is more memory-efficient. Old ones remain readable. |

Selection flags: `--unpublished`, `--published`, `--outdated` (processed with an older NOMAD), `--processing-failure`, or ids after `--`. With many ids:

```bash
cat ids.txt | xargs nomad admin uploads ls --
```

## Older migrations

- **v1.2.2:** JupyterHub database upgrade for NORTH.
- **v1.2.0:** plugin mechanism and new archive format; reprocessing recommended.
- **v0.8 → v1:** full migration.

See the nomad-docs `docs/howto/oasis/migrate/`.

# Oasis operations: backup, restore, CLI, access, security, performance, troubleshooting

Commands assume the template's container names (`nomad_oasis_app`, `nomad_oasis_mongo`, ...) and are run from the Oasis repo directory on the server.

## Backups

What to back up:

1. **MongoDB** (users' metadata, uploads, entries) with `bash scripts/backup-mongo.sh`. It runs `docker exec nomad_oasis_mongo mongodump -d nomad_oasis_v1 -o /backup` into `.volumes/mongo` and appends to `.volumes/mongo/backup.log`.
2. **Files** in `.volumes/fs`, which holds raw uploads and processed archives. Copy them with rsync or another file backup.
3. Elasticsearch is **not** needed. It can be rebuilt from MongoDB and the files with `nomad admin uploads index`.
4. Also keep the Oasis repo commit, `.env` and `.env.north` (store the secrets safely), and any TLS certs.

Schedule nightly at 02:00, from the repo root:

```bash
(crontab -l 2>/dev/null; echo "0 2 * * * bash $(realpath scripts/backup-mongo.sh)") | crontab -
crontab -l
```

Then copy `.volumes/mongo` and `.volumes/fs` **off the server**. The script only dumps locally.

In template 2.0.0 the live MongoDB data is the named volume `nomad_oasis_mongo`, so a file copy of `.volumes` without a fresh dump does not contain the database.

## Restore onto a new server

```bash
# put .volumes/ back from backup, set .env/.env.north, then
docker compose up -d
docker exec nomad_oasis_mongo mongorestore /backup
docker exec nomad_oasis_app python -m nomad.cli admin uploads index
```

## Admin CLI (inside the app container: `docker exec -ti nomad_oasis_app bash`)

```bash
nomad admin uploads ls [--unpublished|--published|--outdated|--processing-failure] [-- <ids>]
nomad admin uploads rm -- <upload_id> ...          # destructive: confirm with user
nomad admin uploads chown ...                      # also: ownership transfer API exists in 2.0
nomad admin uploads reset -- <upload_id>           # unstick
nomad admin uploads process [-- <ids>]             # reparse + renormalize
nomad admin uploads index [--parallel N] [--print-progress 10]
nomad admin uploads convert                        # archives to v3 format (optional)
nomad admin reset --i-am-really-sure               # wipes everything: never without explicit instruction
```

## Access control (`nomad.yaml` → `auth`)

Read-only public, the default:

```yaml
auth: {require_authentication: false, unauthenticated_user_scopes: {include: ["*:read"]}}
```

Public read, with only a whitelist allowed to write:

```yaml
auth:
  require_authentication: false
  reject_unauthorized_users: false
  unauthenticated_user_scopes: {include: ["*:read"]}
  unauthorized_user_scopes: {include: ["*:read"]}
  authorized_users: [alice, bob]
```

Fully restricted:

```yaml
auth: {require_authentication: true, reject_unauthorized_users: true, authorized_users: [alice, bob]}
```

- Scopes are glob patterns like `*:read` and `*:*`. Partial wildcards such as `u*:read` are not supported. `exclude` beats `include`. All scopes are listed in `nomad.auth.scopes.Scope`.
- Users come from the central NOMAD Keycloak by default (`oasis.uses_central_user_management: true`). The Oasis must reach nomad-lab.eu over HTTP, and users' browsers must reach both.
- A self-hosted Keycloak is possible (configure.md, "Provide and connect your own user management"), and enables MFA and LDAP.

## Security checklist

- HTTPS only:
  - `services.https: true`
  - `nginx_https.conf` with the cert and key mounted
  - NORTH `OAUTH_CALLBACK_URL` on https
  - certs renewed (Let's Encrypt via certbot)
- Only the proxy publishes ports. Host firewall allows 443, plus 80 if it redirects, plus 22 from known IP ranges.
- Secrets live in `.env` and `.env.north`, never in git.
- Containers run as non-root (uid 1000). `sudo chown -R 1000 .volumes` on Linux.
- Keep images updated. Scan them with Trivy or Grype, and check Python deps with `pip-audit`. Enable Dependabot.
- Use disk encryption at the host level.
- Follow FAIRmat Discord `software-updates` and template releases for security notices. Register the Oasis with FAIRmat so they can reach you.

## Performance tuning (`nomad.yaml` → `temporal`)

```yaml
temporal:
  internal_worker:
    pool_size: 1              # processes per container; prefer more replicas first
    max_tasks_per_child: 100
    target_cpu_usage: 0.8     # stop taking tasks above this
    target_memory_usage: 0.8
  entry_workflow_batch_concurrency: 5   # per upload
  entry_concurrency_target: 50          # per upload, per batch
  entry_activity_batch_size: 5
```

- Scale `worker.deploy.replicas` and resource limits in compose. The default is 4 replicas at 4 CPU / 8 GB each. Size them to the server.
- If MongoDB or Elasticsearch time out under many parallel uploads, lower the two concurrency values.
- Set `OMP_NUM_THREADS: 1` on workers to stop numpy/OpenMP oversubscription.
- Hardware minimum: 4 cores, 8 GB RAM (2 GB per core recommended), 30 GB disk.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ghcr.io ... unauthorized` on pull | Make the GHCR package public, or `docker login ghcr.io` with a PAT. |
| `ImmatureSignatureError: The token is not yet valid (iat)` at login | Server clock skew. Sync time (`timedatectl`). |
| Elasticsearch won't start / watermark errors | Free disk space (>30 GB). Set `ulimit -n 65535`. |
| NORTH tool first start times out | Pre-pull the jupyter image (`docker pull ghcr.io/<owner>/<repo>/jupyter:main`). The `jupyterlab_image` service does this on `docker compose pull`. |
| Proxy or firewall networks | Docker proxy in `~/.docker/config.json`, plus Java proxy options for ES. NORTH does not work behind a proxy with central user management. |
| Containers restart in a loop | Temporarily set `restart: "no"`, then `docker compose logs <svc>`. |
| Old bookmarks `/nomad-oasis/gui/...` (2.0) | Handled by the nginx redirect to `/select-gui`. The user picks a GUI, stored in the `nomad_gui_pref` cookie. |

Report problems to FAIRmat with logs from `nomad_oasis_app` and the workers. Use Discord, channel "oasis".

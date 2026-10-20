---
name: update-distro
description: Update this nomad-distro-dev fork and its nomad-FAIR submodule from upstream FAIRmat, resolve the usual conflicts, keep the HZB plugin repos on their branches, re-sync uv and verify the plugins. Use when the user wants to update the distro, update/upgrade nomad or nomad-FAIR, pull upstream changes, or recover from a messy git pull or rebase in this repo.
---

# Update the distro from upstream

This repo is a fork with local commits. `origin` (Dimi-G) is usually stale; `upstream` (FAIRmat-NFDI) is the source of updates. Never use `git pull` here, and never run a blanket `git submodule update`. Use `git -C <path>` instead of `cd` so commands don't change directory.

## 0. Recover first if a pull went wrong

```bash
git status            # look for "rebase in progress" or "merging"
git rebase --abort    # or: git merge --abort
git stash list        # a "WIP on main" stash made just before the pull holds the user's uncommitted work
```

Check `git config pull.rebase` is `false` in this repo.

## 1. Preflight

1. The superproject working tree must be clean. If not, ask the user whether to commit or stash. A stash must be re-applied in step 6.
2. Record each HZB plugin repo's branch and commit, so they can be restored if anything moves them:
   ```bash
   for p in nomad-baseclasses nomad-hysprint nomad-tfsc-general nomad-perovskite-solar-cells-database; do
     echo "$p $(git -C packages/$p rev-parse --abbrev-ref HEAD) $(git -C packages/$p rev-parse --short HEAD)"; done
   ```
3. Fetch and make a backup branch:
   ```bash
   git fetch upstream
   git branch backup/before-update-$(date +%F) main
   git rev-list --left-right --count main...upstream/main   # local-only vs. new upstream commits
   ```
4. Dry-run the merge to see conflicts: `git merge-tree --write-tree --name-only main upstream/main`.

## 2. Merge

```bash
git merge --no-ff upstream/main
```

Typical conflicts and how to resolve them:

- **`packages/nomad-FAIR`**: take upstream's pin. First confirm the local pin is an ancestor of upstream's (`git -C packages/nomad-FAIR merge-base --is-ancestor <local> <upstream>`). If nomad-FAIR has local edits (often only an auto-added `packageManager` line in `gui/package.json`), stash them inside the submodule. Then:
  ```bash
  git -C packages/nomad-FAIR checkout <upstream-pin>
  git add packages/nomad-FAIR
  ```
- **`pyproject.toml`**: keep the local plugin lists (`dependencies`, `[tool.uv.workspace] members`, `[tool.uv.sources]`) and add upstream's new entries (new dependencies, poe tasks). Compare both sides against the merge base:
  ```bash
  B=$(git merge-base main upstream/main)
  git diff $B main -- pyproject.toml
  git diff $B upstream/main -- pyproject.toml
  ```
  Validate the result before committing:
  ```bash
  python3 -I -c "import tomllib,sys; tomllib.load(open(sys.argv[1],'rb')); print('TOML OK')" pyproject.toml
  ```

Commit the merge with a message listing how each conflict was resolved.

## 3. Submodules

Update only nomad-FAIR: `git submodule update packages/nomad-FAIR`. Then check `git submodule status`. If any HZB plugin repo was detached from the branch recorded in step 1, check it out again. A `+` prefix in the status output just means the plugin is newer than its pin. If the user wants it pinned, commit the pointer with `git add packages/<name>`.

## 4. Environment

```bash
cp uv.lock <scratchpad>/uv.lock.before-update   # uv.lock is untracked
uv sync
uv run --no-sync python -c "from nomad.config import config; config.load_plugins(); print(len(config.plugins.entry_points.options))"
```

## 5. Verify plugins against the new nomad-lab

Run each installed plugin's tests from its own directory with the workspace venv:

```bash
(cd packages/nomad-hysprint && ../../.venv/bin/python -m pytest -q tests)
```

For nomad-tfsc-general, exclude hysprint's entry points via a temporary config in the scratchpad. Otherwise the hysprint parser claims tfsc's Excel files and tests fail for reasons unrelated to the update:

```yaml
plugins:
  entry_points:
    exclude: ["nomad_hysprint.parsers:hysprint_parser", "nomad_hysprint.parsers:hysprint_experiment_parser"]
```

Then run `NOMAD_CONFIG=<that file> ../../.venv/bin/python -m pytest -q tests`. If a plugin is not installed in the current workspace, install it temporarily with `uv pip install --no-deps -e packages/<name>`. Afterwards, run `uv pip uninstall` on it and then `uv sync`.

Check what changed in nomad-FAIR between the old and new pins. Look for removed config options, removed APIs and infrastructure changes:

```bash
git -C packages/nomad-FAIR diff <old> <new> -- CHANGELOG.md
git -C packages/nomad-FAIR log --oneline --merges <old>..<new> | grep -iE "break|remov|deprecat|migrat|config|elastic|mongo|pydantic"
```

Then grep the HZB plugins' `src/` and their `nomad.yaml` files for anything that was removed.

## 6. Restore work and push

1. If a stash was made in step 1, run `git stash apply` (not `pop`), check the result, then drop the stash.
2. Before pushing, check for large files: `git diff --stat origin/main..main`. Look for anything unexpected such as installers or `.deb` files. Removing one from unpushed history needs a rewrite. Rewrite only your own commits, because rewriting upstream's signed commits changes their hashes:
   ```bash
   git filter-branch --index-filter 'git rm --cached --quiet --ignore-unmatch <file>' -- main --not origin/main --remotes=upstream
   ```
   Then confirm `git rev-list --left-right --count main...upstream/main` still shows `0` on the right.
3. Ask the user before pushing. HTTPS has no credentials here, so push over SSH:
   ```bash
   git push git@github.com:Dimi-G/nomad-distro-dev.git main:main
   git update-ref refs/remotes/origin/main main
   ```
4. Once the push is confirmed, delete the backup branch if the user wants.

## 7. Report

Tell the user:

- which upstream PRs and which nomad-FAIR commit range came in
- how each conflict was resolved
- the test results for each plugin
- anything in the nomad-FAIR changes that needs action in their plugins or `nomad.yaml`

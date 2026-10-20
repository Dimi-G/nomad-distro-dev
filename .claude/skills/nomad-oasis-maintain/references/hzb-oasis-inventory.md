# HZB Oasis repositories (nomad-hzb GitHub org), snapshot 2026-10-20

Read from each repo's `main` branch (`pyproject.toml`, `docker-compose.yaml`, `configs/nomad.yaml`). All were created from `FAIRmat-NFDI/nomad-distro-template`. Re-run the collection loop at the bottom to refresh.

| Repo | nomad-lab | Elasticsearch | api_base_path | logtransfer svc | HZB/FAIRmat plugins (git) |
| --- | --- | --- | --- | --- | --- |
| perseus-image | **2.0.0** | 9.5.0 | /backend | no | none yet (fresh template init by Dimi-G on 2026-10-20); intended for PERSEUS (tfsc-general) |
| hzb-se-image-2 | 1.4.2 | 7.17.28 | /nomad-oasis | yes | baseclasses, hysprint, chemical-energy, hzb-combinatorial-libraries, nomad-material-processing (branch) |
| sol-ai-image | 1.4.2 | 7.17.28 | /nomad-oasis | yes | baseclasses, hysprint, tfsc-general, perotf, pvcomb, hiern, perovskite-solar-cell-database |
| hzb-pvcomb-image | 1.4.2 | 7.17.28 | /nomad-oasis | yes | baseclasses, chemical-energy, pvcomb |
| hzb-ce-image | 1.4.2 | 7.17.28 | /nomad-oasis | yes | baseclasses, chemical-energy |
| hzb-bessy2-image | 2.0.0rc1 | 7.17.28 | /nomad-oasis | yes | baseclasses, hzb-emil |
| perotf-image | 1.4.2 | 7.17.28 | /nomad-oasis | yes | baseclasses, perotf, luqy-plugin, perovskite-solar-cell-database |
| hzb-emil-image | 1.4.3 | 7.17.28 | /nomad-oasis | yes | baseclasses, hzb-emil |
| hzb-bat-image | 1.4.2 | 7.17.28 | /nomad-oasis | yes | baseclasses, battery-space, aitoolkit, porous-materials, perovskite-solar-cell-database |
| beamline-image | 1.3.16rc1 | 7.17.1 | /nomad-oasis | yes | baseclasses, chemical-energy, hzb-beamlines |
| nrel-cub-nomad-image | ? | 7.17.1 | /nomad-oasis | yes | baseclasses, material-processing, nrel, perovskite-solar-cell-database |

Observations:

- **nomad-baseclasses is in every image.** A baseclasses change, such as the `a_plot` to `PlotSection` migration, reaches all Oases on their next image build. Coordinate the rollout and reprocessing.
- sol-ai-image installs **both hysprint and tfsc-general**, so the batch parser overlap is live there. Pick the active parser with `plugins.entry_points.include/exclude` in its `configs/nomad.yaml`.
- Every non-2.0 image still runs `logtransfer`, which must go on the 2.0 upgrade, and ES7, which needs the ES7→9 migration before v2.2.0.
- hzb-se-image-2's compose `image:` lines point at `ghcr.io/fairmat-nfdi/nomad-distro-template:main`. Verify that the server overrides `APP_IMAGE`, otherwise HZB plugins are not in the running image.
- hzb-se-image-2 pins the prerelease `nomad-gui==2.0.0a2.dev583`. Use `nomad-gui==2.0.0` when moving to nomad-lab 2.0.0.
- perotf-image puts `dev` extras into the production `nomad-lab` requirement, which is unnecessary in an image.

Related HZB plugin repos in the org: nomad-chemical-energy, nomad-pvcomb, nomad-perotf, nomad-hzb-emil, nomad-hzb-beamlines, nomad-battery-space, nomad-hiern, nomad-icat-plugin, nomad-pv-analysis-apps, hzb-combinatorial-libraries-plugin. Jupyter content lives in nomad-hysprint-jupyter-scripts, hzb-ce-nome-jupyter, hzb-ce-nesd-jupyter and nomad-battery-space-jupyter.

## Refresh

```bash
for r in $(curl -s "https://api.github.com/orgs/nomad-hzb/repos?per_page=100" | python3 -c "import json,sys;[print(x['name']) for x in json.load(sys.stdin) if x['name'].endswith('-image')]"); do
  pp=$(curl -fsS https://raw.githubusercontent.com/nomad-hzb/$r/main/pyproject.toml 2>/dev/null)
  dc=$(curl -fsS https://raw.githubusercontent.com/nomad-hzb/$r/main/docker-compose.yaml 2>/dev/null)
  echo "$r | $(echo "$pp" | grep -oE 'nomad-lab\[[^]]*\]==[0-9a-z.]+' | head -1) | $(echo "$dc" | grep -oE 'elasticsearch:[0-9.]+' | head -1)"
done
```

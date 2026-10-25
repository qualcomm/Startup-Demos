# Repository Workflows

| Workflow | Purpose and Triggers |
| --- | --- |
| [Forward Sync](forward-sync.yml) | Updates README tables, then syncs source to destination on pushes to `main` or manual dispatch. |
| [Reverse Sync](reverse-sync.yml) | Syncs destination changes into source on PR events, merge groups, every 12 hours, or manual dispatch. |
| [Pages](deploy.yml) | Deploys the latest `main` after Forward Sync completes, regardless of its outcome, or on manual dispatch. |
| [Preflight Checks](qcom-preflight-checks.yml) | Runs repository policy checks. |
| [Stale Issues](stale-issues.yaml) | Manages inactive issues and pull requests. |

## Sync Configuration

Configure these secrets in the source repository:

| Secret | Purpose |
| --- | --- |
| `SYNC_SOURCE_URL`, `SYNC_SOURCE_BRANCH` | Source repository and branch; also identify where sync jobs may run. |
| `SYNC_DEST_URL`, `SYNC_DEST_BRANCH` | Destination repository and branch. |
| `SYNC_SOURCE_TOKEN` | Source clone/push and README updates. |
| `SYNC_DEST_TOKEN` | Destination access, including Contents and Workflows write for forward sync. Reverse sync falls back to the source token when unset. |

Both sync workflows check repository identity and branch on `ubuntu-latest`
without checkout. Missing source configuration or a nonmatching repository or
branch skips synchronization and README updates. PRs and merge groups use their
target branch. Actual sync jobs require a self-hosted runner in the source.
Automatic forward sync targets `main`; update its trigger for other branches.

Sync preserves history: it fast-forwards when possible, merges divergent branches
when conflict-free, and aborts conflicts without pushing. It never force-pushes.
The [README workflow](update-readme.yml) is reusable and runs within Forward Sync.

## Pages

Enable Pages with **Source: GitHub Actions** in each hosting repository.
Deployment uses the automatic `GITHUB_TOKEN`; no deployment PAT is required.
Without `SYNC_SOURCE_URL`, Pages defaults to `ubuntu-latest`, and the destination
requires no repository secrets.

Set the optional repository variable `PAGES_RUNNER` to `self-hosted` or
`ubuntu-latest` to override selection. For configured repositories, optional
`RUNNER_STATUS_TOKEN` (Administration: read) enables discovery of online
self-hosted runners. Otherwise, selection checks hosted access and retains the
configured source's self-hosted fallback when runner discovery is unavailable.
The selected runner must have repository access; neither a token nor runner
selection bypasses an organization IP allow list.

## Validation

Run from the repository root (Ruby standard library only):

```bash
ruby scripts/workflows/tests/workflow-gates.test.rb
```

See [shared helpers](../../scripts/common/README.md) for Python configuration and
tests, and [reverse sync](../../scripts/reverse-sync/README.md) for local usage.

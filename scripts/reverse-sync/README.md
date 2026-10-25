# Reverse Sync

Syncs destination changes into the source branch without rewriting history:

- Identical branches or destination changes already contained in source: no-op.
- Destination ahead: fast-forward, preserving original commits.
- Divergent branches: merge when conflict-free; otherwise abort without pushing.

Dry runs report the proposed changes without committing or pushing. For divergent
branches, the trial merge is aborted after checking for conflicts.

## Local Usage

From the repository root, with Python 3.12:

```bash
python3 -m pip install -r scripts/reverse-sync/requirements.txt
export PYTHONPATH=scripts
export SYNC_SOURCE_URL="https://github.com/<owner>/<source>"
export SYNC_SOURCE_BRANCH="main"
export SYNC_DEST_URL="https://github.com/<owner>/<destination>"
export SYNC_DEST_BRANCH="main"
python3 scripts/reverse-sync/reverse_sync.py --dry-run
```

Set `SYNC_SOURCE_TOKEN` securely in your environment before running. Set
`SYNC_DEST_TOKEN` when destination access requires a different token; otherwise
it falls back to the source token. Never commit credentials.
Use `--no-dry-run` only when ready to update and push the source branch.

[reverse_sync_config.yaml](reverse_sync_config.yaml) extends the
[shared defaults](../common/README.md). Local credential files and GitHub CLI
authentication require explicit opt-in through the authentication settings.

## GitHub Actions

The [workflow](../../.github/workflows/reverse-sync.yml) runs on PR events, merge
groups, every 12 hours, and manual dispatch. Only the configured source repository
and target branch perform synchronization; other repositories skip it without a
self-hosted runner. See the [workflow guide](../../.github/workflows/Readme.md)
for secrets, runner requirements, and deployment configuration.

Required repository secrets: `SYNC_SOURCE_TOKEN` (read/write access to source's configured branch), `SYNC_DEST_TOKEN` (optional; read access to destination), `SYNC_SOURCE_URL`, `SYNC_SOURCE_BRANCH`, `SYNC_DEST_URL`, `SYNC_DEST_BRANCH`. The script does not bypass branch protection; a blocked push fails cleanly.

## Tests

```bash
cd scripts
PYTHONPATH=. python3 -m pytest reverse-sync/tests common/tests
```

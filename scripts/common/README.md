# Shared Automation Helpers

Shared configuration, authentication, logging, and Git operations for forward
sync, reverse sync, and README updates. Action-specific orchestration lives in
the corresponding script directory.

## Configuration

Each action config extends [common_config.yaml](common_config.yaml):

```yaml
extends: "../common/common_config.yaml"
```

Mappings merge recursively; other values replace defaults. Relative paths resolve
from the action config's directory. Repository URLs, branches, and tokens come
from the configured environment variables. Credential-file and GitHub CLI
fallbacks are disabled by default; tokens are redacted from logs.

See the [workflow guide](../../.github/workflows/Readme.md) for repository setup.

## Tests

From the repository root, with Python 3.12:

```bash
python3 -m pip install -r scripts/common/requirements.txt
PYTHONPATH=scripts python3 -m pytest --import-mode=importlib \
	scripts/common/tests scripts/reverse-sync/tests scripts/update-readme/tests
bash scripts/forward/tests/forward-sync.test.sh
```
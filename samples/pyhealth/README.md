# PyHealth Fixtures

These files are request fixtures for the existing medication reconciliation and data-quality validation APIs.

They are generated from PyHealth Synthetic MIMIC-III when the public dataset is reachable, and they are committed to the repository so tests still run without PyHealth installed.

The generation script includes a Windows compatibility workaround for PyHealth URL handling, so regenerating from PowerShell is supported.

## Regenerate

```bash
pip install -r scripts/requirements-scripts.txt
python scripts/generate_pyhealth_fixtures.py
```

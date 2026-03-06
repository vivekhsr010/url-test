---
# Fill in the fields below to create a basic custom agent for your repository.
# The Copilot CLI can be used for local testing: https://gh.io/customagents/cli
# To make this agent available, merge this file into the default repository branch.
# For format details, see: https://gh.io/customagents/config

name: CSV to YAML Migration Agent 
description: Migrates url_validator.py input from CSV format to YAML for better consistency, comments, and multi-environment support.
---

# CSV to YAML Migration Agent

## Goal

Convert the URL test suite input from `url.csv` to `urls.yaml` and update `url_validator.py` to read YAML instead of CSV.

## Steps

### 1. Add PyYAML dependency

In `requirements.txt`, add:
```
PyYAML>=6.0
```

### 2. Convert `url.csv` to `urls.yaml`

Create `urls.yaml` with this structure:
```yaml
tests:
  - name: "Descriptive test name"
    base: "https://example.com"
    path: "/some/path"
    expected_status: 301
    expected_redirect: "https://www.example.com/some/path"
```

Rules:
- Every row in `url.csv` becomes one entry under `tests:`
- Add a meaningful `name:` for each test case
- `expected_redirect` is optional — omit if empty in CSV
- `expected_status` must be an integer

### 3. Replace `read_csv_file()` with `read_yaml_file()`

Remove:
```python
import csv
CSV_FILE: str = "url.csv"

def read_csv_file(path: str) -> List[Dict[str, Any]]:
    ...
def normalize_row(row: Dict[str, str]) -> Dict[str, str | int]:
    ...
```

Add:
```python
import yaml
YAML_FILE: str = "urls.yaml"

def read_yaml_file(path: str) -> List[Dict[str, Any]]:
    """Read and normalize test cases from a YAML file."""
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return [normalize_entry(entry) for entry in data.get("tests", [])]
    except FileNotFoundError:
        sys.exit(f"[ERROR] File not found: {path}")
    except Exception as error:
        sys.exit(f"[ERROR] Failed to read YAML file: {error}")

def normalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a YAML test entry into a structured test case."""
    from urllib.parse import urljoin
    base = str(entry.get("base", "")).strip()
    path = str(entry.get("path", "")).strip()
    redirect = str(entry.get("expected_redirect", "")).strip()
    try:
        status = int(entry.get("expected_status", 200))
    except ValueError:
        status = 200
    return {
        "name": entry.get("name", ""),
        "url": urljoin(base, path),
        "expected_status": status,
        "expected_redirect": redirect,
    }
```

### 4. Update `main()`

Change:
```python
tests = read_csv_file(CSV_FILE)
```
To:
```python
tests = read_yaml_file(YAML_FILE)
```

### 5. Surface test `name` in JUnit XML

In `write_junit_xml()`, change:
```python
case = SubElement(suite, "testcase", classname="URLTest", name=f"[{idx}] {result['url']}")
```
To:
```python
label = result.get("name") or result["url"]
case = SubElement(suite, "testcase", classname="URLTest", name=f"[{idx}] {label}")
```

## Acceptance Criteria

- [ ] `urls.yaml` exists and contains all test cases from the old `url.csv`
- [ ] `url_validator.py` no longer imports `csv`
- [ ] Running the script produces an identical `results.xml` as before
- [ ] Each JUnit `testcase` shows a human-readable name, not just a URL

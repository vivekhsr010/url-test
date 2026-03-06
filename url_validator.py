#!/usr/bin/env python3

import sys
import yaml
import requests
import urllib3
import xml.dom.minidom
from xml.etree.ElementTree import Element, SubElement, tostring
from urllib.parse import urljoin
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

# === Configuration ===
YAML_FILE: str = "urls.yaml"
XML_FILE: str = "results.xml"
TIMEOUT: int = 6
VERIFY_SSL: bool = os.getenv("VERIFY_SSL", "false").lower() == "true"

if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

def check_url(test: Dict[str, Any]) -> Dict[str, Any]:
    """Send HTTP request and validate the response."""
    url: Optional[str] = test.get("url")

    if not isinstance(url, str) or not url.strip():
        print("[ERROR] Invalid or missing URL in test case.")
        return {
            **test,
            "status": None,
            "redirect": None,
            "success": False,
            "error": "URL is invalid or empty"
        }

    try:
        response = requests.get(url, allow_redirects=False, timeout=TIMEOUT, verify=VERIFY_SSL)
        status: int = response.status_code
        redirect: str = response.headers.get("Location", "")

        is_status_ok: bool = status == test["expected_status"]
        is_redirect_ok: bool = (
            not test["expected_redirect"] or redirect.startswith(test["expected_redirect"])
        )

        success: bool = is_status_ok and is_redirect_ok

        print_test_result(url, success, status, test["expected_status"], test["expected_redirect"], redirect)

        return {
            **test,
            "status": status,
            "redirect": redirect,
            "success": success
        }

    except requests.exceptions.RequestException as error:
        print(f"[ERROR] {url} → {error}")
        return {
            **test,
            "status": None,
            "redirect": None,
            "success": False,
            "error": str(error)
        }

def print_test_result(
    url: str,
    success: bool,
    actual_status: Optional[int],
    expected_status: int,
    expected_redirect: str,
    actual_redirect: str
) -> None:
    """Print the test result to the terminal."""
    if success:
        message = f"[PASS] {url} → {actual_status}"
        if actual_redirect:
            message += f", Redirect: {actual_redirect}"
        print(message)
    else:
        print(f"[FAIL] {url} → {actual_status} (Expected {expected_status})")
        if expected_redirect:
            print(f"       Redirect: expected → {expected_redirect}, got → {actual_redirect or 'None'}")

def write_junit_xml(results: List[Dict[str, Any]], file_path: str) -> None:
    """Write test results to a JUnit-compatible XML file."""
    suite = Element("testsuite", name="URL Check")
    suite.set("tests", str(len(results)))
    suite.set("failures", str(sum(1 for r in results if not r["success"])))
    suite.set("errors", "0")
    suite.set("timestamp", datetime.now().astimezone().isoformat())

    for idx, result in enumerate(results, 1):
        label = result.get("name") or result["url"]
        case = SubElement(suite, "testcase", classname="URLTest", name=f"[{idx}] {label}")
        if not result["success"]:
            msg = f"Status: {result.get('status')}, Redirect: {result.get('redirect')}"
            if "error" in result:
                msg += f"\nError: {result['error']}"
            SubElement(case, "failure", message=msg)

    xml_data = xml.dom.minidom.parseString(tostring(suite, encoding="utf-8"))
    pretty_xml = xml_data.toprettyxml(indent="  ")

    try:
        with open(file_path, "w", encoding="utf-8") as xmlfile:
            xmlfile.write(pretty_xml)
        print(f"[INFO] JUnit report written to {file_path}")
    except Exception as error:
        sys.exit(f"[ERROR] Failed to write report: {error}")

def main() -> None:
    """Main execution function."""
    print(f"[INFO] Reading test cases from {YAML_FILE}")
    tests = read_yaml_file(YAML_FILE)

    print(f"[INFO] Running {len(tests)} tests...")
    results = [check_url(test) for test in tests]

    write_junit_xml(results, XML_FILE)

    failed = sum(1 for r in results if not r["success"])
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
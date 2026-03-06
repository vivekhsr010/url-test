#!/usr/bin/env python3

import sys
import csv
import time
import requests
import urllib3
import xml.dom.minidom
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree.ElementTree import Element, SubElement, tostring
from urllib.parse import urljoin
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

# === Configuration ===
CSV_FILE: str = "url.csv"
XML_FILE: str = "results.xml"
TIMEOUT: int = 6
VERIFY_SSL: bool = os.getenv("VERIFY_SSL", "false").lower() == "true"
try:
    MAX_WORKERS: int = max(1, int(os.getenv("MAX_WORKERS", "10")))
except ValueError:
    MAX_WORKERS = 10

try:
    MAX_RETRIES: int = max(0, int(os.getenv("MAX_RETRIES", "3")))
except ValueError:
    MAX_RETRIES = 3

try:
    RETRY_DELAY: float = max(0.0, float(os.getenv("RETRY_DELAY", "1.0")))
except ValueError:
    RETRY_DELAY = 1.0

if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def read_csv_file(path: str) -> List[Dict[str, Any]]:
    """Read and normalize test cases from a CSV file."""
    try:
        with open(path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            return [normalize_row(row) for row in reader]
    except FileNotFoundError:
        sys.exit(f"[ERROR] File not found: {path}")
    except Exception as error:
        sys.exit(f"[ERROR] Failed to read CSV file: {error}")

def normalize_row(row: Dict[str, str]) -> Dict[str, str | int]:
    """Normalize a CSV row into a structured test case."""
    base: str = (row.get("Base") or "").strip()
    path: str = (row.get("Path") or "").strip()
    redirect: str = (row.get("ExpectedRedirect") or "").strip()
    status: str = (row.get("ExpectedStatus") or "200").strip()

    try:
        expected_status: int = int(status)
    except ValueError:
        expected_status = 200

    url: str = urljoin(base, path)

    return {
        "url": url,
        "expected_status": expected_status,
        "expected_redirect": redirect
    }

def check_url(test: Dict[str, Any]) -> Dict[str, Any]:
    """Send HTTP request and validate the response, retrying on transient network errors."""
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

    retryable_exceptions = (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    )

    last_error: Optional[Exception] = None

    for attempt in range(MAX_RETRIES + 1):
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

        except retryable_exceptions as error:
            last_error = error
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** attempt)
                print(f"[RETRY] {url} → retry {attempt + 1}/{MAX_RETRIES} after error: {error}. "
                      f"Waiting {delay:.1f}s...")
                time.sleep(delay)
            else:
                if MAX_RETRIES == 0:
                    print(f"[ERROR] {url} → {error}")
                else:
                    print(f"[ERROR] {url} → all {MAX_RETRIES} retries exhausted: {error}")

        except requests.exceptions.RequestException as error:
            print(f"[ERROR] {url} → {error}")
            return {
                **test,
                "status": None,
                "redirect": None,
                "success": False,
                "error": str(error)
            }

    return {
        **test,
        "status": None,
        "redirect": None,
        "success": False,
        "error": str(last_error)
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
        case = SubElement(suite, "testcase", classname="URLTest", name=f"[{idx}] {result['url']}")
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
    print(f"[INFO] Reading test cases from {CSV_FILE}")
    tests = read_csv_file(CSV_FILE)

    print(f"[INFO] Running {len(tests)} tests with {MAX_WORKERS} workers "
          f"(max retries: {MAX_RETRIES}, retry delay: {RETRY_DELAY}s)...")

    start_time = time.time()

    results: List[Dict[str, Any]] = [None] * len(tests)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_index = {
            executor.submit(check_url, test): idx
            for idx, test in enumerate(tests)
        }

        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                results[idx] = {
                    **tests[idx],
                    "status": None,
                    "redirect": None,
                    "success": False,
                    "error": str(exc)
                }

    elapsed = time.time() - start_time
    print(f"[INFO] All tests completed in {elapsed:.2f}s")

    write_junit_xml(results, XML_FILE)

    failed = sum(1 for r in results if not r["success"])
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
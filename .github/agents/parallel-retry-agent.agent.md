---
# Fill in the fields below to create a basic custom agent for your repository.
# The Copilot CLI can be used for local testing: https://gh.io/customagents/cli
# To make this agent available, merge this file into the default repository branch.
# For format details, see: https://gh.io/customagents/config

name: Parallel URL Checks and Retry Logic Agent
description: Improves url_validator.py performance and reliability by introducing concurrent URL testing and automatic retry on transient failures.
---

# Parallel URL Checks and Retry Logic Agent

## Goal

Make the URL validator faster and more resilient in CI environments by running checks in parallel and retrying failed requests before marking them as genuine failures.

---

## Problem

### Why Parallel?

The current tool checks URLs one at a time. In a worst-case scenario (e.g. 26 URLs × 6 second timeout), the entire test run could take over **2.5 minutes** just waiting for network responses — even when all URLs are healthy.

Since each URL check is independent and the bottleneck is network I/O (not CPU), running them concurrently is a safe and natural improvement.

### Why Retry?

CI cloud runners occasionally experience transient issues — brief DNS hiccups, connection resets, or load balancer blips. A single failed request currently causes a permanent `FAIL` in the report, which leads to false negatives and unnecessary pipeline failures that waste developer time.

---

## Key Ideas

### Parallel Execution
- Run all URL checks concurrently instead of one by one
- The number of concurrent workers should be configurable (e.g. via an environment variable or CLI flag)
- Results should be collected in the same order as the input list to keep the report consistent
- Errors in one URL check must not affect others

### Retry Logic
- Before marking a URL as failed, retry the request a configurable number of times
- Wait a short, increasing delay between each retry (exponential backoff) to avoid hammering a temporarily slow server
- Only network/connection errors should trigger a retry — a definitive HTTP response (even a wrong status code) should not be retried
- The maximum number of retries should be configurable (e.g. via environment variable)

### Configurable Behaviour
- Max number of parallel workers — to avoid overwhelming the target server or CI network
- Max retry attempts — to balance reliability vs. speed
- Wait time between retries — to control backoff aggressiveness
- All three should have sensible defaults that work without any configuration

---

## Expected Outcome

- The test suite runs significantly faster (all URLs checked nearly simultaneously)
- Transient network blips no longer cause false failures
- The JUnit XML output remains identical in structure — only execution speed and reliability change
- No change to how test cases are defined (`urls.yaml` or `url.csv`)

---

## Acceptance Criteria

- [ ] All URL checks run concurrently, not sequentially
- [ ] Number of parallel workers is configurable
- [ ] Failed requests are retried up to a configurable number of times
- [ ] Retries use increasing wait times between attempts
- [ ] Only connection/network errors trigger retries — not wrong-status responses
- [ ] Results are collected in original input order
- [ ] JUnit XML output structure is unchanged
- [ ] Total CI runtime is measurably reduced compared to sequential execution

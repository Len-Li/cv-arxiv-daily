# Codebase Bug Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all confirmed data, search, parsing, automation, and growth issues without changing the published JSON schema.

**Architecture:** Keep the Python producer and static HTML consumer, but make both parse the tab-delimited contract directly. Pass the active result array through browser pagination, fail closed during legacy repair, and preserve all historical records indefinitely.

**Tech Stack:** Python 3.10, `unittest`, Node.js VM tests, vanilla JavaScript, YAML, GitHub Actions.

---

### Task 1: Add Regression Tests

**Files:**
- Modify: `tests/test_daily_arxiv.py`

**Step 1: Write failing backend tests**

Add tests proving pipe-delimited legacy entries retain their title and author,
malformed entries raise without replacing the file, and very old records remain
after subsequent updates.

**Step 2: Write failing frontend tests**

Execute the page script in Node's `vm` module and assert that starred titles
round-trip exactly and a filtered array produces its own second page.

**Step 3: Run tests to verify failure**

Run: `python -m unittest discover -s tests -v`

Expected: failures for legacy parsing, starred titles, and filtered
pagination.

### Task 2: Protect and Bound Stored Data

**Files:**
- Modify: `daily_arxiv.py`
- Modify: `config.yaml`
- Modify: `README.md`

**Step 1: Implement strict entry parsing**

Parse current Tab fields first, then historical Markdown pipe fields. Strip
only outer bold markers and raise `ValueError` when date, title, or author is
missing.

**Step 2: Preserve history indefinitely**

Keep `update_json_file` merge-only: update matching arXiv IDs and retain every
other historical record regardless of date.

**Step 3: Restrict Diffusion and document settings**

Add `categories: ["cat:cs.CV"]` and explain unlimited history and the test
commands in the README.

**Step 4: Run backend tests**

Run: `python -m unittest discover -s tests -v`

Expected: backend tests pass; frontend tests remain failing until Task 3.

### Task 3: Fix Frontend Parsing and Pagination

**Files:**
- Modify: `docs/papers-json.html`

**Step 1: Parse fields directly**

Read date, title, author, and PDF from the four Tab-separated fields. Remove
only the outer `**` from date and title.

**Step 2: Page the active result set**

Change `appendLoadMore` to accept the sorted `categoryPapers` array and slice
that same array on every click.

**Step 3: Run frontend regression tests**

Run: `python -m unittest discover -s tests -v`

Expected: all backend and frontend tests pass.

### Task 4: Enforce Tests in Automation

**Files:**
- Modify: `.github/workflows/cv-arxiv-daily.yml`

**Step 1: Add deterministic Node setup**

Use `actions/setup-node@v4` with Node 20 for JavaScript regression tests.

**Step 2: Run tests before production update**

Add `python -m unittest discover -s tests -v` after dependency installation
and before `python daily_arxiv.py`.

### Task 5: Verify End to End

**Files:**
- Verify: all changed source, tests, configuration, workflow, and docs

**Step 1: Run syntax and unit checks**

Run Python compilation, all unit tests, JSON parsing, and `git diff --check`.

**Step 2: Verify real dependencies**

Load the configuration with the pinned packages and confirm the Diffusion
query contains `cat:cs.CV`.

**Step 3: Verify the served page**

Serve the repository locally, load `docs/papers-json.html`, and confirm the
page renders data while the Node regression checks prove starred-title and
filtered-pagination behavior.

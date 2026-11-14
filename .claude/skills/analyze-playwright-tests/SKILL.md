---
name: analyze-playwright-tests
description: >-
  Analyze a repository's Playwright end-to-end tests for the property dataset:
  clone the repo, find each active test and its line span, classify the
  high-level property each test verifies using the shared vocabulary, and store
  the annotations in data/dataset.db. Use when adding a repo or more tests to the
  dataset, writing an annotations JSON, extracting test line spans, classifying
  tests as a batch subagent, or reconciling property names across batches.
---

# Analyze Playwright tests for the property dataset

## Goal

You build a **discovery dataset** that informs the design of a property-based-testing
(PBT) specification language. For each real-world Playwright test, you record the
**property** it verifies.

A **property** is a reusable correctness claim that holds in many apps, such as
"setting a value and reading it back returns the same value." A property is **not**
a restatement of the steps the test performs.

| Test does | Property is | Not |
|---|---|---|
| Unchecks an already-unchecked box, asserts it stays unchecked | `idempotence` | `uncheck-checkbox` |
| Fills an input, reads `value`, asserts it matches | `round-trip-fidelity` | `fill-works` |
| Calls `check()` on a `<div>`, asserts it throws | `precondition-enforcement` | `checkbox-error-message` |

You (or a subagent) classify every test by reading its source. Scripts only clone
and store; they never classify.

## Workflow for one repo

1. **Load the vocabulary.** Read every existing property before you classify anything:
   ```sh
   uv run scripts/seed_db.py   # only if data/dataset.db does not exist yet
   sqlite3 -header -column data/dataset.db \
     "SELECT name, rating, tag, description FROM properties ORDER BY name;"
   ```
   Reuse these names. The database is the source of truth; `data/seed_template.json`
   holds only a sample.

2. **Clone the repo** (needs `GITHUB_TOKEN`, see Environment):
   ```sh
   uv run scripts/clone_repo.py https://github.com/owner/name
   ```
   The script prints a `RepoRef(...)` line and the clone directory
   `tmp/data/<commit-sha>/`. Copy `full_name`, `commit_SHA`, `repo_size`, `stars`,
   `language`, and `url` from that line into the annotations `repo` object.

3. **Find the suite.** Open each `playwright.config.*` and read `testDir`. Without
   `testDir`, the suite lives next to the config. List the `*.spec.*`, `*.test.*`,
   and `*.e2e.*` files under that directory.

4. **Extract test spans.** Follow "Find test boundaries" below. Record each test's
   `test_path`, `start_line`, `end_line`, and title.

5. **Classify each test.** Read the test's source, then follow "Classify a test."
   For more than ~40 tests, split the work across subagents (see "Batch work with
   subagents").

6. **Write the annotations JSON** in the session scratchpad (see "Annotations JSON").

7. **Run the pre-store checklist**, then store:
   ```sh
   uv run scripts/store_analysis.py <scratchpad>/annotations.json
   ```
   The script upserts the repo, properties, and tests in one transaction. Re-running
   the same file changes nothing. If any test references an unknown property, the
   script raises `UnknownPropertyError` and writes nothing.

## Find test boundaries

A test **declaration** is a call to `test`, `it`, or a modifier (`test.only`,
`test.fail`, `test.slow`) whose **first argument is a string literal** (quotes or
backticks) and that takes a function body.

| Line | Boundary? | Why |
|---|---|---|
| `it('CH-004 should not uncheck the unchecked box', async ({ page }) => {` | Yes | String first argument, function body |
| ``test(`should fill ${type}`, async ({ page }) => {`` | Yes | Template strings count; keep `${type}` verbatim in `name` |
| `test.describe('checkbox', () => {` | No | Groups tests; never record a `describe` |
| `it.fixme(browserName === 'firefox', 'reason');` | No | Conditional skip inside another test; that test still counts |
| `test.skip('broken on CI', async ({ page }) => {` | Disabled | String first argument with a body: a disabled test. Skip it |

Span rules:
- Lines are **1-based and inclusive**.
- `start_line` is the line containing `test(` / `it(`. Do not include comments or
  blank lines above it.
- `end_line` is the line containing the call's closing `});`. Match brackets from
  `start_line`; do not stop at "the line before the next test," which drags in
  comments, helpers, and the enclosing `describe`'s `});`.
- `test_path` is relative to the clone root, with forward slashes:
  `tests/page/page-check.spec.ts`, not `tmp/data/<sha>/tests/...`.
- A loop that generates tests (`for (const type of types) { test(...) }`) produces
  **one** record: the single declaration in the source.
- For pytest-playwright files, a test is a `def test_*` function (or a method of a
  `Test*` class); the span runs from its first decorator to its last body line.

Verify before classifying: open three spans at random and confirm each bounds
exactly one test call, from `it(` to its closing `});`.

The unique key for a test is `test_path#start_line`
(e.g. `tests/page/page-check.spec.ts#38`). Use it to merge batch results and dedupe.
Copy the title verbatim into `name`; never edit files in the clone.

## Classify a test

Follow these rules in order:

1. **Read the assertions, not the title.** Titles describe intent; `expect(...)` calls
   show what the test actually checks.
2. **Reuse an existing property** whenever its description fits the test.
3. **Pick the 1–2 properties the assertions pin most directly.** List a extra properties only
   if separate assertions clearly verifies them.
4. **Coin a new property only when nothing fits.** Follow "Name a new property."

### Worked examples (from `microsoft/playwright`)

**Example 1: idempotence**
```ts
it('CH-004 should not uncheck the unchecked box', async ({ page }) => {   // line 38
  await page.setContent(`<input id='checkbox' type='checkbox'></input>`);
  await page.uncheck('input');
  expect(await page.evaluate(() => window['checkbox'].checked)).toBe(false);
});                                                                        // line 42
```
```json
{ "name": "CH-004 should not uncheck the unchecked box",
  "description": "Unchecking an already-unchecked box leaves it unchecked.",
  "language": "typescript", "test_path": "tests/page/page-check.spec.ts",
  "start_line": 38, "end_line": 42, "property_names": ["idempotence"] }
```
Why: the target already satisfies the goal state, and the action causes no change.

**Example 2: round-trip-fidelity, including the empty value**
```ts
it('FI-030 should be able to clear using fill()', async ({ page, server }) => {
  await page.goto(server.PREFIX + '/input/textarea.html');
  await page.fill('input', 'some value');
  expect(await page.evaluate(() => window['result'])).toBe('some value');
  await page.fill('input', '');
  expect(await page.evaluate(() => window['result'])).toBe('');
});
```
→ `["round-trip-fidelity"]`. A written value reads back unchanged, and so does `''`.

**Example 3: precondition-enforcement**
```ts
it('CH-011 should throw when not a checkbox 2', async ({ page }) => {
  await page.setContent(`<div role=button>Check me</div>`);
  const error = await page.check('div').catch(e => e);
  expect(error.message).toContain('Not a checkbox or radio button');
});
```
→ `["precondition-enforcement"]`. An invalid target is rejected with an explicit error.

**Example 4: dry-run-purity, not idempotence**
```ts
it('CH-015 trial run should not uncheck', async ({ page }) => {
  await page.setContent(`<input id='checkbox' type='checkbox' checked></input>`);
  await page.uncheck('input', { trial: true });
  expect(await page.evaluate(() => window['checkbox'].checked)).toBe(true);
});
```
→ `["dry-run-purity"]`. The box starts **checked**, so unchecking would change it. The
`trial` flag is what keeps state unchanged. Compare with Example 1 before choosing.

### Name a new property

- Use **kebab-case**, 2–4 words: `radio-group-single-selection`.
- Name the behavior plainly and concretely. Prefer a literal description over jargon.
- Keep it independent of any one app: it must make sense for any app with the same
  kind of feature.
- Describe it in one sentence that states the invariant, not the test steps.

| Candidate | Verdict | Fix |
|---|---|---|
| `radio-group-single-selection` | Good | Concrete, kebab-case, holds in any app with radio groups |
| `Radio Button Correctness` | Bad | Not kebab-case, and "correctness" does not say what holds |
| `openmct-telemetry-plot-updates` | Bad | Names the app; use the general behavior |
| `structural-isomorphism-preservation` | Bad | Jargon; say what stays the same |
| `ordering-consistency` | Bad | Synonym of existing `ordering-correctness`; reuse it |

### Rate a new property

`rating` is an integer from 1 to 5. It rates how reusable the **property** is as a PBT
property, not how good the test is.

| Rating | Meaning | Existing examples |
|---|---|---|
| 5 | Clean, general invariant that applies almost everywhere | `idempotence`, `round-trip-fidelity`, `precondition-enforcement` |
| 4 | General, but needs some domain context | `request-minimality` |
| 3 | Applies to a family of features | `input-clamping`, `derived-state-correctness` |
| 2 | Mostly about UI presentation | `responsive-relayout`, `ordering-correctness` |
| 1 | Narrow or tied to one kind of widget | `injection-safety` |

## Annotations JSON

One file describes one repo. `dataset/annotation_parser.py` parses it.

```json
{
  "repo": {
    "full_name": "microsoft/playwright",
    "commit_SHA": "f0eadb9783f97ea495cb8bd55860c5d5b99fe1c1",
    "repo_size": 247211, "stars": 99306,
    "language": "TypeScript", "url": "https://github.com/microsoft/playwright"
  },
  "repo_description": "Cross-browser automation framework; this suite checks its input actions (check, fill, selectOption) against controlled HTML fixtures.",
  "properties": [
    { "name": "radio-group-single-selection",
      "description": "Selecting one option in a radio group deselects every other option in that group.",
      "rating": 3, "tag": null }
  ],
  "tests": [
    { "name": "CH-004 should not uncheck the unchecked box",
      "description": "Unchecking an already-unchecked box leaves it unchecked.",
      "language": "typescript", "test_path": "tests/page/page-check.spec.ts",
      "start_line": 38, "end_line": 42, "property_names": ["idempotence"] }
  ]
}
```

Field rules:
- `repo.*`: copy from the `clone_repo.py` output. `repo.language` is GitHub's label
  (`"TypeScript"`); it is not the test `language` enum.
- `repo_description`: 1–3 sentences on what the app is and what the suite exercises.
- `properties`: list **only properties you are adding**. Omit the key or use `[]`
  when every name already exists.
  - **Never re-list an existing property.** The store overwrites the stored
    description, rating, and tag with whatever you list, so a re-listed property
    with `"tag": null` erases its tag.
- `tag`: always `null` for new properties. A human assigns tags later.
- `tests[].language`: one of `typescript`, `javascript`, `python`, matching the
  test file's extension.
- `tests[].description`: one sentence stating the invariant this test pins down,
  in terms of the app's behavior.
- `tests[].property_names`: every name must exist in the database **or** in this
  file's `properties`.

## Batch work with subagents

Parallel subagents classify faster, but each one invents its own synonyms. Contain
that with a fixed contract and one reconciliation pass.

**Orchestrator: give each subagent**
1. A batch of ~30 test keys with their spans (`test_path#start_line` → `end_line`, title).
2. The clone directory path.
3. The full current vocabulary from step 1 of the workflow.
4. This skill, and this instruction: "Do not coin properties directly. Put any new
   property in `proposed_properties`."

**Subagent: return exactly this JSON**, and write it to
`<scratchpad>/batches/<batch_id>.json` so the work can resume after a failure:
```json
{
  "batch_id": "b03",
  "results": {
    "tests/page/page-check.spec.ts#38": {
      "end_line": 42,
      "name": "CH-004 should not uncheck the unchecked box",
      "description": "Unchecking an already-unchecked box leaves it unchecked.",
      "property_names": ["idempotence"]
    },
    "tests/page/page-check.spec.ts#20": { "skip": "setup only, no assertion on behavior" }
  },
  "proposed_properties": [
    { "name": "radio-group-single-selection",
      "description": "Selecting one option in a radio group deselects every other option in that group.",
      "rating": 3, "closest_existing": "predicate-correctness" }
  ]
}
```

**Orchestrator: reconcile before storing**
1. Collect every `proposed_properties` entry across batches.
2. Merge duplicates and near-synonyms into one canonical name. If an existing
   property fits, map the proposal to it.
3. Record each merge in a `RENAME` map and apply it to every batch's
   `property_names`. Past merges, for reference:

   | Synonyms | Canonical |
   |---|---|
   | `ordering-consistency` | `ordering-correctness` |
   | `layout-responsiveness`, `responsive-visibility` | `responsive-relayout` |
   | `input-sanitization`, `export-sanitization`, `navigation-safety` | `injection-safety` |
   | `*-indication` | `user-feedback-indication` |
   | `request-batching` | `request-minimality` |

4. Build one annotations JSON from the merged results.

## Pre-store checklist

- [ ] Every `property_names` entry exists in the database or in `properties`.
- [ ] `properties` holds only new names, each with `rating` 1–5 and `tag: null`.
- [ ] No test has empty `property_names`; skipped tests are absent.
- [ ] No two tests share a `test_path#start_line` key.
- [ ] Every `start_line <= end_line`; three random spans open to exactly one test.
- [ ] Every `test_path` is relative to the clone root.
- [ ] `commit_SHA` matches the clone directory name under `tmp/data/`.

## Environment

- `clone_repo.py` and `find_playwright_repos.py` need `GITHUB_TOKEN`.
  `store_analysis.py` and `seed_db.py` do not.
- If the harness blocks you from reading credentials (for example
  `$(gh auth token)`), ask the user to run the clone:
  `GITHUB_TOKEN=$(gh auth token) uv run scripts/clone_repo.py <url>`.
- Run everything with `uv run` (Python 3.14). Source lives under
  `playwright-test-index/src`.
- `data/dataset.db` is **git-ignored**; each person works in a local copy.
  `data/seed_template.json` is the committed sample used to build a fresh database.
- Clones live in git-ignored `tmp/data/`. Put scratch files (extraction scripts, batch
  results, annotations JSON) in the session scratchpad, not the repo.

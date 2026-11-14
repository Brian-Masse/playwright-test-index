# Playwright Test Analysis

Tools for building a dataset of real-world Playwright tests. The repo has 2 functions

1. **Querying:** Finding real-world GitHub projects that use Playwright.
2. **Analyzing** Clones a project safely and shallowly to enable test property anlaysis. Stores results of analysis into a local MySQL DB.

## Local Development & Setup

Requirements:
```
-[uv](https://docs.astral.sh/uv/)
-a GitHub Personal Access Token.
```

Setup

```sh
uv sync
export GITHUB_TOKEN=<your-token>
```

## Usage

### Find repos that use Playwright

```sh
uv run scripts/find_playwright_repos.py \\
    [keywords ...] \\
    [--language {python,typescript,javascript}] \\
    [--min-stars N] \\
    [--limit N]
```

Searches GitHub and keeps repos that pass every check listed in `scripts/find_playwright_repos.py`.

Example 

```sh
uv run scripts/find_playwright_repos.py topic:nextjs topic:self-hosted --language typescript --min-stars 500 --limit 100
```

> - `limit` is the limit against the GH API, and does not guarentee limit number playwright repos.
> - `Keywords` are joined by `and`. 
> - Each candidate costs GitHub API calls, so keep `--limit` modest (max 1000).


### Clone a repo for analysis

```sh
uv run scripts/clone_repo.py <github-repo-url>
```

Pins the repo to the latest commit on its default branch and clones it into `tmp/data/<commit-sha>/`.

> **Notes**
>
> - The clone is shallow (one commit) and sandboxed: no hooks, no submodules, no global git config, symlinks disabled.
> - Re-cloning the same commit replaces the existing checkout.

## Project Structure

```
playwright-test-index/src/
├─ ghapi/                    GitHub API access, Playwright checks, and cloning repos to disk
├─ models/                   Immutable domain types shared by every package
└─ pipelines/                Workflows that compose the ghapi pieces

scripts/                     CLI entry points that build the concrete classes and run a pipeline
├─ find_playwright_repos.py
└─ clone_repo.py

tmp/data/                    Local clones (created on demand, git-ignored)
```
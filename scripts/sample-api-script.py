import os

from api.github_gateway import GitHubGateway
from api.repo_reader import RepoReader
from models.repo_ref import RepoRef

GITHUB_URL_PREFIX: str = "https://github.com/"
TOKEN_ENV_VAR: str = "GITHUB_TOKEN"


# MARK: basic_positive_repo_check
def basic_positive_repo_check() -> None:

    repo_url: str = "https://github.com/AutomationPanda/playwright-python-tutorial"
    full_name: str = repo_url.removeprefix(GITHUB_URL_PREFIX)

    with GitHubGateway.from_token(os.environ[TOKEN_ENV_VAR]) as gateway:
        repo: RepoRef = gateway.get_repo(full_name)

        reader: RepoReader = RepoReader(gateway)
        has_playwright: bool = reader.repo_has_playwright(repo)

    assert has_playwright, f"{full_name} was not detected as a Playwright repo."
    print(f"PASS: {full_name} uses Playwright.")


# MARK: main
def main() -> None:

    basic_positive_repo_check()


if __name__ == "__main__":
    main()

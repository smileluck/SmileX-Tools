import re
from playwright.sync_api import Page, expect
import os
from typing import Generator

import pytest
from playwright.sync_api import Playwright, APIRequestContext

def test_has_title(page: Page):
    page.goto("https://pixabay.com/zh/videos/search/?order=ec&pagi=1")

    # Expect a title "to contain" a substring.
    # expect(page).to_have_title(re.compile("Playwright"))
    api_request_context()


@pytest.fixture(scope="session")
def api_request_context(
    playwright: Playwright,
) -> Generator[APIRequestContext, None, None]:
    headers = {
        # We set this header per GitHub guidelines.
        "Accept": "application/vnd.github.v3+json",
        # Add authorization token to all requests.
        # Assuming personal access token available in the environment.
        "Authorization": f"token {GITHUB_API_TOKEN}",
    }
    request_context = playwright.request.new_context(
        base_url="https://api.github.com", extra_http_headers=headers
    )
    yield request_context
    request_context.dispose()


if __name__ == "__main__":
    test_has_title()
    time.sleep(100000)

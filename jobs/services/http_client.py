import logging
import random
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("scraper")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]


class LinkedInHTTPClient:
    """Robust HTTP client with User-Agent rotation, backoff strategies, and jitter delays."""

    def __init__(
        self, min_delay: float = 1.2, max_delay: float = 3.0, max_retries: int = 4
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.session = self._init_session()

    def _init_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def sleep_jitter(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)

    def get(self, url: str, params: dict = None) -> requests.Response:
        attempt = 0
        while attempt < self.max_retries:
            self.sleep_jitter()
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=self._get_headers(),
                    timeout=20,
                )
                if response.status_code == 429:
                    wait_time = (2**attempt) * 15 + random.uniform(2, 8)
                    logger.warning(
                        f"Rate limit encountered (429) on {url}. Backing off for {wait_time:.1f} seconds..."
                    )
                    time.sleep(wait_time)
                    attempt += 1
                    continue

                return response

            except requests.RequestException as exc:
                attempt += 1
                wait_time = (2**attempt) * 3
                logger.warning(
                    f"Network error ({exc}) requesting {url}. Retry {attempt}/{self.max_retries} in {wait_time}s."
                )
                time.sleep(wait_time)

        raise RuntimeError(
            f"Max connection attempts ({self.max_retries}) exceeded for URL: {url}"
        )

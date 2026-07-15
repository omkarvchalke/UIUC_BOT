from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

# Matches the User-Agent the ingestion client actually sends
# (app/ingestion/fetch.py) -- robots.txt rules are checked against whatever
# UA shows up in the access log, so this must stay in sync with that string.
_USER_AGENT = "IlliniGuideAI-Ingestion"


class RobotsChecker:
    """Fetches and caches one robots.txt per domain for the lifetime of a
    crawl run, so a 13-seed crawl makes at most 13 robots.txt requests
    total rather than one per page visited.
    """

    def __init__(self) -> None:
        self._parsers: dict[str, RobotFileParser] = {}

    async def is_allowed(self, url: str, client: httpx.AsyncClient) -> bool:
        origin = self._origin(url)
        if origin not in self._parsers:
            self._parsers[origin] = await self._fetch_parser(origin, client)
        return self._parsers[origin].can_fetch(_USER_AGENT, url)

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    async def _fetch_parser(origin: str, client: httpx.AsyncClient) -> RobotFileParser:
        parser = RobotFileParser()
        try:
            response = await client.get(f"{origin}/robots.txt")
        except httpx.HTTPError:
            # Unreachable robots.txt: fail open (allow) rather than abandon
            # the whole domain over a transient network blip -- matches
            # RobotFileParser's own behavior when it can't fetch a file.
            parser.parse([])
            return parser

        if response.status_code >= 400:
            # No robots.txt published (very common) means no restrictions.
            parser.parse([])
        else:
            parser.parse(response.text.splitlines())
        return parser

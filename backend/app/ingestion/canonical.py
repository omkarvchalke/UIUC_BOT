from urllib.parse import parse_qsl, urldefrag, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

# Tracking/session query params that don't change which page this is --
# stripped so a shared link with a campaign tag and the plain URL
# canonicalize to the same document instead of being ingested twice.
# Deliberately an allowlist of known-safe-to-strip params, not a denylist:
# most query strings on UIUC sites are genuinely meaningful (a course
# catalog search, a filtered event list), so the default is to leave a
# query string alone -- see normalize_url's docstring.
_TRACKING_QUERY_PARAMS = frozenset(
    {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}
)


def normalize_url(url: str) -> str:
    """Canonical form of a URL for dedup/storage purposes: lowercase
    scheme/host/path (illinois.edu sites are served case-insensitively --
    WordPress etc. -- so /Apply/Freshman and /apply/freshman are the same
    page), fragment and tracking params stripped, no trailing slash. Query
    params outside the tracking allowlist are left exactly as-is -- query
    values can be genuinely meaningful (e.g. a course catalog search), and
    only fragment/tracking-param removal has no real chance of collapsing
    two genuinely different pages into one.
    """
    without_fragment = urldefrag(url)[0]
    parsed = urlparse(without_fragment)
    kept_params = [(k, v) for k, v in parse_qsl(parsed.query) if k not in _TRACKING_QUERY_PARAMS]
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=parsed.path.lower(),
        query=urlencode(kept_params),
    )
    return normalized.geturl().rstrip("/")


def extract_canonical_link(soup: BeautifulSoup, *, base_url: str) -> str | None:
    """The page's own <link rel="canonical"> target, resolved to an
    absolute URL against base_url -- or None if the page doesn't declare
    one (most don't). When present, it's the site's own authoritative
    answer to "which URL is this page really at," which is more reliable
    than guessing from the fetched URL alone (e.g. a page reachable via
    several different query-string variants that all point at one
    canonical article).

    Checked manually against every <link> tag rather than
    soup.find("link", rel="canonical") -- rel is a multi-valued HTML
    attribute and different parsers represent it differently (a list vs.
    a single string), so this is correct regardless of parser behavior.
    """
    for tag in soup.find_all("link"):
        if not isinstance(tag, Tag):
            continue
        rel = tag.get("rel")
        rel_values = rel if isinstance(rel, list) else [rel] if rel else []
        if "canonical" in rel_values and (href := tag.get("href")):
            return urljoin(base_url, str(href))
    return None

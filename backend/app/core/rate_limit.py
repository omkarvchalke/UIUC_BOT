from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared across the app: slowapi tracks per-key (default: client IP) request
# counts in-process, so one Limiter instance must back every rate-limited
# route for the counts to be consistent.
limiter = Limiter(key_func=get_remote_address)

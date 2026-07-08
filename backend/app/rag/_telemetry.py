"""Chroma's default Posthog telemetry client raises on some installed
`posthog` package versions (`capture() takes 1 positional argument but 3
were given`) — a version-skew bug, not something wrong with our code. We
don't want Chroma usage telemetry anyway, so this is a trivial no-op
replacement to keep ingestion/query logs clean.
"""
from chromadb.telemetry.product import ProductTelemetryClient, ProductTelemetryEvent
from overrides import override


class NoopProductTelemetryClient(ProductTelemetryClient):
    @override
    def capture(self, event: ProductTelemetryEvent) -> None:
        pass

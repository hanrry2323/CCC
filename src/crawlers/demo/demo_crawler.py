from crawlers.base import BaseCrawler, CrawlerConfig
from copy import deepcopy
from typing import List, Dict, Any


DEMO_RECORDS = [
    {
        "product_name": "阿莫西林胶囊",
        "spec": "0.25g*24粒",
        "manufacturer": "白云山制药",
        "reference_price": 18.90,
    },
    {
        "product_name": "布洛芬缓释胶囊",
        "spec": "0.3g*20粒",
        "manufacturer": "芬必得制药",
        "reference_price": 25.50,
    },
    {
        "product_name": "维生素C片",
        "spec": "100mg*100片",
        "manufacturer": "民生药业",
        "reference_price": 12.80,
    },
]


def probe() -> bool:
    """Verify demo crawler can be loaded."""
    return True


class DemoCrawler(BaseCrawler):
    """Demo implementation of BaseCrawler for testing purposes."""

    def __init__(self):
        self.config = CrawlerConfig(name="demo", site_url="https://demo.local")

    def _load_credential(self) -> Dict[str, Any]:
        """Load demo credentials."""
        return {"username": "demo", "api_key": "demo-key"}

    def login(self, credential: Dict[str, Any]) -> bool:
        """Simulate login for demo."""
        print(f"[demo] login OK")
        return True

    def crawl(self) -> Any:
        """Crawl demo data and return records."""
        print(f"[demo] crawl OK ({len(DEMO_RECORDS)} records)")
        return deepcopy(DEMO_RECORDS)

    def extract(self, raw: Any) -> List[Dict[str, Any]]:
        """Extract demo records with additional metadata."""
        if not isinstance(raw, list):
            return []

        result = []
        for record in raw:
            if not isinstance(record, dict):
                continue

            cleaned = {
                "product_name": record.get("product_name"),
                "spec": record.get("spec"),
                "manufacturer": record.get("manufacturer"),
                "reference_price": record.get("reference_price"),
                "fetched_at": "2026-07-17T00:00:00Z",
            }

            # Remove internal fields if any
            cleaned.pop("_internal", None)
            result.append(cleaned)

        return result


if __name__ == "__main__":
    crawler = DemoCrawler()
    results = crawler.run()
    print(f"\nDemo crawler completed: {len(results)} records processed")

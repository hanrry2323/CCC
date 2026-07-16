#!/usr/bin/env python3
"""Demo crawler CLI entry point."""

import sys
import argparse
from pathlib import Path

# Add project src/ to path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from crawlers.demo.demo_crawler import DemoCrawler, probe, DEMO_RECORDS


def main():
    parser = argparse.ArgumentParser(description="Run a demo crawler")
    parser.add_argument(
        "--name",
        default="demo",
        help="Crawler name (default: demo)",
    )
    args = parser.parse_args()

    # Validate crawler name
    crawler_map = {"demo": DemoCrawler}

    if args.name not in crawler_map:
        print(f"Error: Crawler '{args.name}' not found")
        sys.exit(1)

    crawler = crawler_map[args.name]()

    # Run crawler
    print(f"Starting {args.name} crawler...")
    results = crawler.run()

    # Print result summary
    print(f"\nResults: {len(results)} rows")
    if results:
        print(f"Sample (first 3 fields):")
        for record in results[:1]:
            print(
                f"  {record.get('product_name')}, {record.get('spec')}, ..."
                f" {record.get('reference_price')}"
            )

    sys.exit(0)


if __name__ == "__main__":
    main()

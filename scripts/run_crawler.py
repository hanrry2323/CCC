#!/usr/bin/env python3
"""Demo and Sichuan crawler CLI entry point."""

import sys
import argparse
from pathlib import Path

# Add project src/ to path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from crawlers.demo.demo_crawler import DemoCrawler
from crawlers.sichuan.sichuan_crawler import SichuanCrawler


def main():
    parser = argparse.ArgumentParser(description="Run a demo crawler")
    parser.add_argument(
        "--name",
        default="demo",
        help="Crawler name (default: demo)",
    )
    args = parser.parse_args()

    # Validate crawler name
    crawler_map = {"demo": DemoCrawler, "sichuan": SichuanCrawler}

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
        first_record = results[0]
        if args.name == "demo":
            print(f"Sample (first 3 fields):")
            sample = f"{first_record.get('product_name')}, {first_record.get('spec')}, {first_record.get('reference_price')}"
            print(f"  {sample}")
        else:
            print(f"Sample:")
            print(
                f"  {first_record.get('product_name')}, {first_record.get('spec')}, ..."
            )
        print(f"  参考价格: {first_record.get('reference_price')}")

    sys.exit(0)


if __name__ == "__main__":
    main()

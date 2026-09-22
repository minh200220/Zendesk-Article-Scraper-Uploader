#!/usr/bin/env python3
"""
OptiBot Main Orchestrator
Runs scraper followed by uploader in sequence
"""

import sys
from datetime import datetime
from scraper import ZendeskScraper
from uploader import ArticleUploader


def main():
    """Run scraper and uploader in sequence"""
    print("=" * 60)
    print(f"OptiBot Started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    scraper_success = False
    uploader_success = False

    # Step 1: Run Scraper
    try:
        print("\n[1/2] Running Scraper...")
        print("-" * 60)
        scraper = ZendeskScraper()
        scraper.run()
        scraper_success = True
        print("-" * 60)
        print("✅ Scraper completed successfully\n")
    except Exception as e:
        print(f"\n❌ Scraper failed: {e}\n")
        scraper_success = False

    # Step 2: Run Uploader
    try:
        print("\n[2/2] Running Uploader...")
        print("-" * 60)
        uploader = ArticleUploader()
        uploader.run()
        uploader_success = True
        print("-" * 60)
        print("✅ Uploader completed successfully\n")
    except Exception as e:
        print(f"\n❌ Uploader failed: {e}\n")
        uploader_success = False

    # Final Summary
    print("=" * 60)
    print("OptiBot Summary:")
    print(f"  Scraper:  {'✅ Success' if scraper_success else '❌ Failed'}")
    print(f"  Uploader: {'✅ Success' if uploader_success else '❌ Failed'}")
    print(f"Completed - {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    # Exit with appropriate code (but don't crash the container)
    # Return 0 even on failure so cron continues running
    if scraper_success and uploader_success:
        return 0
    else:
        return 0  # Don't exit container, just log failure


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Zendesk Support Article Scraper
Scrapes articles from Zendesk support using the API
"""

import os
import json
import re
import requests
from pathlib import Path
from datetime import datetime
from markdownify import markdownify as md
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ZendeskScraper:
    def __init__(self):
        self.base_url = os.getenv('API_BASE_URL', 'https://your-domain.zendesk.com/api/v2/help_center/en-us/articles.json')
        self.state_file = os.getenv('STATE_FILE', 'scraper_state.json')
        self.output_dir = Path(os.getenv('OUTPUT_DIR', 'articles'))
        self.page_size = int(os.getenv('PAGE_SIZE', '30'))
        self.output_dir.mkdir(exist_ok=True)

        # Track statistics
        self.stats = {
            'added': 0,
            'updated': 0,
            'skipped': 0
        }

    def load_state(self):
        """Load the cursor state from state file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    return state.get('after_cursor')
            except (json.JSONDecodeError, ValueError):
                # State file is corrupted or empty, treat as first run
                print("⚠️  State file corrupted, treating as first run")
                return None
        return None

    def save_state(self, after_cursor, has_more):
        """Save the cursor state to state file"""
        # If we've reached the end, reset cursor for next full scan
        if not has_more:
            after_cursor = None

        with open(self.state_file, 'w') as f:
            json.dump({
                'after_cursor': after_cursor,
                'has_more': has_more,
                'last_run': datetime.now().isoformat()
            }, f, indent=2)

    def fetch_articles(self):
        """Fetch articles from API using cursor pagination"""
        after_cursor = self.load_state()

        # Build URL with cursor pagination
        if after_cursor:
            # Continue from saved cursor
            url = f"{self.base_url}?page%5Bafter%5D={after_cursor}&page%5Bsize%5D={self.page_size}&sort_by=updated_at&sort_order=asc"
            print(f"📥 Continuing from saved cursor (page {self.page_size} articles)")
        else:
            # First run or completed previous scan - start from beginning
            url = f"{self.base_url}?page%5Bsize%5D={self.page_size}&sort_by=updated_at&sort_order=asc"
            print(f"📥 Starting new scan - fetching {self.page_size} oldest articles")

        response = requests.get(url)
        response.raise_for_status()

        data = response.json()
        articles = data.get('articles', [])

        # Extract pagination metadata
        meta = data.get('meta', {})
        has_more = meta.get('has_more', False)
        next_cursor = meta.get('after_cursor')

        print(f"✓ Found {len(articles)} article(s) | has_more: {has_more}")

        return articles, next_cursor, has_more

    def html_to_markdown(self, html):
        """Convert HTML to Markdown using markdownify library"""
        if not html:
            return ""

        # Use markdownify with ATX-style headings (#) and dash bullets (-)
        return md(
            html,
            heading_style="ATX",
            bullets="-",
            strip=['script', 'style']
        ).strip()

    def slugify(self, text):
        """Convert text to URL-friendly slug"""
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text[:50]  # Limit length

    def find_existing_file(self, article_id):
        """Find existing file for this article ID (regardless of slug)"""
        pattern = f"{article_id}-*.md"
        matches = list(self.output_dir.glob(pattern))
        return matches[0] if matches else None

    def save_article(self, article):
        """Save article as markdown file"""
        article_id = article['id']
        title = article['title']
        slug = self.slugify(title)
        filename = f"{article_id}-{slug}.md"
        filepath = self.output_dir / filename

        # Check if this article already exists (possibly with different slug)
        existing_file = self.find_existing_file(article_id)
        is_update = existing_file is not None

        # If exists with different filename, clean up old version
        if existing_file and existing_file != filepath:
            print(f"  🗑️  Removing old version: {existing_file.name}")
            existing_file.unlink()

        # Convert HTML body to markdown
        content = self.html_to_markdown(article['body'])

        # Create frontmatter
        frontmatter = f"""---
title: {title}
id: {article_id}
url: {article['html_url']}
created_at: {article['created_at']}
updated_at: {article['updated_at']}
section_id: {article['section_id']}
---

"""

        # Write file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(frontmatter + content)

        # Update stats and log
        if is_update:
            self.stats['updated'] += 1
            print(f"  ✓ Updated: {filename}")
        else:
            self.stats['added'] += 1
            print(f"  ✓ Added: {filename}")

    def should_skip_article(self, article):
        """Determine if an article should be skipped"""
        # Skip drafts
        if article.get('draft', False):
            return True, "draft"

        # Skip if no body content
        if not article.get('body'):
            return True, "no content"

        # Skip outdated articles
        if article.get('outdated', False):
            return True, "outdated"

        return False, None

    def run(self):
        """Main execution flow"""
        print("🚀 Zendesk Article Scraper Starting...\n")

        try:
            # Fetch articles with cursor pagination
            articles, next_cursor, has_more = self.fetch_articles()

            if not articles:
                print("ℹ️  No articles to process")
                return

            # Save each article
            print(f"\n📝 Processing {len(articles)} article(s)...\n")

            for article in articles:
                try:
                    # Check if should skip
                    should_skip, reason = self.should_skip_article(article)
                    if should_skip:
                        self.stats['skipped'] += 1
                        print(f"  ⊘ Skipped: {article.get('title', 'Untitled')} ({reason})")
                        continue

                    # Save article
                    self.save_article(article)

                except Exception as e:
                    # Skip individual article on error, continue with others
                    self.stats['skipped'] += 1
                    print(f"  ❌ Error processing article {article.get('id', 'unknown')}: {e}")
                    continue

            # Update state with cursor
            self.save_state(next_cursor, has_more)

            if has_more:
                print(f"\n✅ Complete! Cursor saved - more pages available")
            else:
                print(f"\n✅ Complete! Reached end of articles - will start from beginning on next run")

            # Print summary
            print(f"\n📊 Summary: {self.stats['added']} added, {self.stats['updated']} updated, {self.stats['skipped']} skipped ({len(articles)} total)")

            print(f"\n📁 Articles saved to: {self.output_dir.absolute()}")

        except requests.RequestException as e:
            print(f"❌ API Error: {e}")
            raise
        except Exception as e:
            print(f"❌ Error: {e}")
            raise


if __name__ == "__main__":
    scraper = ZendeskScraper()
    scraper.run()

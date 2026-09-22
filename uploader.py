#!/usr/bin/env python3
"""
Article Uploader
Uploads markdown articles to OpenAI Vector Store with incremental tracking
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()


class ArticleUploader:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.vector_store_id = os.getenv('VECTOR_STORE_ID')
        if not self.vector_store_id:
            raise ValueError("VECTOR_STORE_ID not found in environment variables")

        self.client = OpenAI(api_key=self.api_key)
        self.articles_dir = Path(os.getenv('OUTPUT_DIR', 'articles'))
        self.state_file = os.getenv('UPLOADER_STATE_FILE', 'uploader_state.json')

        # Track statistics
        self.stats = {
            'uploaded': 0,
            'skipped': 0,
            'failed': 0
        }

    def load_state(self):
        """Load uploader state from state file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, ValueError):
                print("⚠️  State file corrupted, treating as first run")
                return {'uploaded_files': {}}
        return {'uploaded_files': {}}

    def save_state(self, state):
        """Save uploader state to state file"""
        state['last_run'] = datetime.now().isoformat()
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def parse_frontmatter(self, content):
        """Extract YAML frontmatter from markdown content"""
        # Match frontmatter between --- delimiters
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not match:
            return None

        frontmatter = {}
        frontmatter_text = match.group(1)

        # Parse key-value pairs
        for line in frontmatter_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                frontmatter[key.strip()] = value.strip()

        return frontmatter

    def validate_article(self, filepath):
        """Validate markdown file has required frontmatter and content"""
        try:
            content = filepath.read_text(encoding='utf-8')

            # Check file is not empty
            if not content or len(content.strip()) < 10:
                return False, "empty or too short"

            # Parse and validate frontmatter
            frontmatter = self.parse_frontmatter(content)
            if not frontmatter:
                return False, "missing frontmatter"

            # Check required fields
            required_fields = ['id', 'title', 'updated_at']
            for field in required_fields:
                if field not in frontmatter:
                    return False, f"missing {field} in frontmatter"

            # Check content exists beyond frontmatter
            content_only = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, count=1, flags=re.DOTALL)
            if len(content_only.strip()) < 10:
                return False, "no content beyond frontmatter"

            return True, frontmatter

        except Exception as e:
            return False, f"validation error: {e}"

    def should_upload(self, filepath, frontmatter, state):
        """Determine if file should be uploaded"""
        article_id = frontmatter.get('id')
        updated_at = frontmatter.get('updated_at')

        # Check if already uploaded
        if article_id in state['uploaded_files']:
            existing = state['uploaded_files'][article_id]

            # Skip if same version already uploaded
            if existing.get('updated_at') == updated_at:
                return False, "already uploaded (same version)"

            # File was updated - need to re-upload
            return True, "updated version detected"

        # New file - needs upload
        return True, "new file"

    def upload_file(self, filepath):
        """Upload a single file to OpenAI vector store"""
        try:
            with open(filepath, 'rb') as f:
                file_response = self.client.files.create(
                    file=f,
                    purpose='assistants'
                )

            # Add file to vector store
            vector_file = self.client.vector_stores.files.create(
                vector_store_id=self.vector_store_id,
                file_id=file_response.id
            )

            return True, {
                'file_id': file_response.id,
                'vector_store_file_id': vector_file.id
            }

        except Exception as e:
            return False, str(e)

    def process_articles(self):
        """Main processing loop for all articles"""
        # Load state
        state = self.load_state()

        # Get all markdown files
        md_files = sorted(self.articles_dir.glob('*.md'))

        if not md_files:
            print(f"ℹ️  No markdown files found in {self.articles_dir}")
            return

        print(f"\n📝 Processing {len(md_files)} article(s)...\n")

        for filepath in md_files:
            try:
                # Validate article
                is_valid, result = self.validate_article(filepath)
                if not is_valid:
                    self.stats['skipped'] += 1
                    print(f"  ⊘ Skipped: {filepath.name} ({result})")
                    continue

                frontmatter = result
                article_id = frontmatter.get('id')

                # Check if should upload
                should_upload, reason = self.should_upload(filepath, frontmatter, state)
                if not should_upload:
                    self.stats['skipped'] += 1
                    print(f"  ⊘ Skipped: {filepath.name} ({reason})")
                    continue

                # Upload file
                print(f"  ⬆️  Uploading: {filepath.name}...", end=' ')
                success, upload_result = self.upload_file(filepath)

                if success:
                    # Update state
                    state['uploaded_files'][article_id] = {
                        'filename': filepath.name,
                        'updated_at': frontmatter.get('updated_at'),
                        'file_id': upload_result['file_id'],
                        'vector_store_file_id': upload_result['vector_store_file_id'],
                        'uploaded_at': datetime.now().isoformat()
                    }

                    self.stats['uploaded'] += 1
                    print(f"✓")
                else:
                    self.stats['failed'] += 1
                    print(f"❌ ({upload_result})")

            except Exception as e:
                self.stats['failed'] += 1
                print(f"  ❌ Error processing {filepath.name}: {e}")
                continue

        # Save state
        self.save_state(state)

    def run(self):
        """Main execution flow"""
        print("🚀 Article Uploader Starting...\n")

        # Validate directory exists
        if not self.articles_dir.exists():
            print(f"❌ Articles directory not found: {self.articles_dir}")
            return

        try:
            # Process all articles
            self.process_articles()

            # Print summary
            total = self.stats['uploaded'] + self.stats['skipped'] + self.stats['failed']
            print(f"\n📊 Summary: {self.stats['uploaded']} uploaded, {self.stats['skipped']} skipped, {self.stats['failed']} failed ({total} total)")

            if self.stats['uploaded'] > 0:
                print(f"✅ Successfully uploaded {self.stats['uploaded']} article(s) to vector store")

            if self.stats['failed'] > 0:
                print(f"⚠️  {self.stats['failed']} article(s) failed to upload")

        except Exception as e:
            print(f"❌ Error: {e}")
            raise


if __name__ == "__main__":
    uploader = ArticleUploader()
    uploader.run()
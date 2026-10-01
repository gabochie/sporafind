"""
Seed the blog_posts table from frontend/data/posts.json.

The JSON file is the canonical editorial source for long-form content; the API
serves whatever is in Postgres. Without this step the blog renders empty even
though 60 articles exist on disk.

Idempotent: matches on slug, inserts what is missing, updates body/meta of
existing posts, never duplicates. Views counters are preserved.

Usage:
    python scripts/seed_blog.py              # seed or refresh
    python scripts/seed_blog.py --dry-run    # report only
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_FILE = ROOT / "frontend" / "data" / "posts.json"

sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal  # noqa: E402
from app.models.blog import BlogPost  # noqa: E402


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


async def seed(dry_run: bool = False) -> int:
    if not SEED_FILE.exists():
        print(f"ERROR: seed file not found at {SEED_FILE}")
        return 1

    posts = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    posts = [p for p in posts if p.get("status") == "published"]
    if not posts:
        print("ERROR: no published posts in seed file")
        return 1

    inserted = updated = 0
    async with SessionLocal() as db:
        from sqlalchemy import select

        existing = {
            row.slug: row
            for row in (await db.execute(select(BlogPost))).scalars().all()
        }

        for p in posts:
            slug = p["slug"]
            row = existing.get(slug)
            if row is None:
                row = BlogPost(id=p.get("id") or slug)
                db.add(row)
                inserted += 1
            else:
                updated += 1

            row.slug = slug
            row.title = p.get("title") or "Untitled"
            row.body = p.get("body") or ""
            row.excerpt = p.get("excerpt") or ""
            row.tags = p.get("tags") or []
            row.category = p.get("category") or "Uncategorised"
            row.status = p.get("status") or "published"
            row.published_at = parse_dt(p.get("publishedAt")) or datetime.now(timezone.utc)
            row.created_at = parse_dt(p.get("createdAt")) or row.published_at
            row.updated_at = parse_dt(p.get("updatedAt")) or row.published_at
            row.meta_title = p.get("metaTitle") or row.title
            row.meta_desc = p.get("metaDesc") or row.excerpt
            # Views are runtime data: seed file value only on first insert.
            if row.views is None:
                row.views = p.get("views") or 0

        if not dry_run:
            await db.commit()
        else:
            await db.rollback()

    verb = "would seed" if dry_run else "seeded"
    print(f"{verb} {inserted} new, {updated} updated ({len(posts)} published posts in seed file)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(seed(dry_run="--dry-run" in sys.argv)))
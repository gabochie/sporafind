import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.blog import BlogPost
from app.routers.auth_utils import verify_public_access

router = APIRouter(prefix="/blog", tags=["blog"])


def slugify(text: str) -> str:
    return re.sub(r'-+', '-', re.sub(r'[^\w\s-]', '', text.lower()).replace(' ', '-')).strip('-')


def iso_date(d):
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.isoformat()
    return str(d)


def post_to_dict(p: BlogPost) -> dict:
    return {
        "id": p.id,
        "slug": p.slug,
        "title": p.title,
        "body": p.body,
        "excerpt": p.excerpt,
        "tags": p.tags or [],
        "category": p.category,
        "status": p.status,
        "publishedAt": iso_date(p.published_at),
        "createdAt": iso_date(p.created_at),
        "updatedAt": iso_date(p.updated_at),
        "metaTitle": p.meta_title,
        "metaDesc": p.meta_desc,
        "views": p.views or 0,
    }


# --- PUBLIC ---

@router.get("/posts")
async def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(9, ge=1, le=50),
    tag: str | None = None,
    cat: str | None = None,
    _: bool = Depends(verify_public_access),
    db: AsyncSession = Depends(get_db),
):
    query = select(BlogPost).where(BlogPost.status == "published")
    count_query = select(func.count(BlogPost.id)).where(BlogPost.status == "published")

    if tag:
        query = query.where(BlogPost.tags.any(tag))
        count_query = count_query.where(BlogPost.tags.any(tag))
    if cat:
        query = query.where(BlogPost.category == cat)
        count_query = count_query.where(BlogPost.category == cat)

    total = await db.execute(count_query)
    total_count = total.scalar() or 0

    rows = await db.execute(
        query.order_by(BlogPost.published_at.desc().nulls_last())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = rows.scalars().all()

    # Get distinct categories and tags from published posts
    cat_rows = await db.execute(
        select(BlogPost.category, func.count(BlogPost.id))
        .where(BlogPost.status == "published", BlogPost.category.isnot(None))
        .group_by(BlogPost.category)
    )
    categories = [{"name": row[0], "count": row[1]} for row in cat_rows.all()]

    return {
        "items": [post_to_dict(p) for p in items],
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "categories": [c["name"] for c in categories],
        "tags": [],
    }


@router.get("/posts/{slug}")
async def get_post(
    slug: str,
    _: bool = Depends(verify_public_access),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BlogPost).where(BlogPost.slug == slug, BlogPost.status == "published")
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.views = (post.views or 0) + 1
    await db.commit()

    return post_to_dict(post)


# --- ANALYTICS (no auth) ---

class PageViewRequest(BaseModel):
    slug: str


@router.post("/analytics/pageview")
async def track_pageview(
    body: PageViewRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(BlogPost).where(BlogPost.slug == body.slug))
    post = result.scalar_one_or_none()
    if post:
        post.views = (post.views or 0) + 1
        await db.commit()
    return {"ok": True}


@router.get("/analytics/posts")
async def post_analytics(
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(BlogPost).where(BlogPost.status == "published")
        .order_by(BlogPost.published_at.desc().nulls_last())
    )
    posts = rows.scalars().all()
    return {
        "totalPosts": sum(1 for p in posts),
        "posts": [
            {
                "id": p.id,
                "title": p.title,
                "slug": p.slug,
                "views": p.views or 0,
                "publishedAt": iso_date(p.published_at),
                "category": p.category,
                "tags": p.tags or [],
            }
            for p in posts
        ],
    }


# --- ADMIN ---

async def verify_admin(x_admin_key: str = Header(...)):
    from app.config import settings
    if x_admin_key != settings.admin_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    return True


class CreatePostRequest(BaseModel):
    title: str = "Untitled"
    body: str = ""
    excerpt: str = ""
    tags: list[str] = []
    category: str = "Uncategorised"
    status: str = "draft"
    publishedAt: str | None = None
    metaTitle: str | None = None
    metaDesc: str | None = None


class UpdatePostRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    excerpt: str | None = None
    tags: list[str] | None = None
    category: str | None = None
    status: str | None = None
    publishedAt: str | None = None
    metaTitle: str | None = None
    metaDesc: str | None = None


@router.get("/admin/posts")
async def list_all_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
    _: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(BlogPost)
    count_query = select(func.count(BlogPost.id))
    if status:
        query = query.where(BlogPost.status == status)
        count_query = count_query.where(BlogPost.status == status)

    total = await db.execute(count_query)
    total_count = total.scalar() or 0

    rows = await db.execute(
        query.order_by(BlogPost.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = rows.scalars().all()

    return {
        "items": [post_to_dict(p) for p in items],
        "total": total_count,
        "page": page,
        "page_size": page_size,
    }


@router.post("/admin/posts")
async def create_post(
    body: CreatePostRequest,
    _: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    from uuid import uuid4
    post_id = str(uuid4())
    slug = slugify(body.title) + "-" + post_id[:4]

    published_dt = None
    if body.publishedAt:
        try:
            published_dt = datetime.fromisoformat(body.publishedAt.replace("Z", "+00:00"))
        except ValueError:
            pass
    elif body.status == "published":
        published_dt = datetime.now(timezone.utc)

    post = BlogPost(
        id=post_id,
        slug=slug,
        title=body.title,
        body=body.body,
        excerpt=body.excerpt,
        tags=body.tags,
        category=body.category,
        status=body.status,
        published_at=published_dt,
        meta_title=body.metaTitle or body.title,
        meta_desc=body.metaDesc or body.excerpt,
        views=0,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post_to_dict(post)


@router.put("/admin/posts/{post_id}")
async def update_post(
    post_id: str,
    body: UpdatePostRequest,
    _: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(BlogPost).where(BlogPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if body.title is not None:
        post.title = body.title
        post.slug = slugify(body.title) + "-" + post.id[:4]
    if body.body is not None:
        post.body = body.body
    if body.excerpt is not None:
        post.excerpt = body.excerpt
    if body.tags is not None:
        post.tags = body.tags
    if body.category is not None:
        post.category = body.category
    if body.status is not None:
        post.status = body.status
        if body.status == "published" and not post.published_at:
            post.published_at = datetime.now(timezone.utc)
    if body.metaTitle is not None:
        post.meta_title = body.metaTitle
    if body.metaDesc is not None:
        post.meta_desc = body.metaDesc
    if body.publishedAt is not None:
        try:
            post.published_at = datetime.fromisoformat(body.publishedAt.replace("Z", "+00:00"))
        except ValueError:
            pass

    post.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(post)
    return post_to_dict(post)


@router.delete("/admin/posts/{post_id}")
async def delete_post(
    post_id: str,
    _: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(BlogPost).where(BlogPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.delete(post)
    await db.commit()
    return {"ok": True}

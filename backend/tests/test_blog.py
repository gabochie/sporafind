from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.blog import BlogPost


SAMPLE_POST = {
    "id": str(uuid4()),
    "slug": "test-post",
    "title": "Test Post",
    "body": "This is a test post body",
    "excerpt": "Test excerpt",
    "tags": ["test", "ci"],
    "category": "Tech",
    "status": "published",
}


@pytest.mark.asyncio
async def test_list_posts_empty(client):
    resp = await client.get("/blog/posts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1


@pytest.mark.asyncio
async def test_list_published_posts(client, db_session):
    post = BlogPost(**SAMPLE_POST)
    db_session.add(post)
    await db_session.commit()

    resp = await client.get("/blog/posts")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "test-post"
    assert body["items"][0]["category"] == "Tech"


@pytest.mark.asyncio
async def test_draft_not_in_public(client, db_session):
    draft = BlogPost(
        id=str(uuid4()), slug="draft-post", title="Draft",
        body="Draft body", status="draft",
    )
    db_session.add(draft)
    published = BlogPost(
        id=str(uuid4()), slug="published-post", title="Published",
        body="Published body", status="published",
    )
    db_session.add(published)
    await db_session.commit()

    resp = await client.get("/blog/posts")
    assert resp.status_code == 200
    body = resp.json()
    slugs = [p["slug"] for p in body["items"]]
    assert "published-post" in slugs
    assert "draft-post" not in slugs


@pytest.mark.asyncio
async def test_get_post_by_slug(client, db_session):
    post = BlogPost(**SAMPLE_POST)
    db_session.add(post)
    await db_session.commit()

    resp = await client.get("/blog/posts/test-post")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Test Post"
    assert body["body"] == "This is a test post body"
    assert body["views"] > 0


@pytest.mark.asyncio
async def test_get_post_not_found(client):
    resp = await client.get("/blog/posts/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_filter_by_tag(client, db_session):
    post1 = BlogPost(**{**SAMPLE_POST, "id": str(uuid4()), "slug": "post-1", "tags": ["python"]})
    post2 = BlogPost(**{**SAMPLE_POST, "id": str(uuid4()), "slug": "post-2", "tags": ["javascript"]})
    db_session.add_all([post1, post2])
    await db_session.commit()

    resp = await client.get("/blog/posts?tag=python")
    assert resp.status_code == 200
    body = resp.json()
    slugs = [p["slug"] for p in body["items"]]
    assert "post-1" in slugs
    assert "post-2" not in slugs


@pytest.mark.asyncio
async def test_filter_by_category(client, db_session):
    post1 = BlogPost(**{**SAMPLE_POST, "id": str(uuid4()), "slug": "post-a", "category": "Tech"})
    post2 = BlogPost(**{
        **SAMPLE_POST, "id": str(uuid4()), "slug": "post-b",
        "title": "Marketing Post", "category": "Marketing",
    })
    db_session.add_all([post1, post2])
    await db_session.commit()

    resp = await client.get("/blog/posts?cat=Marketing")
    assert resp.status_code == 200
    body = resp.json()
    slugs = [p["slug"] for p in body["items"]]
    assert "post-b" in slugs
    assert "post-a" not in slugs


@pytest.mark.asyncio
async def test_admin_create_post(client):
    resp = await client.post(
        "/blog/admin/posts",
        headers={"X-Admin-Key": "test-admin-key"},
        json={
            "title": "Admin Created",
            "body": "Created via admin",
            "status": "published",
            "tags": ["admin"],
            "category": "News",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Admin Created"
    assert body["status"] == "published"
    assert body["slug"].startswith("admin-created")


@pytest.mark.asyncio
async def test_admin_create_post_unauthorized(client):
    resp = await client.post(
        "/blog/admin/posts",
        json={"title": "Hacked"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_list_posts(client, db_session):
    post = BlogPost(**{**SAMPLE_POST, "id": str(uuid4()), "slug": "admin-list-test"})
    db_session.add(post)
    await db_session.commit()

    resp = await client.get(
        "/blog/admin/posts",
        headers={"X-Admin-Key": "test-admin-key"},
    )
    assert resp.status_code == 200
    body = resp.json()
    slugs = [p["slug"] for p in body["items"]]
    assert "admin-list-test" in slugs


@pytest.mark.asyncio
async def test_admin_update_post(client, db_session):
    post = BlogPost(**{**SAMPLE_POST, "id": str(uuid4()), "slug": "to-update"})
    db_session.add(post)
    await db_session.commit()

    resp = await client.put(
        f"/blog/admin/posts/{post.id}",
        headers={"X-Admin-Key": "test-admin-key"},
        json={"title": "Updated Title", "status": "draft"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Updated Title"
    assert body["status"] == "draft"


@pytest.mark.asyncio
async def test_admin_delete_post(client, db_session):
    post = BlogPost(**{**SAMPLE_POST, "id": str(uuid4()), "slug": "to-delete"})
    db_session.add(post)
    await db_session.commit()

    resp = await client.delete(
        f"/blog/admin/posts/{post.id}",
        headers={"X-Admin-Key": "test-admin-key"},
    )
    assert resp.status_code == 200

    result = await db_session.execute(select(BlogPost).where(BlogPost.id == post.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_analytics_pageview(client, db_session):
    post = BlogPost(**{**SAMPLE_POST, "id": str(uuid4()), "slug": "analytics-test", "views": 5})
    db_session.add(post)
    await db_session.commit()

    resp = await client.post(
        "/blog/analytics/pageview",
        json={"slug": "analytics-test"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    result = await db_session.execute(select(BlogPost).where(BlogPost.slug == "analytics-test"))
    updated = result.scalar_one()
    assert updated.views == 6


@pytest.mark.asyncio
async def test_analytics_posts(client, db_session):
    post = BlogPost(**{**SAMPLE_POST, "id": str(uuid4()), "slug": "analytics-list-test"})
    db_session.add(post)
    await db_session.commit()

    resp = await client.get("/blog/analytics/posts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalPosts"] == 1
    assert body["posts"][0]["slug"] == "analytics-list-test"

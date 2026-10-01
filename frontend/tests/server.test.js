import { describe, it, expect, beforeAll, afterAll, vi, beforeEach } from 'vitest';
import request from 'supertest';
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TEST_DIR = path.resolve(__dirname, '..');
const require = createRequire(import.meta.url);

let app;

beforeAll(() => {
  process.env.API_BASE = 'http://mock-api';
  process.env.ADMIN_KEY = 'test-admin-key';
  process.env.PUBLIC_API_KEY = 'test-public-key';

  vi.stubGlobal('fetch', vi.fn());

  app = require(path.join(TEST_DIR, 'server.js'));
});

afterAll(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('GET /', () => {
  it('serves index.html', async () => {
    const res = await request(app).get('/');
    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toMatch(/html/);
    expect(res.text).toContain('Sporafind');
  });

  it('injects session.js script', async () => {
    const res = await request(app).get('/');
    expect(res.text).toContain('session.js');
  });
});

describe('Static HTML redirects', () => {
  const pages = ['/admin', '/pricing', '/about', '/features', '/privacy', '/terms'];

  for (const page of pages) {
    it(`redirects ${page} -> ${page}.html`, async () => {
      const res = await request(app).get(page);
      expect(res.status).toBe(301);
      expect(res.headers.location).toBe(page + '.html');
    });
  }
});

describe('Static file serving', () => {
  it('serves /js/session.js', async () => {
    const res = await request(app).get('/js/session.js');
    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toMatch(/javascript/);
  });
});

describe('Blog pages', () => {
  it('renders /blog with EJS', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [],
        total: 0,
        page: 1,
        totalPages: 0,
        categories: [],
        tags: [],
      }),
    });

    const res = await request(app).get('/blog');
    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toMatch(/html/);
    expect(res.text).toContain('Blog');
  });

  it('falls back to local posts.json when API is down', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 502,
    });

    const res = await request(app).get('/blog');
    expect(res.status).toBe(200);
  });

  it('falls back to local posts when the API is healthy but empty', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, categories: [], tags: [] }),
    });

    const res = await request(app).get('/blog');
    expect(res.status).toBe(200);
    // 60 posts exist on disk; an empty DB must never blank the archive.
    expect(res.text).toContain('post-card');
    expect(res.text).not.toContain('Nothing matched that search');
  });

  it('forwards search queries to the API', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0, page: 1, categories: [], tags: [] }),
    });

    await request(app).get('/blog?q=obroni');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('q=obroni'),
      expect.anything()
    );
  });

  it('requests 9 posts per page and decorates cards', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [{
          id: '1',
          slug: 'obroni-pricing-ghana',
          title: 'Obroni pricing in Ghana',
          body: '<p>' + 'word '.repeat(500) + '</p>',
          excerpt: 'How to negotiate.',
          tags: ['obroni'],
          category: 'Relocation Guides',
          publishedAt: '2026-01-05T00:00:00Z',
          views: 1500,
        }],
        total: 1,
        page: 1,
        categories: ['Relocation Guides'],
        category_counts: { 'Relocation Guides': 1 },
        tags: [{ name: 'obroni', count: 1 }],
        tag_total: 1,
      }),
    });

    await request(app).get('/blog');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('page_size=9'),
      expect.anything()
    );

    const res = await request(app).get('/blog');
    expect(res.text).toContain('post-card');
    expect(res.text).toMatch(/class="cover cover-\d"/);
    expect(res.text).toMatch(/\d+ min read/);
    expect(res.text).toMatch(/1\.5K/); // compact view count
  });
});

describe('API proxy routes', () => {
  beforeEach(() => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ plans: [] }),
    });
  });

  it('proxies GET /api/pricing', async () => {
    const res = await request(app).get('/api/pricing');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ plans: [] });
  });

  it('proxies GET /api/admin/activity', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [] }),
    });

    const res = await request(app).get('/api/admin/activity');
    expect(res.status).toBe(200);
  });
});

describe('Sitemap and RSS', () => {
  it('generates /sitemap.xml', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ posts: [] }),
    });

    const res = await request(app).get('/sitemap.xml');
    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toMatch(/xml/);
    expect(res.text).toContain('sporafind.com');
  });

  it('generates /rss.xml', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ posts: [] }),
    });

    const res = await request(app).get('/rss.xml');
    expect(res.status).toBe(200);
    expect(res.headers['content-type']).toMatch(/rss/);
    expect(res.text).toContain('Sporafind Blog');
  });
});

describe('404 handling', () => {
  it('returns 404 for unknown routes', async () => {
    const res = await request(app).get('/nonexistent-route-xyz');
    expect(res.status).toBe(404);
  });
});

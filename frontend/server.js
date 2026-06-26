const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3001;
const DIR = __dirname;
const DATA_DIR = path.join(DIR, 'data');
const POSTS_FILE = path.join(DATA_DIR, 'posts.json');
const API_BASE = process.env.API_BASE || 'http://localhost:8000';

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, {recursive: true});
if (!fs.existsSync(POSTS_FILE)) fs.writeFileSync(POSTS_FILE, JSON.stringify([], null, 2));

function readPosts() {
  try { return JSON.parse(fs.readFileSync(POSTS_FILE, 'utf8')); } catch { return []; }
}
function isoDate(d) { return d ? new Date(d).toISOString() : ''; }

async function fetchFromAPI(pathname, opts = {}) {
  try {
    const url = `${API_BASE}${pathname}`;
    const res = await fetch(url, {
      ...opts,
      headers: { 'Content-Type': 'application/json', ...opts.headers },
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

app.set('view engine', 'ejs');
app.set('views', path.join(DIR, 'views'));

app.use(express.json());

app.get(['/admin', '/workspace', '/features', '/segments', '/pricing', '/api-docs', '/changelog', '/about', '/careers', '/press', '/contact', '/privacy', '/terms', '/gdpr', '/sources', '/roadmap', '/fundraising'], (req, res) => {
  res.redirect(301, req.path + '.html');
});

app.use((req, res, next) => {
  if (req.path.startsWith('/api/')) return next();
  const ext = path.extname(req.path);
  if (ext === '.html' || req.path === '/') {
    const filePath = path.join(DIR, req.path === '/' ? 'index.html' : req.path.replace(/^\//, ''));
    if (fs.existsSync(filePath)) {
      let html = fs.readFileSync(filePath, 'utf8');
      html = html.replace('</head>', '<script src="/js/session.js"></script></head>');
      res.setHeader('Content-Type', 'text/html');
      return res.send(html);
    }
  }
  next();
});

app.get('/blog', async (req, res) => {
  try {
    const data = await fetchFromAPI(`/blog/posts?page=${req.query.page || 1}&page_size=6${req.query.tag ? '&tag=' + encodeURIComponent(req.query.tag) : ''}${req.query.cat ? '&cat=' + encodeURIComponent(req.query.cat) : ''}`);
    if (data) {
      return res.render('blog', {
        posts: data.items, page: data.page, totalPages: Math.ceil(data.total / 6),
        total: data.total, tag: req.query.tag || null, cat: req.query.cat || null,
        categories: data.categories, tags: data.tags, isoDate,
      });
    }
  } catch {}
  const posts = readPosts();
  const published = posts.filter(p => p.status === 'published').sort((a,b) => new Date(b.publishedAt) - new Date(a.publishedAt));
  const page = parseInt(req.query.page) || 1;
  const tag = req.query.tag || null;
  const cat = req.query.cat || null;
  const limit = 6;
  let filtered = published;
  if (tag) filtered = filtered.filter(p => p.tags?.includes(tag));
  if (cat) filtered = filtered.filter(p => p.category === cat);
  const total = filtered.length;
  const totalPages = Math.ceil(total / limit);
  const categories = [...new Set(published.map(p => p.category).filter(Boolean))];
  const tags = [...new Set(published.flatMap(p => p.tags || []))];
  res.render('blog', { posts: filtered.slice((page-1)*limit, page*limit), page, totalPages, total, tag, cat, categories, tags, isoDate });
});

app.get('/blog/:slug', async (req, res) => {
  try {
    const post = await fetchFromAPI(`/blog/posts/${req.params.slug}`);
    if (post) {
      const data = await fetchFromAPI(`/blog/posts?page=1&page_size=100&cat=${encodeURIComponent(post.category)}`);
      const related = data ? data.items.filter(p => p.id !== post.id).slice(0, 3) : [];
      const allTags = data ? data.tags : [];
      return res.render('blog-post', { post, related, allTags, isoDate });
    }
  } catch {}
  const posts = readPosts();
  const post = posts.find(p => p.slug === req.params.slug && p.status === 'published');
  if (!post) return res.status(404).send('Post not found');
  const related = posts.filter(p => p.id !== post.id && p.status === 'published' && p.category === post.category).slice(0, 3);
  const allTags = [...new Set(posts.filter(p => p.status === 'published').flatMap(p => p.tags || []))];
  res.render('blog-post', { post, related, allTags, isoDate });
});

const ADMIN_KEY = process.env.ADMIN_KEY || '';
const PUBLIC_API_KEY = process.env.PUBLIC_API_KEY || '';

// Blog admin proxy — forwards to FastAPI with X-Admin-Key
async function proxyAdmin(req, res, pathSuffix) {
  try {
    const url = `${API_BASE}/blog/admin/${pathSuffix}`;
    const opts = {
      method: req.method,
      headers: { 'Content-Type': 'application/json', 'X-Admin-Key': ADMIN_KEY },
    };
    if (!['GET','DELETE'].includes(req.method)) opts.body = JSON.stringify(req.body);
    const r = await fetch(url, opts);
    return res.status(r.status).json(await r.json());
  } catch {
    res.status(502).json({ error: 'Backend unavailable' });
  }
}

app.get('/api/blog-admin/posts', (req, res) => proxyAdmin(req, res, `posts?page=${req.query.page||1}&page_size=${req.query.page_size||50}${req.query.status ? '&status='+req.query.status : ''}`));
app.post('/api/blog-admin/posts', (req, res) => proxyAdmin(req, res, 'posts'));
app.put('/api/blog-admin/posts/:id', (req, res) => proxyAdmin(req, res, `posts/${req.params.id}`));
app.delete('/api/blog-admin/posts/:id', (req, res) => proxyAdmin(req, res, `posts/${req.params.id}`));

app.get('/api/admin/activity', async (req, res) => {
  try {
    const url = `${API_BASE}/admin/activity?limit=${req.query.limit || 50}`;
    const r = await fetch(url, { headers: { 'X-Admin-Key': ADMIN_KEY } });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ items: [] }); }
});

app.get('/api/pricing', async (req, res) => {
  try {
    const headers = {};
    if (PUBLIC_API_KEY) headers['X-Api-Key'] = PUBLIC_API_KEY;
    const r = await fetch(`${API_BASE}/pricing`, { headers });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ plans: [] }); }
});

app.post('/api/analytics/pageview', async (req, res) => {
  try {
    await fetchFromAPI('/blog/analytics/pageview', {
      method: 'POST', body: JSON.stringify({ slug: req.body.slug }),
    });
    return res.json({ ok: true });
  } catch {}
  const posts = readPosts();
  const post = posts.find(p => p.slug === req.body.slug);
  if (post) { post.views = (post.views || 0) + 1; fs.writeFileSync(POSTS_FILE, JSON.stringify(posts, null, 2)); }
  res.json({ ok: true });
});

app.get('/api/analytics/posts', async (req, res) => {
  try {
    const data = await fetchFromAPI('/blog/analytics/posts');
    if (data) return res.json(data);
  } catch {}
  const posts = readPosts();
  res.json({
    totalPosts: posts.filter(p => p.status === 'published').length,
    posts: posts.filter(p => p.status === 'published').map(p => ({
      id: p.id, title: p.title, slug: p.slug, views: p.views || 0,
      publishedAt: p.publishedAt, category: p.category, tags: p.tags,
    })),
  });
});

app.get('/investors', (req, res) => res.render('investors'));
app.get('/investors/metrics', (req, res) => res.render('investors-metrics'));
app.get('/investors/financials', (req, res) => res.render('investors-financials'));
app.get('/investors/deck', (req, res) => res.render('investors-deck'));
app.get('/investors/data-room', (req, res) => res.render('investors-data-room'));

app.get('/sitemap.xml', async (req, res) => {
  let blogPosts = [];
  try {
    const data = await fetchFromAPI('/blog/analytics/posts');
    if (data) blogPosts = data.posts;
  } catch {}
  if (!blogPosts.length) blogPosts = readPosts().filter(p => p.status === 'published');
  const site = 'https://sporafind.com';
  let xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n';
  const staticPages = ['/', '/features', '/segments', '/pricing', '/api-docs', '/changelog', '/about', '/blog', '/careers', '/press', '/contact', '/privacy', '/terms', '/gdpr', '/sources', '/roadmap', '/fundraising', '/investors', '/investors/metrics', '/investors/financials', '/investors/deck', '/investors/data-room'];
  staticPages.forEach(p => { xml += `  <url><loc>${site}${p}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>\n`; });
  blogPosts.forEach(p => { xml += `  <url><loc>${site}/blog/${p.slug}</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>\n`; });
  xml += '</urlset>';
  res.header('Content-Type', 'application/xml').send(xml);
});

app.get('/rss.xml', async (req, res) => {
  let blogPosts = [];
  try {
    const data = await fetchFromAPI('/blog/analytics/posts');
    if (data) blogPosts = data.posts;
  } catch {}
  if (!blogPosts.length) blogPosts = readPosts().filter(p => p.status === 'published').sort((a,b) => new Date(b.publishedAt) - new Date(a.publishedAt));
  const site = 'https://sporafind.com';
  let rss = '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>\n';
  rss += `<title>Sporafind Blog</title>\n<link>${site}/blog</link>\n<description>Ghanaian diaspora intelligence, insights, and strategies</description>\n<language>en</language>\n`;
  blogPosts.forEach(p => {
    rss += `<item><title><![CDATA[${p.title}]]></title><link>${site}/blog/${p.slug}</link><guid>${site}/blog/${p.slug}</guid>`;
    const pd = p.publishedAt || p.published_at;
    rss += `<pubDate>${new Date(pd).toUTCString()}</pubDate><description><![CDATA[${p.excerpt || ''}]]></description>`;
    rss += `<category>${p.category || 'Uncategorised'}</category>`;
    (p.tags || []).forEach(t => { rss += `<tag>${t}</tag>`; });
    rss += `</item>\n`;
  });
  rss += '</channel></rss>';
  res.header('Content-Type', 'application/rss+xml').send(rss);
});

app.use(express.static(DIR));

app.use((req, res) => {
  res.status(404).type('html').send('<h1>404 — Page not found</h1><p>Go back to <a href="/">sporafind.com</a></p>');
});

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(' Sporafind running at http://localhost:' + PORT);
    console.log('  Workspace  user@sporafind.com / demo123');
    console.log('  Admin      admin@sporafind.com / demo123');
    console.log('  Blog       http://localhost:' + PORT + '/blog');
  });
}

module.exports = app;

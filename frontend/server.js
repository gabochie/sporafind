const express = require('express');
const path = require('path');
const fs = require('fs');
const cookieParser = require('cookie-parser');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');

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

// Security middleware
app.use(helmet({
  contentSecurityPolicy: false,
  crossOriginEmbedderPolicy: false,
}));

const loginLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: { detail: 'Too many requests, try again later' },
});

app.set('view engine', 'ejs');
app.set('views', path.join(DIR, 'views'));

app.use(express.json());
app.use(cookieParser());

app.get(['/admin', '/features', '/segments', '/pricing', '/api-docs', '/changelog', '/about', '/careers', '/press', '/contact', '/privacy', '/terms', '/gdpr', '/sources', '/roadmap', '/fundraising'], (req, res) => {
  res.redirect(301, req.path + '.html');
});

app.use((req, res, next) => {
  if (req.path.startsWith('/api/')) return next();
  const ext = path.extname(req.path);
  if (ext === '.html' || req.path === '/') {
    const filePath = path.join(DIR, req.path === '/' ? 'index.html' : req.path.replace(/^\//, ''));
    if (fs.existsSync(filePath)) {
      let html = fs.readFileSync(filePath, 'utf8');
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
  } catch (e) { console.error('Blog fetch error:', e); }
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
  } catch (e) { console.error('Blog post fetch error:', e); }
  const posts = readPosts();
  const post = posts.find(p => p.slug === req.params.slug && p.status === 'published');
  if (!post) return res.status(404).send('Post not found');
  const related = posts.filter(p => p.id !== post.id && p.status === 'published' && p.category === post.category).slice(0, 3);
  const allTags = [...new Set(posts.filter(p => p.status === 'published').flatMap(p => p.tags || []))];
  res.render('blog-post', { post, related, allTags, isoDate });
});

const ADMIN_KEY = process.env.ADMIN_KEY || '';
const PUBLIC_API_KEY = process.env.PUBLIC_API_KEY || '';

// Change password — uses admin_token cookie as Bearer token
app.post('/api/auth/change-password', loginLimiter, async (req, res) => {
  try {
    const token = req.cookies?.admin_token || req.headers.authorization?.replace('Bearer ', '') || '';
    const r = await fetch(`${API_BASE}/auth/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify(req.body),
    });
    return res.status(r.status).json(await r.json());
  } catch {
    res.status(502).json({ detail: 'Backend unavailable' });
  }
});

// Refresh token — accepts Bearer token, returns new token
app.post('/api/auth/refresh', async (req, res) => {
  try {
    const token = req.headers.authorization?.replace('Bearer ', '') || req.cookies?.admin_token || '';
    if (!token) return res.status(401).json({ detail: 'No token provided' });
    const r = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
    });
    const data = await r.json();
    return res.status(r.status).json(data);
  } catch {
    res.status(502).json({ detail: 'Backend unavailable' });
  }
});

// Admin login — proxies to FastAPI /auth/login, sets httpOnly cookie
app.post('/api/admin/login', loginLimiter, async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: req.body.email, password: req.body.password }),
    });
    const data = await r.json();
    if (!r.ok) return res.status(r.status).json(data);
    res.cookie('admin_token', data.token, {
      httpOnly: true, secure: true, sameSite: 'strict', path: '/',
      maxAge: 24 * 60 * 60 * 1000,
    });
    return res.json(data);
  } catch {
    res.status(502).json({ detail: 'Backend unavailable' });
  }
});

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

app.get('/api/admin/smoke-test-stats', async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/admin/smoke-test-stats`, {
      headers: { 'X-Admin-Key': ADMIN_KEY },
    });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ uptime_pct: 0, total_checks: 0, passed: 0, failed: 0, endpoints: {}, latest: [] }); }
});

// Admin import endpoints — proxy with server-side admin key
app.post('/api/admin/import/start-sync', async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/admin/import/start-sync`, {
      method: 'POST', headers: { 'X-Admin-Key': ADMIN_KEY },
    });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ error: 'Backend unavailable' }); }
});

app.post('/api/admin/import/diaspora-sync', async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/admin/import/diaspora-sync`, {
      method: 'POST', headers: { 'X-Admin-Key': ADMIN_KEY },
    });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ error: 'Backend unavailable' }); }
});

app.get('/api/admin/import/status', async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/admin/import/status`, {
      headers: { 'X-Admin-Key': ADMIN_KEY },
    });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ runs: [] }); }
});

app.get('/api/stats', async (req, res) => {
  try {
    const headers = {};
    if (PUBLIC_API_KEY) headers['X-Api-Key'] = PUBLIC_API_KEY;
    const r = await fetch(`${API_BASE}/stats`, { headers });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ total_profiles: 0 }); }
});

app.get('/api/pricing', async (req, res) => {
  try {
    const headers = {};
    if (PUBLIC_API_KEY) headers['X-Api-Key'] = PUBLIC_API_KEY;
    const r = await fetch(`${API_BASE}/pricing`, { headers });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ plans: [] }); }
});

async function proxyInvestorAPI(req, res) {
  try {
    const auth = req.headers.authorization || '';
    const pathSuffix = req.path.replace('/api/investor', '');
    const qs = req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : '';
    const url = `${API_BASE}/investor${pathSuffix}${qs}`;
    const headers = { 'Content-Type': 'application/json' };
    if (auth) headers['Authorization'] = auth;
    const opts = { method: req.method, headers };
    if (!['GET','DELETE'].includes(req.method)) opts.body = JSON.stringify(req.body);
    const r = await fetch(url, opts);
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ error: 'Backend unavailable' }); }
}

app.all('/api/investor/me', (req, res) => proxyInvestorAPI(req, res));
app.all('/api/investor/profile', (req, res) => proxyInvestorAPI(req, res));
app.all('/api/investor/commit', (req, res) => proxyInvestorAPI(req, res));
app.all('/api/investor/message', (req, res) => proxyInvestorAPI(req, res));
app.all('/api/investor/messages', (req, res) => proxyInvestorAPI(req, res));

async function proxyWorkspaceAPI(req, res) {
  try {
    const auth = req.headers.authorization || '';
    const pathSuffix = req.path.replace('/api/workspace', '');
    const qs = req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : '';
    const url = `${API_BASE}/workspace${pathSuffix}${qs}`;
    const headers = { 'Content-Type': 'application/json' };
    if (auth) headers['Authorization'] = auth;
    const opts = { method: req.method, headers };
    if (!['GET','DELETE'].includes(req.method)) opts.body = JSON.stringify(req.body);
    const r = await fetch(url, opts);
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ error: 'Backend unavailable' }); }
}

app.all('/api/workspace/me', (req, res) => proxyWorkspaceAPI(req, res));
app.all('/api/workspace/search', (req, res) => proxyWorkspaceAPI(req, res));
app.all('/api/workspace/lists', (req, res) => proxyWorkspaceAPI(req, res));
app.all('/api/workspace/lists/:id', (req, res) => proxyWorkspaceAPI(req, res));
app.all('/api/workspace/exports', (req, res) => proxyWorkspaceAPI(req, res));
app.all('/api/workspace/activity', (req, res) => proxyWorkspaceAPI(req, res));

// Billing proxy — forwards Bearer token same as workspace API
async function proxyBilling(req, res) {
  try {
    const auth = req.headers.authorization || '';
    const pathSuffix = req.path.replace('/api/billing', '');
    const url = `${API_BASE}/billing${pathSuffix}`;
    const headers = { 'Content-Type': 'application/json' };
    if (auth) headers['Authorization'] = auth;
    const opts = { method: req.method, headers };
    if (!['GET','DELETE'].includes(req.method)) opts.body = JSON.stringify(req.body);
    const r = await fetch(url, opts);
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ error: 'Backend unavailable' }); }
}

app.post('/api/billing/create-checkout-session', (req, res) => proxyBilling(req, res));
app.post('/api/billing/portal', (req, res) => proxyBilling(req, res));
app.get('/api/billing/status', (req, res) => proxyBilling(req, res));

// Billing webhook — raw body passthrough, no auth
app.post('/api/billing/webhook', async (req, res) => {
  try {
    const raw = req.body ? JSON.stringify(req.body) : '';
    const r = await fetch(`${API_BASE}/billing/webhook`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'stripe-signature': req.headers['stripe-signature'] || '' },
      body: raw,
    });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ status: 'error' }); }
});

app.get('/api/admin/investors', async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/admin/investors`, { headers: { 'X-Admin-Key': ADMIN_KEY } });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ investors: [] }); }
});

app.get('/api/admin/investors/:id', async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/admin/investors/${req.params.id}`, { headers: { 'X-Admin-Key': ADMIN_KEY } });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ error: 'Backend unavailable' }); }
});

app.patch('/api/admin/investors/:id/status', async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/admin/investors/${req.params.id}/status`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-Admin-Key': ADMIN_KEY }, body: JSON.stringify(req.body) });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ error: 'Backend unavailable' }); }
});

app.patch('/api/admin/investors/:id/note', async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/admin/investors/${req.params.id}/note`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-Admin-Key': ADMIN_KEY }, body: JSON.stringify(req.body) });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ error: 'Backend unavailable' }); }
});

app.post('/api/admin/investors/:id/message', async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/admin/investors/${req.params.id}/message`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Admin-Key': ADMIN_KEY }, body: JSON.stringify(req.body) });
    return res.status(r.status).json(await r.json());
  } catch { res.status(502).json({ error: 'Backend unavailable' }); }
});

app.post('/api/analytics/pageview', async (req, res) => {
  try {
    await fetchFromAPI('/blog/analytics/pageview', {
      method: 'POST', body: JSON.stringify({ slug: req.body.slug }),
    });
    return res.json({ ok: true });
  } catch (e) { console.error('Pageview error:', e); }
  const posts = readPosts();
  const post = posts.find(p => p.slug === req.body.slug);
  if (post) { post.views = (post.views || 0) + 1; fs.writeFileSync(POSTS_FILE, JSON.stringify(posts, null, 2)); }
  res.json({ ok: true });
});

app.get('/api/analytics/posts', async (req, res) => {
  try {
    const data = await fetchFromAPI('/blog/analytics/posts');
    if (data) return res.json(data);
  } catch (e) { console.error('Analytics fetch error:', e); }
  const posts = readPosts();
  res.json({
    totalPosts: posts.filter(p => p.status === 'published').length,
    posts: posts.filter(p => p.status === 'published').map(p => ({
      id: p.id, title: p.title, slug: p.slug, views: p.views || 0,
      publishedAt: p.publishedAt, category: p.category, tags: p.tags,
    })),
  });
});

async function requireInvestor(req, res, next) {
  const token = req.cookies?.investor_token || req.query.token;
  if (!token) return res.redirect('/investors/login');
  try {
    const r = await fetch(`${API_BASE}/auth/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!r.ok) return res.redirect('/investors/login');
    const user = await r.json();
    if (user.role !== 'investor' && user.role !== 'admin') return res.redirect('/investors/login');
    req.investor = user;
    req.investorToken = token;
    next();
  } catch {
    res.redirect('/investors/login');
  }
}

app.get('/investors', (req, res) => res.render('investors'));

app.get('/investors/login', (req, res) => {
  if (req.cookies?.investor_token) return res.redirect('/investors/dashboard');
  res.render('investor-login');
});
app.get('/investors/verify', (req, res) => res.render('investor-verify'));

app.post('/api/investor/login', loginLimiter, async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: req.body.email, name: req.body.name, role: 'investor' }),
    });
    const data = await r.json();
    if (!r.ok) return res.status(r.status).json(data);
    res.cookie('investor_token', data.token, {
      httpOnly: true, secure: true, sameSite: 'strict', path: '/',
      maxAge: 30 * 24 * 60 * 60 * 1000,
    });
    return res.json(data);
  } catch {
    res.status(502).json({ detail: 'Backend unavailable' });
  }
});

app.get('/investors/dashboard', requireInvestor, (req, res) => {
  res.render('investor-dashboard', { token: req.investorToken, investor: req.investor });
});

app.get('/investors/metrics', requireInvestor, (req, res) => res.render('investors-metrics', { investor: req.investor }));
app.get('/investors/financials', requireInvestor, (req, res) => res.render('investors-financials', { investor: req.investor }));
app.get('/investors/deck', requireInvestor, (req, res) => res.render('investors-deck', { investor: req.investor }));
app.get('/investors/data-room', requireInvestor, (req, res) => res.render('investors-data-room', { investor: req.investor }));

app.get('/workspace', (req, res) => res.render('workspace'));
app.get('/workspace/app', (req, res) => res.sendFile(path.join(DIR, 'workspace.html')));

app.post('/api/workspace/login', async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: req.body.email, password: req.body.password }),
    });
    const data = await r.json();
    return res.status(r.status).json(data);
  } catch {
    res.status(502).json({ detail: 'Backend unavailable' });
  }
});

app.post('/api/workspace/signup', async (req, res) => {
  try {
    const r = await fetch(`${API_BASE}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: req.body.email, name: req.body.name, password: req.body.password, role: 'subscriber' }),
    });
    const data = await r.json();
    return res.status(r.status).json(data);
  } catch {
    res.status(502).json({ detail: 'Backend unavailable' });
  }
});

app.get('/sitemap.xml', async (req, res) => {
  let blogPosts = [];
  try {
    const data = await fetchFromAPI('/blog/analytics/posts');
    if (data) blogPosts = data.posts;
  } catch (e) { console.error('Sitemap fetch error:', e); }
  if (!blogPosts.length) blogPosts = readPosts().filter(p => p.status === 'published');
  const site = 'https://sporafind.com';
  let xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n';
  const staticPages = ['/', '/features', '/segments', '/pricing', '/api-docs', '/changelog', '/about', '/blog', '/careers', '/press', '/contact', '/privacy', '/terms', '/gdpr', '/sources', '/roadmap', '/fundraising', '/investors', '/investors/login', '/workspace'];
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
  } catch (e) { console.error('RSS fetch error:', e); }
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

app.use(express.static(DIR, {
  maxAge: '1h',
  etag: true,
}));

app.use((err, req, res, next) => {
  console.error('Unhandled error:', err);
  res.status(500).type('html').send('<!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>500 — Sporafind</title><style>body{font-family:Inter,sans-serif;background:#0f0f0f;color:#e8e8e8;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px;text-align:center}h1{font-size:clamp(24px,5vw,48px);color:#ef4444}a{color:#00a85a}</style></head><body><div><h1>500</h1><p>Something went wrong</p><p><a href="/">← Back to sporafind.com</a></p></div></body></html>');
});

app.use((req, res) => {
  res.status(404).type('html').send('<!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>404 — Sporafind</title><style>body{font-family:Inter,sans-serif;background:#0f0f0f;color:#e8e8e8;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px;text-align:center}h1{font-size:clamp(24px,5vw,48px)}a{color:#00a85a}</style></head><body><div><h1>404</h1><p>Page not found</p><p><a href="/">← Back to sporafind.com</a></p></div></body></html>');
});

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(' Sporafind running at http://localhost:' + PORT);
    console.log('  Investor   investor@sporafind.com (via portal)');
    console.log('  Blog       http://localhost:' + PORT + '/blog');
  });
}

module.exports = app;

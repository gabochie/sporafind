import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');

// Must mirror scripts/build-chrome.js PAGES (public chrome) — app shells excluded by design
const CHROME_PAGES = [
  'about.html', 'api-docs.html', 'blog.html', 'careers.html', 'changelog.html',
  'contact.html', 'features.html', 'fundraising.html', 'gdpr.html', 'index.html',
  'press.html', 'pricing.html', 'privacy.html', 'roadmap.html', 'segments.html',
  'sources.html', 'terms.html', 'views/blog.ejs', 'views/blog-post.ejs',
  'views/workspace.ejs', 'views/investors.ejs', 'views/investor-login.ejs',
  'views/investor-verify.ejs',
];
const APP_SHELLS = [
  'admin.html', 'workspace.html', 'views/investor-dashboard.ejs',
  'views/investors-data-room.ejs', 'views/investors-deck.ejs',
  'views/investors-financials.ejs', 'views/investors-metrics.ejs',
];
const inner = (src, s, e) => {
  const m = src.match(new RegExp(`${s}([\\s\\S]*?)${e}`));
  return m ? m[1].trim() : null;
};

describe('shared chrome (header/footer)', () => {
  const header = read('partials/header.html').trim();
  const footer = read('partials/footer.html').trim();

  it('every public page carries markers matching the partials', () => {
    const bad = [];
    for (const p of CHROME_PAGES) {
      const src = read(p);
      const h = inner(src, '<!--CHROME:HEADER:START-->', '<!--CHROME:HEADER:END-->');
      const f = inner(src, '<!--CHROME:FOOTER:START-->', '<!--CHROME:FOOTER:END-->');
      if (h === null || f === null) { bad.push(`${p}:missing-markers`); continue; }
      // header may carry one active-link decoration vs the partial
      const hPlain = h.replace(' class="active" style="color:#fff"', '');
      if (hPlain !== header) bad.push(`${p}:header-drift`);
      if (f !== footer) bad.push(`${p}:footer-drift`);
    }
    expect(bad).toEqual([]);
  });

  it('no legacy per-page hamburger handlers remain', () => {
    const bad = CHROME_PAGES.filter((p) => read(p).includes("getElementById('navToggle')"));
    expect(bad).toEqual([]);
  });

  it('app shells intentionally keep their own chrome', () => {
    for (const p of APP_SHELLS) {
      expect(read(p).includes('CHROME:HEADER')).toBe(false);
    }
  });

  it('Sign in target is consistent (workspace, not admin)', () => {
    const bad = CHROME_PAGES.filter((p) => read(p).includes('href="admin.html" class="btn-ghost-nav"'));
    expect(bad).toEqual([]);
  });
});

describe('PWA installability', () => {
  const HEAD_PAGES = [
    'about.html', 'admin.html', 'api-docs.html', 'blog.html', 'careers.html',
    'changelog.html', 'contact.html', 'features.html', 'fundraising.html', 'gdpr.html',
    'index.html', 'press.html', 'pricing.html', 'privacy.html', 'roadmap.html',
    'segments.html', 'sources.html', 'terms.html', 'workspace.html',
    'views/blog.ejs', 'views/blog-post.ejs', 'views/workspace.ejs', 'views/investors.ejs',
    'views/investor-login.ejs', 'views/investor-verify.ejs', 'views/investor-dashboard.ejs',
    'views/investors-data-room.ejs', 'views/investors-deck.ejs', 'views/investors-financials.ejs',
    'views/investors-metrics.ejs',
  ];

  it('every template carries PWA head tags matching the partial', () => {
    const head = read('partials/head-pwa.html').trim();
    const bad = [];
    for (const p of HEAD_PAGES) {
      const src = read(p);
      const m = src.match(/<!--CHROME:HEAD:START-->([\s\S]*?)<!--CHROME:HEAD:END-->/);
      if (!m) { bad.push(`${p}:missing-head`); continue; }
      if (m[1].trim() !== head) bad.push(`${p}:head-drift`);
    }
    expect(bad).toEqual([]);
  });

  it('manifest is valid with required icons', () => {
    const manifest = JSON.parse(read('manifest.webmanifest'));
    expect(manifest.display).toBe('standalone');
    expect(manifest.start_url).toBe('/');
    expect(manifest.theme_color).toMatch(/^#[0-9a-fA-F]{6}$/);
    const sizes = manifest.icons.map((i) => `${i.sizes}/${i.purpose}`);
    expect(sizes).toContain('192x192/any');
    expect(sizes).toContain('512x512/any');
    expect(sizes).toContain('512x512/maskable');
    for (const icon of manifest.icons) {
      expect(fs.existsSync(path.join(ROOT, icon.src.replace(/^\//, '')))).toBe(true);
    }
  });

  it('service worker guards auth and versions caches', () => {
    const sw = read('sw.js');
    expect(sw).toContain('hasAuth');
    expect(sw).toContain("req.method !== 'GET'");
    expect(sw).toContain('/offline.html');
    expect(sw).toContain('push');
    expect(sw).toMatch(/const VERSION = 'sf-v\d+'/);
  });

  it('pwa.js registers the worker and wires push via backend key', () => {
    const pwa = read('js/pwa.js');
    expect(pwa).toContain("register('/sw.js')");
    expect(pwa).toContain('/api/push/vapid-key');
    expect(pwa).toContain('/api/push/subscribe');
  });
});

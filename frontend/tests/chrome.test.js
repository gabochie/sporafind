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

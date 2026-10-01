/* Builds shared chrome into pages. Idempotent — safe to re-run.
 * Usage: npm run build:chrome
 * Source of truth: partials/header.html, partials/footer.html, partials/subscribe.html
 * Pages carry markers; this script refreshes marker content + active link. */
const fs = require('fs');
const path = require('path');

const ROOT = __dirname + '/..';
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');
const headerTpl = read('partials/header.html').trim();
const footerTpl = read('partials/footer.html').trim();
const subscribeTpl = read('partials/subscribe.html').trim();
const headTpl = read('partials/head-pwa.html').trim();

// page -> data-nav value to highlight (null = none)
const PAGES = {
  'about.html': null, 'api-docs.html': 'api-docs', 'blog.html': null,
  'careers.html': null, 'changelog.html': 'changelog', 'contact.html': null,
  'features.html': 'features', 'fundraising.html': null, 'gdpr.html': null,
  'index.html': null, 'press.html': null, 'pricing.html': 'pricing',
  'privacy.html': null, 'roadmap.html': null, 'segments.html': 'segments',
  'sources.html': null, 'terms.html': null,
  'views/blog.ejs': null, 'views/blog-post.ejs': null, 'views/workspace.ejs': null,
  'views/investors.ejs': null, 'views/investor-login.ejs': null, 'views/investor-verify.ejs': null,
};
const APP_SHELLS = ['admin.html', 'workspace.html',
  'views/investor-dashboard.ejs', 'views/investors-data-room.ejs', 'views/investors-deck.ejs',
  'views/investors-financials.ejs', 'views/investors-metrics.ejs'];

const H_S = '<!--CHROME:HEADER:START-->';
const H_E = '<!--CHROME:HEADER:END-->';
const F_S = '<!--CHROME:FOOTER:START-->';
const F_E = '<!--CHROME:FOOTER:END-->';
const S_S = '<!--CHROME:SUBSCRIBE:START-->';
const S_E = '<!--CHROME:SUBSCRIBE:END-->';
const P_S = '<!--CHROME:HEAD:START-->';
const P_E = '<!--CHROME:HEAD:END-->';
// Every template gets PWA head tags (manifest, theme-color, icons, pwa.js),
// including app shells — installability must not depend on chrome choice.
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

function withActive(tpl, active) {
  if (!active) return tpl;
  return tpl.replace(
    new RegExp(`(<a href="[^"]*" data-nav="${active}")`),
    '$1 class="active" style="color:#fff"'
  );
}
function swap(src, start, end, inner) {
  const re = new RegExp(start.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[\\s\\S]*?' + end.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return { hit: re.test(src), out: src.replace(re, `${start}\n${inner}\n${end}`) };
}

let togglesStripped = 0;
for (const [page, active] of Object.entries(PAGES)) {
  const fp = path.join(ROOT, page);
  let s = fs.readFileSync(fp, 'utf8');
  const log = [];

  // strip legacy per-page hamburger handlers (now in shared header, guarded)
  const toggleRe = /document\.getElementById\('navToggle'\)\?\.addEventListener\('click', function\(\)\{[\s\S]*?\n\}\);/g;
  const m = s.match(toggleRe);
  if (m) { s = s.replace(toggleRe, ''); togglesStripped += m.length; log.push(`stripped ${m.length} legacy toggle`); }

  // header
  const marked = withActive(headerTpl, active);
  let r = swap(s, H_S, H_E, marked);
  if (r.hit) { s = r.out; log.push('header refreshed'); }
  else if (/<nav[\s>]/i.test(s)) {
    s = s.replace(/<nav[\s\S]*?<\/nav\s*>/i, `${H_S}\n${marked}\n${H_E}`);
    log.push('header canonicalized');
  } else {
    s = s.replace(/<body[^>]*>/i, (b) => `${b}\n${H_S}\n${marked}\n${H_E}`);
    log.push('header inserted');
  }

  // footer
  r = swap(s, F_S, F_E, footerTpl);
  if (r.hit) { s = r.out; log.push('footer refreshed'); }
  else if (/<footer[\s>]/i.test(s)) {
    s = s.replace(/<footer[\s\S]*?<\/footer\s*>/i, `${F_S}\n${footerTpl}\n${F_E}`);
    log.push('footer canonicalized');
  } else {
    s = s.replace(/<\/body\s*>/i, `${F_S}\n${footerTpl}\n${F_E}\n</body>`);
    log.push('footer inserted');
  }

  // subscribe demo forms (blog templates only)
  if (page === 'views/blog.ejs' || page === 'views/blog-post.ejs') {
    const subRe = /<form[^>]*alert\('Subscribed! \(demo\)'\)[^>]*>[\s\S]*?<\/form\s*>/gi;
    if (subRe.test(s)) {
      s = s.replace(subRe, `${S_S}\n${subscribeTpl}\n${S_E}`);
      log.push('subscribe partialized');
    } else {
      r = swap(s, S_S, S_E, subscribeTpl);
      if (r.hit) { s = r.out; log.push('subscribe refreshed'); }
    }
  }

  fs.writeFileSync(fp, s);
  console.log(`${page}: ${log.join('; ')}`);
}

// PWA head tags on every template (public + app shells).
for (const page of HEAD_PAGES) {
  const fp = path.join(ROOT, page);
  let s = fs.readFileSync(fp, 'utf8');
  const r = swap(s, P_S, P_E, headTpl);
  if (r.hit) {
    s = r.out;
  } else if (/<meta charset[^>]*>/i.test(s)) {
    s = s.replace(/<meta charset[^>]*>/i, (m) => `${m}\n${P_S}\n${headTpl}\n${P_E}`);
  } else {
    s = s.replace(/<head[^>]*>/i, (b) => `${b}\n${P_S}\n${headTpl}\n${P_E}`);
  }
  fs.writeFileSync(fp, s);
}
console.log(`head tags stamped on ${HEAD_PAGES.length} templates`);
console.log(`legacy toggles stripped: ${togglesStripped}`);
console.log(`app shells untouched: ${APP_SHELLS.join(', ')}`);

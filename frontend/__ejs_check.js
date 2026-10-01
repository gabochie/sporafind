const ejs = require('ejs');
const fs = require('fs');
const ROOT = 'C:/Users/user/Documents/GitHub/sporafind/frontend';

const base = {
  posts: [{ slug: 'a', title: 'T', excerpt: 'E', category: 'C', tags: ['x'], dateLabel: '1 Jan 2026', readMinutes: 1, coverTheme: 0, url: '/blog/a' }],
  page: 1, totalPages: 1, total: 0, tag: null, cat: null, q: null,
  categories: [], categoryCounts: {}, tags: [], tagTotal: 0,
  pageWindow: [1], blogQs: () => '/blog', isoDate: (d) => String(d),
  hasQuery: false, hasTag: false, hasCat: false,
  canonicalUrl: 'https://sporafind.com/blog',
};

for (const view of ['blog', 'blog-post']) {
  try {
    const tpl = fs.readFileSync(`${ROOT}/views/${view}.ejs`, 'utf8');
    ejs.render(tpl, view === 'blog' ? base : { ...base, post: base.posts[0], related: [], prevPost: null, nextPost: null });
    console.log(`${view}: render OK`);
  } catch (err) {
    console.error(`${view}: EJS ERROR -> ${err.message.split('\n').slice(0, 8).join('\n')}`);
  }
}
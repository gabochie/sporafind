import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const pages = [
  ...fs.readdirSync(ROOT).filter((f) => f.endsWith('.html')),
  ...fs.readdirSync(path.join(ROOT, 'views')).filter((f) => f.endsWith('.ejs')).map((f) => `views/${f}`),
];

const read = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');

describe('design-token consistency', () => {
  it('tokens.css + components.css exist with core tokens', () => {
    const tokens = read('css/tokens.css');
    for (const t of ['--green:', '--gold:', '--navy:', '--cream:', '--s0:', '--t1:', '--radius:', '--sidebar-w:', '--header-h:']) {
      expect(tokens).toContain(t);
    }
    expect(read('css/components.css')).toContain('.sf-btn');
  });

  it('no page re-declares :root (single source of truth)', () => {
    const offenders = pages.filter((p) => /:root\s*\{/.test(read(p)));
    expect(offenders).toEqual([]);
  });

  it('every page links the shared stylesheets', () => {
    const missing = pages.filter((p) => !read(p).includes('/css/tokens.css'));
    expect(missing).toEqual([]);
  });

  it('Tabler pinned to 3.19.0 everywhere', () => {
    const bad = pages.filter((p) => {
      const src = read(p);
      return src.includes('icons-webfont') && !src.includes('icons-webfont@3.19.0');
    });
    expect(bad).toEqual([]);
  });

  it('no dead variable references', () => {
    const bad = pages.filter((p) => /--header-w|--shadow-sm/.test(read(p)));
    expect(bad).toEqual([]);
  });
});

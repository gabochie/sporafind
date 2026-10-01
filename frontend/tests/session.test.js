import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const src = fs.readFileSync(path.join(__dirname, '..', 'js', 'session.js'), 'utf8');

describe('session.js — real backend auth (no mocks)', () => {
  it('contains no demo credentials', () => {
    expect(src).not.toContain('demo123');
    expect(src).not.toContain('user@sporafind.com');
    expect(src).not.toContain("var UK='df_user'");
    expect(src).not.toContain('Gabochie Intel');
  });

  it('exposes token-based API wired to backend proxies', () => {
    expect(src).toContain('sf_token');
    expect(src).toContain('/api/workspace/login');
    expect(src).toContain('/api/workspace/signup');
    expect(src).toContain('/api/workspace/me');
    expect(src).toContain('Authorization');
    expect(src).toContain('DF.login');
    expect(src).toContain('DF.logout');
  });
});

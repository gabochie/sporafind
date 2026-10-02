"""One-off: add a socials row under the footer branding, drop the dead links.

Every page inlines the same footer (23 copies), so this patches them all:

  1. insert a socials row directly under the branding tagline
  2. delete the footer-bottom-links block, whose three links were
     javascript:void(0) + alert() placeholders rather than real profiles

Idempotent: running twice makes no further changes.
"""
import glob
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOCIALS = (
    '        <div class="footer-socials">\n'
    '          <a class="footer-social" href="https://x.com/sporafind" target="_blank" rel="noopener noreferrer" aria-label="Sporafind on X"><i class="ti ti-brand-x" aria-hidden="true"></i></a>\n'
    '          <a class="footer-social" href="https://www.linkedin.com/company/sporafind" target="_blank" rel="noopener noreferrer" aria-label="Sporafind on LinkedIn"><i class="ti ti-brand-linkedin" aria-hidden="true"></i></a>\n'
    '          <a class="footer-social" href="https://wa.me/233243262019" target="_blank" rel="noopener noreferrer" aria-label="Chat with Sporafind on WhatsApp"><i class="ti ti-brand-whatsapp" aria-hidden="true"></i></a>\n'
    '        </div>\n'
)

BRAND_P_RE = re.compile(
    r'(<div class="footer-brand">.*?</p>\n)', re.S)
BOTTOM_LINKS_RE = re.compile(
    r'\n?[ \t]*<div class="footer-bottom-links">.*?</div>\n', re.S)


def patch(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    original = text
    if "footer-socials" not in text:
        text, n = BRAND_P_RE.subn(lambda m: m.group(1) + SOCIALS, text, count=1)
        if not n:
            return "no footer-brand <p> matched"
    if "footer-bottom-links" in text:
        text = BOTTOM_LINKS_RE.sub("\n", text, count=1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return "patched"
    return "unchanged"


targets = sorted(
    p for p in list(ROOT.glob("*.html"))
    + list(ROOT.glob("views/*.ejs"))
    + list(ROOT.glob("partials/*.html"))
    if "<footer" in p.read_text(encoding="utf-8")
)
for p in targets:
    print(f"{patch(p):10} {p.relative_to(ROOT)}")
print(f"\n{len(targets)} footer files processed")
print("Now run: node scripts/build-chrome.js  (partials/footer.html is the "
      "source of truth and will otherwise overwrite the pages)")

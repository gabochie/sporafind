"""Generate a local contact sheet for human review of the curated feature photos.

Machine checks (dimensions, licence, duplicate titles, perceptual hashes) already
passed. What cannot be verified without eyes is whether each photo actually
depicts what its alt text claims. This page puts every image next to its alt
text, provenance and the posts that use it, so the review is one scroll.
"""

import html
import json
import pathlib
import re
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "feature-images.json"
POSTS = ROOT / "data" / "posts.json"
SCRIPT = ROOT / "scripts" / "fetch_feature_images.py"
OUT = ROOT / "photo-review.html"

manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
themes = manifest["themes"]
post_images = manifest["post_images"]

# Which themes were deliberately pinned to a named Commons file. A pinned theme
# was chosen by eye at some point; an unpinned one was auto-picked by keyword
# search, so its match is the most likely to be wrong. Each T(...) call is one
# theme, so a pick= inside a call belongs to that call's key.
pinned = set()
for block in SCRIPT.read_text(encoding="utf-8").split("T(")[1:]:
    key = re.match(r'\s*"([a-z0-9_]+)"', block)
    if key and "pick=" in block:
        pinned.add(key.group(1))

post_titles = {}
for p in json.loads(POSTS.read_text(encoding="utf-8")):
    post_titles[p["slug"]] = p["title"]

posts_by_file = defaultdict(list)
for slug, path in post_images.items():
    posts_by_file[path].append(slug)

theme_by_file = {v["file"]: k for k, v in themes.items()}

cards = []
for path in sorted(set(post_images.values())):
    meta = themes.get(theme_by_file.get(path, ""), {})
    key = theme_by_file.get(path, path)
    alt = meta.get("alt", "(no alt)")
    title = (meta.get("title") or "").removeprefix("File:").removesuffix(".jpg")
    auto = key not in pinned
    slugs = sorted(posts_by_file[path])
    cards.append((key, path, alt, title, meta, auto, slugs, post_titles))

auto_cards = [c for c in cards if c[5]]
shared_cards = [c for c in cards if len(c[6]) > 1]

CSS = """
:root{
  --navy:#080D1A; --green:#006B3C; --gold:#D4A017; --cream:#F5F0E8;
  --line:#E4DDD0; --muted:#5C6675;
}
*{box-sizing:border-box}
body{margin:0;background:var(--cream);color:var(--navy);
  font:16px/1.55 Inter,system-ui,-apple-system,"Segoe UI",sans-serif}
header{background:var(--navy);color:#fff;padding:40px 32px}
header h1{font-family:"Space Grotesk",Inter,sans-serif;margin:0 0 8px;
  font-size:30px;letter-spacing:-.02em}
header p{margin:4px 0;color:#B9C2D0;max-width:70ch}
.wrap{max-width:1400px;margin:0 auto;padding:28px 24px 80px}
.bar{position:sticky;top:0;z-index:20;background:var(--cream);
  border-bottom:1px solid var(--line);padding:12px 24px;display:flex;
  gap:16px;align-items:center;flex-wrap:wrap}
.bar b{font-family:"Space Grotesk",Inter,sans-serif}
.btn{font:inherit;padding:9px 16px;border-radius:8px;border:1px solid var(--navy);
  background:var(--navy);color:#fff;cursor:pointer;font-weight:600}
.btn.alt{background:#fff;color:var(--navy)}
.grid{display:grid;gap:22px;grid-template-columns:repeat(auto-fill,minmax(330px,1fr))}
.card{background:#fff;border:1px solid var(--line);border-radius:14px;
  overflow:hidden;display:flex;flex-direction:column}
.card img{width:100%;aspect-ratio:16/10;object-fit:cover;display:block;
  background:#ddd;cursor:zoom-in}
.body{padding:16px 18px 18px;display:flex;flex-direction:column;gap:10px;flex:1}
.key{font-family:"Space Grotesk",Inter,sans-serif;font-weight:700;font-size:17px}
.tags{display:flex;gap:6px;flex-wrap:wrap}
.tag{font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
  padding:3px 8px;border-radius:99px}
.auto{background:#FDF0D5;color:#7A5200;border:1px solid #E8CE93}
.pinned{background:#E4F1EA;color:var(--green);border:1px solid #B9DCC9}
.shared{background:#E7EEFB;color:#1B3F87;border:1px solid #BCCBEE}
.alt{background:var(--cream);border-left:3px solid var(--gold);padding:10px 12px;
  border-radius:0 6px 6px 0;font-size:14px}
.meta{font-size:12.5px;color:var(--muted);line-height:1.5}
.meta a{color:var(--green)}
.meta b{color:var(--navy)}
.posts{list-style:none;padding:0;margin:0;font-size:13px;display:flex;
  flex-direction:column;gap:6px}
.posts li{padding-left:14px;position:relative}
.posts li::before{content:"";position:absolute;left:0;top:8px;width:5px;height:5px;
  border-radius:50%;background:var(--green)}
.posts a{color:var(--navy);text-decoration:none}
.posts a:hover{text-decoration:underline}
h2{font-family:"Space Grotesk",Inter,sans-serif;font-size:21px;margin:38px 0 4px;
  padding-top:14px;border-top:2px solid var(--navy)}
.note{color:var(--muted);font-size:14px;margin:0 0 18px}
dialog{border:none;padding:0;background:transparent;max-width:96vw;max-height:96vh}
dialog::backdrop{background:rgba(8,13,26,.92)}
dialog img{max-width:96vw;max-height:96vh;display:block;border-radius:8px}
dialog .cap{color:#fff;text-align:center;padding:10px;font-size:14px}
@media(max-width:640px){header{padding:28px 18px}.wrap{padding:18px 14px 60px}
  .bar{padding:10px 14px}.grid{grid-template-columns:1fr}}
"""

JS = """
const dlg=document.getElementById('lb');
const img=document.getElementById('lb-img'),cap=document.getElementById('lb-cap');
document.querySelectorAll('.card img').forEach(i=>i.addEventListener('click',()=>{
  img.src=i.src;cap.textContent=i.dataset.caption;dlg.showModal();}));
dlg.addEventListener('click',e=>{if(e.target===dlg)dlg.close();});
const only=document.getElementById('only-auto');
function apply(){const a=only.checked;
  document.querySelectorAll('.card').forEach(c=>
    c.style.display=(!a||c.dataset.auto==='1')?'':'none');}
only.addEventListener('change',apply);
"""


def esc(s):
    return html.escape(str(s), quote=True)


cards_html = []
for key, path, alt, title, meta, auto, slugs, ptitles in sorted(
    cards, key=lambda c: (not c[5], c[0])
):
    licence = meta.get("licence", "?")
    lic_url = meta.get("licence_url", "")
    author = meta.get("author", "?")
    page = meta.get("file_page", "")
    lic_html = (
        f'<a href="{esc(lic_url)}" target="_blank" rel="noopener">{esc(licence)}</a>'
        if lic_url
        else esc(licence)
    )
    post_html = "".join(
        f'<li><a href="/blog/{esc(s)}" target="_blank" rel="noopener">'
        f'{esc(ptitles.get(s, s))}</a></li>'
        for s in slugs
    )
    tags = ['<span class="tag auto">auto-picked</span>' if auto else
            '<span class="tag pinned">pinned</span>']
    if len(slugs) > 1:
        tags.append(f'<span class="tag shared">{len(slugs)} posts</span>')
    caption = f"{key} — {alt}"
    cards_html.append(f"""    <article class="card" data-auto="{1 if auto else 0}">
      <img src="{esc(path)}" alt="{esc(alt)}" loading="lazy"
           data-caption="{esc(caption)}">
      <div class="body">
        <div class="key">{esc(key)}</div>
        <div class="tags">{''.join(tags)}</div>
        <div class="alt"><b>Alt text on the page:</b> {esc(alt)}</div>
        <div class="meta">
          <b>Source:</b> {esc(title)}<br>
          <b>By:</b> {esc(author)} &middot; <b>Licence:</b> {lic_html}<br>
          <a href="{esc(page)}" target="_blank" rel="noopener">View on Commons</a>
        </div>
        <ul class="posts">{post_html}</ul>
      </div>
    </article>""")

unresolved_html = "".join(
    f"<li><code>{esc(k)}</code></li>" for k in manifest.get("unresolved", [])
)

doc = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sporafind feature photo review</title>
<style>{CSS}</style>
</head><body>
<header>
  <h1>Feature photo review</h1>
  <p>{len(cards)} images across {len(post_images)} published posts. Everything
     machine-checkable has already passed: licence allowlist, minimum 1400&times;800,
     aspect ratio, no two themes sharing a Commons title, no byte-identical or
     perceptually near-duplicate files. What is left is the one thing a script
     cannot do &mdash; confirm each photograph actually shows what the caption
     says it shows.</p>
  <p>Click any image to enlarge. Work top to bottom. Note the theme key of
     anything that looks wrong and the theme key of anything where the caption
     is merely defensible rather than accurate.</p>
</header>
<div class="bar">
  <b>{len(cards)} photos &middot; {len(auto_cards)} auto-picked &middot;
     {len(shared_cards)} shared between posts</b>
  <label class="btn alt"><input type="checkbox" id="only-auto">
    Auto-picked only ({len(auto_cards)})</label>
  <button class="btn" onclick="window.scrollTo(0,0)">Back to top</button>
</div>
<main class="wrap">
  <h2>Auto-picked first ({len(auto_cards)})</h2>
  <p class="note">These were chosen by keyword search, not pinned by name, so
     they carry the most risk of being technically relevant but visually wrong.</p>
  <div class="grid">
{''.join(c for c in cards_html if 'auto' in c.split('data-auto="1"')[0][-40:])}
  </div>
  <h2>Remaining ({len(cards) - len(auto_cards)})</h2>
  <p class="note">Each of these is pinned to a named Commons file that was
     selected deliberately.</p>
  <div class="grid">
{''.join(c for c in cards_html if 'data-auto="0"' in c)}
  </div>
  <h2>No photo (by design)</h2>
  <p class="note">These themes had no honest Wikimedia Commons result, so their
     posts keep the designed gradient cover. Nothing to review.</p>
  <ul>{unresolved_html}</ul>
</main>
<dialog id="lb"><img id="lb-img" alt=""><div class="cap" id="lb-cap"></div></dialog>
<script>{JS}</script>
</body></html>
"""

OUT.write_text(doc, encoding="utf-8")
print(f"wrote {OUT}")
print(f"  {len(cards)} photos, {len(auto_cards)} auto-picked, "
      f"{len(shared_cards)} shared, {len(manifest.get('unresolved', []))} unresolved")
/* Sporafind PWA UI: install prompt + update notification.
 *
 * Injected on every page via partials/head-pwa.html. Both surfaces follow the
 * current platform guidance rather than prompting on load:
 *
 *  - Install never shows until the visitor has actually engaged (dwell or
 *    scroll depth). A prompt to someone who has not yet seen what the product
 *    does reads as an ad, and Chrome's own install UI moved to the address bar
 *    for this reason.
 *  - iOS never fires beforeinstallprompt and has no programmatic install, so
 *    it gets instructions rather than a button that cannot work.
 *  - Updates notify and offer a reload; they never force one, because silently
 *    swapping the document mid-task discards form input and scroll position.
 */
(function () {
  'use strict';

  var DISMISS_INSTALL = 'sf:install-dismissed';
  var DISMISS_UPDATE = 'sf:update-dismissed';
  var INSTALL_RETRY = 30 * 24 * 60 * 60 * 1000; // don't nag for 30 days
  var DWELL_MS = 45000;
  var SCROLL_RATIO = 0.5;

  // ---------- shared styles ----------
  var CSS = [
    '.sf-pwa{position:fixed;left:50%;transform:translateX(-50%);z-index:900;',
    'width:calc(100% - 32px);max-width:460px;display:flex;align-items:center;gap:14px;',
    'background:#fff;border:1px solid rgba(8,13,26,.1);border-radius:14px;',
    'box-shadow:0 10px 30px rgba(8,13,26,.18);padding:14px 16px;',
    'font:400 14px/1.45 Inter,system-ui,-apple-system,"Segoe UI",sans-serif;color:#080D1A}',
    '.sf-pwa[hidden]{display:none}',
    '.sf-pwa-mark{width:40px;height:40px;border-radius:10px;flex:0 0 auto;',
    'display:flex;align-items:center;justify-content:center;',
    'background:#006B3C;color:#D4A017;font-weight:800;font-size:18px}',
    '.sf-pwa-text{flex:1;min-width:0}',
    '.sf-pwa-title{font-weight:700;font-size:14px;letter-spacing:-.1px}',
    '.sf-pwa-sub{font-size:13px;color:#5C6675;margin-top:2px}',
    '.sf-pwa-act{flex:0 0 auto;display:flex;align-items:center;gap:8px}',
    '.sf-pwa-btn{min-height:40px;padding:0 16px;border-radius:9px;border:0;cursor:pointer;',
    'font:600 14px Inter,system-ui,sans-serif;background:#006B3C;color:#fff;',
    'display:inline-flex;align-items:center;justify-content:center}',
    '.sf-pwa-btn:active{transform:translateY(1px)}',
    '.sf-pwa-btn:focus-visible{outline:2px solid #D4A017;outline-offset:2px}',
    '.sf-pwa-x{min-width:40px;min-height:40px;border-radius:9px;border:0;background:transparent;',
    'color:#5C6675;font-size:20px;cursor:pointer;line-height:1}',
    '.sf-pwa-x:focus-visible{outline:2px solid #D4A017;outline-offset:2px}',
    '@media(max-width:640px){.sf-pwa-sub{display:none}}'
  ].join('');

  function injectStyles() {
    if (document.getElementById('sf-pwa-css')) return;
    var s = document.createElement('style');
    s.id = 'sf-pwa-css';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function dismissed(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }
  function dismiss(key) {
    try { localStorage.setItem(key, String(Date.now())); } catch (e) { /* private mode */ }
  }

  function standalone() {
    return window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true;
  }

  function isIOS() {
    var ua = navigator.userAgent;
    // iPadOS 13+ reports as Mac; the touch-point count is what distinguishes it.
    return /iPad|iPhone|iPod/.test(ua) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  }

  function isSafari() {
    var ua = navigator.userAgent;
    return /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|Chrome/.test(ua);
  }

  /* Bottom sheet, clear of the home indicator. update=true restyles it as a
   * toast and lets the caller swap the copy and actions. */
  function build(opts) {
    injectStyles();
    var el = document.createElement('div');
    el.className = 'sf-pwa';
    el.setAttribute('role', 'status');
    el.hidden = true;

    var mark = document.createElement('div');
    mark.className = 'sf-pwa-mark';
    mark.textContent = opts.mark || '★';

    var text = document.createElement('div');
    text.className = 'sf-pwa-text';
    var title = document.createElement('div');
    title.className = 'sf-pwa-title';
    title.textContent = opts.title;
    var sub = document.createElement('div');
    sub.className = 'sf-pwa-sub';
    sub.textContent = opts.sub;
    text.appendChild(title);
    text.appendChild(sub);

    var act = document.createElement('div');
    act.className = 'sf-pwa-act';

    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'sf-pwa-x';
    close.innerHTML = '&times;';
    close.setAttribute('aria-label', opts.dismissLabel || 'Dismiss');
    act.appendChild(close);

    el.appendChild(mark);
    el.appendChild(text);
    el.appendChild(act);
    document.body.appendChild(el);

    var hide = function () { el.hidden = true; };
    // Plain value first, then the inset-aware one. A browser without env()
    // support drops the whole calc() declaration and keeps the fallback.
    el.style.bottom = '16px';
    el.style.bottom = 'calc(16px + env(safe-area-inset-bottom, 0px))';

    return { el: el, sub: sub, act: act, close: close, hide: hide };
  }

  // ---------- update toast ----------
  document.addEventListener('sf:update-available', function () {
    if (dismissed(DISMISS_UPDATE) && Date.now() - Number(dismissed(DISMISS_UPDATE)) < 7 * 24 * 60 * 60 * 1000) return;
    var c = build({
      mark: '↻',
      title: 'New version available',
      sub: 'Reload to get the latest.',
      dismissLabel: 'Dismiss update notice'
    });

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'sf-pwa-btn';
    btn.textContent = 'Reload';
    btn.addEventListener('click', function () {
      if (window.__sfReloadOnNextNav) { window.__sfReloadOnNextNav = false; }
      c.hide();
      window.location.reload();
    });
    c.act.appendChild(btn);

    c.close.addEventListener('click', function () {
      // Dismissed, but honour it at the next navigation: the user is not
      // interrupted, and the new build takes effect when they next move on.
      window.__sfReloadOnNextNav = true;
      dismiss(DISMISS_UPDATE);
      c.hide();
    });

    c.el.hidden = false;
  });

  // Reload for real once the user starts a fresh navigation, so a dismissed
  // update still lands without an interrupt.
  window.addEventListener('pagehide', function () {
    if (!window.__sfReloadOnNextNav) return;
    window.__sfReloadOnNextNav = false;
    try { sessionStorage.setItem('sf:reload-on-nav', '1'); } catch (e) { /* ignore */ }
  });
  try {
    if (sessionStorage.getItem('sf:reload-on-nav')) {
      sessionStorage.removeItem('sf:reload-on-nav');
      window.location.reload();
    }
  } catch (e) { /* private mode */ }

  // ---------- install ----------
  var deferred = null;
  var ui = null;

  function showInstall() {
    if (ui || standalone()) return;
    var ios = isIOS();

    // iOS has no programmatic install; the honest offer is instructions.
    var uiCopy = ios && isSafari()
      ? { title: 'Add Sporafind to Home Screen',
          sub: 'Tap Share, then "Add to Home Screen".',
          label: 'How?' }
      : { title: 'Install Sporafind',
          sub: 'Faster loading and offline access.',
          label: 'Install' };

    ui = build({
      mark: '↓',
      title: uiCopy.title,
      sub: uiCopy.sub,
      dismissLabel: 'Dismiss install prompt'
    });

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'sf-pwa-btn';
    btn.textContent = uiCopy.label;
    btn.addEventListener('click', function () {
      dismiss(DISMISS_INSTALL);
      if (window.SFInstall) {
        window.SFInstall().then(function (ok) {
          if (!ok && !deferred) ui.hide(); // genuinely not installable
        });
      } else if (ios) {
        // Explain inline rather than opening a dead button.
        ui.sub.textContent = 'In Safari: Share button, then "Add to Home Screen".';
        ui.sub.style.display = '';
        ui.el.hidden = false;
      }
    });
    ui.act.appendChild(btn);

    ui.close.addEventListener('click', function () {
      dismiss(DISMISS_INSTALL);
      ui.hide();
    });

    ui.el.hidden = false;
  }

  function engaged() {
    var fired = false;
    return function () {
      if (fired) return;
      fired = true;
      showInstall();
    };
  }

  window.addEventListener('sf:installable', function () { deferred = true; });

  function coolOff() {
    var last = dismissed(DISMISS_INSTALL);
    return !last || Date.now() - Number(last) >= INSTALL_RETRY;
  }

  /* Arm the engagement gate. Fires once the visitor has dwelled or scrolled
   * half the page, and only if we have something real to offer: a deferred
   * install prompt, or iOS Safari where the offer is instructions. Without an
   * offer there is no point interrupting anyone. */
  function gate() {
    var onEngaged = engaged();
    var offerable = function () { return deferred || (isIOS() && isSafari()); };
    if (!offerable()) return false;

    var t = setTimeout(function () {
      if (offerable()) onEngaged();
    }, DWELL_MS);

    var onScroll = function () {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      if (h > 0 && window.scrollY / h >= SCROLL_RATIO) {
        clearTimeout(t);
        window.removeEventListener('scroll', onScroll);
        if (offerable()) onEngaged();
      }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return true;
  }

  function start() {
    if (standalone() || !coolOff()) return;
    // Arm immediately if already installable, otherwise wait for the browser
    // to decide and arm then. Either way the dwell/scroll gate still applies.
    if (!gate()) {
      document.addEventListener('sf:installable', function once() {
        document.removeEventListener('sf:installable', once);
        if (!ui && coolOff()) gate();
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
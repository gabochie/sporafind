/* Sporafind PWA bootstrap: service worker registration + install prompt + push opt-in. */
(function () {
  'use strict';
  if (!('serviceWorker' in navigator)) return;
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/sw.js').then(function (reg) {
      reg.addEventListener('updatefound', function () {
        var sw = reg.installing;
        if (!sw) return;
        sw.addEventListener('statechange', function () {
          if (sw.state === 'installed' && navigator.serviceWorker.controller) {
            document.dispatchEvent(new CustomEvent('sf:update-available'));
          }
        });
      });
    }).catch(function (err) {
      console.warn('SW registration failed:', err);
    });
  });

  // Deferred install prompt — pages surface their own [data-sf-install] button.
  var deferred = null;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferred = e;
    document.dispatchEvent(new CustomEvent('sf:installable'));
  });
  window.SFInstall = function () {
    if (!deferred) return Promise.resolve(false);
    deferred.prompt();
    return deferred.userChoice.then(function (c) {
      deferred = null;
      return c.outcome === 'accepted';
    });
  };

  // Push opt-in helper. VAPID public key served by backend (503 until configured).
  function urlBase64ToUint8Array(base64) {
    var padding = '='.repeat((4 - (base64.length % 4)) % 4);
    var b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw = window.atob(b64);
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  window.SFPush = {
    supported: function () { return 'PushManager' in window && 'serviceWorker' in navigator; },
    permission: function () { return window.Notification ? Notification.permission : 'denied'; },
    subscribe: async function () {
      var keyRes = await fetch('/api/push/vapid-key');
      if (!keyRes.ok) throw new Error('Push not configured on server');
      var keyData = await keyRes.json();
      if (!keyData.publicKey) throw new Error('Push not configured on server');
      var perm = await Notification.requestPermission();
      if (perm !== 'granted') throw new Error('Notifications blocked');
      var reg = await navigator.serviceWorker.ready;
      var sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(keyData.publicKey),
      });
      var token = (window.DF && window.DF.getToken && window.DF.getToken()) || '';
      var res = await fetch('/api/push/subscribe', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' },
          token ? { Authorization: 'Bearer ' + token } : {}),
        body: JSON.stringify(sub.toJSON()),
      });
      if (!res.ok) throw new Error('Subscribe failed');
      return sub;
    },
  };
})();

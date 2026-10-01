(function () {
  'use strict';
  var TOKEN_KEY = 'sf_token';
  var USER_KEY = 'sf_user';
  window.DF = window.DF || {};

  function getToken() {
    try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
  }
  function getUser() {
    try {
      var r = localStorage.getItem(USER_KEY);
      return r ? JSON.parse(r) : null;
    } catch (e) { return null; }
  }
  function setSession(token, user) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
    } catch (e) {}
  }
  function authHeaders() {
    var t = getToken();
    return t ? { 'Authorization': 'Bearer ' + t } : {};
  }
  async function handleAuthResponse(res) {
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) throw new Error(data.detail || 'Auth failed');
    setSession(data.token, { email: data.email, role: data.role, user_id: data.user_id });
    return data;
  }
  DF.getToken = getToken;
  DF.getUser = getUser;
  DF.isLoggedIn = function () { return !!getToken(); };
  DF.authHeaders = authHeaders;
  DF.login = async function (email, password) {
    var res = await fetch('/api/workspace/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, password: password }),
    });
    return handleAuthResponse(res);
  };
  DF.signup = async function (email, name, password) {
    var res = await fetch('/api/workspace/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, name: name, password: password }),
    });
    return handleAuthResponse(res);
  };
  DF.me = async function () {
    var res = await fetch('/api/workspace/me', { headers: authHeaders() });
    if (!res.ok) throw new Error('Session expired');
    var user = await res.json();
    try { localStorage.setItem(USER_KEY, JSON.stringify(user)); } catch (e) {}
    return user;
  };
  DF.logout = function () {
    try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); } catch (e) {}
    // legacy key cleanup (removes old mock session if present)
    try { localStorage.removeItem('df_user'); } catch (e) {}
    window.location.href = '/';
  };
})();

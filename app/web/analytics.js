/* First-party consent gate. Google receives only allowlisted public page locations. */
(() => {
  'use strict';
  const ID = 'G-C20RTKJJGK'; // Dedicated OpenEdu GA4 web stream.
  const DEBUG = new URLSearchParams(location.search).get('analytics_debug') === '1';
  const KEY = 'openedu.analytics.v1';
  const ORIGIN = 'https://openedu4u.com';
  if (!/^G-[A-Z0-9]+$/.test(ID) || ID === 'G-PENDING') return;
  if (!['openedu4u.com', 'www.openedu4u.com'].includes(location.hostname)) return;

  function publicPage(href) {
    const u = new URL(href, ORIGIN);
    if (!['openedu4u.com', 'www.openedu4u.com'].includes(u.hostname)) return null;
    if (/(?:access_token|refresh_token|password|email|code|token)=/i.test(u.search + u.hash)) return null;
    const path = u.pathname;
    if (/^\/(?:a|s)\/\d+\.html$/.test(path) || /^\/g\/(?:daechi|mokdong|banpo|jamsil)\.html$/.test(path) || /^\/t\/[a-z0-9-]+\.html$/.test(path) || path === '/method.html') return ORIGIN + path;
    if (path === '/privacy/' || path === '/privacy/index.html') return ORIGIN + '/privacy/';
    if (!['/', '/index.html'].includes(path)) return null;
    if (!u.hash || u.hash === '#/' || u.hash === '#') return ORIGIN + '/';
    const route = u.hash.slice(1).split('?')[0];
    if (/^\/academy\/\d+$/.test(route)) return ORIGIN + '/a/' + route.split('/').pop() + '.html';
    if (['/rank', '/compare', '/map', '/tree', '/method'].includes(route)) return ORIGIN + '/#' + route;
    return null;
  }

  let choice = null;
  try { choice = localStorage.getItem(KEY); } catch (_) { /* No persisted consent. */ }
  let loaded = false;
  let lastPage = null;
  let panel;
  let settingsButton;
  const gtag = (...args) => { (window.dataLayer = window.dataLayer || []).push(args); };
  const safeReferrer = () => { try { return new URL(document.referrer).origin; } catch (_) { return ''; } };
  function track() {
    const page = publicPage(location.href);
    window['ga-disable-' + ID] = choice !== 'granted' || !page;
    if (choice !== 'granted' || !page) { lastPage = null; return; }
    if (!loaded) {
      loaded = true;
      window.gtag = gtag;
      gtag('consent', 'default', {analytics_storage: 'granted', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied'});
      gtag('set', 'page_location', page);
      gtag('set', 'page_referrer', safeReferrer());
      gtag('js', new Date());
      gtag('config', ID, {send_page_view: false, allow_google_signals: false, allow_ad_personalization_signals: false, page_location: page, page_referrer: safeReferrer(), cookie_expires: 7776000, ...(DEBUG ? {debug_mode: true} : {})});
      const script = document.createElement('script');
      script.async = true;
      script.referrerPolicy = 'origin';
      script.src = 'https://www.googletagmanager.com/gtag/js?id=' + ID;
      document.head.appendChild(script);
    }
    if (page !== lastPage) {
      gtag('set', 'page_location', page);
      gtag('event', 'page_view', {...(DEBUG ? {debug_mode: true} : {}), page_location: page, page_referrer: safeReferrer(), page_title: page.includes('/a/') ? '학원 상세 · 학원실록' : page.includes('/s/') ? '학교 정보 · 학원실록' : '학원 탐색 · 학원실록'});
      lastPage = page;
    }
  }
  function choose(value) {
    choice = value === 'granted' ? 'granted' : 'denied';
    try { localStorage.setItem(KEY, choice); } catch (_) { /* Choice still applies to this page. */ }
    window['ga-disable-' + ID] = choice !== 'granted';
    if (loaded && choice === 'denied') gtag('consent', 'update', {analytics_storage: 'denied', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied'});
    if (loaded && choice === 'granted') gtag('consent', 'update', {analytics_storage: 'granted', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied'});
    panel.hidden = true;
    settingsButton.focus();
    track();
  }
  function refresh() {
    const allowed = !!publicPage(location.href);
    if (settingsButton) settingsButton.hidden = !allowed;
    if (panel) panel.hidden = !allowed || choice === 'granted' || choice === 'denied';
    track();
  }
  function mount() {
    const style = document.createElement('style');
    style.textContent = `#oe-analytics{position:fixed;z-index:10000;bottom:24px;left:16px;right:16px;max-width:440px;padding:18px;background:#fff;color:#173b32;border:1px solid #bfcfc8;border-radius:14px;font:15px/1.6 system-ui,sans-serif;box-shadow:0 4px 24px #163b3220}#oe-analytics[hidden],#oe-analytics-settings[hidden]{display:none}#oe-analytics p{margin:0 0 12px}#oe-analytics button{min-height:44px;min-width:80px;border:1px solid #16705d;border-radius:8px;background:white;color:#155c4c;font:inherit;margin:0 8px 8px 0;padding:8px 16px;cursor:pointer}#oe-analytics a{color:#155c4c}#oe-analytics-settings{position:fixed;z-index:9999;bottom:16px;left:12px;min-height:44px;padding:8px 12px;border:1px solid #bfcfc8;background:#fff;color:#155c4c;border-radius:8px;font:13px system-ui;cursor:pointer}#oe-analytics button:focus-visible,#oe-analytics-settings:focus-visible{outline:3px solid #d98b2f;outline-offset:3px}@media(max-width:600px){#oe-analytics{bottom:calc(82px + env(safe-area-inset-bottom))}#oe-analytics-settings{bottom:calc(72px + env(safe-area-inset-bottom))}}@media(prefers-color-scheme:dark){#oe-analytics,#oe-analytics-settings{background:#142d27;color:#edf5ef;border-color:#66877a}#oe-analytics a{color:#b8e4d1}#oe-analytics button{background:#203e34;color:#edf5ef;border-color:#8bbdab}}`;
    document.head.appendChild(style);
    panel = document.createElement('section');
    panel.id = 'oe-analytics';
    panel.setAttribute('aria-label', '방문 통계 선택');
    panel.innerHTML = '<p>방문 통계를 허용하면 학원 탐색을 개선하는 데 도움이 됩니다. 광고에는 사용하지 않으며, 선택은 언제든 바꿀 수 있어요.</p><button type="button" data-choice="granted">허용</button><button type="button" data-choice="denied">거절</button><br><a href="/privacy/">방문 통계 안내</a>';
    panel.querySelectorAll('button').forEach(b => b.addEventListener('click', () => choose(b.dataset.choice)));
    settingsButton = document.createElement('button');
    settingsButton.id = 'oe-analytics-settings';
    settingsButton.type = 'button';
    settingsButton.textContent = '통계 설정';
    settingsButton.addEventListener('click', () => { panel.hidden = false; panel.querySelector('button').focus(); });
    document.body.append(panel, settingsButton);
    refresh();
  }
  window.addEventListener('hashchange', refresh);
  window.addEventListener('popstate', refresh);
  // Do not collect forms, search terms, emails, account routes or comparison IDs.
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once: true}); else mount();
})();

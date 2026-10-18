// Real release check: submits one synthetic private opinion, then deletes it.
// Use PARENT_V2_PREVIEW_URL to serve a local build under the production Origin.
// No receipt secrets, opinion text, or request bodies are written to artifacts.
const { chromium } = require(process.env.PARENT_V2_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const base = (process.env.PARENT_V2_WEB_URL || 'https://openedu4u.com/').replace(/\/$/, '') + '/';
const preview = process.env.PARENT_V2_PREVIEW_URL;
const out = process.env.PARENT_V2_ARTIFACT_DIR || path.join(os.tmpdir(), 'openedu-release');
assert.equal(process.env.PARENT_V2_VERIFY_VOICE, 'true', 'Set PARENT_V2_VERIFY_VOICE=true to submit and delete a synthetic opinion');
fs.mkdirSync(out, {recursive: true});
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.PARENT_V2_CHROME, args: ['--disable-gpu']});
  let receipt, api, headers, deleted = false;
  const errors = [], apiStatuses = [];
  const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce'});
  try {
    if (preview) {
      await context.route(new URL(base).origin + '/**', async route => {
        const u = new URL(route.request().url());
        const response = await context.request.get(new URL(u.pathname + u.search, preview).href);
        await route.fulfill({response});
      });
    }
    const page = await context.newPage();
    page.setDefaultTimeout(60000);
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', e => { if (e.type() === 'error') errors.push(e.text()); });
    page.on('response', async response => {
      const request = response.request();
      if (!request.url().includes('/functions/v1/parent-voice/') || request.method() !== 'POST') return;
      const action = new URL(request.url()).pathname.split('/').at(-1);
      apiStatuses.push({action, status: response.status()});
      if (action === 'submit' && response.ok()) {
        const row = await response.json();
        receipt = {receiptId: row.receiptId, receiptSecret: request.postDataJSON().receiptSecret};
        api = request.url().replace(/\/submit$/, '/delete');
        const original = await request.allHeaders();
        headers = {apikey: original.apikey, authorization: original.authorization, origin: new URL(base).origin};
      }
      if (action === 'delete' && response.status() === 204) deleted = true;
    });
    async function open(route) {
      await page.goto(base + route);
      const placeholder = page.locator('flt-semantics-placeholder');
      await page.locator('flt-semantics-placeholder, flt-semantics').first().waitFor({state: 'attached'});
      if (await placeholder.count()) await placeholder.evaluate(e => e.click());
      await page.locator('flt-semantics').first().waitFor({state: 'attached'});
    }
    const labels = () => page.locator('flt-semantics').evaluateAll(els => els.map(e => e.getAttribute('aria-label') || '').join('\n'));
    async function reveal(locator) {
      for (let i = 0; i < 10 && !await locator.isVisible(); i++) {
        await page.mouse.move(700, 800);
        await page.mouse.wheel(0, 500);
        await page.waitForTimeout(200);
      }
      await locator.waitFor({state: 'visible'});
      return locator;
    }
    await open('');
    console.log('Checking opening and responsive layouts');
    await page.getByRole('button', {name: '숙제 부담이 걱정돼요', exact: true}).click();
    assert.match(await labels(), /하루 숙제 분량/);
    assert.equal(await page.evaluate(() => localStorage.getItem('parent.concern.v2')), 'homework');
    await page.screenshot({path: path.join(out, 'release-opening-desktop.png')});
    const widths = [];
    for (const width of [320, 375, 768, 1440]) {
      await page.setViewportSize({width, height: 1100});
      await page.waitForTimeout(150);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
      widths.push(width);
      if (width === 375) await page.screenshot({path: path.join(out, 'release-opening-mobile.png')});
    }
    await page.emulateMedia({colorScheme: 'dark'});
    await page.screenshot({path: path.join(out, 'release-opening-dark.png')});
    await page.emulateMedia({colorScheme: 'light'});
    await open('#/academy/14435');
    console.log('Checking academy entry and logged-out admin access');
    await page.getByRole('button', {name: '비교 담기', exact: true}).or(page.getByRole('button', {name: '비교에서 빼기', exact: true})).first().waitFor();
    await open('#/admin/parent-voice');
    await page.waitForFunction(() => [...document.querySelectorAll('flt-semantics')].some(e => /로그인|관리자/.test(e.getAttribute('aria-label') || '')));
    assert.doesNotMatch(await labels(), /접수 목록|선택한 의견/);
    await open('#/feedback');
    console.log('Checking real private opinion lifecycle');
    const send = page.getByRole('button', {name: '비공개로 의견 보내기', exact: true});
    await send.waitFor({state: 'attached'});
    assert.doesNotMatch(await labels(), /현재 의견 접수를 준비 중/);
    assert.match(await labels(), /90일/);
    assert.equal(await send.isDisabled(), true);
    await page.getByRole('button', {name: /의견 유형 · 필수/}).click();
    await page.getByRole('menuitem', {name: '찾거나 비교하기 어려워요', exact: true}).click();
    await page.getByRole('textbox', {name: '조금 더 들려주세요 · 선택', exact: true}).fill('운영 배포 검증용 의견입니다. 비교 화면에서 의견을 제출하고 상태 확인 후 원문을 삭제하는 동작을 점검합니다.');
    assert.equal(await send.isEnabled(), true);
    await send.click();
    await page.waitForFunction(() => [...document.querySelectorAll('flt-semantics')].some(e => (e.getAttribute('aria-label') || '').includes('의견을 접수했습니다.')));
    await (await reveal(page.getByRole('button', {name: '상태 확인', exact: true}))).click();
    await page.waitForFunction(() => [...document.querySelectorAll('flt-semantics')].some(e => (e.getAttribute('aria-label') || '').includes('접수됨')));
    await page.getByRole('button', {name: '원문 삭제', exact: true}).click();
    await page.getByRole('button', {name: '삭제', exact: true}).click();
    await page.waitForFunction(() => [...document.querySelectorAll('flt-semantics')].some(e => (e.getAttribute('aria-label') || '').includes('의견 원문과 확인 코드를 삭제했습니다.')));
    assert.equal(await page.evaluate(() => sessionStorage.getItem('parent.receipt.v2')), null);
    assert.deepEqual(apiStatuses, [{action: 'submit', status: 201}, {action: 'status', status: 200}, {action: 'delete', status: 204}]);
    assert.deepEqual(errors, []);
    const result = {status: 'pass', scope: preview ? 'local release assets under production Origin with real deployed API' : 'live production website and API', widths, checks: ['opening concern persists', 'responsive light and dark opening', 'academy direct entry', 'logged-out admin guard', 'real opinion submit and status', '204 delete clears receipt'], apiStatuses, errors};
    fs.writeFileSync(path.join(out, 'release-browser.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally {
    if (receipt && !deleted) {
      const response = await context.request.post(api, {headers, data: receipt});
      assert.equal(response.status(), 204, 'Synthetic opinion cleanup failed');
    }
    await browser.close();
  }
})().catch(e => {console.error(e); process.exit(1);});

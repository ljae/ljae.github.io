// Compiled Flutter comparison regression using real public assets. No backend.
const { chromium } = require(process.env.PARENT_V2_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const base = (process.env.PARENT_V2_WEB_URL || 'http://127.0.0.1:8769/').replace(/\/$/, '') + '/';
const out = process.env.PARENT_V2_ARTIFACT_DIR || path.join(os.tmpdir(), 'openedu-comparison');
fs.mkdirSync(out, { recursive: true });
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.PARENT_V2_CHROME, args: ['--disable-gpu']});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce', permissions: ['clipboard-read', 'clipboard-write']});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', e => { if (e.type() === 'error') errors.push(e.text()); });
    await page.goto(base + '#/compare?ids=14435,3000030122');
    await page.locator('flt-semantics-placeholder').waitFor({state: 'attached', timeout: 60000});
    await page.locator('flt-semantics-placeholder').evaluate(e => e.click());
    await page.getByRole('button', {name: '비교 초기화', exact: true}).waitFor();
    const labels = () => page.locator('flt-semantics').evaluateAll(els => els.map(e => e.getAttribute('aria-label') || '').join('\n'));
    await page.getByRole('checkbox', {name: '숙제 부담', exact: true}).click();
    await page.waitForTimeout(150);
    const initial = await labels();
    assert.ok(initial.indexOf('확인할 내용  하루 소요 시간') < initial.indexOf('확인할 내용  시작 수준'));
    assert.match(initial, /숙제로 집에서 푸는 교재인 소마셈과 팩토 키즈/);
    assert.match(initial, /엄마가 바짝 챙겨줘야/);
    assert.match(initial, /집에서 쓸 시간과 부모가 도와야 할 일/);
    assert.match(initial, /학년 미확인/);
    assert.match(initial, /글 작성 2025-07-10/);
    await page.screenshot({path: path.join(out, 'comparison-desktop-top.png')});
    await page.mouse.move(1000, 800);
    await page.mouse.wheel(0, 820);
    await page.waitForTimeout(250);
    await page.screenshot({path: path.join(out, 'comparison-desktop-evidence.png')});
    // Actual content, scope, and school-specific question survive clipboard copy.
    await page.mouse.wheel(0, 7000);
    await page.waitForTimeout(300);
    const copies = page.getByRole('button', {name: '이 학원 질문 복사', exact: true});
    await copies.nth(1).click();
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    assert.match(clip, /필즈더클래식 문의 질문/);
    assert.match(clip, /엄마가 바짝 챙겨줘야/);
    assert.match(clip, /원문: https:\/\/blog.naver.com/);
    assert.match(clip, /예비초~초3 수학/);
    // Let the copy confirmation leave before saving the layout artifacts.
    await page.waitForTimeout(4500);
    await page.mouse.wheel(0, -9000);
    await page.waitForTimeout(250);
    await page.getByRole('checkbox', {name: '고등', exact: true}).click();
    await page.waitForTimeout(150);
    const high = await labels();
    assert.doesNotMatch(high, /숙제로 집에서 푸는 교재인 소마셈과 팩토 키즈/);
    assert.match(high, /학년 미확인/); // unscoped material is labelled, never relabelled as high school
    await page.getByRole('checkbox', {name: '예비초~초3', exact: true}).click();
    const widths = [];
    for (const width of [320, 375, 768, 1440]) {
      await page.setViewportSize({width, height: 1100});
      await page.waitForTimeout(120);
      const actual = await page.evaluate(() => document.documentElement.scrollWidth);
      assert.equal(actual, width);
      widths.push(width);
      if (width === 375) {
        await page.mouse.move(200, 700);
        await page.mouse.wheel(0, 1050);
        await page.waitForTimeout(250);
        await page.screenshot({path: path.join(out, 'comparison-mobile-evidence.png')});
        await page.mouse.wheel(0, -9000);
        await page.waitForTimeout(150);
      }
    }
    await page.goto(base + '#/compare?ids=3000019569,9294');
    await page.getByRole('button', {name: '영어', exact: true}).click();
    await page.waitForFunction(() => [...document.querySelectorAll('flt-semantics')].some(e => (e.getAttribute('aria-label') || '').includes('선택 학년·반에 적용되는지 확인 필요')));
    const official = await labels();
    assert.match(official, /공식 안내 요약/);
    assert.match(official, /자료 대조 2026-09-17/);
    assert.match(official, /지필은 읽기·쓰기·어휘·문법/);
    assert.match(official, /월요일 정오에 일정을 공지/);
    await page.mouse.move(1000, 800);
    await page.mouse.wheel(0, 820);
    await page.waitForTimeout(200);
    await page.screenshot({path: path.join(out, 'comparison-official-guidance.png')});
    assert.deepEqual(errors, []);
    const result = {status: 'pass', widths, errors, checks: ['priority reorders criteria', 'distinct real quotations and decision meaning', 'source date and unknown grade', 'school-specific clipboard with original source', 'grade change excludes known other-grade excerpt', 'responsive layout', 'official guidance retains source date and unverified grade applicability'], scope: 'local compiled Flutter web; existing public assets, no live source revalidation'};
    fs.writeFileSync(path.join(out, 'comparison-browser.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(e => {console.error(e); process.exit(1);});

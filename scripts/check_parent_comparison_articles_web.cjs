// Real compiled Flutter assets. External popup destination is stubbed; source
// body review is separately recorded in the dated research report.
const {chromium} = require(process.env.PARENT_V2_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const base = (process.env.PARENT_V2_WEB_URL || 'http://127.0.0.1:8769/').replace(/\/$/, '') + '/';
const out = process.env.PARENT_V2_ARTIFACT_DIR || path.join(os.tmpdir(), 'openedu-comparison-articles');
fs.mkdirSync(out, {recursive: true});
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.PARENT_V2_CHROME, args: ['--disable-gpu']});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce', permissions: ['clipboard-read', 'clipboard-write']});
    await context.route('https://daechijang.tistory.com/**', route => route.fulfill({body: 'External navigation test destination'}));
    const page = await context.newPage(), errors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', e => {if (e.type() === 'error') errors.push(e.text());});
    const labels = () => page.locator('flt-semantics').evaluateAll(els => els.map(e => e.getAttribute('aria-label') || '').join('\n'));
    const waitText = text => page.waitForFunction(t => [...document.querySelectorAll('flt-semantics')].some(e => (e.getAttribute('aria-label') || '').includes(t)), text);
    const top = async () => {await page.mouse.move(200, 700); await page.mouse.wheel(0, -50000); await page.waitForTimeout(200);};
    await page.goto(base + '#/compare?ids=14435,3000030122,3000018730');
    await page.locator('flt-semantics-placeholder').waitFor({state: 'attached', timeout: 60000});
    await page.locator('flt-semantics-placeholder').evaluate(e => e.click());
    await waitText('선택한 3곳 중 2곳을 다룬 글');
    const partial = await labels();
    assert.match(partial, /이 글에서 비교하지 않은 곳: 에디센어학원/);
    assert.doesNotMatch(partial, /선택한 3곳 중 3곳을 다룬 글/);
    assert.match(partial, /브랜드·지역 참고 · 선택 지점 확인 필요/);
    assert.match(partial, /작성 후 2년이 지난 글/);
    // Source metadata is accessible without leaving the comparison.
    await page.mouse.move(1100, 900);
    await page.mouse.wheel(0, 800);
    await page.waitForTimeout(200);
    await page.getByRole('button', {name: '글의 범위·검토 정보', exact: true}).first().click();
    await waitText('본문·접근 확인 2026-10-18');
    assert.match(await labels(), /소마의 글 속 주소는 현재 선택한 대치소마 등록 주소와 달라/);
    assert.match(await labels(), /광고·협찬 여부는 확인하지 못했습니다/);
    await page.screenshot({path: path.join(out, 'articles-partial-desktop.png')});
    const [popup] = await Promise.all([
      page.waitForEvent('popup'),
      page.getByRole('button', {name: '비교 글 원문 읽기', exact: true}).first().click(),
    ]);
    await popup.waitForURL('https://daechijang.tistory.com/8');
    await popup.close();
    // A comparison link must not enter the unrelated third school's questions.
    await page.mouse.wheel(0, 50000);
    await page.waitForTimeout(300);
    await page.getByRole('button', {name: '이 학원 질문 복사', exact: true}).nth(2).click();
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    assert.match(clip, /에디센어학원 문의 질문/);
    assert.doesNotMatch(clip, /함께 읽은 비교 글:/);
    await page.waitForTimeout(4500); // allow the copy confirmation to leave
    await top();
    await page.getByRole('button', {name: '국어·논술', exact: true}).click();
    await waitText('이 조합·과목·학년에 연결해 검토한 비교 글은 아직 없어요');
    assert.equal(await page.getByRole('button', {name: '비교 글 원문 읽기', exact: true}).count(), 0);
    await page.getByRole('button', {name: '영어', exact: true}).click();
    await page.goto(base + '#/compare?ids=3000018730,1000036573,26427');
    await waitText('선택한 3곳 중 3곳을 다룬 글');
    const full = await labels();
    assert.match(full, /에디센 · 렉스김 · 알파/);
    assert.doesNotMatch(full, /이 글에서 비교하지 않은 곳:/);
    assert.match(full, /글 속 주소 대조 · 현재 운영 확인 필요/);
    await page.getByRole('checkbox', {name: '질문·피드백', exact: true}).click();
    await page.waitForTimeout(100);
    const prioritized = await labels();
    assert.ok(prioritized.indexOf('확인할 내용  질문 시간') < prioritized.indexOf('확인할 내용  시작 수준'));
    await page.mouse.move(1100, 800);
    await page.mouse.wheel(0, 720);
    await page.waitForTimeout(200);
    await page.screenshot({path: path.join(out, 'articles-three-desktop.png')});
    await top();
    await page.getByRole('checkbox', {name: '고등', exact: true}).click();
    await waitText('이 조합·과목·학년에 연결해 검토한 비교 글은 아직 없어요');
    await page.getByRole('checkbox', {name: '예비초~초3', exact: true}).click();
    await waitText('선택한 3곳 중 3곳을 다룬 글');
    const widths = [];
    for (const width of [320, 375, 768, 1440]) {
      await page.setViewportSize({width, height: 1100});
      await page.waitForTimeout(120);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
      widths.push(width);
      if (width === 375) {
        await page.mouse.move(200, 700);
        await page.mouse.wheel(0, 1350);
        await page.waitForTimeout(200);
        await page.screenshot({path: path.join(out, 'articles-three-mobile.png')});
        await top();
      }
    }
    // The Mokdong article also works with two registry-only candidates.
    await page.goto(base + '#/compare?ids=3000033068,3000035683,3000051192');
    await waitText('목동 초저 영어학원 비교 ②');
    assert.match(await labels(), /MI 목동 · 트윈클 목동 · 윌스 목동/);
    assert.deepEqual(errors, []);
    const result = {status: 'pass', widths, errors, checks: ['partial 2/3 with missing school named', 'source date vs body review date', 'historical and branch limitations', 'external link opens correct destination', 'unrelated school clipboard excludes pair article', 'subject and grade filtering', 'complete 3/3 coverage', 'feedback concern reorders separate axes', 'responsive layout', 'registry-only candidates keep article links'], scope: 'local compiled Flutter; external destination stubbed for navigation only; source body review in research report'};
    fs.writeFileSync(path.join(out, 'articles-browser.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally {await browser.close();}
})().catch(e => {console.error(e); process.exit(1);});

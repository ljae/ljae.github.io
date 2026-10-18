// Real compiled Flutter journey. Synthetic travel notes stay in an isolated
// browser profile. No private notes, request bodies, or credentials in artifacts.
const {chromium} = require(process.env.PARENT_V2_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const base = (process.env.PARENT_V2_WEB_URL || 'http://127.0.0.1:8769/').replace(/\/$/, '') + '/';
const out = process.env.PARENT_V2_ARTIFACT_DIR || path.join(os.tmpdir(), 'openedu-parent-journey');
fs.mkdirSync(out, {recursive: true});
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.PARENT_V2_CHROME, args: ['--disable-gpu']});
  const errors = [], checks = [], widths = [];
  let travelSent = false;
  let page;
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce', permissions: ['clipboard-read', 'clipboard-write']});
    let releaseAcademies, heldAcademies = false;
    const allowAcademies = new Promise(resolve => {releaseAcademies = resolve;});
    await context.route('**/assets/assets/data/academies.json', async route => {
      heldAcademies = true;
      await allowAcademies;
      await route.continue();
    });
    context.on('request', req => {
      if (/parent\.riding|guardianMinutes|oneWayMinutes|18%3A30/.test(req.url() + (req.postData() || ''))) travelSent = true;
    });
    await context.route('https://map.naver.com/**', route => route.fulfill({body: 'Map navigation destination test'}));
    page = await context.newPage();
    page.setDefaultTimeout(60000);
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', e => {if (e.type() === 'error') errors.push(e.text());});
    const labels = () => page.locator('flt-semantics').evaluateAll(els => els.map(e => e.getAttribute('aria-label') || e.textContent || '').join('\n'));
    const waitText = text => page.waitForFunction(t => [...document.querySelectorAll('flt-semantics')].some(e => (e.getAttribute('aria-label') || e.textContent || '').includes(t)), text);
    const button = name => page.getByRole('button', {name, exact: true});
    const chip = name => page.getByRole('checkbox', {name, exact: true});
    async function open(route, reload = false) {
      if (reload) await page.reload(); else await page.goto(base + route);
      await page.locator('flt-semantics-placeholder, flt-semantics').first().waitFor({state: 'attached'});
      if (await page.locator('flt-semantics-placeholder').count()) await page.locator('flt-semantics-placeholder').evaluate(e => e.click());
    }
    async function scroll(delta) {
      const {width, height} = page.viewportSize();
      await page.mouse.move(width * .7, height * .7);
      await page.mouse.wheel(0, delta);
      await page.waitForTimeout(180);
    }
    async function reveal(locator) {
      for (let i = 0; i < 45; i++) {
        const box = await locator.count() ? await locator.boundingBox() : null;
        if (box && box.y >= 70 && box.y + box.height < page.viewportSize().height - 5) return locator;
        await scroll(box && box.y < 80 ? -500 : 500);
      }
      throw Error('Could not reveal ' + locator);
    }
    async function edit(index, {days, daily, finish}) {
      await (await reveal(button('라이딩 메모 작성').nth(index))).click();
      await page.getByRole('button', {name: /이동 방법/}).click();
      await page.getByRole('menuitem', {name: '보호자 직접 라이딩', exact: true}).click();
      await page.getByRole('textbox', {name: '확인한 편도 이동 시간 · 선택', exact: true}).fill('15');
      await page.waitForTimeout(150); // allow Flutter's input frame before the next dropdown rebuild
      await page.getByRole('button', {name: /주간 등원 횟수/}).click();
      await page.getByRole('menuitem', {name: `주 ${days}회`, exact: true}).click();
      await (await reveal(page.getByRole('textbox', {name: '하루 보호자 이동·대기 시간 · 선택', exact: true}))).fill(String(daily));
      await page.waitForTimeout(150);
      await page.getByRole('textbox', {name: '검토 중인 하원 시각 · 선택', exact: true}).fill(finish);
      await page.waitForTimeout(150);
      await (await reveal(page.getByRole('button', {name: /내 일정에서의 하원 동선/}))).click();
      await page.getByRole('menuitem', {name: '내 판단: 하원 동선 가능', exact: true}).click();
      await (await reveal(button('내 기기에 저장'))).click();
      await waitText(`보호자 주간 이동·대기 ${days * daily}분`);
      console.log('Saved and rendered personal weekly burden:', days * daily);
      await page.waitForTimeout(4200);
    }
    console.log('Checking opening → exploration → ranking → detail');
    await open('');
    await button('숙제 부담이 걱정돼요').click();
    await button('이 고민으로 학원 살펴보기').click();
    await waitText('학원 목록을 불러오고 있어요. 준비되면 선택한 고민으로 이어집니다.');
    assert.equal(heldAcademies, true);
    releaseAcademies();
    await waitText('숙제 부담부터 살펴보고 있어요');
    console.log('Opening concern reached exploration');
    assert.equal(await chip('숙제 부담').getAttribute('aria-checked'), 'true');
    await (await reveal(button('전체 보기 →'))).click();
    await page.waitForURL('**/#/rank');
    await waitText('숙제 부담부터 살펴보고 있어요');
    console.log('Ranking kept the same concern');
    await open('#/academy/14435');
    await waitText('숙제로 집에서 푸는 교재인 소마셈과 팩토 키즈');
    console.log('Detail loaded the relevant actual excerpt');
    assert.match(await labels(), /숙제 부담 · 먼저 확인할 내용/);
    checks.push('opening concern continues into exploration, ranking and real detail excerpt');
    checks.push('delayed initial data resumes requested exploration without opening search');
    await (await reveal(chip('라이딩·하원'))).click();
    await waitText('라이딩·하원부터 살펴보고 있어요');
    assert.match(await labels(), /셔틀·하원 조건은 현재 반에 문의 필요/);
    const [map] = await Promise.all([page.waitForEvent('popup'), (async () => (await reveal(button('지도에서 동선 확인'))).click())()]);
    await map.waitForURL('https://map.naver.com/p/search/**');
    assert.ok(decodeURIComponent(map.url()).includes('서울'));
    await map.close();
    await edit(0, {days: 3, daily: 60, finish: '18:30'});
    assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('parent.riding.v1'))['14435/math/elem_low'].oneWayMinutes), 15);
    checks.push('public branch map and explicitly personal travel notes');
    await open('#/compare?ids=14435,3000030122');
    await waitText('보호자 주간 이동·대기 180분');
    assert.equal(await chip('라이딩·하원').getAttribute('aria-checked'), 'true');
    let content = await labels();
    assert.ok(content.indexOf('확인할 내용  등원·하원 동선') < content.indexOf('확인할 내용  시작 수준'));
    await reveal(button('라이딩 메모 수정'));
    assert.equal(await button('라이딩 메모 수정').count(), 1);
    assert.equal(await button('라이딩 메모 작성').count(), 1);
    await edit(0, {days: 2, daily: 30, finish: '19:15'});
    checks.push('riding priority and distinct weekly guardian burden for two academies');
    await scroll(-50000);
    await chip('고등').click();
    await waitText('내 이동 조건 · 고등 수학');
    assert.doesNotMatch(await labels(), /보호자 주간 이동·대기 (180|60)분/);
    await chip('예비초~초3').click();
    await waitText('보호자 주간 이동·대기 180분');
    await button('영어').click();
    await waitText('내 이동 조건 · 예비초~초3 영어');
    assert.doesNotMatch(await labels(), /보호자 주간 이동·대기 (180|60)분/);
    await button('수학').click();
    await waitText('보호자 주간 이동·대기 180분');
    await open('', true);
    await waitText('보호자 주간 이동·대기 180분');
    assert.match(await labels(), /보호자 주간 이동·대기 60분/);
    checks.push('subject and grade isolation plus full-page reload restoration');
    await (await reveal(button('학원 목록 링크 복사'))).click();
    const link = await page.evaluate(() => navigator.clipboard.readText());
    assert.equal(new URL(link).hash, '#/compare?ids=14435,3000030122');
    assert.doesNotMatch(link, /homework|riding|18:30|19:15|guardian|days/);
    await scroll(50000);
    await button('이 학원 질문 복사').first().click();
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    assert.match(clip, /하원 18:30/);
    assert.doesNotMatch(clip, /19:15/);
    checks.push('own schedule in school inquiry; shared URL contains only public IDs');
    await page.waitForTimeout(4200);
    await scroll(-50000);
    for (const width of [320, 375, 768, 1440]) {
      await page.setViewportSize({width, height: 1100});
      await page.waitForTimeout(150);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
      widths.push(width);
      await reveal(button('라이딩 메모 수정').first());
      await page.screenshot({path: path.join(out, `riding-compare-${width}.png`)});
      if (width === 375) {
        await button('라이딩 메모 수정').first().click();
        await page.screenshot({path: path.join(out, 'riding-editor-mobile.png')});
        await (await reveal(button('취소'))).click();
      }
      await scroll(-50000);
    }
    await page.emulateMedia({colorScheme: 'dark'});
    await reveal(button('라이딩 메모 수정').first());
    await page.screenshot({path: path.join(out, 'riding-compare-dark.png')});
    await page.emulateMedia({colorScheme: 'light'});
    await button('라이딩 메모 수정').first().click();
    await (await reveal(button('이 반의 메모 지우기'))).click();
    await open('', true);
    await waitText('보호자 주간 이동·대기 60분');
    assert.doesNotMatch(await labels(), /보호자 주간 이동·대기 180분/);
    await reveal(button('라이딩 메모 수정'));
    assert.equal(await button('라이딩 메모 수정').count(), 1);
    checks.push('per-class deletion survives reload and preserves other academy');
    await open('#/academy/3000033068');
    await waitText('셔틀·하원 조건은 현재 반에 문의 필요');
    await reveal(button('라이딩 메모 작성'));
    assert.equal(await button('라이딩 메모 작성').count(), 1);
    assert.doesNotMatch(await labels(), /보호자 주간 이동·대기 (180|60)분/);
    checks.push('registry-only academy exposes travel and preserves missing facts');
    assert.equal(travelSent, false);
    assert.deepEqual(errors, []);
    checks.push('no travel payload sent to server', 'four responsive widths and light/dark rendering');
    const result = {status: 'pass', scope: base, checkedAt: new Date().toISOString(), checks, widths, errors, limitation: 'Map destination stubbed; actual routes, shuttle operation and timetables are not verified.'};
    fs.writeFileSync(path.join(out, 'journey-browser.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } catch (error) {
    if (page) {
      await page.screenshot({path: path.join(out, 'journey-failure.png')}).catch(() => {});
      const labels = await page.locator('flt-semantics').evaluateAll(els => els.map(e => e.getAttribute('aria-label') || e.textContent || '').filter(Boolean));
      fs.writeFileSync(path.join(out, 'journey-failure-labels.json'), JSON.stringify(labels, null, 2));
    }
    throw error;
  } finally {await browser.close();}
})().catch(e => {console.error(e); process.exit(1);});

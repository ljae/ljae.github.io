// Smoke test for a local V2 build without Supabase configuration. See docs/PARENT_DECISION_IMPLEMENTATION.md.
const { chromium } = require(
  process.env.PARENT_V2_PLAYWRIGHT_MODULE || "playwright",
);
const assert = require("node:assert/strict"),
  fs = require("node:fs"),
  path = require("node:path"),
  os = require("node:os");
const baseUrl =
  (process.env.PARENT_V2_WEB_URL || "http://127.0.0.1:8769/").replace(
    /\/$/,
    "",
  ) + "/";
const artifactDir = process.env.PARENT_V2_ARTIFACT_DIR ||
  path.join(os.tmpdir(), "openedu-parent-v2-browser");
fs.mkdirSync(artifactDir, { recursive: true });
const rows = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, "../app/assets/data/academies.json"),
    "utf8",
  ),
);
(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.PARENT_V2_CHROME,
    args: ["--disable-gpu"],
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      reducedMotion: "reduce",
      permissions: ["clipboard-read", "clipboard-write"],
    });
    const page = await context.newPage();
    const errors = [], consoleErrors = [], writes = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => {
      if (m.type() === "error") consoleErrors.push(m.text());
    });
    page.on("request", (r) => {
      if (r.method() !== "GET") writes.push(r.url());
    });
    async function open(path) {
      await page.goto(baseUrl + path);
      await page.locator("flt-glass-pane").waitFor({
        state: "attached",
        timeout: 60000,
      });
      try {
        await page.locator("flt-semantics-placeholder").waitFor({
          state: "attached",
          timeout: 15000,
        });
        await page.locator("flt-semantics-placeholder").evaluate((e) =>
          e.click()
        );
      } catch {}
      await page.locator("flt-semantics").first().waitFor({
        state: "attached",
      });
    }
    const labels = () =>
      page.locator("flt-semantics").evaluateAll((els) =>
        els.map((e) => e.getAttribute("aria-label") || "").join("\n")
      );
    await open("");
    await page.getByRole("button", {
      name: "숙제 부담이 걱정돼요",
      exact: true,
    }).click();
    await page.waitForTimeout(100);
    assert.match(await labels(), /하루 숙제 분량/);
    assert.equal(
      await page.evaluate(() => localStorage.getItem("parent.concern.v2")),
      "homework",
    );
    await page.getByRole("button", { name: "의견 남기기", exact: true })
      .click();
    await page.getByRole("button", {
      name: "비공개로 의견 보내기",
      exact: true,
    }).waitFor({ state: "attached" });
    assert.match(await labels(), /현재 의견 접수를 준비 중/);
    assert.equal(
      await page.getByRole("button", {
        name: "비공개로 의견 보내기",
        exact: true,
      }).isDisabled(),
      true,
    );
    await page.keyboard.press("Escape");
    let escapeClosed = true;
    try {
      await page.getByRole("button", {
        name: "닫기 · 작성 내용 삭제",
        exact: true,
      }).waitFor({ state: "detached", timeout: 5000 });
    } catch {
      escapeClosed = false;
      await page.getByRole("button", {
        name: "닫기 · 작성 내용 삭제",
        exact: true,
      }).click();
    }
    const ids = rows.slice(0, 4).map((r) => r.id);
    await open("#/compare?ids=" + ids.join(","));
    await page.getByRole("button", { name: "비교 초기화", exact: true })
      .waitFor();
    assert.equal(
      (await page.evaluate(() => localStorage.getItem("parent.compare.v2")))
        .split(",").length,
      3,
    );
    assert.match(page.url(), /#\/compare/);
    await page.setViewportSize({ width: 375, height: 900 });
    await page.waitForTimeout(150);
    await page.screenshot({
      path: path.join(artifactDir, "app-comparison-mobile.png"),
    });
    await open("#/academy/" + rows[0].id);
    assert.match(page.url(), /#\/academy/);
    await page.getByRole("button", { name: "비교 담기", exact: true }).or(
      page.getByRole("button", { name: "비교에서 빼기", exact: true }),
    ).first().waitFor();
    await open("#/feedback");
    assert.equal(
      await page.getByRole("button", {
        name: "비공개로 의견 보내기",
        exact: true,
      }).isDisabled(),
      true,
    );
    assert.equal(writes.length, 0);
    await open("");
    await page.screenshot({
      path: path.join(artifactDir, "app-opening-mobile.png"),
    });
    const viewports = [];
    for (const width of [320, 375, 768, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.waitForTimeout(80);
      viewports.push({
        width,
        documentWidth: await page.evaluate(() =>
          document.documentElement.scrollWidth
        ),
      });
      assert.equal(viewports.at(-1).documentWidth, width);
    }
    await page.screenshot({
      path: path.join(artifactDir, "app-opening-desktop.png"),
    });
    await page.emulateMedia({ colorScheme: "dark" });
    await page.waitForTimeout(100);
    await page.screenshot({
      path: path.join(artifactDir, "app-opening-dark.png"),
    });
    assert.deepEqual(errors, []);
    assert.equal(
      consoleErrors.filter((s) => /overflow|exception|error/i.test(s)).length,
      0,
    );
    const result = {
      status: "pass",
      scope: "compiled Flutter web, local assets, no Supabase configuration",
      checks: [
        "concern changes question and persists",
        "voice unconfigured state disables submission",
        "compare URL restores and bounds three public IDs",
        "academy deep link",
        "no write requests",
        "mobile desktop dark reduced motion",
      ],
      escapeClosesSheet: escapeClosed,
      viewports,
      pageErrors: errors,
      consoleErrors,
    };
    fs.writeFileSync(
      path.join(artifactDir, "browser-flows.json"),
      JSON.stringify(result, null, 2),
    );
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

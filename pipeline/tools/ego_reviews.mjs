// Executed by ego_reviews.collect via `ego-browser nodejs` stdin. The Python
// wrapper injects __EDUTREE_EGO_OPTIONS__ as a JSON literal (never shell code).
// DOM selectors grounded against live Naver blog/cafe tabs on 2026-10-17.
// Only public search cards are read. Never visit an article or save full HTML.
const options = __EDUTREE_EGO_OPTIONS__;
const marker = "EDUTREE_EGO_REVIEWS_JSON:";
const emit = (status, rows = []) => console.log(marker + JSON.stringify({ status, rows }));

function errorStatus(error) {
  const message = String(error?.message || error).toLowerCase();
  if (/user.control|user-owned|ownership|inactive|unassigned|not agent-owned|사용자 제어/.test(message)) return "user_control";
  if (/captcha|robot|blocked|access denied|자동입력|접근 제한/.test(message)) return "blocked";
  if (/login.required|sign in required|로그인이 필요/.test(message)) return "login_required";
  if (/timeout|timed out/.test(message)) return "timeout";
  return "browser_error";
}

try {
  // Resuming a numeric id never creates a recovery space or claims user control.
  const task = await taskSpace(options.spaceId);
  if (task.ownership && task.ownership !== "agent") {
    emit("user_control");
  } else {
    const page = task.page("p1");
    const started = Date.now();
    const budget = () => Math.max(500, options.timeoutMs - (Date.now() - started));
    await page.goto(options.searchUrl, { timeout: budget(), waitUntil: "domcontentloaded" });
    // Naver populates cards asynchronously; a generic blog/profile link is not
    // proof that results have loaded. An unknown DOM must time out, not return 0.
    await page.waitForFunction(({ source }) => {
      const text = document.body?.innerText || "";
      const selector = source === "naver_blog" ? '[data-template-id="ugcItem"]' : ".view_wrap";
      return Boolean(document.querySelector(selector)) ||
        /검색결과가 없습니다|검색 결과가 없습니다|검색결과를 찾을 수 없습니다/.test(text) ||
        /자동입력 방지|자동 입력 방지|비정상적인 접근|접근이 제한|로봇이 아닙니다/.test(text) ||
        location.hostname === "nid.naver.com";
    }, { source: options.source }, { timeout: budget() });

    const result = await page.evaluate(({ source, limit, query }) => {
      const pageText = document.body?.innerText || "";
      if (/자동입력 방지|자동 입력 방지|비정상적인 접근|접근이 제한|로봇이 아닙니다/.test(pageText)) {
        return { status: "blocked", rows: [] };
      }
      if (location.hostname === "nid.naver.com" || /로그인이 필요합니다|로그인 후 이용해 주세요/.test(pageText)) {
        return { status: "login_required", rows: [] };
      }
      const current = new URL(location.href);
      const tab = source === "naver_blog" ? "tab.blog.all" : "tab.cafe.all";
      if (current.hostname !== "search.naver.com" || current.searchParams.get("ssc") !== tab || current.searchParams.get("query") !== query) {
        return { status: "browser_error", rows: [] };
      }
      const text = (element, length) => (element?.innerText || "").replace(/\s+/g, " ").trim().slice(0, length);
      const isShown = (element) => Boolean(element?.getClientRects().length) &&
        getComputedStyle(element).visibility !== "hidden" && getComputedStyle(element).display !== "none";
      const datePattern = /^(?:20\d{2}[.\-/]\s*\d{1,2}[.\-/]\s*\d{1,2}\.?|\d{1,4}\s*(?:일|시간|분|초)\s*전|오늘|어제|방금(?:\s*전)?)$/;
      const selector = source === "naver_blog" ? '[data-template-id="ugcItem"]' : ".view_wrap";
      const cards = [...document.querySelectorAll(selector)].filter(isShown).slice(0, 100);
      const rows = [];
      for (const card of cards) {
        // Dedicated tabs and recognized cards exclude generated AI briefings,
        // navigation links, author profiles and search suggestions.
        const headline = source === "naver_blog"
          ? card.querySelector(".sds-comps-text-type-headline1")
          : card.querySelector(".title_area a");
        const anchor = headline?.closest("a");
        if (!anchor || !isShown(anchor)) continue;
        let url;
        try { url = new URL(anchor.href); } catch { continue; }
        const expected = source === "naver_blog" ? ["blog.naver.com", "m.blog.naver.com"] : ["cafe.naver.com", "m.cafe.naver.com"];
        if (!expected.includes(url.hostname) || !["https:", "http:"].includes(url.protocol)) continue;
        const description = source === "naver_blog"
          ? card.querySelector(".fds-ugc-ellipsis3 .sds-comps-text-type-body1, .fds-ugc-ellipsis2 .sds-comps-text-type-body1")
          : card.querySelector(".dsc_area a");
        const dateRoot = source === "naver_blog"
          ? card.querySelector('[data-template-id="articleSource"]')
          : card.querySelector(".user_box");
        const dateNodes = dateRoot ? [dateRoot, ...dateRoot.querySelectorAll("span, time")] : [];
        // A standalone date in the source metadata only: a year mentioned in
        // the review snippet is not a publication date.
        const dateLabel = dateNodes.filter(isShown).map(node => text(node, 80)).find(value => datePattern.test(value)) || null;
        const title = text(headline, 200);
        if (!title) continue;
        // Drop tracking tokens before crossing the browser/process boundary.
        const knownQuery = new URLSearchParams();
        for (const key of ["blogId", "logNo", "clubid", "articleid"]) {
          if (url.searchParams.has(key)) knownQuery.set(key, url.searchParams.get(key));
        }
        url.search = knownQuery.toString();
        url.hash = "";
        rows.push({ url: url.href, title, snippet: isShown(description) ? text(description, 600) : "", date_text: dateLabel });
        if (rows.length >= limit) break;
      }
      if (rows.length) return { status: "ok", rows };
      if (!cards.length && /검색결과가 없습니다|검색 결과가 없습니다|검색결과를 찾을 수 없습니다/.test(pageText)) {
        return { status: "empty", rows: [] };
      }
      return { status: "parse_error", rows: [] };
    }, { source: options.source, limit: options.limit, query: options.query });
    emit(result.status, result.rows);
  }
} catch (error) {
  // Raw errors can contain page content, usernames or browser state. Emit only
  // the category; the Python caller keeps failures separate from empty success.
  emit(errorStatus(error));
}

const { test, expect } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

const projectRoot = path.resolve(__dirname, "../..");

async function loadScript(page, relativePath) {
  await page.addScriptTag({
    content: fs.readFileSync(path.join(projectRoot, relativePath), "utf8"),
  });
}

async function fireDomReady(page) {
  await page.evaluate(() => {
    document.dispatchEvent(new Event("DOMContentLoaded", { bubbles: true }));
  });
}

test.describe("public-site controls", () => {
  test("scroll-to-top button becomes visible and scrolls to the top", async ({ page }) => {
    await page.setContent(`
      <body class="public-site">
        <main class="site-content"><section data-reveal></section></main>
        <button id="scrollToTopBtn" hidden>top</button>
      </body>
    `);
    await page.evaluate(() => {
      window.scrollTo = (options) => { window.__scrollOptions = options; };
      window.matchMedia = () => ({ matches: true, addListener() {}, removeListener() {} });
    });
    await loadScript(page, "assets/js/home-refactor.js");
    await fireDomReady(page);

    await page.evaluate(() => {
      Object.defineProperty(window, "scrollY", { configurable: true, value: 500 });
      window.dispatchEvent(new Event("scroll"));
    });
    await expect(page.locator("#scrollToTopBtn")).toBeVisible();
    await page.locator("#scrollToTopBtn").click();
    await expect.poll(() => page.evaluate(() => window.__scrollOptions)).toEqual({ top: 0, behavior: "auto" });
  });

  test("off-canvas menu is exposed as a dialog and closes on Escape", async ({ page }) => {
    await page.setContent(`
      <body class="public-site">
        <header class="modern-header">
          <button aria-label="باز کردن منو"></button>
          <div class="modern-offcanvas__panel translate-x-0">
            <button aria-label="بستن منو" onclick="window.__closed = true"></button>
          </div>
        </header>
      </body>
    `);
    await loadScript(page, "assets/js/home-refactor.js");
    await fireDomReady(page);

    const panel = page.locator(".modern-offcanvas__panel");
    await expect(panel).toHaveAttribute("role", "dialog");
    await expect(panel).toHaveAttribute("aria-modal", "true");
    await page.keyboard.press("Escape");
    await expect.poll(() => page.evaluate(() => window.__closed === true)).toBe(true);
  });

  test("Swiper slider configuration wires navigation controls", async ({ page }) => {
    await page.setContent(`
      <div class="col3-swiper-slider">
        <div class="swiper-button-prev"></div><div class="swiper-button-next"></div>
      </div>
    `);
    await page.evaluate(() => {
      window.__swiperCalls = [];
      window.Swiper = function(selector, options) {
        window.__swiperCalls.push({ selector, options });
      };
      window.Plyr = function() {};
    });
    await loadScript(page, "assets/js/app.js");

    const call = await page.evaluate(() => window.__swiperCalls.find((item) => item.selector === ".col3-swiper-slider"));
    expect(call.options.navigation).toEqual({ nextEl: ".swiper-button-next", prevEl: ".swiper-button-prev" });
    expect(call.options.breakpoints[992].slidesPerView).toBe(3);
  });

  test("episode buttons load the first episode and switch the video source", async ({ page }) => {
    await page.setContent(`
      <video id="episode-video"><source id="video-source" src=""></video>
      <a href="#" data-episode-trigger data-video-url="/episodes/1.mp4">one</a>
      <a href="#" data-episode-trigger data-video-url="/episodes/2.mp4">two</a>
    `);
    await page.evaluate(() => {
      const video = document.getElementById("episode-video");
      video.load = () => { window.__loadCount = (window.__loadCount || 0) + 1; };
      video.play = () => Promise.resolve();
    });
    await loadScript(page, "assets/js/course-episodes.js");
    await fireDomReady(page);
    await expect(page.locator("#video-source")).toHaveAttribute("src", "/episodes/1.mp4");
    await page.locator('[data-episode-trigger]').nth(1).click();
    await expect(page.locator("#video-source")).toHaveAttribute("src", "/episodes/2.mp4");
    await expect.poll(() => page.evaluate(() => window.__loadCount)).toBe(2);
  });
});

test.describe("account and comment interactions", () => {
  test("analysis metric and calendar controls update filters and submit", async ({ page }) => {
    await page.setContent(`
      <section data-analysis-root data-jalali-year="1404">
        <button type="button" data-analysis-metric-toggle aria-expanded="false">
          <span data-analysis-metric-label>درصد چربی بدن</span>
        </button>
        <div data-analysis-metric-menu hidden>
          <button type="button" data-analysis-metric="weight">وزن</button>
        </div>
        <input data-analysis-start value="1404/01/01">
        <input data-analysis-end value="1404/01/02">
        <div data-analysis-calendar hidden>
          <strong data-analysis-calendar-title></strong>
          <div data-analysis-calendar-grid></div>
          <button type="button" data-analysis-calendar-prev>prev</button>
          <button type="button" data-analysis-calendar-next>next</button>
          <button type="button" data-analysis-calendar-confirm>confirm</button>
        </div>
        <form data-analysis-filter-form>
          <input data-analysis-metric-input>
          <input data-analysis-start-input>
          <input data-analysis-end-input>
        </form>
        <div data-analysis-chart-card></div><div data-analysis-empty></div>
      </section>
    `);
    await page.evaluate(() => {
      const form = document.querySelector("form");
      form.submit = () => { window.__submitCount = (window.__submitCount || 0) + 1; };
    });
    await loadScript(page, "assets/js/account-user.js");
    await fireDomReady(page);

    await page.locator("[data-analysis-metric-toggle]").click();
    await expect(page.locator("[data-analysis-metric-menu]")).toBeVisible();
    await page.locator('[data-analysis-metric="weight"]').click();
    await expect(page.locator("[data-analysis-metric-label]")).toHaveText("وزن");
    await expect(page.locator("[data-analysis-metric-input]")).toHaveValue("weight");

    await page.locator("[data-analysis-start]").click();
    await expect(page.locator("[data-analysis-calendar]")).toBeVisible();
    await page.locator('[data-analysis-calendar-grid] button[data-day="5"]').click();
    await page.locator('[data-analysis-calendar-grid] button[data-day="10"]').click();
    await page.locator("[data-analysis-calendar-confirm]").click();
    await expect(page.locator("[data-analysis-start]")).toHaveValue("1404/01/05");
    await expect(page.locator("[data-analysis-end]")).toHaveValue("1404/01/10");
    await expect.poll(() => page.evaluate(() => window.__submitCount)).toBe(2);
  });

  test("auth forms show loading state and reset when browser validation fails", async ({ page }) => {
    await page.setContent(`
      <body class="auth-page">
        <section class="auth-mobile-form"><form><button type="submit">ورود</button></form></section>
      </body>
    `);
    await loadScript(page, "assets/js/auth-refactor.js");
    await fireDomReady(page);
    const button = page.locator("button[type=submit]");
    await page.locator("form").dispatchEvent("submit");
    await expect(button).toHaveClass(/is-loading/);
    await expect(button).toHaveAttribute("aria-busy", "true");
    await expect(button).toHaveText("لطفاً صبر کنید…");
    await page.locator("form").dispatchEvent("invalid");
    await expect(button).not.toHaveClass(/is-loading/);
    await expect(button).toHaveText("ورود");
  });

  test("OTP resend timer enables the link after its cooldown", async ({ page }) => {
    await page.setContent(`
      <body class="auth-page">
        <div data-otp-timers data-expires-in="2" data-cooldown-remaining="1">
          <span data-otp-expiry-value></span>
          <span data-otp-resend><span data-otp-resend-value></span></span>
        </div>
        <a href="/resend" data-otp-resend-link>resend</a>
      </body>
    `);
    await loadScript(page, "assets/js/auth-refactor.js");
    await fireDomReady(page);
    await expect(page.locator("[data-otp-resend-link]")).toHaveAttribute("aria-disabled", "true");
    await page.waitForTimeout(1_100);
    await expect(page.locator("[data-otp-resend-link]")).not.toHaveAttribute("aria-disabled");
    await expect(page.locator("[data-otp-resend]")).toBeHidden();
  });

  test("comment validation blocks short text and AJAX success replaces the comments section", async ({ page }) => {
    await page.setContent(`
      <section id="tabThree" data-comment-endpoint="/course/1/">
        <form id="comment-form"><textarea name="text"></textarea><button type="submit">ثبت دیدگاه</button></form>
      </section>
    `);
    await page.evaluate(() => {
      window.__fetchCalls = [];
      window.fetch = (...args) => {
        window.__fetchCalls.push(args);
        return Promise.resolve({
          ok: true,
          text: () => Promise.resolve('<section id="tabThree" data-comment-endpoint="/course/1/"><p>submitted</p></section>'),
        });
      };
    });
    await loadScript(page, "assets/js/course-comments.js");
    await fireDomReady(page);

    await page.locator("textarea").fill("bad");
    await page.locator("button").click();
    await expect(page.locator(".success-message")).toContainText("حداقل در ۵ کاراکتر");
    expect(await page.evaluate(() => window.__fetchCalls.length)).toBe(0);

    await page.locator("textarea").fill("این یک دیدگاه معتبر است");
    await page.locator("button").click();
    await expect(page.locator("#tabThree")).toContainText("submitted");
    await expect.poll(() => page.evaluate(() => window.__fetchCalls.length)).toBe(1);
    expect(await page.evaluate(() => window.__fetchCalls[0][0])).toBe("/course/1/");
  });
});

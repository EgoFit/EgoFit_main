const { test, expect } = require('@playwright/test');

for (const [name, path, width] of [['home','/',390], ['blog','/blog/',768]]) {
  test(`${name} menu and theme debug`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    page.on('console', message => { if (message.type() === 'error' || message.type() === 'warning') errors.push(`${message.type()}: ${message.text()}`); });
    await page.goto(`http://127.0.0.1:8000${path}`);
    await page.waitForTimeout(800);
    const initial = await page.evaluate(() => ({
      display: getComputedStyle(document.querySelector('.modern-offcanvas')).display,
      panelDisplay: getComputedStyle(document.querySelector('#site-mobile-menu')).display,
      transform: getComputedStyle(document.querySelector('#site-mobile-menu')).transform,
      theme: document.documentElement.classList.contains('dark'),
      darkMode: Alpine.$data(document.documentElement).darkMode
    }));
    console.log(name, initial);
    console.log(name, 'browser errors', errors);
    expect(initial.display).toBe('none');
    expect(initial.transform).toBe('none');
    await page.locator('.modern-menu-toggle').click();
    await expect(page.locator('.modern-offcanvas')).toBeVisible();
    await expect(page.locator('#site-mobile-menu')).toBeVisible();
    await page.locator('#site-mobile-menu button[aria-label="بستن منو"]').click();
    await expect(page.locator('.modern-offcanvas')).toBeHidden();
    await page.locator('header button[aria-label="تغییر حالت تاریک"]').click();
    await expect.poll(() => page.evaluate(() => document.documentElement.classList.contains('dark'))).toBe(true);
  });
}

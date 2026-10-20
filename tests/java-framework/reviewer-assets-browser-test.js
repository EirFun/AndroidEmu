// SPDX-License-Identifier: GPL-2.0-or-later
// First generate the HTML fixture with AnkiReviewerAssetsTest and an official APK.
// Requires Playwright and Chromium; this checks desktop JS execution, not iOS WebKit.
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
    const browser = await chromium.launch({
        executablePath: process.env.CHROMIUM_PATH || '/usr/lib/chromium/chromium',
        headless: true,
        timeout: 15000,
        args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    });
    try {
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        // Host-only substitute for the app's Android keyboard bridge. Never shipped in the IPA.
        const keyboard = '<script>window.AnkiDroidKeyboard={setNoSuggest:function(){}};</script>';
        await page.setContent(keyboard + fs.readFileSync(process.argv[2], 'utf8'), {
            waitUntil: 'domcontentloaded', timeout: 15000,
        });
        const exports = await page.evaluate(() => ({ question: typeof _showQuestion, answer: typeof _showAnswer }));
        if (exports.question !== 'function' || exports.answer !== 'function') throw new Error('Reviewer exports missing');
        await page.evaluate(() => _showQuestion('<div id="host-card">Question text</div>', 'Answer text', 'card'));
        await page.waitForSelector('#host-card', { timeout: 5000 });
        if (await page.locator('#qa').textContent() !== 'Question text') throw new Error('Question did not render');
        await page.evaluate(() => _showAnswer('<div id="host-answer">Answer text</div>', 'card'));
        await page.waitForSelector('#host-answer', { timeout: 5000 });
        if (await page.locator('#qa').textContent() !== 'Answer text') throw new Error('Answer did not render');
        if (errors.length) throw new Error(errors.join('\n'));
        console.log('PASS: actual APK reviewer scripts initialize and render a plain question and answer in Chromium');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error.message); process.exitCode = 1; });

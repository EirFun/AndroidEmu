// SPDX-License-Identifier: GPL-2.0-or-later
// Reproduces the page-world eval failure in Chromium. This is not a WebKit or
// Objective-C integration test; native callback JSON serialization needs iOS.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({
        executablePath: process.env.CHROMIUM_PATH || '/usr/lib/chromium/chromium',
        headless: true,
        args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    try {
        const page = await browser.newPage();
        // Run the old wrapper in an allowed page script: DevTools evaluation can
        // bypass CSP even for nested eval, which would hide the original failure.
        await page.setContent(`<meta http-equiv="Content-Security-Policy" content="script-src 'self' 'nonce-husk-test'">
            <script nonce="husk-test">
                window.evalBlocked = false;
                try { (0, eval)('1 + 2'); }
                catch (error) { window.evalBlocked = error.name === 'EvalError'; }
            </script>`);
        const blocked = await page.evaluate(() => window.evalBlocked);
        assert.equal(blocked, true, 'The original eval wrapper must fail under CSP');
        // Inject the source directly using the browser API, as the native fix does.
        // Include statements and expressions so no expression-only rewrite is assumed.
        const cases = [
            ['1 + 2', 3],
            ['"a string"', 'a string'],
            ['true', true],
            ['null', null],
            ['({ready:true, values:[1,"two",null]})', { ready: true, values: [1, 'two', null] }],
            ['var bridgeCommand = function(request) { window.lastRequest = request; };', undefined],
            ['bridgeCommand("ready"); window.lastRequest', 'ready'],
        ];
        for (const [source, expected] of cases) {
            assert.deepEqual(await page.evaluate(source), expected);
        }
        await assert.rejects(page.evaluate('throw new Error("test error")'), /test error/);
        console.log('PASS: strict CSP blocks the old eval wrapper; direct browser execution handles expressions, statements and errors');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });

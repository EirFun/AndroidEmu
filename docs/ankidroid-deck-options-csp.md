# AnkiDroid Deck Options: native JavaScript evaluation under CSP

AnkiDroid 2.26.0alpha6 Deck Options opens `/deck-options/<deck-id>` in a WebView.
The bundled page retains its strict `script-src` policy. Husk's native
`W_eval` implementation previously passed callback-bearing scripts through
`(0, eval)(source)`. WebKit rejects this page-world eval with an `EvalError`.
Scripts submitted without a callback already used direct native evaluation.

The source change runs both paths with `WKWebView.evaluateJavaScript`, then
serializes callback results in Objective-C. Strings retain JSON quotes;
objects, arrays, numbers, booleans and null use JSON serialization. Undefined,
unsupported results and evaluation errors yield `"null"` to the Java callback.
The page's Content Security Policy remains intact.

The device report shows three CSP failures, followed by POST requests for
`i18nResources` and `getDeckConfigsForUpdate`, without a visible Deck Options
screen. The CSP failure is confirmed; it is not yet established that this fix
alone resolves the stall. The report does not include POST completion status.

Run `node tests/java-framework/web-eval-csp-browser-test.js` for a desktop
Chromium reproduction of the old failure and direct-execution alternative.
This does not test Objective-C compilation, WebKit result conversion, or the
Android-to-iOS callback round trip. A native iOS build and device testing are
still required. The downloadable v10 IPA does not contain this native change.

## Missing card images are a separate issue

The v10 report logs `mediaDirectory=true directoryReadable=true imageFile=false`
for the requested images. Requests return 404, and the browser reports natural
image dimensions of zero. This establishes that the read-only fallback could
not resolve those names in the configured media directory. It does not prove
that no copy exists elsewhere or that a media sync has completed.

The sample APKG was exported on Windows for inspection. It has not been
confirmed imported into AnkiDroid inside Husk. Importing it with its media is
a useful independent test. If it displays correctly, investigate media sync
for the original collection; if it also fails, inspect the import outcome and
the actual media directory before changing rendering again.

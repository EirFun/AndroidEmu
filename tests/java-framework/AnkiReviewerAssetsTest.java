// SPDX-License-Identifier: GPL-2.0-or-later
import husk.AnkiReviewerAssets;
import husk.Native;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.zip.ZipFile;

public final class AnkiReviewerAssetsTest {
    public static void main(String[] args) throws Exception {
        Native.currentPackage = "com.ichi2.anki";
        Native.assets.clear();
        Native.assets.put("backend/js/reviewer.js", "window._showQuestion = function () {return '$1 \\ literal </SCRIPT>';};".getBytes(StandardCharsets.UTF_8));
        String script = "<script src=\"file:///android_asset/backend/js/reviewer.js\"></script>";
        String html = "<!doctype html><html><body>" + script + "</body></html>";
        String result = AnkiReviewerAssets.prepare(html, "text/html");
        require(result.contains("window._showQuestion = function"), "Actual APK script bytes must replace the URL");
        require(result.contains("$1 \\ literal <\\/script>"), "Replacement must preserve dollar/backslash text and neutralize case-insensitive HTML end tags");
        require(result.contains("Husk reviewer ready:"), "Reviewer readiness diagnostic must be present");
        require(!result.contains("src=\"huskapp://android_asset/backend/js/reviewer.js\""), "Inlined script must no longer make an asset request");
        String unknown = "<script src='file:///android_asset/user.js'></script>";
        Native.assets.put("user.js", "throw new Error('must not inline');".getBytes(StandardCharsets.UTF_8));
        require(!AnkiReviewerAssets.prepare(unknown, "text/html").contains("must not inline"), "Unlisted card scripts must stay external");
        for (String attributes : new String[] {"type='module' ", "defer ", "async "}) {
            String special = "<script " + attributes + "src='file:///android_asset/backend/js/reviewer.js'></script>";
            require(!AnkiReviewerAssets.prepare(special, "text/html").contains("window._showQuestion ="), "Nonclassic script semantics must be preserved");
        }
        Native.assets.clear();
        require(AnkiReviewerAssets.prepare(html, "text/html").contains("src=\"huskapp://"), "Missing asset must retain URL fallback");
        require(html.equals(AnkiReviewerAssets.prepare(html, "text/plain")), "Non-HTML content must be unchanged");
        Native.currentPackage = "another.app";
        Native.assets.put("backend/js/reviewer.js", "must not inline".getBytes(StandardCharsets.UTF_8));
        require(!AnkiReviewerAssets.prepare(html, "text/html").contains("must not inline"), "Other apps must retain v5 behavior");
        Native.currentPackage = "com.ichi2.anki";
        if (args.length == 2) {
            StringBuilder page = new StringBuilder("<!doctype html><html><head>");
            try (ZipFile apk = new ZipFile(args[0])) {
                for (String path : new String[] {"backend/js/jquery.min.js", "backend/js/reviewer.js", "scripts/ankidroid-cardviewer.js", "scripts/ankidroid-reviewer.js", "scripts/type-answer.js", "backend/css/root-vars.css", "backend/css/reviewer.css", "ankidroid.css"}) {
                    try (java.io.InputStream stream = apk.getInputStream(apk.getEntry("assets/" + path))) {
                        java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
                        byte[] buffer = new byte[16384];
                        for (int n; (n = stream.read(buffer)) != -1;) bytes.write(buffer, 0, n);
                        Native.assets.put(path, bytes.toByteArray());
                    }
                    if (path.endsWith(".css")) page.append("<link rel=\"stylesheet\" type=\"text/css\" href=\"file:///android_asset/").append(path).append("\">");
                }
            }
            page.append("</head><body><div id='qa'></div>");
            for (String path : new String[] {"backend/js/jquery.min.js", "backend/js/reviewer.js", "scripts/ankidroid-cardviewer.js", "scripts/ankidroid-reviewer.js", "scripts/type-answer.js"}) page.append("<script src=\"file:///android_asset/").append(path).append("\"></script>");
            page.append("<script>document.body.setAttribute('data-reviewer-test',typeof window._showQuestion);</script></body></html>");
            Files.write(Paths.get(args[1]), AnkiReviewerAssets.prepare(page.toString(), "text/html").getBytes(StandardCharsets.UTF_8));
        }
        System.out.println("PASS: known reviewer assets inline safely; missing/unlisted/other-app/non-HTML cases retain fallback");
    }

    private static void require(boolean condition, String reason) {
        if (!condition) throw new AssertionError(reason);
    }
}

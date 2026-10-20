// SPDX-License-Identifier: GPL-2.0-or-later
import husk.HtmlResourceUrls;

public final class HtmlResourceUrlsTest {
    public static void main(String[] args) {
        String document = "<link href=\"file:///android_asset/backend/css/reviewer.css\">"
                + "<script src='file:///android_asset/backend/js/jquery.min.js'></script>"
                + "<script src='file:///android_asset/backend/js/reviewer.js?v=1#x'></script>"
                + "<script src='file:///android_asset/scripts/ankidroid-cardviewer.js'></script>";
        String expected = document.replace("file:///android_asset/", "huskapp://android_asset/");
        require(expected.equals(HtmlResourceUrls.rewrite(document, "text/html")), "Reviewer scripts and styles must use the registered asset scheme");
        require(expected.equals(HtmlResourceUrls.rewrite(document, null)), "Default HTML MIME must work");
        require(expected.equals(HtmlResourceUrls.rewrite(document, "TEXT/HTML; charset=utf-8")), "HTML MIME parameters and case must work");
        require(expected.equals(HtmlResourceUrls.rewrite(document, "application/xhtml+xml")), "XHTML assets must be routed");
        require(expected.equals(HtmlResourceUrls.rewrite(expected, "text/html")), "Rewriting must be repeatable");
        require(document.equals(HtmlResourceUrls.rewrite(document, "text/plain")), "Non-HTML content must not be changed");
        String external = "https://example.com/x.js http://127.0.0.1:56116/api file:///private/user-data";
        require(external.equals(HtmlResourceUrls.rewrite(external, "text/html")), "Network and ordinary local-file URLs must remain unchanged");
        require("".equals(HtmlResourceUrls.rewrite(null, null)), "Null data must retain empty-document behavior");
        require("huskapp://android_res/drawable/a.png".equals(HtmlResourceUrls.rewrite("file:///android_res/drawable/a.png", "text/html")), "Android resource URLs must match top-level conversion");
        System.out.println("PASS: embedded reviewer assets route through Husk's scheme without changing other URLs or non-HTML data");
    }

    private static void require(boolean condition, String reason) {
        if (!condition) throw new AssertionError(reason);
    }
}

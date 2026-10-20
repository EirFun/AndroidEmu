// SPDX-License-Identifier: GPL-2.0-or-later
package husk;

import android.util.Log;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Temporary AnkiDroid workaround for reviewer assets failing to load through WebKit. */
public final class AnkiReviewerAssets {
    private static final String TAG = "HuskAnkiAssets";
    private static final String ASSET = "(?:file:///android_asset/|huskapp://android_asset/)";
    private static final Pattern SCRIPT = Pattern.compile("<script\\s+src\\s*=\\s*([\"'])" + ASSET + "([^\"']+)\\1\\s*>\\s*</script\\s*>", Pattern.CASE_INSENSITIVE);
    private static final Pattern STYLE = Pattern.compile("<link\\s+rel=([\"'])stylesheet\\1\\s+type=([\"'])text/css\\2\\s+href=([\"'])" + ASSET + "([^\"']+)\\3\\s*/?>", Pattern.CASE_INSENSITIVE);

    private AnkiReviewerAssets() {}

    public static String prepare(String data, String mimeType) {
        String html = HtmlResourceUrls.rewrite(data, mimeType);
        if (!"com.ichi2.anki".equals(Native.packageName()) || !isHtml(mimeType)) return html;
        // Only the known, synchronous classic scripts from AnkiDroid's stdHtml are inlined.
        // Card-template scripts, remote URLs, modules and deferred scripts are left alone.
        html = inline(html, SCRIPT, 2, true);
        html = inline(html, STYLE, 4, false);
        String probe = "<script>console.log('Husk reviewer ready: jquery=' + typeof window.jQuery + ' _showQuestion=' + typeof window._showQuestion);</script>";
        int end = html.toLowerCase(java.util.Locale.ROOT).lastIndexOf("</body>");
        if (end >= 0) html = html.substring(0, end) + probe + html.substring(end);
        return html;
    }

    private static boolean isHtml(String mimeType) {
        if (mimeType == null || mimeType.isEmpty()) return true;
        int separator = mimeType.indexOf(';');
        String type = (separator < 0 ? mimeType : mimeType.substring(0, separator)).trim();
        return "text/html".equalsIgnoreCase(type) || "application/xhtml+xml".equalsIgnoreCase(type);
    }

    private static String inline(String html, Pattern pattern, int pathGroup, boolean script) {
        Matcher matcher = pattern.matcher(html);
        StringBuffer output = new StringBuffer();
        while (matcher.find()) {
            String path = matcher.group(pathGroup);
            String replacement = matcher.group();
            if (allowed(path, script)) {
                byte[] bytes = Native.readAsset(path);
                if (bytes == null) {
                    Log.w(TAG, "missing APK asset: " + path);
                } else {
                    String body = new String(bytes, StandardCharsets.UTF_8);
                    // Prevent an embedded HTML end tag from ending the script/style element.
                    body = Pattern.compile(script ? "</script" : "</style", Pattern.CASE_INSENSITIVE)
                            .matcher(body).replaceAll(Matcher.quoteReplacement(script ? "<\\/script" : "<\\/style"));
                    replacement = script ? "<script>\n" + body + "\n</script>" : "<style>\n" + body + "\n</style>";
                    Log.i(TAG, "inlined " + path + " (" + bytes.length + " bytes)");
                }
            }
            matcher.appendReplacement(output, Matcher.quoteReplacement(replacement));
        }
        matcher.appendTail(output);
        return output.toString();
    }

    private static boolean allowed(String path, boolean script) {
        if (script) return "backend/js/jquery.min.js".equals(path)
                || "backend/js/reviewer.js".equals(path)
                || "scripts/ankidroid-cardviewer.js".equals(path)
                || "scripts/ankidroid-reviewer.js".equals(path)
                || "scripts/type-answer.js".equals(path);
        return "backend/css/root-vars.css".equals(path)
                || "backend/css/reviewer.css".equals(path)
                || "ankidroid.css".equals(path);
    }
}

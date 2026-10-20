// SPDX-License-Identifier: GPL-2.0-or-later
package husk;

/** Route embedded Android assets through the same WebKit scheme as top-level loads. */
public final class HtmlResourceUrls {
    private HtmlResourceUrls() {}

    public static String rewrite(String data, String mimeType) {
        if (data == null) return "";
        if (mimeType != null && !mimeType.isEmpty()) {
            int separator = mimeType.indexOf(';');
            String type = (separator < 0 ? mimeType : mimeType.substring(0, separator)).trim();
            if (!"text/html".equalsIgnoreCase(type) && !"application/xhtml+xml".equalsIgnoreCase(type)) return data;
        }
        return data.replace("file:///android_asset/", "huskapp://android_asset/")
                .replace("file:///android_res/", "huskapp://android_res/");
    }
}

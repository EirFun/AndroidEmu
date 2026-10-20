// SPDX-License-Identifier: GPL-2.0-or-later
package husk;

/** Host-only navigation recorder. Never include in the production DEX. */
public final class Web {
    public static String lastBaseUrl;
    public static final java.util.List<String> events = new java.util.ArrayList<>();
    public static void settings(int id, boolean javaScript, String userAgent, int zoom, boolean gesture) {
        events.add("settings:" + javaScript);
    }
    public static void loadData(int id, byte[] data, String mime, String encoding, String baseUrl) {
        lastBaseUrl = baseUrl;
        events.add("loadData");
    }
    public static void load(int id, String url, String[] headers, byte[] postBody) {
        events.add("load");
    }
}

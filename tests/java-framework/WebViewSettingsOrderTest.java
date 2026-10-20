// SPDX-License-Identifier: GPL-2.0-or-later
package android.webkit;

import java.lang.reflect.Field;
import java.util.HashMap;
import husk.Native;
import husk.Web;

/** Reproduce setJavaScriptEnabled followed by navigation before deferred settings run. */
public final class WebViewSettingsOrderTest {
    public static void main(String[] args) throws Exception {
        Field field = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        sun.misc.Unsafe unsafe = (sun.misc.Unsafe) field.get(null);
        // Avoid platform construction; use the real navigation methods and settings container.
        WebView view = (WebView) unsafe.allocateInstance(WebView.class);
        final int[] pending = {0};
        HuskWebSettings settings = new HuskWebSettings(() -> pending[0]++);
        set(view, "mSettings", settings);
        set(view, "mLocalSchemes", new HashMap<String, String>());
        Native.currentPackage = "test.app";
        for (boolean enabled : new boolean[] {true, false}) {
            settings.setJavaScriptEnabled(enabled);
            require(pending[0] > 0, "Setting changes must still be deferred in this reproduction");
            check(() -> view.loadDataWithBaseURL("file:///android_asset/index.html", "<html></html>", "text/html", null, null), "loadData", enabled);
            check(() -> view.loadData("<html></html>", "text/html", null), "loadData", enabled);
            check(() -> view.loadUrl("file:///android_asset/index.html"), "load", enabled);
            check(() -> view.postUrl("file:///android_asset/index.html", new byte[0]), "load", enabled);
        }
        set(view, "mDestroyed", true);
        Web.events.clear();
        view.loadData("", "text/html", null);
        view.loadDataWithBaseURL(null, "", "text/html", null, null);
        view.loadUrl("file:///android_asset/index.html");
        view.postUrl("file:///android_asset/index.html", null);
        require(Web.events.isEmpty(), "Destroyed views must not push settings or load pages");
        System.out.println("PASS: all four navigation paths submit the current JavaScript preference before loading, including explicit false");
    }

    private static void check(Runnable navigate, String load, boolean enabled) {
        Web.events.clear();
        navigate.run();
        require(Web.events.equals(java.util.Arrays.asList("settings:" + enabled, load)),
                "Settings must precede navigation: " + Web.events);
    }
    private static void set(WebView view, String name, Object value) throws Exception {
        Field field = WebView.class.getDeclaredField(name);
        field.setAccessible(true);
        field.set(view, value);
    }
    private static void require(boolean condition, String reason) {
        if (!condition) throw new AssertionError(reason);
    }
}

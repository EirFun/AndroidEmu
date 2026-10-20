// SPDX-License-Identifier: GPL-2.0-or-later
package husk;

import android.view.View;
import android.view.ViewGroup;

/** Keep AnkiDroid's visible Android whiteboard overlay above the native WebView for input. */
public final class AnkiWhiteboardInput {
    private AnkiWhiteboardInput() {}

    public static boolean blocksNativeWebTouches(View root) {
        return "com.ichi2.anki".equals(Native.packageName()) && hasVisibleWhiteboard(root);
    }

    private static boolean hasVisibleWhiteboard(View view) {
        if (view == null || view.getVisibility() != View.VISIBLE) return false;
        String name = view.getClass().getName();
        if (view.getWidth() > 0 && view.getHeight() > 0
                && ("com.ichi2.anki.ui.windows.reviewer.whiteboard.WhiteboardView".equals(name)
                || "com.ichi2.anki.ui.windows.reviewer.whiteboard.WhiteboardToolbar".equals(name))) return true;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                if (hasVisibleWhiteboard(group.getChildAt(i))) return true;
            }
        }
        return false;
    }
}

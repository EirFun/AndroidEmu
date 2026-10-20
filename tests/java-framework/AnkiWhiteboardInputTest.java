// SPDX-License-Identifier: GPL-2.0-or-later
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import husk.AnkiWhiteboardInput;
import husk.Native;
import java.lang.reflect.Field;
import com.ichi2.anki.ui.windows.reviewer.whiteboard.WhiteboardView;

public final class AnkiWhiteboardInputTest {
    public static void main(String[] args) throws Exception {
        Field field = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        sun.misc.Unsafe unsafe = (sun.misc.Unsafe) field.get(null);
        View canvas = (View) unsafe.allocateInstance(WhiteboardView.class);
        set(View.class, canvas, "mRight", 100);
        set(View.class, canvas, "mBottom", 100);
        ViewGroup parent = (ViewGroup) unsafe.allocateInstance(FrameLayout.class);
        set(ViewGroup.class, parent, "mChildren", new View[] {canvas});
        set(ViewGroup.class, parent, "mChildrenCount", 1);
        Native.currentPackage = "com.ichi2.anki";
        require(AnkiWhiteboardInput.blocksNativeWebTouches(parent), "Visible overlay must receive Android touches");
        set(View.class, canvas, "mVisibility", View.GONE);
        require(!AnkiWhiteboardInput.blocksNativeWebTouches(parent), "Hidden canvas must restore native web input");
        set(View.class, canvas, "mVisibility", View.VISIBLE);
        set(View.class, parent, "mVisibility", View.INVISIBLE);
        require(!AnkiWhiteboardInput.blocksNativeWebTouches(parent), "Hidden ancestor must restore native web input");
        set(View.class, parent, "mVisibility", View.VISIBLE);
        set(View.class, canvas, "mRight", 0);
        require(!AnkiWhiteboardInput.blocksNativeWebTouches(parent), "Unlaid-out overlay must not intercept input");
        set(View.class, canvas, "mRight", 100);
        Native.currentPackage = "another.app";
        require(!AnkiWhiteboardInput.blocksNativeWebTouches(parent), "Other apps must retain normal input");
        Native.currentPackage = "com.ichi2.anki";
        set(ViewGroup.class, parent, "mChildrenCount", 0);
        require(!AnkiWhiteboardInput.blocksNativeWebTouches(parent), "Removing overlay must restore native web input");
        require(!AnkiWhiteboardInput.blocksNativeWebTouches(null), "Null root must not intercept input");
        System.out.println("PASS: only visible laid-out AnkiDroid whiteboards divert native web touches; hide/removal restores input");
    }
    private static void set(Class<?> owner, Object instance, String name, Object value) throws Exception {
        Field field = owner.getDeclaredField(name);
        field.setAccessible(true);
        field.set(instance, value);
    }
    private static void require(boolean condition, String reason) { if (!condition) throw new AssertionError(reason); }
}

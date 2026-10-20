// SPDX-License-Identifier: GPL-2.0-or-later
import android.os.Handler;
import android.os.Looper;
import android.os.Message;

/** Host regression probe: no ART, native loop, device, or network is used. */
public final class MessageCopyTest {
    public static void main(String[] args) {
        final int[] clicked = {0};
        Handler handler = new Handler((Looper) null) {
            @Override public void handleMessage(Message message) {
                if (message.what == -1 && message.obj == clicked) clicked[0]++;
            }
        };
        Message original = Message.obtain(handler, -1, 17, 23, clicked);
        original.getData().putString("marker", "before");
        original.sendingUid = 42;
        original.workSourceUid = 43;
        Runnable callback = new Runnable() { public void run() {} };
        original.callback = callback;

        Message copied = Message.obtain(original);
        require(copied != null, "AppCompat button callback must not disappear");
        require(copied != original, "Copy must be a distinct Message");
        require(copied.target == handler, "Delivery target must survive");
        require(copied.what == -1 && copied.arg1 == 17 && copied.arg2 == 23, "Integer payload must survive");
        require(copied.obj == clicked && copied.callback == callback, "Object and callback must survive");
        require(copied.sendingUid == 42 && copied.workSourceUid == 43, "Sender identity must survive");
        copied.getData().putString("marker", "after");
        require("before".equals(original.getData().getString("marker")), "Bundle must be copied");
        require(copied.when == 0, "Copy must not inherit a queued delivery time");
        copied.callback = null;
        copied.target.dispatchMessage(copied);
        require(clicked[0] == 1, "Copied dialog-style message must dispatch its action exactly once");
        Message noData = Message.obtain(Message.obtain(handler, -2));
        require(noData.getTarget() == handler && noData.what == -2, "Message without Bundle must copy");
        System.out.println("PASS: Message.obtain preserves dialog delivery, payload, callback, and independent Bundle");
    }

    private static void require(boolean condition, String reason) {
        if (!condition) throw new AssertionError(reason);
    }
}

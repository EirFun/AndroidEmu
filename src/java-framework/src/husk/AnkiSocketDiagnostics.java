// SPDX-License-Identifier: GPL-2.0-or-later
package husk;

import android.util.Log;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.LogManager;
import java.util.logging.LogRecord;
import java.util.logging.Logger;

/** Bound NanoHTTPD's IOException retry loop while retaining its first actual socket errors. */
public final class AnkiSocketDiagnostics extends Handler {
    private static Logger installedLogger;
    private long failures;

    public static synchronized void install() {
        if (installedLogger != null || !"com.ichi2.anki".equals(Native.packageName())) return;
        LogManager manager = LogManager.getLogManager();
        Logger logger = manager.getLogger("fi.iki.elonen.NanoHTTPD");
        // R8 name verified in the official AnkiDroid 2.26.0alpha6 arm64 APK.
        if (logger == null) logger = manager.getLogger("bv");
        if (logger == null) {
            Log.w("HuskAnkiSocket", "NanoHTTPD logger not found; retry guard not installed");
            return;
        }
        logger.addHandler(new AnkiSocketDiagnostics());
        logger.setUseParentHandlers(false);
        logger.setLevel(Level.FINE);
        installedLogger = logger;
        Log.i("HuskAnkiSocket", "NanoHTTPD error retry guard installed (250 ms on failed accept)");
    }

    @Override public void publish(LogRecord record) {
        if (record == null) return;
        if ("NanoHttpd Main Listener".equals(Thread.currentThread().getName())
                && "Communication with the client broken".equals(record.getMessage())
                && record.getThrown() != null) {
            long count;
            synchronized (this) { count = ++failures; }
            if (count <= 3 || count % 100 == 0) {
                Log.w("HuskAnkiSocket", "accept failure #" + count + "; limiting retries", record.getThrown());
            }
            try { Thread.sleep(250); }
            catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); }
        } else if (record.getLevel().intValue() >= Level.WARNING.intValue()) {
            Log.w("HuskAnkiSocket", record.getMessage(), record.getThrown());
        }
    }
    @Override public void flush() {}
    @Override public void close() {}
}

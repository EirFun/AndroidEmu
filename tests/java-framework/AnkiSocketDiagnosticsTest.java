// SPDX-License-Identifier: GPL-2.0-or-later
import husk.AnkiSocketDiagnostics;
import husk.Native;
import java.io.IOException;
import java.util.logging.Level;
import java.util.logging.Logger;

public final class AnkiSocketDiagnosticsTest {
    public static void main(String[] args) throws Exception {
        Logger nano = Logger.getLogger("bv");
        nano.setLevel(Level.INFO);
        Native.currentPackage = "another.app";
        AnkiSocketDiagnostics.install();
        require(nano.getLevel() == Level.INFO && nano.getHandlers().length == 0, "Other apps must be unchanged");
        Native.currentPackage = "com.ichi2.anki";
        AnkiSocketDiagnostics.install();
        AnkiSocketDiagnostics.install();
        require(nano.getLevel() == Level.FINE && nano.getHandlers().length == 1, "Install exactly one NanoHTTPD handler");
        long[] duration = {0};
        Thread listener = new Thread(() -> {
            long start = System.nanoTime();
            nano.log(Level.FINE, "Communication with the client broken", new IOException("accept failure fixture"));
            duration[0] = System.nanoTime() - start;
        }, "NanoHttpd Main Listener");
        listener.start(); listener.join(5000);
        require(!listener.isAlive() && duration[0] >= 200000000L, "Failed listener accepts must back off");
        nano.log(Level.FINE, "Communication with the client broken", new IOException("other thread"));
        System.out.println("PASS: failed NanoHTTPD accept is delayed; install is idempotent and other apps unchanged");
    }
    private static void require(boolean condition, String reason) { if (!condition) throw new AssertionError(reason); }
}

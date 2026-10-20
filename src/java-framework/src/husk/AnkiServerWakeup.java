// SPDX-License-Identifier: GPL-2.0-or-later
package husk;

import android.util.Log;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;

/** Wake the current indefinite accept so subsequent accepts use the new timeout. */
final class AnkiServerWakeup extends Thread {
    private final int port;
    AnkiServerWakeup(ServerSocket socket) {
        super("Husk Anki listener wakeup");
        port = socket.getLocalPort();
        setDaemon(true);
    }
    @Override public void run() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", port), 500);
            Log.i("HuskAnkiSocket", "listener wakeup connection completed");
        } catch (Exception error) {
            Log.w("HuskAnkiSocket", "listener wakeup failed; current accept may still block", error);
        }
    }
}

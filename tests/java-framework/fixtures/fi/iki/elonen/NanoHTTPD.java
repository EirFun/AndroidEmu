// SPDX-License-Identifier: GPL-2.0-or-later
package fi.iki.elonen;

/** Host-only server shape and accept loop; not shipped or an implementation of the HTTP protocol. */
public final class NanoHTTPD {
    private final java.net.ServerSocket socket;
    public final Thread listener;
    public volatile int accepts;
    public NanoHTTPD() throws Exception {
        socket = new java.net.ServerSocket(0, 8, java.net.InetAddress.getByName("127.0.0.1"));
        listener = new Thread(() -> {
            while (!socket.isClosed()) {
                try (java.net.Socket client = socket.accept()) { accepts++; }
                catch (java.net.SocketTimeoutException expected) {}
                catch (java.io.IOException failure) { if (socket.isClosed()) break; }
            }
        }, "NanoHttpd Main Listener");
        listener.setDaemon(true);
        listener.start();
    }
    public int timeout() throws Exception { return socket.getSoTimeout(); }
    public void stop() throws Exception { socket.close(); listener.join(2000); }
}

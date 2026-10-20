// SPDX-License-Identifier: GPL-2.0-or-later
import fi.iki.elonen.NanoHTTPD;
import husk.AnkiServerLifecycle;
import husk.Native;

public final class AnkiServerLifecycleTest {
    // Mirrors the private client -> fragment -> lazy -> viewmodel -> server ownership path.
    private static final class Link {
        private final Object value;
        private Object cycle;
        Link(Object value) { this.value = value; cycle = this; }
    }
    public static void main(String[] args) throws Exception {
        NanoHTTPD server = new NanoHTTPD();
        try {
            Object client = new Link(new Link(new Link(new Link(server))));
            Native.currentPackage = "another.app";
            AnkiServerLifecycle.configure(client);
            require(server.timeout() == 0, "Other apps' sockets must remain unchanged");
            Native.currentPackage = "com.ichi2.anki";
            Thread.sleep(30); // let the existing accept enter before setting the timeout
            AnkiServerLifecycle.configure(client);
            require(server.timeout() == 500, "Reviewer listener must use a bounded accept");
            long deadline = System.nanoTime() + 2000000000L;
            while (server.accepts == 0 && System.nanoTime() < deadline) Thread.sleep(10);
            require(server.accepts >= 1, "Wakeup must release the accept that started without a timeout");
            int accepts = server.accepts;
            AnkiServerLifecycle.configure(client);
            Thread.sleep(50);
            require(server.accepts == accepts, "Repeated configuration must not create another wakeup");
            server.stop();
            require(!server.listener.isAlive(), "Listener must terminate so shutdown can finish");
            AnkiServerLifecycle.configure(new Link(new Object()));
            System.out.println("PASS: private server graph found, existing accept awakened, timeout set once, shutdown finishes; other apps untouched");
        } finally { server.stop(); }
    }
    private static void require(boolean condition, String reason) { if (!condition) throw new AssertionError(reason); }
}

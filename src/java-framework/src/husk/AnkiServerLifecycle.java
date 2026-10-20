// SPDX-License-Identifier: GPL-2.0-or-later
package husk;

import android.app.Activity;
import android.content.Context;
import android.util.Log;
import android.view.View;
import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.net.ServerSocket;
import java.util.ArrayDeque;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.WeakHashMap;

/** Temporary listener shutdown workaround, scoped to the known AnkiDroid APK. */
public final class AnkiServerLifecycle {
    private static final Map<ServerSocket, Boolean> configured = new WeakHashMap<>();
    private AnkiServerLifecycle() {}

    public static void configure(Object webClient) {
        if (!"com.ichi2.anki".equals(Native.packageName())) return;
        ServerSocket socket;
        try { socket = findListener(webClient); }
        catch (RuntimeException error) {
            Log.w("HuskAnkiSocket", "could not inspect reviewer listener", error);
            return;
        }
        if (socket == null) {
            Log.w("HuskAnkiSocket", "listener not found in reviewer client; accept timeout unchanged");
            return;
        }
        synchronized (configured) {
            if (configured.containsKey(socket)) return;
            try {
                socket.setSoTimeout(500);
                configured.put(socket, Boolean.TRUE);
                Log.i("HuskAnkiSocket", "listener accept timeout set to 500 ms");
                new AnkiServerWakeup(socket).start();
            } catch (Exception error) {
                Log.w("HuskAnkiSocket", "could not configure listener timeout", error);
            }
        }
    }

    public static void stopped(Activity activity) {
        Log.d("Husk", "finish: stop completed " + activity.getClass().getName());
    }
    public static void destroyed(Activity activity) {
        Log.d("Husk", "finish: destroy completed " + activity.getClass().getName());
    }

    private static ServerSocket findListener(Object client) {
        if (client == null) return null;
        ArrayDeque<Object> queue = new ArrayDeque<>();
        ArrayDeque<Integer> depths = new ArrayDeque<>();
        IdentityHashMap<Object, Boolean> visited = new IdentityHashMap<>();
        queue.add(client); depths.add(0);
        while (!queue.isEmpty() && visited.size() < 512) {
            Object object = queue.remove();
            int depth = depths.remove();
            if (visited.put(object, Boolean.TRUE) != null) continue;
            Class<?> type = object.getClass();
            for (Class<?> current = type; current != null; current = current.getSuperclass()) {
                // Exact R8 name verified for the supplied alpha6 APK; original name supports unobfuscated builds.
                if ("bv".equals(current.getName()) || "fi.iki.elonen.NanoHTTPD".equals(current.getName())) {
                    for (Field field : current.getDeclaredFields()) {
                        if (field.getType() != ServerSocket.class || Modifier.isStatic(field.getModifiers())) continue;
                        try { field.setAccessible(true); return (ServerSocket) field.get(object); }
                        catch (ReflectiveOperationException | RuntimeException ignored) {}
                    }
                }
            }
            if (depth >= 6 || object instanceof View || object instanceof Context
                    || object instanceof Thread || object instanceof Class || object instanceof CharSequence
                    || object instanceof Number || object instanceof Enum) continue;
            if (object instanceof Map) {
                for (Object value : ((Map<?, ?>) object).values()) enqueue(value, depth, queue, depths, visited);
                continue;
            }
            if (type.getName().startsWith("java.")) continue;
            for (Class<?> current = type; current != null && current != Object.class; current = current.getSuperclass()) {
                for (Field field : current.getDeclaredFields()) {
                    if (Modifier.isStatic(field.getModifiers()) || field.getType().isPrimitive()) continue;
                    try {
                        field.setAccessible(true);
                        enqueue(field.get(object), depth, queue, depths, visited);
                    } catch (ReflectiveOperationException | RuntimeException ignored) {}
                }
            }
        }
        return null;
    }
    private static void enqueue(Object value, int depth, ArrayDeque<Object> queue,
                                ArrayDeque<Integer> depths, IdentityHashMap<Object, Boolean> visited) {
        if (value != null && !visited.containsKey(value) && queue.size() < 512) {
            queue.add(value); depths.add(depth + 1);
        }
    }
}

// SPDX-License-Identifier: GPL-2.0-or-later
package husk;

/** Host-only package-name shim. Keep this off the production framework classpath. */
public final class Native {
    public static String currentPackage = "com.ichi2.anki";
    public static void log(int priority, String tag, String message) { System.out.println(tag + ": " + message); }
    public static String currentDataDir;
    public static final java.util.Map<String, byte[]> assets = new java.util.HashMap<>();
    public static byte[] readAsset(String path) { return assets.get(path); }
    public static String packageName() { return currentPackage; }
    public static String dataDir() { return currentDataDir; }
}

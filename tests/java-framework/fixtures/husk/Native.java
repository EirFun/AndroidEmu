// SPDX-License-Identifier: GPL-2.0-or-later
package husk;

/** Host-only package-name shim. Keep this off the production framework classpath. */
public final class Native {
    public static String currentPackage = "com.ichi2.anki";
    public static String currentDataDir;
    public static String packageName() { return currentPackage; }
    public static String dataDir() { return currentDataDir; }
}

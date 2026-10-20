// SPDX-License-Identifier: GPL-2.0-or-later
package husk;

import java.io.File;
import java.io.IOException;

/** Recover an existing Anki collection after iOS relocates Husk's data container. */
public final class AnkiStoragePath {
    private AnkiStoragePath() {}

    public static String forPreference(String key, String saved) {
        if (!"deckPath".equals(key) || !"com.ichi2.anki".equals(Native.packageName())) return saved;
        return relocate(saved, Native.dataDir());
    }

    public static String relocate(String saved, String currentDataDir) {
        if (saved == null || currentDataDir == null) return saved;
        String marker = "/Documents/TranslationLayer/";
        int currentMarker = currentDataDir.indexOf(marker);
        int oldMarker = saved.indexOf(marker);
        if (currentMarker < 0 || oldMarker < 0 || !currentDataDir.endsWith("/java-data")) return saved;
        String instanceSuffix = currentDataDir.substring(currentMarker);
        int relativeStart = oldMarker + instanceSuffix.length();
        if (!saved.regionMatches(oldMarker, instanceSuffix, 0, instanceSuffix.length())
                || saved.length() <= relativeStart || saved.charAt(relativeStart) != '/') return saved;
        String relative = saved.substring(relativeStart + 1);
        for (String part : relative.split("/", -1)) {
            if (part.length() == 0 || part.equals(".") || part.equals("..")) return saved;
        }
        File candidate = new File(currentDataDir, relative);
        // Never hide a still-accessible collection or silently select a new/empty folder.
        if (new File(saved, "collection.anki2").isFile()
                || !candidate.isDirectory() || !new File(candidate, "collection.anki2").isFile()) return saved;
        try {
            String base = new File(currentDataDir).getCanonicalPath() + File.separator;
            if (!candidate.getCanonicalPath().startsWith(base)) return saved;
        } catch (IOException e) {
            return saved;
        }
        return candidate.getPath();
    }
}

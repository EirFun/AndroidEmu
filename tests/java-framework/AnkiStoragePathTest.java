// SPDX-License-Identifier: GPL-2.0-or-later
import android.content.HuskSharedPreferences;
import husk.AnkiStoragePath;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.stream.Stream;

public final class AnkiStoragePathTest {
    public static void main(String[] args) throws Exception {
        Path root = Files.createTempDirectory("husk-relocation-test-");
        try {
            String suffix = "/Documents/TranslationLayer/same-instance/java-data";
            String old = root + "/old" + suffix + "/sdcard/AnkiDroid";
            String current = root + "/current" + suffix;
            Path collection = Files.createDirectories(java.nio.file.Paths.get(current, "sdcard/AnkiDroid"));
            Files.write(collection.resolve("collection.anki2"), new byte[] {1, 2, 3});
            require(collection.toString().equals(AnkiStoragePath.relocate(old, current)), "Existing relocated collection must be found");
            require(old.equals(AnkiStoragePath.relocate(old, current.replace("same-instance", "another-instance"))), "Different library entry must not be substituted");
            require(old.equals(AnkiStoragePath.relocate(old, root + "/missing" + suffix)), "Missing collection must not be replaced with an empty one");
            require(AnkiStoragePath.relocate(null, current) == null, "Unset paths must remain unset");
            String escape = root + "/old" + suffix + "/../sdcard/AnkiDroid";
            require(escape.equals(AnkiStoragePath.relocate(escape, current)), "Traversal paths must not be rewritten");
            Path foreign = Files.createDirectories(root.resolve("foreign"));
            Files.write(foreign.resolve("collection.anki2"), new byte[] {9});
            Path link = java.nio.file.Paths.get(current, "sdcard/linked");
            Files.createSymbolicLink(link, foreign);
            String linkedOld = root + "/old" + suffix + "/sdcard/linked";
            require(linkedOld.equals(AnkiStoragePath.relocate(linkedOld, current)), "Symlinks outside current data root must not be substituted");

            Path prefsFile = root.resolve("prefs.xml");
            HuskSharedPreferences prefs = new HuskSharedPreferences(prefsFile.toFile());
            prefs.edit().putString("deckPath", old).commit();
            husk.Native.currentDataDir = current;
            require(old.equals(new HuskSharedPreferences(root.resolve("unset-prefs.xml").toFile())
                    .getString("deckPath", old)), "Caller defaults must not be relocated");
            require(collection.toString().equals(prefs.getString("deckPath", null)), "Preference read must use current container");
            require(old.equals(prefs.getAll().get("deckPath")), "Stored path must not be overwritten");
            husk.Native.currentPackage = "another.app";
            require(old.equals(prefs.getString("deckPath", null)), "Other apps must be unchanged");
            husk.Native.currentPackage = "com.ichi2.anki";
            require(old.equals(AnkiStoragePath.forPreference("another-key", old)), "Other preferences must be unchanged");

            String next = root + "/next-update" + suffix;
            Path nextCollection = Files.createDirectories(java.nio.file.Paths.get(next, "sdcard/AnkiDroid"));
            Files.write(nextCollection.resolve("collection.anki2"), new byte[] {4});
            husk.Native.currentDataDir = next;
            require(nextCollection.toString().equals(prefs.getString("deckPath", null)), "Another container update must be handled dynamically");

            Path originalCollection = Files.createDirectories(java.nio.file.Paths.get(old));
            Files.write(originalCollection.resolve("collection.anki2"), new byte[] {5});
            require(old.equals(AnkiStoragePath.relocate(old, current)), "Still-accessible original collection must be preserved");
            System.out.println("PASS: relocation finds existing collection, survives repeat updates, preserves stored paths, and rejects missing/foreign/traversal targets");
        } finally {
            try (Stream<Path> paths = Files.walk(root)) {
                Path[] entries = paths.sorted(Comparator.reverseOrder()).toArray(Path[]::new);
                for (Path path : entries) Files.delete(path);
            }
        }
    }

    private static void require(boolean condition, String reason) {
        if (!condition) throw new AssertionError(reason);
    }
}

// SPDX-License-Identifier: GPL-2.0-or-later
import android.content.HuskSharedPreferences;
import java.nio.file.Files;
import java.nio.file.Path;

/** Host probe with fixtures/husk/Native.java supplying only the current package. */
public final class AnkiPreviewPreferenceTest {
    public static void main(String[] args) throws Exception {
        Path file = Files.createTempFile("husk-preview-test-", ".xml");
        try {
            HuskSharedPreferences prefs = new HuskSharedPreferences(file.toFile());
            prefs.edit().putBoolean("noteEditorShowPreviewer", true)
                    .putBoolean("unrelated", true).commit();
            require(!prefs.getBoolean("noteEditorShowPreviewer", true), "Anki preview read must be disabled");
            require(Boolean.TRUE.equals(prefs.getAll().get("noteEditorShowPreviewer")), "Stored preference must remain true");
            require(prefs.getBoolean("unrelated", false), "Unrelated preferences must be unchanged");
            husk.Native.currentPackage = "another.app";
            require(prefs.getBoolean("noteEditorShowPreviewer", false), "Other applications must retain their preference");
            require(new HuskSharedPreferences(file.toFile()).getBoolean("noteEditorShowPreviewer", false),
                    "Saved preview preference must remain true after reload in another app");
            System.out.println("PASS: Anki preview override preserves saved values, unrelated keys, and other applications");
        } finally {
            Files.deleteIfExists(file);
        }
    }

    private static void require(boolean condition, String reason) {
        if (!condition) throw new AssertionError(reason);
    }
}

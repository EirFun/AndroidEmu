// SPDX-License-Identifier: GPL-2.0-or-later
import android.content.HuskSharedPreferences;
import java.nio.file.Files;
import java.nio.file.Path;

public final class AnkiCrashReportingPreferenceTest {
    public static void main(String[] args) throws Exception {
        Path file = Files.createTempFile("husk-acra-test-", ".xml");
        try {
            HuskSharedPreferences prefs = new HuskSharedPreferences(file.toFile());
            require("1".equals(prefs.getString("reportErrorMode", "2")), "Unset mode must override the ask-first default");
            require(!prefs.contains("reportErrorMode"), "Override must not write a preference");
            prefs.edit().putString("reportErrorMode", "2").putString("other", "unchanged").commit();
            require("1".equals(prefs.getString("reportErrorMode", "2")), "Saved ask-first mode must also be overridden");
            require("2".equals(prefs.getAll().get("reportErrorMode")), "Saved reporting choice must be retained");
            require("unchanged".equals(prefs.getString("other", null)), "Unrelated preference must be retained");
            husk.Native.currentPackage = "another.app";
            require("2".equals(prefs.getString("reportErrorMode", "2")), "Other applications must retain reporting settings");
            System.out.println("PASS: Anki report mode overrides unset and saved values without replacing preferences or affecting other applications");
        } finally {
            Files.deleteIfExists(file);
        }
    }

    private static void require(boolean condition, String reason) {
        if (!condition) throw new AssertionError(reason);
    }
}

// SPDX-License-Identifier: GPL-2.0-or-later
import husk.AnkiMediaFiles;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;

public final class AnkiMediaFilesTest {
    public static void main(String[] args) throws Exception {
        Path root = Files.createTempDirectory("husk-media-test");
        Path media = Files.createDirectory(root.resolve("collection.media"));
        Path image = media.resolve("slide space.jpg");
        Files.write(image, new byte[] {1, 2, 3});
        require(image.toFile().equals(AnkiMediaFiles.resolveFile(media.toFile(), "/slide space.jpg")), "Existing flat image must resolve");
        for (String path : new String[] {"/missing.jpg", "/../secret.jpg", "/nested/a.jpg", "/\\secret.jpg", "relative.jpg", "/", "/..", "/bad\0.jpg"})
            require(AnkiMediaFiles.resolveFile(media.toFile(), path) == null, "Missing or unsafe path must be rejected");
        Path secret = root.resolve("secret.jpg"); Files.write(secret, new byte[] {9});
        Path link = media.resolve("link.jpg"); Files.createSymbolicLink(link, secret);
        require(AnkiMediaFiles.resolveFile(media.toFile(), "/link.jpg") == null, "Symlink must not escape media directory");
        require(Files.readAllBytes(image).length == 3 && Files.readAllBytes(secret)[0] == 9, "Lookup must not modify files");
        Files.delete(link); Files.delete(image); Files.delete(media); Files.delete(secret); Files.delete(root);
        System.out.println("PASS: existing image resolution, spaces, missing files, traversal and symlink containment; no file writes by resolver");
    }
    private static void require(boolean condition, String reason) { if (!condition) throw new AssertionError(reason); }
}

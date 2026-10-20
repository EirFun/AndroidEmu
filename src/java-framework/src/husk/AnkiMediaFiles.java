// SPDX-License-Identifier: GPL-2.0-or-later
package husk;

import android.content.Context;
import android.net.Uri;
import android.util.Log;
import android.webkit.MimeTypeMap;
import android.webkit.WebResourceResponse;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.util.Locale;

/** Read-only fallback for images already present in AnkiDroid's current media directory. */
public final class AnkiMediaFiles {
    private AnkiMediaFiles() {}
    public static WebResourceResponse open(Context context, String url, String method) {
        if (!"com.ichi2.anki".equals(Native.packageName()) || !"GET".equals(method)) return null;
        Uri uri = Uri.parse(url);
        if (!"127.0.0.1".equals(uri.getHost())) return null;
        String path = uri.getPath();
        if (path == null || path.startsWith("/_anki/")) return null;
        int dot = path.lastIndexOf('.');
        if (dot < 0) return null;
        String extension = path.substring(dot + 1).toLowerCase(Locale.ROOT);
        if (!(extension.equals("jpg") || extension.equals("jpeg") || extension.equals("png")
                || extension.equals("gif") || extension.equals("svg") || extension.equals("webp")
                || extension.equals("avif") || extension.equals("bmp"))) return null;
        try {
            String fallback = new File(Native.dataDir(), "sdcard/AnkiDroid").getPath();
            String directory = context.getSharedPreferences("com.ichi2.anki_preferences", Context.MODE_PRIVATE)
                    .getString("deckPath", fallback);
            File media = new File(directory, "collection.media");
            File file = resolveFile(media, path);
            Log.i("HuskAnkiMedia", "image lookup: mediaDirectory=" + media.isDirectory()
                    + " directoryReadable=" + media.canRead() + " imageFile=" + (file != null));
            if (file == null) return null;
            String mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension);
            if (mime == null) mime = extension.equals("svg") ? "image/svg+xml" : "application/octet-stream";
            return new WebResourceResponse(mime, null, new FileInputStream(file));
        } catch (IOException | RuntimeException error) {
            // Avoid printing media filenames or paths from a user's collection.
            Log.w("HuskAnkiMedia", "image fallback failed: " + error.getClass().getSimpleName());
            return null;
        }
    }

    public static File resolveFile(File media, String decodedPath) throws IOException {
        if (decodedPath == null || !decodedPath.startsWith("/")) return null;
        String name = decodedPath.substring(1);
        if (name.isEmpty() || name.equals(".") || name.equals("..") || name.indexOf('/') >= 0
                || name.indexOf('\\') >= 0 || name.indexOf('\0') >= 0) return null;
        File file = new File(media, name);
        String root = media.getCanonicalPath() + File.separator;
        if (!file.getCanonicalPath().startsWith(root) || !file.isFile()) return null;
        return file;
    }
}

package cn.guanxiang.liuyao;

import android.content.Context;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

final class AppRuntime {
    static final ExecutorService WORK = Executors.newSingleThreadExecutor();
    static final String TOKEN = UUID.randomUUID().toString() + UUID.randomUUID().toString();
    static volatile String url;
    static synchronized String start(Context context) throws Exception {
        if (url != null) return url;
        Context app = context.getApplicationContext();
        File root = new File(app.getFilesDir(), "program/" + BuildConfig.CONTENT_DIGEST);
        if (!new File(root, ".complete").exists()) {
            root.mkdirs();
            MessageDigest hash = MessageDigest.getInstance("SHA-256");
            try (InputStream input = app.getAssets().open("content.zip")) {
                byte[] data = new byte[65536]; int n; while ((n = input.read(data)) > 0) hash.update(data, 0, n);
            }
            StringBuilder digest = new StringBuilder(); for (byte b : hash.digest()) digest.append(String.format("%02x", b & 255));
            if (!digest.toString().equals(BuildConfig.CONTENT_DIGEST)) throw new IOException("程序文件校验失败，请重新安装完整安装包。");
            try (ZipInputStream zip = new ZipInputStream(app.getAssets().open("content.zip"))) {
                ZipEntry entry; byte[] buffer = new byte[65536];
                while ((entry = zip.getNextEntry()) != null) {
                    File target = new File(root, entry.getName());
                    if (!target.getCanonicalPath().startsWith(root.getCanonicalPath() + File.separator)) throw new IOException("无效的程序文件路径");
                    if (entry.isDirectory()) { target.mkdirs(); continue; }
                    target.getParentFile().mkdirs();
                    try (OutputStream out = new FileOutputStream(target)) { int n; while ((n = zip.read(buffer)) > 0) out.write(buffer, 0, n); }
                }
            }
            new File(root, ".complete").createNewFile();
        }
        if (!Python.isStarted()) Python.start(new AndroidPlatform(app));
        File home = new File(app.getFilesDir(), "workspace"); home.mkdirs();
        url = Python.getInstance().getModule("android_entry").callAttr("start", root.getAbsolutePath(), home.getAbsolutePath(), TOKEN, new SecretStore(app).read()).toString();
        return url;
    }
    static boolean active() { return Python.isStarted() && Python.getInstance().getModule("android_entry").callAttr("active").toBoolean(); }
    static boolean configure(String value) { return Python.getInstance().getModule("android_entry").callAttr("configure", value).toBoolean(); }
}

package cn.guanxiang.liuyao;

import android.app.*;
import android.content.*;
import android.os.*;

public final class AnalysisService extends Service {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private long started;
    private PowerManager.WakeLock wakeLock;
    private final Runnable monitor = new Runnable() {
        @Override public void run() {
            AppRuntime.WORK.execute(() -> {
                boolean busy;
                try { busy = AppRuntime.active(); } catch (Exception ignored) { busy = false; }
                final boolean active = busy;
                handler.post(() -> {
                    if (!active && SystemClock.elapsedRealtime() - started > 10000) stopSelf();
                    else handler.postDelayed(monitor, 10000);
                });
            });
        }
    };
    @Override public void onCreate() {
        super.onCreate();
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("analysis", "AI 分析进度", NotificationManager.IMPORTANCE_LOW));
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification notification = new Notification.Builder(this, "analysis").setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("六爻占问 · 正在分析").setContentText("正在整理判断依据，点此查看进度").setOngoing(true).setContentIntent(open).build();
        startForeground(101, notification);
        wakeLock = getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "liuyao:analysis");
        wakeLock.acquire(100L * 60 * 1000); // bounded by the four-stage request budgets
        started = SystemClock.elapsedRealtime(); handler.postDelayed(monitor, 10000);
    }
    @Override public int onStartCommand(Intent intent, int flags, int startId) { return START_NOT_STICKY; }
    @Override public void onTimeout(int startId, int fgsType) { stopSelf(); }
    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public void onDestroy() { handler.removeCallbacksAndMessages(null); if (wakeLock != null && wakeLock.isHeld()) wakeLock.release(); stopForeground(STOP_FOREGROUND_REMOVE); super.onDestroy(); }
}

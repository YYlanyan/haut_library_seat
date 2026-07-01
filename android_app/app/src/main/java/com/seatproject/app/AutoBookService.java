package com.seatproject.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class AutoBookService extends Service {
    private static final String CHANNEL_ID = "seat_auto_book";
    private static final int NOTIFICATION_ID = 65930;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(NOTIFICATION_ID, notification("正在自动预约"));
        executor.execute(() -> {
            try {
                String accountName = AutoBookScheduler.accountName(this);
                int failures = SeatCommandRunner.run(
                        this,
                        "book",
                        accountName,
                        true,
                        message -> {
                        }
                );
                updateNotification(failures == 0 ? "自动预约完成" : "自动预约完成，有账号失败");
            } finally {
                AutoBookScheduler.scheduleNext(this);
                stopForeground(false);
                stopSelf(startId);
            }
        });
        return START_NOT_STICKY;
    }

    @Override
    public void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void updateNotification(String text) {
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        manager.notify(NOTIFICATION_ID, notification(text));
    }

    private Notification notification(String text) {
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "自动预约",
                    NotificationManager.IMPORTANCE_LOW
            );
            manager.createNotificationChannel(channel);
        }

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return builder
                .setSmallIcon(android.R.drawable.ic_menu_my_calendar)
                .setContentTitle("座位助手")
                .setContentText(text)
                .setOngoing(true)
                .build();
    }
}

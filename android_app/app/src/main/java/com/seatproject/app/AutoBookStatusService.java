package com.seatproject.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

public final class AutoBookStatusService extends Service {
    private static final String CHANNEL_ID = "seat_auto_book_status";
    private static final int NOTIFICATION_ID = 65931;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (!AutoBookScheduler.isEnabled(this)) {
            stopForeground(true);
            stopSelf(startId);
            return START_NOT_STICKY;
        }

        startForeground(NOTIFICATION_ID, notification());
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private Notification notification() {
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "自动预约运行状态",
                    NotificationManager.IMPORTANCE_LOW
            );
            manager.createNotificationChannel(channel);
        }

        String accountName = AutoBookScheduler.accountName(this);
        long next = AutoBookScheduler.scheduleNext(this);
        String text = "目标：" + (accountName == null ? "全部启用账号" : accountName)
                + "；时间：" + AutoBookScheduler.bookTime(this)
                + "；下次：" + AutoBookScheduler.formatTime(next);

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return builder
                .setSmallIcon(android.R.drawable.ic_menu_my_calendar)
                .setContentTitle("座位助手正在运行")
                .setContentText(text)
                .setOngoing(true)
                .build();
    }
}

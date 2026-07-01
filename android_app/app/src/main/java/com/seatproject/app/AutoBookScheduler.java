package com.seatproject.app;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;

import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Locale;

final class AutoBookScheduler {
    static final String ACTION_AUTO_BOOK = "com.seatproject.app.AUTO_BOOK";

    private static final String PREFS = "seat_auto_book";
    private static final String KEY_ENABLED = "enabled";
    private static final String KEY_ACCOUNT_NAME = "account_name";
    private static final String KEY_BOOK_TIME = "book_time";
    private static final String DEFAULT_BOOK_TIME = "06:59:30";
    private static final int REQUEST_CODE = 65930;

    private AutoBookScheduler() {
    }

    static void setEnabled(Context context, boolean enabled, String accountName, String bookTime) {
        prefs(context).edit()
                .putBoolean(KEY_ENABLED, enabled)
                .putString(KEY_ACCOUNT_NAME, accountName == null ? "" : accountName)
                .putString(KEY_BOOK_TIME, normalizeBookTime(bookTime))
                .apply();
        if (enabled) {
            scheduleNext(context);
            startStatusService(context);
        } else {
            cancel(context);
            stopStatusService(context);
        }
    }

    static boolean isEnabled(Context context) {
        return prefs(context).getBoolean(KEY_ENABLED, false);
    }

    static String accountName(Context context) {
        String value = prefs(context).getString(KEY_ACCOUNT_NAME, "");
        return value == null || value.isEmpty() ? null : value;
    }

    static String bookTime(Context context) {
        String value = prefs(context).getString(KEY_BOOK_TIME, DEFAULT_BOOK_TIME);
        return normalizeBookTime(value);
    }

    static long scheduleNext(Context context) {
        if (!isEnabled(context)) {
            return 0L;
        }

        long triggerAt = nextTriggerMillis(bookTime(context));
        AlarmManager alarmManager = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        PendingIntent pendingIntent = pendingIntent(context);
        Intent showIntent = new Intent(context, MainActivity.class);
        PendingIntent showPendingIntent = PendingIntent.getActivity(
                context,
                REQUEST_CODE,
                showIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (alarmManager.canScheduleExactAlarms()) {
                alarmManager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pendingIntent);
            } else {
                alarmManager.setAlarmClock(new AlarmManager.AlarmClockInfo(triggerAt, showPendingIntent), pendingIntent);
            }
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            alarmManager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pendingIntent);
        } else {
            alarmManager.setExact(AlarmManager.RTC_WAKEUP, triggerAt, pendingIntent);
        }
        return triggerAt;
    }

    static void cancel(Context context) {
        AlarmManager alarmManager = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        alarmManager.cancel(pendingIntent(context));
    }

    static void startStatusService(Context context) {
        Intent intent = new Intent(context, AutoBookStatusService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    static void stopStatusService(Context context) {
        context.stopService(new Intent(context, AutoBookStatusService.class));
    }

    static String formatTime(long millis) {
        if (millis <= 0L) {
            return "";
        }
        return new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.CHINA).format(millis);
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static PendingIntent pendingIntent(Context context) {
        Intent intent = new Intent(context, AutoBookAlarmReceiver.class);
        intent.setAction(ACTION_AUTO_BOOK);
        return PendingIntent.getBroadcast(
                context,
                REQUEST_CODE,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
    }

    private static long nextTriggerMillis(String bookTime) {
        int[] parts = parseClockTime(bookTime);
        Calendar target = Calendar.getInstance();
        target.set(Calendar.HOUR_OF_DAY, parts[0]);
        target.set(Calendar.MINUTE, parts[1]);
        target.set(Calendar.SECOND, parts[2]);
        target.set(Calendar.MILLISECOND, 0);
        if (target.getTimeInMillis() <= System.currentTimeMillis()) {
            target.add(Calendar.DAY_OF_MONTH, 1);
        }
        return target.getTimeInMillis();
    }

    private static String normalizeBookTime(String value) {
        int[] parts = parseClockTime(value == null || value.trim().isEmpty() ? DEFAULT_BOOK_TIME : value);
        return String.format(Locale.CHINA, "%02d:%02d:%02d", parts[0], parts[1], parts[2]);
    }

    private static int[] parseClockTime(String value) {
        String[] parts = value.trim().split(":");
        if (parts.length < 2 || parts.length > 3) {
            return new int[]{6, 59, 30};
        }
        try {
            int hour = Integer.parseInt(parts[0]);
            int minute = Integer.parseInt(parts[1]);
            int second = parts.length == 3 ? Integer.parseInt(parts[2]) : 0;
            if (hour < 0 || hour > 23 || minute < 0 || minute > 59 || second < 0 || second > 59) {
                return new int[]{6, 59, 30};
            }
            return new int[]{hour, minute, second};
        } catch (NumberFormatException exception) {
            return new int[]{6, 59, 30};
        }
    }
}

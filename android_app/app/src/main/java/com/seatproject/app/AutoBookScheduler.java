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
    private static final int REQUEST_CODE = 65930;

    private AutoBookScheduler() {
    }

    static void setEnabled(Context context, boolean enabled, String accountName) {
        prefs(context).edit()
                .putBoolean(KEY_ENABLED, enabled)
                .putString(KEY_ACCOUNT_NAME, accountName == null ? "" : accountName)
                .apply();
        if (enabled) {
            scheduleNext(context);
        } else {
            cancel(context);
        }
    }

    static boolean isEnabled(Context context) {
        return prefs(context).getBoolean(KEY_ENABLED, false);
    }

    static String accountName(Context context) {
        String value = prefs(context).getString(KEY_ACCOUNT_NAME, "");
        return value == null || value.isEmpty() ? null : value;
    }

    static long scheduleNext(Context context) {
        if (!isEnabled(context)) {
            return 0L;
        }

        long triggerAt = nextTriggerMillis();
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

    private static long nextTriggerMillis() {
        Calendar target = Calendar.getInstance();
        target.set(Calendar.HOUR_OF_DAY, 6);
        target.set(Calendar.MINUTE, 59);
        target.set(Calendar.SECOND, 30);
        target.set(Calendar.MILLISECOND, 0);
        if (target.getTimeInMillis() <= System.currentTimeMillis()) {
            target.add(Calendar.DAY_OF_MONTH, 1);
        }
        return target.getTimeInMillis();
    }
}

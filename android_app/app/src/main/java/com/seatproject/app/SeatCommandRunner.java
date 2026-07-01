package com.seatproject.app;

import android.content.Context;

import org.json.JSONArray;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;
import java.util.Locale;

final class SeatCommandRunner {
    private SeatCommandRunner() {
    }

    static int run(
            Context context,
            String command,
            String selectedAccountName,
            String bookingSendTime,
            LogSink logSink
    ) {
        List<Account> accounts = loadAccounts(context, logSink);
        List<Account> targets = selectedAccountName == null
                ? enabledAccounts(accounts)
                : namedAccount(accounts, selectedAccountName);

        if (targets.isEmpty()) {
            logSink.log("没有可运行的账号");
            return 1;
        }

        if ("book".equals(command) && bookingSendTime != null && !bookingSendTime.trim().isEmpty()) {
            if (!waitUntilClockTime(bookingSendTime, logSink)) {
                return targets.size();
            }
        }

        SeatApiClient client = new SeatApiClient(logSink);
        int failures = 0;
        for (Account account : targets) {
            try {
                String token = client.login(account);
                if (token.isEmpty()) {
                    failures += 1;
                    continue;
                }

                boolean ok;
                switch (command) {
                    case "book":
                        ok = client.reserve(account, token);
                        break;
                    case "status":
                        ok = client.latestBooking(account, token) != null;
                        break;
                    case "leave-short":
                        ok = client.leave(account, token, false);
                        break;
                    case "leave-long":
                        ok = client.leave(account, token, true);
                        break;
                    case "signoff":
                        ok = client.signoff(account, token);
                        break;
                    default:
                        throw new IllegalArgumentException("未知命令：" + command);
                }

                if (!ok) {
                    failures += 1;
                }
            } catch (Exception exception) {
                failures += 1;
                logSink.log("[" + account.name + "] 操作失败：" + exception.getMessage());
            }
        }
        return failures;
    }

    private static boolean waitUntilClockTime(String value, LogSink logSink) {
        int[] parts = parseClockTime(value);
        Calendar target = Calendar.getInstance();
        target.set(Calendar.HOUR_OF_DAY, parts[0]);
        target.set(Calendar.MINUTE, parts[1]);
        target.set(Calendar.SECOND, parts[2]);
        target.set(Calendar.MILLISECOND, 0);
        if (target.getTimeInMillis() <= System.currentTimeMillis()) {
            target.add(Calendar.DAY_OF_MONTH, 1);
        }

        logSink.log(String.format(Locale.CHINA,
                "等待到 %04d-%02d-%02d %02d:%02d:%02d 发送预约指令",
                target.get(Calendar.YEAR),
                target.get(Calendar.MONTH) + 1,
                target.get(Calendar.DAY_OF_MONTH),
                target.get(Calendar.HOUR_OF_DAY),
                target.get(Calendar.MINUTE),
                target.get(Calendar.SECOND)));

        while (System.currentTimeMillis() < target.getTimeInMillis()) {
            long remaining = target.getTimeInMillis() - System.currentTimeMillis();
            try {
                Thread.sleep(Math.min(remaining, 1000L));
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                logSink.log("等待被系统中断，取消本次预约");
                return false;
            }
        }
        return true;
    }

    private static int[] parseClockTime(String value) {
        String[] parts = value.trim().split(":");
        if (parts.length < 2 || parts.length > 3) {
            throw new IllegalArgumentException("时间格式错误，请使用 HH:MM:SS");
        }

        int hour = Integer.parseInt(parts[0]);
        int minute = Integer.parseInt(parts[1]);
        int second = parts.length == 3 ? Integer.parseInt(parts[2]) : 0;
        if (hour < 0 || hour > 23 || minute < 0 || minute > 59 || second < 0 || second > 59) {
            throw new IllegalArgumentException("时间范围错误，请使用 HH:MM:SS");
        }
        return new int[]{hour, minute, second};
    }

    static List<Account> loadAccounts(Context context, LogSink logSink) {
        List<Account> accounts = new ArrayList<>();
        try {
            JSONArray array = new JSONArray(new SecureStore(context).loadAccountsJson());
            for (int i = 0; i < array.length(); i++) {
                accounts.add(Account.fromJson(array.getJSONObject(i)));
            }
        } catch (Exception exception) {
            logSink.log("读取账号失败：" + exception.getMessage());
        }
        return accounts;
    }

    static List<Account> enabledAccounts(List<Account> accounts) {
        List<Account> result = new ArrayList<>();
        for (Account account : accounts) {
            if (account.enabled) {
                result.add(account);
            }
        }
        return result;
    }

    static List<Account> namedAccount(List<Account> accounts, String name) {
        List<Account> result = new ArrayList<>();
        for (Account account : accounts) {
            if (account.name.equals(name)) {
                result.add(account);
                break;
            }
        }
        return result;
    }
}

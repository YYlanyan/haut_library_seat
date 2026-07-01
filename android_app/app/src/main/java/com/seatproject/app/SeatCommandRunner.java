package com.seatproject.app;

import android.content.Context;

import org.json.JSONArray;

import java.util.ArrayList;
import java.util.List;

final class SeatCommandRunner {
    private SeatCommandRunner() {
    }

    static int run(
            Context context,
            String command,
            String selectedAccountName,
            boolean waitForBookingWindow,
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

        if ("book".equals(command) && waitForBookingWindow) {
            SeatApiClient.waitUntilLoginWindowIfNeeded(logSink);
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

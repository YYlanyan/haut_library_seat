package com.seatproject.app;

import android.Manifest;
import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final String WAIT_NOTIFICATION_CHANNEL_ID = "seat_manual_wait";
    private static final int WAIT_NOTIFICATION_ID = 65932;

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final List<Account> accounts = new ArrayList<>();
    private final List<Button> actionButtons = new ArrayList<>();

    private SecureStore secureStore;
    private Spinner accountSpinner;
    private Spinner bookingModeSpinner;
    private Spinner bookingHourSpinner;
    private Spinner bookingMinuteSpinner;
    private Spinner bookingSecondSpinner;
    private EditText nameInput;
    private EditText usernameInput;
    private EditText passwordInput;
    private EditText seatsInput;
    private Spinner regionSpinner;
    private Spinner seatSpinner;
    private CheckBox enabledInput;
    private CheckBox autoBookInput;
    private TextView autoBookStatusView;
    private TextView libraryPeopleView;
    private TextView logView;
    private final Map<Integer, List<SeatOption>> seatsByRegion = new LinkedHashMap<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        secureStore = new SecureStore(this);
        setContentView(buildContentView());
        requestNotificationPermissionIfNeeded();
        loadAccounts();
        refreshSpinner(null);
        loadAutoBookSettings();
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private View buildContentView() {
        ScrollView scrollView = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16), dp(16), dp(16), dp(16));
        scrollView.addView(root);

        LinearLayout titleRow = horizontalRow();
        titleRow.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = new TextView(this);
        title.setText("图书馆座位助手");
        title.setTextSize(22);
        title.setGravity(Gravity.START);
        title.setPadding(0, 0, 0, dp(12));
        title.setLayoutParams(new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        libraryPeopleView = new TextView(this);
        libraryPeopleView.setText("约 -- 人");
        libraryPeopleView.setTextSize(14);
        libraryPeopleView.setGravity(Gravity.END);
        libraryPeopleView.setPadding(dp(8), 0, 0, dp(12));
        titleRow.addView(title);
        titleRow.addView(libraryPeopleView);
        root.addView(titleRow);

        accountSpinner = new Spinner(this);
        root.addView(label("目标账号"));
        root.addView(accountSpinner);

        bookingModeSpinner = new Spinner(this);
        List<String> bookingModes = new ArrayList<>();
        bookingModes.add("直接发送预约指令");
        bookingModes.add("指定时间发送预约指令");
        ArrayAdapter<String> bookingModeAdapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, bookingModes);
        bookingModeAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        bookingModeSpinner.setAdapter(bookingModeAdapter);
        bookingHourSpinner = numberSpinner(0, 23, "时");
        bookingMinuteSpinner = numberSpinner(0, 59, "分");
        bookingSecondSpinner = numberSpinner(0, 59, "秒");
        setClockSpinners("06:59:30");
        root.addView(label("手动预约发送方式"));
        root.addView(bookingModeSpinner);
        root.addView(label("预约发送时间"));
        LinearLayout bookingTimeRow = horizontalRow();
        bookingTimeRow.addView(bookingHourSpinner);
        bookingTimeRow.addView(bookingMinuteSpinner);
        bookingTimeRow.addView(bookingSecondSpinner);
        root.addView(bookingTimeRow);

        autoBookInput = new CheckBox(this);
        autoBookInput.setText("每天按所选时分秒定时预约座位");
        root.addView(autoBookInput);

        Button saveAutoButton = plainButton("保存自动预约设置");
        saveAutoButton.setOnClickListener(v -> saveAutoBookSettings());
        root.addView(saveAutoButton);

        autoBookStatusView = label("");
        root.addView(autoBookStatusView);

        LinearLayout actionRow1 = horizontalRow();
        actionRow1.addView(actionButton("预约", "book"));
        actionRow1.addView(actionButton("查询", "status"));
        root.addView(actionRow1);

        LinearLayout actionRow2 = horizontalRow();
        actionRow2.addView(actionButton("短暂离开", "leave-short"));
        actionRow2.addView(actionButton("长暂离开", "leave-long"));
        actionRow2.addView(actionButton("签退", "signoff"));
        root.addView(actionRow2);

        TextView section = label("账号配置");
        section.setTextSize(18);
        section.setPadding(0, dp(18), 0, dp(8));
        root.addView(section);

        nameInput = input("账号名称，例如 account_1");
        usernameInput = input("学号 / 用户名");
        passwordInput = input("密码");
        seatsInput = input("座位列表，例如 1399, 623");
        enabledInput = new CheckBox(this);
        enabledInput.setText("启用账号");
        enabledInput.setChecked(true);

        root.addView(label("名称"));
        root.addView(nameInput);
        root.addView(label("用户名"));
        root.addView(usernameInput);
        root.addView(label("密码"));
        root.addView(passwordInput);
        root.addView(label("座位优先级"));
        root.addView(seatsInput);

        root.addView(label("从座位列表选择"));
        regionSpinner = new Spinner(this);
        seatSpinner = new Spinner(this);
        root.addView(regionSpinner);
        root.addView(seatSpinner);

        LinearLayout seatPickerRow = horizontalRow();
        Button crawlSeatsButton = plainButton("刷新座位列表");
        crawlSeatsButton.setOnClickListener(v -> crawlSeats());
        Button addSelectedSeatButton = plainButton("添加所选座位");
        addSelectedSeatButton.setOnClickListener(v -> addSelectedSeat());
        seatPickerRow.addView(crawlSeatsButton);
        seatPickerRow.addView(addSelectedSeatButton);
        root.addView(seatPickerRow);

        root.addView(enabledInput);

        LinearLayout editRow = horizontalRow();
        Button saveButton = plainButton("保存/更新账号");
        saveButton.setOnClickListener(v -> saveOrUpdateAccount());
        Button deleteButton = plainButton("删除当前账号");
        deleteButton.setOnClickListener(v -> deleteSelectedAccount());
        editRow.addView(saveButton);
        editRow.addView(deleteButton);
        root.addView(editRow);

        logView = new TextView(this);
        logView.setTextSize(13);
        logView.setTextIsSelectable(true);
        logView.setPadding(0, dp(16), 0, 0);
        root.addView(label("运行日志"));
        Button clearLogButton = plainButton("清空运行日志");
        clearLogButton.setOnClickListener(v -> clearLogs());
        root.addView(clearLogButton);
        root.addView(logView);
        return scrollView;
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 65931);
        }
    }

    private Button actionButton(String text, String command) {
        Button button = plainButton(text);
        button.setOnClickListener(v -> runCommand(command));
        actionButtons.add(button);
        return button;
    }

    private Button plainButton(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, dp(46), 1);
        params.setMargins(dp(4), dp(6), dp(4), dp(6));
        button.setLayoutParams(params);
        return button;
    }

    private EditText input(String hint) {
        EditText editText = new EditText(this);
        editText.setSingleLine(true);
        editText.setHint(hint);
        return editText;
    }

    private Spinner numberSpinner(int min, int max, String suffix) {
        List<String> values = new ArrayList<>();
        for (int value = min; value <= max; value++) {
            values.add(String.format(Locale.CHINA, "%02d%s", value, suffix));
        }
        Spinner spinner = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, values);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(adapter);
        return spinner;
    }

    private String selectedClockTime() {
        return String.format(
                Locale.CHINA,
                "%02d:%02d:%02d",
                bookingHourSpinner.getSelectedItemPosition(),
                bookingMinuteSpinner.getSelectedItemPosition(),
                bookingSecondSpinner.getSelectedItemPosition()
        );
    }

    private void setClockSpinners(String time) {
        int[] parts = parseClockTimeParts(time);
        bookingHourSpinner.setSelection(parts[0]);
        bookingMinuteSpinner.setSelection(parts[1]);
        bookingSecondSpinner.setSelection(parts[2]);
    }

    private int[] parseClockTimeParts(String time) {
        String[] parts = time == null ? new String[0] : time.trim().split(":");
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

    private TextView label(String text) {
        TextView label = new TextView(this);
        label.setText(text);
        label.setTextSize(14);
        label.setPadding(0, dp(8), 0, dp(4));
        return label;
    }

    private LinearLayout horizontalRow() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        return row;
    }

    private void saveOrUpdateAccount() {
        Account account = new Account(
                nameInput.getText().toString(),
                usernameInput.getText().toString(),
                passwordInput.getText().toString(),
                seatsInput.getText().toString(),
                enabledInput.isChecked()
        );

        if (account.name.isEmpty()) {
            toast("账号名称不能为空");
            return;
        }

        int existing = findAccountIndex(account.name);
        if (existing >= 0) {
            accounts.set(existing, account);
        } else {
            accounts.add(account);
        }

        saveAccounts();
        refreshSpinner(account.name);
        appendLog("已保存账号：" + account.name);
    }

    private void deleteSelectedAccount() {
        String selected = selectedAccountName();
        if (selected == null) {
            toast("请选择单个账号再删除");
            return;
        }

        int index = findAccountIndex(selected);
        if (index >= 0) {
            accounts.remove(index);
            saveAccounts();
            refreshSpinner(null);
            clearInputs();
            appendLog("已删除账号：" + selected);
        }
    }

    private void crawlSeats() {
        String selectedName = selectedAccountName();
        List<Account> targets = selectedName == null ? enabledAccounts() : namedAccount(selectedName);
        if (targets.isEmpty()) {
            toast("没有可用于爬取的账号");
            return;
        }

        Account account = targets.get(0);
        setRunning(true);
        appendLog("开始爬取座位列表，账号：" + account.name);
        executor.execute(() -> {
            SeatApiClient client = new SeatApiClient(this::appendLogFromWorker);
            try {
                String token = client.login(account);
                if (token.isEmpty()) {
                    throw new IllegalStateException("登录失败");
                }

                List<SeatRegion> regions = client.seatRegions(token);
                List<SeatRegion> availableRegions = new ArrayList<>();
                Map<Integer, List<SeatOption>> result = new LinkedHashMap<>();
                int totalSeatCount = 0;
                int availableSeatCount = 0;
                for (SeatRegion region : regions) {
                    SeatRegionSeats regionSeats = client.seatsByRegionWithStats(token, region.id);
                    List<SeatOption> seats = regionSeats.availableSeats;
                    totalSeatCount += regionSeats.totalSeats;
                    availableSeatCount += seats.size();
                    if (!seats.isEmpty()) {
                        availableRegions.add(region);
                        result.put(region.id, seats);
                    }
                    appendLogFromWorker("已爬取 " + region.name + "：" + seats.size() + " 个座位");
                }

                int occupiedSeatCount = Math.max(0, totalSeatCount - availableSeatCount);
                int finalTotalSeatCount = totalSeatCount;
                int finalAvailableSeatCount = availableSeatCount;
                mainHandler.post(() -> {
                    seatsByRegion.clear();
                    seatsByRegion.putAll(result);
                    refreshRegionSpinner(availableRegions);
                    updateLibraryPeople(occupiedSeatCount, finalTotalSeatCount, finalAvailableSeatCount);
                    setRunning(false);
                    appendLog("座位列表爬取完成：" + availableRegions.size() + " 个区域有可预约座位；约 "
                            + occupiedSeatCount + " 人在馆");
                    toast("座位列表爬取完成");
                });
            } catch (Exception exception) {
                mainHandler.post(() -> {
                    setRunning(false);
                    appendLog("座位列表爬取失败：" + exception.getMessage());
                    toast("座位列表爬取失败");
                });
            }
        });
    }

    private void refreshRegionSpinner(List<SeatRegion> regions) {
        ArrayAdapter<SeatRegion> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, regions);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        regionSpinner.setAdapter(adapter);
        regionSpinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
                SeatRegion region = (SeatRegion) regionSpinner.getSelectedItem();
                refreshSeatSpinner(region == null ? new ArrayList<>() : seatsByRegion.get(region.id));
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {
            }
        });
        if (!regions.isEmpty()) {
            refreshSeatSpinner(seatsByRegion.get(regions.get(0).id));
        } else {
            refreshSeatSpinner(new ArrayList<>());
        }
    }

    private void refreshSeatSpinner(List<SeatOption> seats) {
        List<SeatOption> options = seats == null ? new ArrayList<>() : seats;
        ArrayAdapter<SeatOption> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, options);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        seatSpinner.setAdapter(adapter);
    }

    private void updateLibraryPeople(int occupiedSeatCount, int totalSeatCount, int availableSeatCount) {
        if (libraryPeopleView == null) {
            return;
        }
        if (totalSeatCount <= 0) {
            libraryPeopleView.setText("约 -- 人");
            return;
        }
        libraryPeopleView.setText("约 " + occupiedSeatCount + " 人");
        appendLog("估算人数：总座位 " + totalSeatCount
                + " - 可预约 " + availableSeatCount
                + " = 约 " + occupiedSeatCount + " 人");
    }

    private void addSelectedSeat() {
        SeatOption seat = (SeatOption) seatSpinner.getSelectedItem();
        if (seat == null) {
            toast("请先刷新并选择座位");
            return;
        }
        if (!seat.canBook) {
            toast("该座位当前不可预约");
            return;
        }

        List<Integer> currentSeats = parseSeatIds(seatsInput.getText().toString());
        if (!currentSeats.contains(seat.id)) {
            currentSeats.add(seat.id);
        }
        seatsInput.setText(joinSeatIds(currentSeats));
        appendLog("已添加座位：" + seat);
    }

    private void runCommand(String command) {
        String selectedName = selectedAccountName();
        List<Account> targets = selectedName == null ? enabledAccounts() : namedAccount(selectedName);
        if (targets.isEmpty()) {
            toast("没有可运行的账号");
            return;
        }

        String bookingSendTime = null;
        if ("book".equals(command) && bookingModeSpinner.getSelectedItemPosition() == 1) {
            bookingSendTime = selectedClockTime();
        }

        setRunning(true);
        if ("book".equals(command) && bookingSendTime != null) {
            appendLog("开始执行：" + command + "，目标：" + (selectedName == null ? "全部启用账号" : selectedName)
                    + "，将在 " + bookingSendTime + " 发送预约指令");
            showWaitingBookingNotification(bookingSendTime);
        } else {
            appendLog("开始执行：" + command + "，目标：" + (selectedName == null ? "全部启用账号" : selectedName));
        }
        String finalBookingSendTime = bookingSendTime;
        executor.execute(() -> {
            int finalFailures = SeatCommandRunner.run(
                    this,
                    command,
                    selectedName,
                    finalBookingSendTime,
                    this::appendLogFromWorker
            );
            mainHandler.post(() -> {
                setRunning(false);
                if (finalBookingSendTime != null) {
                    cancelWaitingBookingNotification();
                }
                String message = finalFailures == 0 ? "全部操作完成" : "完成，但有 " + finalFailures + " 个账号失败";
                appendLog(message);
                toast(message);
            });
        });
    }

    private void saveAutoBookSettings() {
        String selectedName = selectedAccountName();
        boolean enabled = autoBookInput.isChecked();
        String bookTime = selectedClockTime();
        AutoBookScheduler.setEnabled(this, enabled, selectedName, bookTime);
        updateAutoBookStatus();

        if (enabled) {
            appendLog("已开启每日自动预约，时间：" + bookTime
                    + "，目标：" + (selectedName == null ? "全部启用账号" : selectedName));
        } else {
            appendLog("已关闭每日自动预约");
        }
    }

    private void loadAutoBookSettings() {
        autoBookInput.setChecked(AutoBookScheduler.isEnabled(this));
        String accountName = AutoBookScheduler.accountName(this);
        if (accountName != null) {
            int index = findAccountIndex(accountName);
            if (index >= 0) {
                accountSpinner.setSelection(index + 1);
            }
        }
        setClockSpinners(AutoBookScheduler.bookTime(this));
        updateAutoBookStatus();
    }

    private void updateAutoBookStatus() {
        if (!AutoBookScheduler.isEnabled(this)) {
            autoBookStatusView.setText("自动预约：未开启");
            return;
        }

        long next = AutoBookScheduler.scheduleNext(this);
        String accountName = AutoBookScheduler.accountName(this);
        autoBookStatusView.setText("自动预约：已开启；目标="
                + (accountName == null ? "全部启用账号" : accountName)
                + "；时间="
                + AutoBookScheduler.bookTime(this)
                + "；下次="
                + AutoBookScheduler.formatTime(next));
    }

    private void loadAccounts() {
        accounts.clear();
        try {
            JSONArray array = new JSONArray(secureStore.loadAccountsJson());
            for (int i = 0; i < array.length(); i++) {
                accounts.add(Account.fromJson(array.getJSONObject(i)));
            }
        } catch (Exception exception) {
            appendLog("读取账号失败：" + exception.getMessage());
        }
    }

    private void saveAccounts() {
        try {
            JSONArray array = new JSONArray();
            for (Account account : accounts) {
                array.put(account.toJson());
            }
            secureStore.saveAccountsJson(array.toString());
        } catch (Exception exception) {
            appendLog("保存账号失败：" + exception.getMessage());
        }
    }

    private void refreshSpinner(String preferredName) {
        List<String> names = new ArrayList<>();
        names.add("全部启用账号");
        for (Account account : accounts) {
            names.add(account.name);
        }

        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, names);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        accountSpinner.setAdapter(adapter);
        accountSpinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
                if (position > 0) {
                    fillInputs(accounts.get(position - 1));
                }
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {
            }
        });

        if (preferredName != null) {
            int index = findAccountIndex(preferredName);
            if (index >= 0) {
                accountSpinner.setSelection(index + 1);
            }
        }
    }

    private String selectedAccountName() {
        int position = accountSpinner.getSelectedItemPosition();
        if (position <= 0) {
            return null;
        }
        return accounts.get(position - 1).name;
    }

    private List<Account> enabledAccounts() {
        return SeatCommandRunner.enabledAccounts(accounts);
    }

    private List<Account> namedAccount(String name) {
        return SeatCommandRunner.namedAccount(accounts, name);
    }

    private int findAccountIndex(String name) {
        for (int i = 0; i < accounts.size(); i++) {
            if (accounts.get(i).name.equals(name)) {
                return i;
            }
        }
        return -1;
    }

    private void fillInputs(Account account) {
        nameInput.setText(account.name);
        usernameInput.setText(account.username);
        passwordInput.setText(account.password);
        seatsInput.setText(account.seats);
        enabledInput.setChecked(account.enabled);
    }

    private void clearInputs() {
        nameInput.setText("");
        usernameInput.setText("");
        passwordInput.setText("");
        seatsInput.setText("");
        enabledInput.setChecked(true);
    }

    private List<Integer> parseSeatIds(String text) {
        List<Integer> seats = new ArrayList<>();
        String normalized = text == null ? "" : text.replace('，', ',');
        for (String part : normalized.split(",")) {
            String value = part.trim();
            if (!value.isEmpty()) {
                try {
                    seats.add(Integer.parseInt(value));
                } catch (NumberFormatException ignored) {
                    // Ignore manually entered fragments that are not numeric seat ids.
                }
            }
        }
        return seats;
    }

    private String joinSeatIds(List<Integer> seats) {
        StringBuilder builder = new StringBuilder();
        for (Integer seat : seats) {
            if (builder.length() > 0) {
                builder.append(", ");
            }
            builder.append(seat);
        }
        return builder.toString();
    }

    private void setRunning(boolean running) {
        for (Button button : actionButtons) {
            button.setEnabled(!running);
        }
    }

    private void appendLogFromWorker(String message) {
        mainHandler.post(() -> appendLog(message));
    }

    private void appendLog(String message) {
        String time = new SimpleDateFormat("HH:mm:ss", Locale.CHINA).format(new Date());
        logView.append("[" + time + "] " + message + "\n");
    }

    private void clearLogs() {
        logView.setText("");
        toast("运行日志已清空");
    }

    private void showWaitingBookingNotification(String bookingSendTime) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return;
        }

        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    WAIT_NOTIFICATION_CHANNEL_ID,
                    "预约等待提示",
                    NotificationManager.IMPORTANCE_LOW
            );
            manager.createNotificationChannel(channel);
        }

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, WAIT_NOTIFICATION_CHANNEL_ID)
                : new Notification.Builder(this);
        Notification notification = builder
                .setSmallIcon(android.R.drawable.ic_menu_my_calendar)
                .setContentTitle("等待到达预约时间")
                .setContentText("将在 " + bookingSendTime + " 发送预约指令")
                .setOngoing(true)
                .build();
        manager.notify(WAIT_NOTIFICATION_ID, notification);
    }

    private void cancelWaitingBookingNotification() {
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        manager.cancel(WAIT_NOTIFICATION_ID);
    }

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    private int dp(int value) {
        float density = getResources().getDisplayMetrics().density;
        return Math.round(value * density);
    }
}

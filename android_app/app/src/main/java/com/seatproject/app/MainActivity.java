package com.seatproject.app;

import android.app.Activity;
import android.os.Bundle;
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
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final List<Account> accounts = new ArrayList<>();
    private final List<Button> actionButtons = new ArrayList<>();

    private SecureStore secureStore;
    private Spinner accountSpinner;
    private EditText nameInput;
    private EditText usernameInput;
    private EditText passwordInput;
    private EditText seatsInput;
    private CheckBox enabledInput;
    private CheckBox autoBookInput;
    private TextView autoBookStatusView;
    private TextView logView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        secureStore = new SecureStore(this);
        setContentView(buildContentView());
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

        TextView title = new TextView(this);
        title.setText("图书馆座位助手");
        title.setTextSize(22);
        title.setGravity(Gravity.START);
        title.setPadding(0, 0, 0, dp(12));
        root.addView(title);

        accountSpinner = new Spinner(this);
        root.addView(label("目标账号"));
        root.addView(accountSpinner);

        autoBookInput = new CheckBox(this);
        autoBookInput.setText("每天 06:59:30 自动预约当前选择目标");
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
        root.addView(logView);
        return scrollView;
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

    private void runCommand(String command) {
        String selectedName = selectedAccountName();
        List<Account> targets = selectedName == null ? enabledAccounts() : namedAccount(selectedName);
        if (targets.isEmpty()) {
            toast("没有可运行的账号");
            return;
        }

        setRunning(true);
        appendLog("开始执行：" + command + "，目标：" + (selectedName == null ? "全部启用账号" : selectedName));
        executor.execute(() -> {
            int finalFailures = SeatCommandRunner.run(
                    this,
                    command,
                    selectedName,
                    "book".equals(command),
                    this::appendLogFromWorker
            );
            mainHandler.post(() -> {
                setRunning(false);
                String message = finalFailures == 0 ? "全部操作完成" : "完成，但有 " + finalFailures + " 个账号失败";
                appendLog(message);
                toast(message);
            });
        });
    }

    private void saveAutoBookSettings() {
        String selectedName = selectedAccountName();
        boolean enabled = autoBookInput.isChecked();
        AutoBookScheduler.setEnabled(this, enabled, selectedName);
        updateAutoBookStatus();

        if (enabled) {
            appendLog("已开启每日自动预约，目标：" + (selectedName == null ? "全部启用账号" : selectedName));
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

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    private int dp(int value) {
        float density = getResources().getDisplayMetrics().density;
        return Math.round(value * density);
    }
}

package com.seatproject.app;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

final class SeatApiClient {
    private static final String BASE_URL = "https://wslib.haut.edu.cn";
    private static final String LOGIN_URL = BASE_URL + "/stage-api/login";
    private static final String BOOK_URL = BASE_URL + "/stage-api/api/seatbook/user/addbooking";
    private static final String MY_BOOKING_URL = BASE_URL + "/stage-api/seat/SeatBookingResult/my";
    private static final String TREE_URL = BASE_URL + "/stage-api/seat/SeatBookingResultAdd/treeselect";
    private static final String SEAT_QUERY_URL = BASE_URL + "/stage-api/api/seatbook/layout/query";
    private static final String LEAVE_SHORT_URL = BASE_URL + "/spacelink/api/seatbook/user/leave4short";
    private static final String LEAVE_LONG_URL = BASE_URL + "/spacelink/api/seatbook/user/leave4long";
    private static final String SIGNOFF_URL = BASE_URL + "/spacelink/api/seatbook/user/signoff";

    private final LogSink logSink;

    SeatApiClient(LogSink logSink) {
        this.logSink = logSink;
    }

    static void waitUntilLoginWindowIfNeeded(LogSink logSink) {
        long waitMillis = millisUntilLoginWindow();
        if (waitMillis <= 0L) {
            return;
        }

        logSink.log("当前不在预约登录时间段，等待到 06:59:30 后再登录预约");
        long target = System.currentTimeMillis() + waitMillis;
        while (System.currentTimeMillis() < target) {
            long remaining = target - System.currentTimeMillis();
            try {
                Thread.sleep(Math.min(remaining, 1000L));
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                logSink.log("等待被系统中断，取消本次预约");
                return;
            }
        }
        logSink.log("已到 06:59:30，开始登录预约");
    }

    String login(Account account) throws Exception {
        JSONObject body = new JSONObject();
        body.put("username", account.username);
        body.put("password", account.password);

        JSONObject result = request("POST", LOGIN_URL, null, body, null);
        String token = result.optString("token", "");
        if (token.isEmpty()) {
            log(account, "登录失败：" + result);
            return "";
        }

        log(account, "登录成功");
        return token;
    }

    boolean reserve(Account account, String token) throws Exception {
        List<Integer> seats = account.seatIds();
        if (seats.isEmpty()) {
            log(account, "座位列表为空");
            return false;
        }

        String startTime = bookingStartTime();
        String endTime = startTime.substring(0, 10) + " 22:00:00";
        long endAt = System.currentTimeMillis() + 5000;
        Map<String, String> headers = authHeaders(token);

        log(account, "开始预约，start=" + startTime + "，end=" + endTime + "，候选座位=" + seats);
        while (System.currentTimeMillis() < endAt) {
            for (Integer seatId : seats) {
                Map<String, String> params = new LinkedHashMap<>();
                params.put("channel", "1001");
                params.put("seatid", String.valueOf(seatId));
                params.put("starttime", startTime);
                params.put("endtime", endTime);

                JSONObject result = request("GET", BOOK_URL, params, null, headers);
                int code = result.optInt("code", -1);
                log(account, "尝试 seatid=" + seatId + "，返回：" + result);
                if (code == 200) {
                    log(account, "预约成功，seatid=" + seatId);
                    return true;
                }
            }
        }

        log(account, "本轮未预约成功");
        return false;
    }

    List<SeatRegion> seatRegions(String token) throws Exception {
        JSONObject result = request("GET", TREE_URL, null, null, authHeaders(token));
        JSONArray data = result.optJSONArray("data");
        List<SeatRegion> regions = new ArrayList<>();
        if (data != null) {
            collectRegions(data, regions);
        }
        return regions;
    }

    SeatRegionSeats seatsByRegionWithStats(String token, int regionId) throws Exception {
        Calendar now = Calendar.getInstance();
        Calendar start = Calendar.getInstance();
        start.add(Calendar.MINUTE, 4);
        String startTime = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.CHINA).format(start.getTime());
        String endTime = new SimpleDateFormat("yyyy-MM-dd", Locale.CHINA).format(now.getTime()) + " 22:00:00";

        Map<String, String> params = new LinkedHashMap<>();
        params.put("pageNum", "1");
        params.put("pageSize", "1000");
        params.put("regionid", String.valueOf(regionId));
        params.put("starttime", startTime);
        params.put("endtime", endTime);

        JSONObject result = request("GET", SEAT_QUERY_URL, params, null, authHeaders(token));
        JSONArray seatList = result.optJSONArray("seatList");
        if (seatList == null && result.optJSONObject("data") != null) {
            seatList = result.optJSONObject("data").optJSONArray("seatList");
        }

        List<SeatOption> seats = new ArrayList<>();
        if (seatList == null) {
            return new SeatRegionSeats(seats, 0);
        }

        int totalSeats = 0;
        for (int i = 0; i < seatList.length(); i++) {
            JSONObject seat = seatList.getJSONObject(i);
            int seatId = seat.optInt("id", 0);
            String seatName = seat.optString("seatName", "");
            if (seatId > 0 && !seatName.isEmpty()) {
                totalSeats += 1;
            }
            boolean canBook = seat.optInt("isCan", 0) == 1;
            if (seatId > 0 && !seatName.isEmpty() && canBook) {
                seats.add(new SeatOption(seatId, seatName, true));
            }
        }
        return new SeatRegionSeats(seats, totalSeats);
    }

    List<SeatOption> seatsByRegion(String token, int regionId) throws Exception {
        SeatRegionSeats result = seatsByRegionWithStats(token, regionId);
        return result.availableSeats;
    }

    private void collectRegions(JSONArray nodes, List<SeatRegion> result) throws Exception {
        for (int i = 0; i < nodes.length(); i++) {
            JSONObject node = nodes.getJSONObject(i);
            JSONArray children = node.optJSONArray("children");
            if (children != null && children.length() > 0) {
                collectRegions(children, result);
            } else {
                result.add(new SeatRegion(node.optInt("id"), node.optString("label")));
            }
        }
    }

    JSONObject latestBooking(Account account, String token) throws Exception {
        Map<String, String> params = new LinkedHashMap<>();
        params.put("pageNum", "1");
        params.put("pageSize", "10");

        JSONObject result = request("GET", MY_BOOKING_URL, params, null, authHeaders(token));
        JSONArray rows = result.optJSONArray("rows");
        if (rows == null || rows.length() == 0) {
            log(account, "没有预约记录");
            return null;
        }

        JSONObject booking = rows.getJSONObject(0);
        String bookingStatus = booking.optString("bookingStatus", "");
        if ("6".equals(bookingStatus) || "7".equals(bookingStatus)) {
            log(account, "当前无预约");
            return null;
        }

        log(account, "当前预约：id=" + booking.optString("id")
                + " seat=" + booking.optString("seatName")
                + " start=" + booking.optString("startDate")
                + " status=" + bookingStatus);
        return booking;
    }

    boolean leave(Account account, String token, boolean longLeave) throws Exception {
        JSONObject booking = latestBooking(account, token);
        if (booking == null) {
            return false;
        }

        String url = longLeave ? LEAVE_LONG_URL : LEAVE_SHORT_URL;
        JSONObject result = bookingCommand(url, booking, token);
        log(account, (longLeave ? "长暂离返回：" : "短暂离返回：") + result);
        return result.optInt("code", -1) == 200;
    }

    boolean signoff(Account account, String token) throws Exception {
        JSONObject booking = latestBooking(account, token);
        if (booking == null) {
            return false;
        }

        JSONObject result = bookingCommand(SIGNOFF_URL, booking, token);
        log(account, "签退返回：" + result);
        return result.optInt("code", -1) == 200;
    }

    private JSONObject bookingCommand(String url, JSONObject booking, String token) throws Exception {
        String bookingId = booking.optString("id", "");
        if (bookingId.isEmpty()) {
            throw new IllegalStateException("预约记录缺少 id");
        }

        Map<String, String> params = new LinkedHashMap<>();
        params.put("bookingid", bookingId);
        params.put("channelType", "1003");
        return request("GET", url, params, null, authHeaders(token));
    }

    private JSONObject request(
            String method,
            String url,
            Map<String, String> params,
            JSONObject body,
            Map<String, String> headers
    ) throws Exception {
        String fullUrl = url;
        if (params != null && !params.isEmpty()) {
            fullUrl = url + "?" + encodeParams(params);
        }

        HttpURLConnection connection = (HttpURLConnection) new URL(fullUrl).openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(10000);
        connection.setReadTimeout(10000);
        connection.setRequestProperty("Accept", "application/json");
        if (headers != null) {
            for (Map.Entry<String, String> entry : headers.entrySet()) {
                connection.setRequestProperty(entry.getKey(), entry.getValue());
            }
        }

        if (body != null) {
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            try (OutputStream out = connection.getOutputStream()) {
                out.write(body.toString().getBytes(StandardCharsets.UTF_8));
            }
        }

        int status = connection.getResponseCode();
        InputStream stream = status >= 200 && status < 400
                ? connection.getInputStream()
                : connection.getErrorStream();
        String text = readAll(stream);
        if (text.isEmpty()) {
            return new JSONObject();
        }
        return new JSONObject(text);
    }

    private Map<String, String> authHeaders(String token) {
        Map<String, String> headers = new LinkedHashMap<>();
        headers.put("Authorization", "Bearer " + token);
        return headers;
    }

    private String encodeParams(Map<String, String> params) throws Exception {
        StringBuilder builder = new StringBuilder();
        for (Map.Entry<String, String> entry : params.entrySet()) {
            if (builder.length() > 0) {
                builder.append('&');
            }
            builder.append(URLEncoder.encode(entry.getKey(), "UTF-8"));
            builder.append('=');
            builder.append(URLEncoder.encode(entry.getValue(), "UTF-8"));
        }
        return builder.toString();
    }

    private String readAll(InputStream stream) throws Exception {
        if (stream == null) {
            return "";
        }

        StringBuilder builder = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                builder.append(line);
            }
        }
        return builder.toString();
    }

    private String bookingStartTime() {
        Calendar now = Calendar.getInstance();
        int hour = now.get(Calendar.HOUR_OF_DAY);
        int minute = now.get(Calendar.MINUTE);

        Calendar start = Calendar.getInstance();
        if (hour < 7) {
            start.set(Calendar.HOUR_OF_DAY, 7);
            start.set(Calendar.MINUTE, 30);
            start.set(Calendar.SECOND, 0);
        } else if (hour == 7 && minute < 30) {
            start.set(Calendar.HOUR_OF_DAY, 7);
            start.set(Calendar.MINUTE, 30);
            start.set(Calendar.SECOND, 0);
        } else if (hour < 21 || (hour == 21 && minute == 0)) {
            start.add(Calendar.MINUTE, 4);
        } else {
            start.add(Calendar.DAY_OF_MONTH, 1);
            start.set(Calendar.HOUR_OF_DAY, 7);
            start.set(Calendar.MINUTE, 30);
            start.set(Calendar.SECOND, 0);
        }
        return new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.CHINA).format(start.getTime());
    }

    private String today() {
        return new SimpleDateFormat("yyyy-MM-dd", Locale.CHINA).format(Calendar.getInstance().getTime());
    }

    private static long millisUntilLoginWindow() {
        Calendar now = Calendar.getInstance();
        Calendar target = Calendar.getInstance();
        target.set(Calendar.HOUR_OF_DAY, 6);
        target.set(Calendar.MINUTE, 59);
        target.set(Calendar.SECOND, 30);
        target.set(Calendar.MILLISECOND, 0);

        Calendar close = Calendar.getInstance();
        close.set(Calendar.HOUR_OF_DAY, 21);
        close.set(Calendar.MINUTE, 0);
        close.set(Calendar.SECOND, 0);
        close.set(Calendar.MILLISECOND, 0);

        long nowMillis = now.getTimeInMillis();
        if (nowMillis >= target.getTimeInMillis() && nowMillis <= close.getTimeInMillis()) {
            return 0L;
        }

        if (nowMillis > close.getTimeInMillis()) {
            target.add(Calendar.DAY_OF_MONTH, 1);
        }
        return Math.max(0L, target.getTimeInMillis() - nowMillis);
    }

    private void log(Account account, String message) {
        logSink.log("[" + account.name + "] " + message);
    }
}

final class SeatRegion {
    final int id;
    final String name;

    SeatRegion(int id, String name) {
        this.id = id;
        this.name = name;
    }

    @Override
    public String toString() {
        return name;
    }
}

final class SeatOption {
    final int id;
    final String name;
    final boolean canBook;

    SeatOption(int id, String name, boolean canBook) {
        this.id = id;
        this.name = name;
        this.canBook = canBook;
    }

    @Override
    public String toString() {
        return name + " | " + id + " | " + (canBook ? "可预约" : "不可预约");
    }
}

final class SeatRegionSeats {
    final List<SeatOption> availableSeats;
    final int totalSeats;

    SeatRegionSeats(List<SeatOption> availableSeats, int totalSeats) {
        this.availableSeats = availableSeats;
        this.totalSeats = totalSeats;
    }
}

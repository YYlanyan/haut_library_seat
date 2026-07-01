package com.seatproject.app;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

final class Account {
    final String name;
    final String username;
    final String password;
    final String seats;
    final boolean enabled;

    Account(String name, String username, String password, String seats, boolean enabled) {
        this.name = name == null ? "" : name.trim();
        this.username = username == null ? "" : username.trim();
        this.password = password == null ? "" : password;
        this.seats = seats == null ? "" : seats.trim();
        this.enabled = enabled;
    }

    List<Integer> seatIds() {
        List<Integer> ids = new ArrayList<>();
        String normalized = seats.replace('，', ',');
        for (String part : normalized.split(",")) {
            String value = part.trim();
            if (!value.isEmpty()) {
                ids.add(Integer.parseInt(value));
            }
        }
        return ids;
    }

    JSONObject toJson() throws JSONException {
        JSONObject json = new JSONObject();
        json.put("name", name);
        json.put("username", username);
        json.put("password", password);
        json.put("seats", seats);
        json.put("enabled", enabled);
        return json;
    }

    static Account fromJson(JSONObject json) {
        return new Account(
                json.optString("name"),
                json.optString("username"),
                json.optString("password"),
                json.optString("seats"),
                json.optBoolean("enabled", true)
        );
    }
}

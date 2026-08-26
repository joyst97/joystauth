package com.joyst;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class api {
    public static class UserData {
        public String username = "";
        public String subscription = "";
        public String expiry = "";
        public String hwid = "";
        public String ip = "";
    }

    public static class ResponseData {
        public boolean success = false;
        public String message = "";
    }

    public final String name;
    public final String token;
    public final String version;
    public final String url;

    public final String hwid;
    public String sessionid;
    public boolean isInitialized = false;

    public UserData userData = new UserData();
    public ResponseData response = new ResponseData();

    private final HttpClient httpClient;

    public api(String name, String token) {
        this(name, token, "1.0", "https://joystauth.cc");
    }

    public api(String name, String token, String version, String url) {
        this.name = name;
        this.token = token;
        this.version = version;
        this.url = (url == null || url.isEmpty() ? "https://joystauth.cc" : url).replaceAll("/+$", "");
        this.hwid = extractHwid();
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(8))
                .build();
    }

    private String extractHwid() {
        try {
            Process process = Runtime.getRuntime().exec("whoami /user");
            BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()));
            String line;
            Pattern pattern = Pattern.compile("S-1-5-21-\\d+-\\d+-\\d+-\\d+");
            while ((line = reader.readLine()) != null) {
                Matcher matcher = pattern.matcher(line);
                if (matcher.find()) {
                    return matcher.group(0);
                }
            }
        } catch (Exception ignored) {}
        return System.getProperty("user.name") + "_" + System.getProperty("os.name");
    }

    public boolean init() {
        try {
            String json = String.format("{\"app_name\":\"%s\",\"app_token\":\"%s\",\"hwid\":\"%s\",\"version\":\"%s\"}",
                    name, token, hwid, version);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url + "/api/v1/client/init"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();

            HttpResponse<String> httpResponse = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            String body = httpResponse.body();

            if (body.contains("\"success\":true") || body.contains("\"success\": true")) {
                this.isInitialized = true;
                this.response.success = true;
                this.response.message = "Initialized successfully";
                return true;
            }

            if (body.contains("maintenance") || body.contains("\"is_maintenance\":true")) {
                this.response.success = false;
                this.response.message = "Application is under maintenance!";
                System.err.println("\n🚨 [EMERGENCY MAINTENANCE ACTIVE] Application is under maintenance!");
                System.exit(0);
            }

            this.response.success = false;
            this.response.message = "Initialization failed";
            return false;
        } catch (Exception e) {
            this.response.success = false;
            this.response.message = e.getMessage();
            return false;
        }
    }

    public boolean login(String username, String password) {
        try {
            String json = String.format("{\"app_name\":\"%s\",\"app_token\":\"%s\",\"username\":\"%s\",\"password\":\"%s\",\"hwid\":\"%s\",\"sessionid\":\"%s\"}",
                    name, token, username, password, hwid, sessionid != null ? sessionid : "");

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url + "/api/v1/client/login"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();

            HttpResponse<String> httpResponse = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            String body = httpResponse.body();

            if (body.contains("\"success\":true") || body.contains("\"success\": true")) {
                this.userData.username = username;
                this.response.success = true;
                this.response.message = "Logged in successfully";
                return true;
            } else {
                this.response.success = false;
                this.response.message = "Login failed";
                return false;
            }
        } catch (Exception e) {
            this.response.success = false;
            this.response.message = e.getMessage();
            return false;
        }
    }

    public boolean license(String key) {
        try {
            String json = String.format("{\"app_name\":\"%s\",\"app_token\":\"%s\",\"license_key\":\"%s\",\"hwid\":\"%s\",\"sessionid\":\"%s\"}",
                    name, token, key, hwid, sessionid != null ? sessionid : "");

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url + "/api/v1/client/license"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();

            HttpResponse<String> httpResponse = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            String body = httpResponse.body();

            if (body.contains("\"success\":true") || body.contains("\"success\": true")) {
                this.userData.username = key;
                this.response.success = true;
                this.response.message = "License valid";
                return true;
            } else {
                this.response.success = false;
                this.response.message = "Invalid license";
                return false;
            }
        } catch (Exception e) {
            this.response.success = false;
            this.response.message = e.getMessage();
            return false;
        }
    }
}

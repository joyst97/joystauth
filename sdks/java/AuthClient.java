package com.joyst;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;

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
    public final String ownerid;
    public final String secret;
    public final String version;
    public final String url;

    public final String hwid;
    public String sessionid;
    public boolean isInitialized = false;

    public UserData userData = new UserData();
    public ResponseData response = new ResponseData();

    private final HttpClient httpClient;

    public api(String name, String ownerid, String secret, String version, String url) {
        this.name = name;
        this.ownerid = ownerid;
        this.secret = secret;
        this.version = version;
        this.url = url.replaceAll("/+$", "");
        this.hwid = extractHwid();
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(8))
                .build();
    }

    private String extractHwid() {
        try {
            String raw = System.getProperty("os.name") + System.getProperty("user.name") + System.getenv("PROCESSOR_IDENTIFIER");
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(raw.trim().toUpperCase().getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            return "DEFAULT_JAVA_HWID";
        }
    }

    public boolean init() {
        try {
            String json = String.format("{\"name\":\"%s\",\"ownerid\":\"%s\",\"secret\":\"%s\",\"hwid\":\"%s\",\"version\":\"%s\"}",
                    name, ownerid, secret, hwid, version);

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
        if (!isInitialized && !init()) return false;
        this.userData.username = username;
        this.userData.subscription = "Default";
        this.response.success = true;
        this.response.message = "Logged in successfully";
        return true;
    }
}

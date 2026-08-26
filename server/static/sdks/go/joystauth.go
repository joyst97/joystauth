package joystauth

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"regexp"
	"strings"
	"time"
)

type UserData struct {
	Username     string `json:"username"`
	Subscription string `json:"subscription"`
	Expiry       string `json:"expiry"`
	HWID         string `json:"hwid"`
}

type ResponseData struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}

type API struct {
	Name      string
	Token     string
	Version   string
	URL       string
	HWID      string
	SessionID string
	UserData  UserData
	Response  ResponseData
	client    *http.Client
}

func New(name, token string, version ...string) *API {
	ver := "1.0"
	if len(version) > 0 {
		ver = version[0]
	}
	api := &API{
		Name:    name,
		Token:   token,
		Version: ver,
		URL:     "https://joystauth.cc",
		HWID:    getHWID(),
		client:  &http.Client{Timeout: 8 * time.Second},
	}
	api.Init(true)
	return api
}

func getHWID() string {
	out, err := exec.Command("whoami", "/user").Output()
	if err == nil {
		re := regexp.MustCompile(`S-1-5-21-\d+-\d+-\d+-\d+`)
		match := re.FindString(string(out))
		if match != "" {
			return match
		}
	}
	hostname, _ := os.Hostname()
	return hostname
}

func (a *API) post(endpoint string, data map[string]interface{}) (map[string]interface{}, error) {
	jsonData, _ := json.Marshal(data)
	resp, err := a.client.Post(a.URL+endpoint, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var res map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&res)
	return res, nil
}

func (a *API) Init(autoExitOnMaint bool) bool {
	res, err := a.post("/api/v1/client/init", map[string]interface{}{
		"app_name":  a.Name,
		"app_token": a.Token,
		"version":   a.Version,
		"hwid":      a.HWID,
	})
	if err != nil || res == nil {
		a.Response = ResponseData{Success: false, Message: "Server connection failed"}
		return false
	}

	if ok, _ := res["success"].(bool); ok {
		if sid, exists := res["sessionid"].(string); exists {
			a.SessionID = sid
		}
		a.Response = ResponseData{Success: true, Message: "Initialized"}
		return true
	}

	msg, _ := res["message"].(string)
	a.Response = ResponseData{Success: false, Message: msg}
	if autoExitOnMaint && strings.Contains(strings.ToLower(msg), "maintenance") {
		fmt.Println("[JOYST ALERT] " + msg)
		os.Exit(1)
	}
	return false
}

func (a *API) Login(username, password string) bool {
	res, err := a.post("/api/v1/client/login", map[string]interface{}{
		"app_name":  a.Name,
		"app_token": a.Token,
		"username":  strings.TrimSpace(username),
		"password":  password,
		"hwid":      a.HWID,
		"sessionid": a.SessionID,
	})
	if err != nil || res == nil {
		a.Response = ResponseData{Success: false, Message: "Connection error"}
		return false
	}

	if ok, _ := res["success"].(bool); ok {
		a.UserData.Username = username
		a.Response = ResponseData{Success: true, Message: "Logged in successfully"}
		return true
	}

	msg, _ := res["message"].(string)
	a.Response = ResponseData{Success: false, Message: msg}
	return false
}

func (a *API) License(key string) bool {
	res, err := a.post("/api/v1/client/license", map[string]interface{}{
		"app_name":    a.Name,
		"app_token":   a.Token,
		"license_key": strings.TrimSpace(key),
		"hwid":        a.HWID,
		"sessionid":   a.SessionID,
	})
	if err != nil || res == nil {
		a.Response = ResponseData{Success: false, Message: "Connection error"}
		return false
	}

	if ok, _ := res["success"].(bool); ok {
		a.UserData.Username = key
		a.Response = ResponseData{Success: true, Message: "License active"}
		return true
	}

	msg, _ := res["message"].(string)
	a.Response = ResponseData{Success: false, Message: msg}
	return false
}

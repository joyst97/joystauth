use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::error::Error;

#[derive(Serialize)]
struct InitPayload {
    name: String,
    ownerid: String,
    secret: String,
    version: String,
    hwid: String,
}

#[derive(Deserialize, Debug)]
struct InitResponse {
    success: bool,
    sessionid: Option<String>,
    message: Option<String>,
}

fn get_hwid() -> String {
    let raw = format!("{}-{}", whoami::username(), whoami::devicename());
    let mut hasher = Sha256::new();
    hasher.update(raw.as_bytes());
    format!("{:x}", hasher.finalize())
}

mod whoami {
    pub fn username() -> String {
        std::env::var("USERNAME").unwrap_or_else(|_| "user".to_string())
    }
    pub fn devicename() -> String {
        std::env::var("COMPUTERNAME").unwrap_or_else(|_| "pc".to_string())
    }
}

pub struct api {
    pub name: String,
    pub ownerid: String,
    pub secret: String,
    pub version: String,
    pub url: String,
    pub hwid: String,
    pub sessionid: Option<String>,
}

impl api {
    pub fn new(name: &str, ownerid: &str, secret: &str, version: &str, url: &str) -> Self {
        Self {
            name: name.to_string(),
            ownerid: ownerid.to_string(),
            secret: secret.to_string(),
            version: version.to_string(),
            url: url.trim_end_matches('/').to_string(),
            hwid: get_hwid(),
            sessionid: None,
        }
    }

    pub async fn init(&mut self) -> Result<bool, Box<dyn Error>> {
        let client = reqwest::Client::new();
        let payload = InitPayload {
            name: self.name.clone(),
            ownerid: self.ownerid.clone(),
            secret: self.secret.clone(),
            version: self.version.clone(),
            hwid: self.hwid.clone(),
        };

        let res: InitResponse = client
            .post(format!("{}/api/v1/client/init", self.url))
            .json(&payload)
            .send()
            .await?
            .json()
            .await?;

        if res.success {
            self.sessionid = res.sessionid;
            Ok(true)
        } else {
            Ok(false)
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    println!("==================================================");
    println!("      ⚡ JOYST CORPORATION - RUST AUTH DEMO       ");
    println!("==================================================");

    let mut auth = api::new("JoystApp", "joyst_owner", "sec_default", "1.0", "http://127.0.0.1:8000");

    println!("[+] Hardware ID (HWID): {}", auth.hwid);
    println!("[*] Initializing connection to Joyst server...");

    if auth.init().await? {
        println!("[+] Session initialized: {:?}", auth.sessionid.unwrap_or_default());
        println!("[+] Rust client authenticated successfully!");
    } else {
        println!("[-] Failed to initialize session.");
    }

    Ok(())
}

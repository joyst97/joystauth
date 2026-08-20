// JOYST CORPORATION AUTH - Advanced Cyber Crimson Interactive Landing Script

document.addEventListener("DOMContentLoaded", () => {
    initScrollReveal();
    initFaqAccordion();
    initSdkPlayground();
    init3DTilt();
    initTelemetryPulse();
});

// 0. Ultra-Smooth Staggered Scroll Reveal Observer
function initScrollReveal() {
    const reveals = document.querySelectorAll(".reveal-on-scroll, .section-wrapper, .pipeline-step, .glass-panel");
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add("is-visible");
            }
        });
    }, {
        threshold: 0.12,
        rootMargin: "0px 0px -50px 0px"
    });

    reveals.forEach(el => {
        el.classList.add("reveal-on-scroll");
        observer.observe(el);
    });
}

// 1. FAQ Accordion
function initFaqAccordion() {
    const questions = document.querySelectorAll(".faq-question");
    questions.forEach(q => {
        q.addEventListener("click", () => {
            const card = q.parentElement;
            const answer = card.querySelector(".faq-answer");
            const icon = q.querySelector(".faq-icon");
            const isOpen = answer.style.display === "block";

            document.querySelectorAll(".faq-answer").forEach(a => a.style.display = "none");
            document.querySelectorAll(".faq-icon").forEach(i => i.textContent = "+");

            if (!isOpen) {
                answer.style.display = "block";
                if (icon) icon.textContent = "−";
            }
        });
    });
}

// 2. Multi-Language SDK Studio
const sdkSnippets = {
    cpp: `// ================== JOYST CORPORATION C++ SDK ==================
#include "AuthClient.hpp"
#include <iostream>

int main() {
    // 1. Initialize with your App parameters
    JoystAuth::api auth("SuperCheatPro", "joyst_dev_88a91c", "sec_77918750...", "2.5", "http://127.0.0.1:8000");
    auth.init();

    // 2. Ultra-Safe Login (Motherboard HWID Check + AES-256 Encryption)
    if (auth.login("gamer123", "password123")) {
        std::cout << "✅ [AUTHENTICATED] Welcome " << auth.user_data.username << "\\n";
        std::cout << "💎 Subscription: " << auth.user_data.subscription << "\\n";
        std::cout << "🔒 Locked HWID:  " << auth.user_data.hwid.substr(0, 16) << "...\\n";
        
        // 3. Fetch Zero-Leak Encrypted Cloud Offsets
        // std::string offset = auth.var("GAME_OFFSET");
    } else {
        std::cout << "❌ [BLOCKED] " << auth.response.message << "\\n";
    }
    return 0;
}`,

    python: `# ================== JOYST CORPORATION PYTHON SDK ==================
from auth_client import api

# 1. Initialize
auth = api(
    name="SuperCheatPro",
    ownerid="joyst_dev_88a91c",
    secret="sec_77918750...",
    version="2.5",
    url="http://127.0.0.1:8000"
)

# 2. Login User (Strict Motherboard HWID Binding)
if auth.login("gamer123", "password123"):
    print(f"✅ Login Success! Welcome {auth.user_data.username}")
    print(f"💎 Subscription: {auth.user_data.subscription}")
    print(f"⏳ Expiry: {auth.user_data.expiry}")
else:
    print(f"❌ Blocked: {auth.response.message}")`,

    csharp: `// ================== JOYST CORPORATION C# .NET SDK ==================
using System;
using System.Threading.Tasks;
using JoystAuth;

class Program {
    static async Task Main(string[] args) {
        var auth = new api("SuperCheatPro", "joyst_dev_88a91c", "sec_77918750...", "2.5", "http://127.0.0.1:8000");
        await auth.init();

        if (await auth.login("gamer123", "password123")) {
            Console.WriteLine($"✅ Login Success! Welcome {auth.user_data.username}");
            Console.WriteLine($"💎 Subscription: {auth.user_data.subscription}");
        } else {
            Console.WriteLine($"❌ Error: {auth.response.message}");
        }
    }
}`,

    nodejs: `// ================== JOYST CORPORATION NODE.JS SDK ==================
const JoystAuth = require('./joyst_auth');

async function start() {
    const auth = new JoystAuth("SuperCheatPro", "joyst_dev_88a91c", "sec_77918750...", "2.5");
    await auth.init();

    if (await auth.login("gamer123", "password123")) {
        console.log("✅ Authenticated: " + auth.userData.username);
    } else {
        console.log("❌ Failed: " + auth.response.message);
    }
}
start();`,

    java: `// ================== JOYST CORPORATION JAVA SDK ==================
import com.joyst.api;

public class Main {
    public static void main(String[] args) {
        api auth = new api("SuperCheatPro", "joyst_dev_88a91c", "sec_77918750...", "2.5");
        auth.init();

        if (auth.login("gamer123", "password123")) {
            System.out.println("✅ Authenticated: " + auth.userData.username);
        } else {
            System.out.println("❌ Blocked: " + auth.response.message);
        }
    }
}`,

    rust: `// ================== JOYST CORPORATION RUST SDK ==================
use joyst_auth::api;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut auth = api::new("SuperCheatPro", "joyst_dev_88a91c", "sec_77918750...", "2.5", "http://127.0.0.1:8000");
    auth.init().await?;

    if auth.login("gamer123", "password123").await? {
        println!("✅ Authenticated! Welcome {:?}", auth.user_data.username);
    } else {
        println!("❌ Failed: {}", auth.response.message);
    }
    Ok(())
}`
};

function initSdkPlayground() {
    const buttons = document.querySelectorAll(".lang-pill-btn");
    buttons.forEach(btn => {
        btn.addEventListener("click", () => {
            buttons.forEach(b => {
                b.classList.remove("active");
                b.style.background = "transparent";
                b.style.color = "var(--text-secondary)";
                b.style.borderColor = "transparent";
            });
            btn.classList.add("active");
            btn.style.background = "rgba(225, 29, 72, 0.25)";
            btn.style.color = "#fff";
            btn.style.borderColor = "var(--brand-rose)";

            const lang = btn.getAttribute("data-lang");
            const codeDisplay = document.getElementById("playground-code-display");
            if (codeDisplay && sdkSnippets[lang]) {
                codeDisplay.textContent = sdkSnippets[lang];
            }
        });
    });
}

function copyPlaygroundCode() {
    const codeDisplay = document.getElementById("playground-code-display");
    if (codeDisplay) {
        navigator.clipboard.writeText(codeDisplay.textContent).then(() => {
            showLandingToast("📋 SDK implementation code copied to clipboard!");
        });
    }
}

// 3. Interactive Game Client Authenticator Demo
let isSimulating = false;
async function triggerClientLaunchDemo() {
    if (isSimulating) return;
    isSimulating = true;

    const btn = document.getElementById("btn-launch-demo");
    const progressBox = document.getElementById("loader-progress-box");
    const progressBar = document.getElementById("loader-progress-bar");
    const statusMsg = document.getElementById("loader-status-msg");
    const statusPct = document.getElementById("loader-status-pct");

    if (progressBox) progressBox.style.display = "block";
    if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ Authenticating Handshake...";
    }

    if (statusMsg) statusMsg.textContent = "🔒 [1/4] Scanning Motherboard BIOS & CPU Enclave...";
    if (progressBar) progressBar.style.width = "25%";
    if (statusPct) statusPct.textContent = "25%";
    await sleep(400);

    if (statusMsg) statusMsg.textContent = "⚡ [2/4] AES-256 Dynamic Session Key Handshake...";
    if (progressBar) progressBar.style.width = "60%";
    if (statusPct) statusPct.textContent = "60%";
    await sleep(450);

    if (statusMsg) statusMsg.textContent = "💎 [3/4] Verifying VIP Lifetime License...";
    if (progressBar) progressBar.style.width = "90%";
    if (statusPct) statusPct.textContent = "90%";
    await sleep(350);

    if (statusMsg) {
        statusMsg.style.color = "#34d399";
        statusMsg.textContent = "✅ [4/4] 200 OK • Memory Enclave Injected (0.8ms)!";
    }
    if (progressBar) {
        progressBar.style.width = "100%";
        progressBar.style.background = "#10b981";
    }
    if (statusPct) statusPct.textContent = "100%";

    if (btn) {
        btn.style.background = "linear-gradient(180deg, #10b981 0%, #059669 100%)";
        btn.style.borderColor = "rgba(16, 185, 129, 0.4)";
        btn.textContent = "✨ Software Launched (0.8ms)";
    }

    showLandingToast("🎮 Software Successfully Authenticated & Injected into Memory!");

    setTimeout(() => {
        if (btn) {
            btn.disabled = false;
            btn.style.background = "";
            btn.style.borderColor = "";
            btn.textContent = "🚀 Launch & Authenticate Software";
        }
        if (progressBox) progressBox.style.display = "none";
        if (progressBar) {
            progressBar.style.width = "0%";
            progressBar.style.background = "linear-gradient(90deg, #e11d48, #ff4d79)";
        }
        if (statusMsg) {
            statusMsg.style.color = "#fff";
            statusMsg.textContent = "Initializing Secure Handshake...";
        }
        isSimulating = false;
    }, 4500);
}

// 4. Interactive Live License Key Generator Widget
function generateLandingKey() {
    const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    function segment(len) {
        let res = "";
        for (let i = 0; i < len; i++) {
            res += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return res;
    }
    const key = `JOYST-PRO-${segment(4)}-${segment(4)}-${segment(4)}`;
    
    const keyEl = document.getElementById("landing-live-key-val");
    const badgeEl = document.getElementById("landing-live-key-status");
    if (keyEl) {
        keyEl.textContent = key;
        keyEl.style.color = "#ff2a5f";
        setTimeout(() => { keyEl.style.color = "#fff"; }, 300);
    }
    if (badgeEl) {
        badgeEl.innerHTML = `<span class="badge-dot" style="background:#10b981;"></span> VALID (30 Days VIP • 256-Bit Mask)`;
    }
    showLandingToast(`🔑 Generated License: ${key}`);
}

function copyLandingGeneratedKey() {
    const keyEl = document.getElementById("landing-live-key-val");
    if (keyEl) {
        navigator.clipboard.writeText(keyEl.textContent.trim()).then(() => {
            showLandingToast("📋 License Key copied to clipboard!");
        });
    }
}

// 5. Interactive Threat Radar Simulator
function testIntruderBlock() {
    const intruderResult = document.getElementById("intruder-sim-result");
    if (!intruderResult) return;

    intruderResult.innerHTML = `
        <div style="background: rgba(225, 29, 72, 0.15); border: 1px solid #e11d48; padding: 14px; border-radius: 10px; margin-top: 14px; animation: pulseGlow 1.5s infinite;">
            <div style="color: #fb7185; font-weight: 800; font-size: 13.5px; margin-bottom: 4px;">🚨 [SECURITY ALERT TRIGGERED]</div>
            <div style="font-size: 12.5px; color: #fff;">Unauthorized PC (HWID: <code class="mono">a9f81...</code>) attempted login. Blocked immediately at gateway.</div>
            <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 6px;">📢 Automated Discord Webhook log dispatched to your admin channel.</div>
        </div>
    `;
    showLandingToast("🛡️ Intruder Attempt Successfully Blocked & Logged!");
}

// 6. 3D Card Tilt & Interactive Spotlight Physics
function init3DTilt() {
    const cards = document.querySelectorAll(".spotlight-card, .glass-panel, .pipeline-step, .hero-matrix-card");
    cards.forEach(card => {
        card.addEventListener("mousemove", (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            card.style.setProperty("--mouse-x", `${x}px`);
            card.style.setProperty("--mouse-y", `${y}px`);

            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            
            const rotateX = ((y - centerY) / centerY) * -4;
            const rotateY = ((x - centerX) / centerX) * 4;
            
            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
        });

        card.addEventListener("mouseleave", () => {
            card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px)";
        });
    });
}

// 7. Live Telemetry Metric Pulse
function initTelemetryPulse() {
    const latencyEl = document.getElementById("live-latency-val");
    if (!latencyEl) return;

    setInterval(() => {
        const pings = ["3.2ms", "3.6ms", "3.4ms", "3.9ms", "3.1ms", "3.5ms"];
        const randomPing = pings[Math.floor(Math.random() * pings.length)];
        latencyEl.textContent = randomPing;
    }, 2800);
}

// Toast Helper
function showLandingToast(msg) {
    let toast = document.getElementById("landing-toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "landing-toast";
        toast.style.cssText = "position: fixed; bottom: 30px; right: 30px; background: rgba(18, 4, 8, 0.95); border: 1px solid #e11d48; color: #fff; padding: 14px 22px; border-radius: 12px; font-size: 13.5px; font-weight: 700; z-index: 99999; box-shadow: 0 10px 40px rgba(225, 29, 72, 0.4); display: flex; align-items: center; gap: 10px; transition: all 0.3s ease;";
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0)";

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(20px)";
    }, 3200);
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

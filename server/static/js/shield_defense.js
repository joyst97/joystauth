/**
 * JOYST AUTH — Hyper-Aggressive Client-Side Enclave Defense Shield
 * Universal Anti-Inspect, Anti-F12, Anti-DevTools Debugger Lock, Console Wiper & DOM Blinder
 */
(function () {
    "use strict";

    // 1. Disable Right Click Context Menu
    document.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        e.stopPropagation();
        return false;
    }, { capture: true });

    // 2. Block Keyboard Shortcuts (F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+Shift+C, Ctrl+U, Ctrl+S, Ctrl+P)
    document.addEventListener("keydown", function (e) {
        // F12
        if (e.key === "F12" || e.keyCode === 123) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }

        // Ctrl + Shift + I (Inspect)
        if (e.ctrlKey && e.shiftKey && (e.key === "I" || e.key === "i" || e.keyCode === 73)) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }

        // Ctrl + Shift + J (Console)
        if (e.ctrlKey && e.shiftKey && (e.key === "J" || e.key === "j" || e.keyCode === 74)) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }

        // Ctrl + Shift + C (Element Inspector)
        if (e.ctrlKey && e.shiftKey && (e.key === "C" || e.key === "c" || e.keyCode === 67)) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }

        // Ctrl + U (View Source)
        if (e.ctrlKey && (e.key === "U" || e.key === "u" || e.keyCode === 85)) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }

        // Ctrl + S (Save Page)
        if (e.ctrlKey && (e.key === "S" || e.key === "s" || e.keyCode === 83)) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }

        // Ctrl + P (Print / PDF Extract)
        if (e.ctrlKey && (e.key === "P" || e.key === "p" || e.keyCode === 80)) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }
    }, { capture: true });

    // 3. Ultra-Aggressive Debugger Freeze Loop (Freezes DevTools if forced open)
    let isLocked = false;

    function triggerLockout() {
        if (isLocked) return;
        isLocked = true;
        try {
            document.body.innerHTML = `
                <div style="position:fixed;top:0;left:0;width:100vw;height:100vh;background:#060205;color:#ff2a5f;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:system-ui, -apple-system, sans-serif;z-index:99999999;text-align:center;padding:20px;">
                    <div style="width:70px;height:70px;border-radius:50%;background:rgba(255,42,95,0.15);border:2px solid #ff2a5f;display:flex;align-items:center;justify-content:center;font-size:32px;margin-bottom:20px;box-shadow:0 0 30px rgba(255,42,95,0.5);">🛡️</div>
                    <h1 style="font-size:26px;font-weight:900;letter-spacing:0.5px;color:#fff;margin-bottom:10px;text-shadow:0 0 20px rgba(255,42,95,0.8);">SECURITY SHIELD • DEVTOOLS DETECTED</h1>
                    <p style="color:#94a3b8;font-size:15px;max-width:500px;line-height:1.6;margin-bottom:25px;">Inspection of Joyst Enclave DOM & source code is strictly prohibited. Please close Developer Tools and reload.</p>
                    <button onclick="window.location.reload()" style="background:linear-gradient(135deg,#ff2a5f,#e11d48);color:#fff;border:none;padding:12px 28px;border-radius:12px;font-weight:800;cursor:pointer;font-size:14px;box-shadow:0 6px 20px rgba(255,42,95,0.5);">Reload Application</button>
                </div>
            `;
        } catch (e) {}

        // Infinite Debugger Hang Loop
        setInterval(function () {
            (function () { return false; }["constructor"]("debugger")());
        }, 50);
    }

    // 4. DevTools Detection Mechanisms
    let threshold = 160;

    // A. Dimension Delta Check
    setInterval(function () {
        let widthThreshold = window.outerWidth - window.innerWidth > threshold;
        let heightThreshold = window.outerHeight - window.innerHeight > threshold;
        if (widthThreshold || heightThreshold) {
            triggerLockout();
        }
    }, 500);

    // B. Console Performance Profiler Timing Check
    setInterval(function () {
        let startTime = performance.now();
        console.log("");
        console.clear();
        let endTime = performance.now();
        if (endTime - startTime > 100) {
            triggerLockout();
        }
    }, 1000);

    // C. ToString Trap
    let element = new Image();
    Object.defineProperty(element, "id", {
        get: function () {
            triggerLockout();
        }
    });
    console.log("%c", element);

})();

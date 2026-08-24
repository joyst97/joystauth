/**
 * JOYST AUTH — Client-Side Zero-Leak Enclave Defense Shield
 * Universal Anti-Inspect, Anti-F12, Anti-DevTools Debugger Trap & Console Wiper
 */
(function () {
    "use strict";

    // 1. Disable Right Click Context Menu
    document.addEventListener("contextmenu", function (e) {
        e.preventDefault();
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

    // 3. Anti-DevTools Debugger Trap (Freezes DevTools if forced open)
    function launchDebuggerTrap() {
        function checkTrap(count) {
            (function () {
                return false;
            }
            ["constructor"]("debugger")());
            checkTrap(++count);
        }
        try {
            checkTrap(0);
        } catch (err) {}
    }

    // 4. Detect Window Resize Anomaly (Docked DevTools Inspector)
    let threshold = 160;
    setInterval(function () {
        let widthThreshold = window.outerWidth - window.innerWidth > threshold;
        let heightThreshold = window.outerHeight - window.innerHeight > threshold;
        if (widthThreshold || heightThreshold) {
            launchDebuggerTrap();
        }
    }, 1000);

    // 5. Periodic Console Sweeper & Tamper Alert
    setInterval(function () {
        try {
            console.clear();
            console.log(
                "%c🛡️ JOYST AUTH ZERO-LEAK SECURITY ENCLAVE ACTIVE",
                "color: #FF2A5F; font-size: 22px; font-weight: 900; text-shadow: 0 0 10px rgba(255,42,95,0.8);"
            );
            console.log(
                "%c⚠️ UNAUTHORIZED INSPECTION OR SCRAPING IS STRICTLY PROHIBITED AND LOGGED.",
                "color: #F59E0B; font-size: 13px; font-weight: bold;"
            );
        } catch (e) {}
    }, 2000);

})();

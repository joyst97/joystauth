// ==================== UNIVERSAL DYNAMIC THEME ENGINE ====================
const THEME_PRESETS = {
    cyan: { label: "Neon Cyan", icon: "🌐", color: "#00f2fe", border: "rgba(0, 242, 254, 0.4)" },
    purple: { label: "Obsidian Violet", icon: "🔮", color: "#a855f7", border: "rgba(168, 85, 247, 0.4)" },
    blue: { label: "Midnight Blue", icon: "🌊", color: "#2563eb", border: "rgba(37, 99, 235, 0.4)" },
    emerald: { label: "Matrix Green", icon: "⚡", color: "#10b981", border: "rgba(16, 185, 129, 0.4)" },
    oled: { label: "Titanium OLED", icon: "🖤", color: "#ffffff", border: "rgba(255, 255, 255, 0.3)" },
    crimson: { label: "Crimson Red", icon: "🩸", color: "#ff2a5f", border: "rgba(255, 42, 95, 0.4)" }
};

function getActiveTheme() {
    return localStorage.getItem("dashboard_theme") || "cyan";
}

function applyGlobalTheme(theme) {
    const valid = THEME_PRESETS[theme] ? theme : "cyan";
    document.documentElement.setAttribute("data-theme", valid);
    if (document.body) {
        document.body.setAttribute("data-theme", valid);
    }
    
    const info = THEME_PRESETS[valid];
    document.querySelectorAll(".current-theme-label, #current-theme-label").forEach(el => {
        el.textContent = info.label;
    });
    document.querySelectorAll(".current-theme-icon, #current-theme-icon").forEach(el => {
        el.textContent = info.icon;
    });

    // Mark active in dropdown
    document.querySelectorAll(".theme-opt-item").forEach(item => {
        const itemTheme = item.getAttribute("data-theme-key") || (item.getAttribute("onclick") || "").match(/'([^']+)'/)?.[1];
        if (itemTheme === valid) {
            item.style.background = "rgba(255, 255, 255, 0.12)";
            item.style.borderColor = info.color;
        } else {
            item.style.background = "transparent";
            item.style.borderColor = "transparent";
        }
    });

    // Broadcast change to interactive canvas engines (particles.js, reactbits.js, etc.)
    try {
        window.dispatchEvent(new CustomEvent("themeChanged", { detail: { theme: valid, info: info } }));
    } catch (e) {}
}

function setDashboardTheme(theme) {
    if (!THEME_PRESETS[theme]) theme = "cyan";
    localStorage.setItem("dashboard_theme", theme);
    applyGlobalTheme(theme);
    document.querySelectorAll(".theme-dropdown-menu").forEach(m => m.style.display = "none");
}

function toggleThemeDropdown(e) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }
    const wrapper = e ? e.currentTarget.closest(".theme-selector-dropdown-wrapper") : null;
    const menu = wrapper ? wrapper.querySelector(".theme-dropdown-menu") : document.getElementById("theme-dropdown-menu");
    if (!menu) return;
    const isShown = menu.style.display === "block";
    document.querySelectorAll(".theme-dropdown-menu").forEach(m => m.style.display = "none");
    menu.style.display = isShown ? "none" : "block";
}

window.addEventListener("click", () => {
    document.querySelectorAll(".theme-dropdown-menu").forEach(m => m.style.display = "none");
});

// Immediate execution in <head> to prevent FOUC (flash of unstyled/wrong color)
(function() {
    const saved = localStorage.getItem("dashboard_theme") || "cyan";
    document.documentElement.setAttribute("data-theme", saved);
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => applyGlobalTheme(saved));
    } else {
        applyGlobalTheme(saved);
    }
})();

window.THEME_PRESETS = THEME_PRESETS;
window.getActiveTheme = getActiveTheme;
window.setDashboardTheme = setDashboardTheme;
window.toggleThemeDropdown = toggleThemeDropdown;
window.applyGlobalTheme = applyGlobalTheme;

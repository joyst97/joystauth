// ==================== UNIVERSAL DYNAMIC THEME ENGINE ====================
const THEME_PRESETS = {
    cyan: { label: "Neon Cyan", icon: "🌐", color: "#00f2fe" },
    purple: { label: "Obsidian Violet", icon: "🔮", color: "#a855f7" },
    blue: { label: "Midnight Blue", icon: "🌊", color: "#2563eb" },
    emerald: { label: "Matrix Green", icon: "⚡", color: "#10b981" },
    oled: { label: "Titanium OLED", icon: "🖤", color: "#ffffff" },
    crimson: { label: "Crimson Red", icon: "🩸", color: "#ff2a5f" }
};

function applyGlobalTheme(theme) {
    const valid = THEME_PRESETS[theme] ? theme : "cyan";
    document.documentElement.setAttribute("data-theme", valid);
    if (document.body) document.body.setAttribute("data-theme", valid);
    
    const info = THEME_PRESETS[valid];
    const labelEl = document.getElementById("current-theme-label");
    const iconEl = document.getElementById("current-theme-icon");
    if (labelEl) labelEl.textContent = info.label;
    if (iconEl) iconEl.textContent = info.icon;
}

function setDashboardTheme(theme) {
    if (!THEME_PRESETS[theme]) theme = "cyan";
    localStorage.setItem("dashboard_theme", theme);
    applyGlobalTheme(theme);
    const menu = document.getElementById("theme-dropdown-menu");
    if (menu) menu.style.display = "none";
}

function toggleThemeDropdown(e) {
    if (e) e.stopPropagation();
    const menu = document.getElementById("theme-dropdown-menu");
    if (!menu) return;
    const isShown = menu.style.display === "block";
    document.querySelectorAll(".theme-dropdown-menu").forEach(m => m.style.display = "none");
    menu.style.display = isShown ? "none" : "block";
}

window.addEventListener("click", () => {
    document.querySelectorAll(".theme-dropdown-menu").forEach(m => m.style.display = "none");
});

// Immediate execution so there's zero flash of wrong color
(function() {
    const saved = localStorage.getItem("dashboard_theme") || "cyan";
    document.documentElement.setAttribute("data-theme", saved);
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => applyGlobalTheme(saved));
    } else {
        applyGlobalTheme(saved);
    }
})();

window.setDashboardTheme = setDashboardTheme;
window.toggleThemeDropdown = toggleThemeDropdown;
window.applyGlobalTheme = applyGlobalTheme;

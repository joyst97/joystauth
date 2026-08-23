// Joyst Corporation Developer Dashboard Controller
let currentAppId = null;
let appsList = [];
let devOwnerId = localStorage.getItem("dev_owner_id") || "Loading...";
let devUsername = localStorage.getItem("dev_username") || "Developer";

function showConfirmDialog({ title = "Confirm Action", message, icon = "⚠️", okText = "Confirm", cancelText = "Cancel", isDanger = true }) {
    return new Promise((resolve) => {
        const modal = document.getElementById("modal-app-confirm");
        const titleEl = document.getElementById("confirm-modal-title");
        const msgEl = document.getElementById("confirm-modal-message");
        const iconEl = document.getElementById("confirm-modal-icon");
        const okBtn = document.getElementById("confirm-modal-ok-btn");
        const cancelBtn = document.getElementById("confirm-modal-cancel-btn");

        if (!modal || !titleEl || !msgEl || !okBtn || !cancelBtn) {
            resolve(window.confirm(message));
            return;
        }

        titleEl.textContent = title;
        msgEl.textContent = message;
        if (iconEl) iconEl.textContent = icon;
        okBtn.textContent = okText;
        cancelBtn.textContent = cancelText;

        okBtn.className = isDanger ? "btn btn-danger" : "btn btn-primary";
        okBtn.style.flex = "1";
        okBtn.style.padding = "10px 0";

        modal.style.display = "flex";

        function cleanup(result) {
            modal.style.display = "none";
            okBtn.removeEventListener("click", onOk);
            cancelBtn.removeEventListener("click", onCancel);
            document.removeEventListener("keydown", onKeyDown);
            resolve(result);
        }

        function onOk(e) {
            if (e) e.preventDefault();
            cleanup(true);
        }
        function onCancel(e) {
            if (e) e.preventDefault();
            cleanup(false);
        }
        function onKeyDown(e) {
            if (e.key === "Escape") cleanup(false);
            if (e.key === "Enter") cleanup(true);
        }

        okBtn.addEventListener("click", onOk);
        cancelBtn.addEventListener("click", onCancel);
        document.addEventListener("keydown", onKeyDown);
    });
}

function escapeHtml(str) {
    if (!str && str !== 0) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function getAuthToken() {
    return localStorage.getItem("auth_admin_token") || "";
}

if (!getAuthToken() && window.location.pathname.includes("/dashboard")) {
    window.location.href = "/login";
}

function bootDashboard() {
    if (getAuthToken() && window.location.pathname.includes("/dashboard")) {
        initDashboard();
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootDashboard);
} else {
    bootDashboard();
}

function getHeaders() {
    return {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${getAuthToken()}`
    };
}

async function apiFetch(url, options = {}) {
    const token = getAuthToken();
    if (!token && window.location.pathname.includes("/dashboard")) {
        window.location.href = "/login";
        return null;
    }
    options.headers = { ...getHeaders(), ...(options.headers || {}) };
    try {
        const res = await fetch(url, options);
        if (res.status === 401) {
            console.warn("Unauthorized API call to:", url);
            localStorage.removeItem("auth_admin_token");
            window.location.href = "/login";
            return null;
        }
        return await res.json();
    } catch (err) {
        showToast("Network error: " + err.message, "error");
        return null;
    }
}

function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    let icon = "🛡️";
    if (type === "success") icon = "✅";
    if (type === "error") icon = "❌";
    if (type === "warning") icon = "⚠️";

    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

async function initDashboard() {
    setupNavigation();
    setupModals();
    setupChangePassword();

    // 1. Instant Cache-First Paint (0.01s instant UI display)
    const cachedApps = localStorage.getItem("cached_apps_list");
    if (cachedApps) {
        try {
            appsList = JSON.parse(cachedApps);
            renderAppsDropdowns();
        } catch (e) {}
    }

    // 2. Fetch fresh data in parallel
    try {
        await Promise.all([
            loadUserProfile(),
            loadApps()
        ]);
        loadGlobalStats();
    } catch (err) {
        console.error("Error during dashboard init:", err);
    }
    loadActiveTab();
}

async function loadUserProfile() {
    const data = await apiFetch("/api/v1/auth/me");
    if (data && data.success) {
        devOwnerId = data.owner_id;
        devUsername = data.username;
        localStorage.setItem("dev_owner_id", devOwnerId);
        localStorage.setItem("dev_username", devUsername);

        const nameEl = document.getElementById("dev-display-name");
        const ownerEl = document.getElementById("dev-owner-id-label");
        const avatarEl = document.getElementById("dev-avatar");
        const planBadge = document.getElementById("header-plan-badge");

        const savedAvatar = localStorage.getItem("dev_avatar");
        if (nameEl) nameEl.textContent = devUsername;
        if (ownerEl) ownerEl.innerHTML = `<span class="badge-dot" style="background: #10b981;"></span> Server Online`;
        if (avatarEl) {
            if (savedAvatar && savedAvatar.startsWith("http")) {
                avatarEl.innerHTML = `<img src="${savedAvatar}" alt="DP" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover; box-shadow: 0 0 10px rgba(88, 101, 242, 0.6);">`;
                avatarEl.style.background = "transparent";
            } else {
                avatarEl.textContent = devUsername.charAt(0).toUpperCase();
            }
        }
        const activePlan = data.plan || 'Free';
        window.currentUserPlan = activePlan;
        if (planBadge) planBadge.textContent = `${activePlan} Plan`;

        // Highlight active plan card
        document.querySelectorAll(".plan-card").forEach(c => c.classList.remove("active-plan"));
        const isPaid = activePlan === "Paid" || activePlan === "Developer" || activePlan === "Pro";
        if (isPaid) {
            document.getElementById("plan-card-paid")?.classList.add("active-plan");
        } else {
            document.getElementById("plan-card-free")?.classList.add("active-plan");
        }

        // Dynamic Plan Buttons
        const freeBtnContainer = document.getElementById("plan-btn-container-free");
        const paidBtnContainer = document.getElementById("plan-btn-container-paid");

        const activeBadgeHtml = `<span class="badge badge-success" style="width: 100%; justify-content: center; padding: 9px; font-size: 13px; font-weight: 800;"><span class="badge-dot"></span> Current Active Plan</span>`;
        const upgradeBtnHtml = `<button class="btn btn-primary btn-sm" style="width: 100%;" onclick="openModal('modal-purchase-plan')">Purchase Key / Upgrade</button>`;
        const includedBadgeHtml = `<span class="badge badge-purple" style="width: 100%; justify-content: center; padding: 8px; font-size: 12px;">Included in Paid tier</span>`;

        if (freeBtnContainer) freeBtnContainer.innerHTML = !isPaid ? activeBadgeHtml : includedBadgeHtml;
        if (paidBtnContainer) paidBtnContainer.innerHTML = isPaid ? activeBadgeHtml : upgradeBtnHtml;

        // Dynamic Sidebar Feature Badges & Locks
        const resellerNav = document.querySelector('.nav-item[data-tab="resellers"]');
        const webhookNav = document.querySelector('.nav-item[data-tab="webhooks"]');

        if (resellerNav) {
            const oldBadge = resellerNav.querySelector(".plan-lock-badge");
            if (oldBadge) oldBadge.remove();
            if (!isPaid) {
                const b = document.createElement("span");
                b.className = "badge badge-purple plan-lock-badge";
                b.style.cssText = "font-size: 9px; padding: 2px 6px; margin-left: auto;";
                b.textContent = "PAID";
                resellerNav.appendChild(b);
            }
        }

        if (webhookNav) {
            const oldBadge = webhookNav.querySelector(".plan-lock-badge");
            if (oldBadge) oldBadge.remove();
            if (!isPaid) {
                const b = document.createElement("span");
                b.className = "badge badge-purple plan-lock-badge";
                b.style.cssText = "font-size: 9px; padding: 2px 6px; margin-left: auto;";
                b.textContent = "PAID";
                webhookNav.appendChild(b);
            }
        }

        // Re-evaluate current active tab permissions
        loadActiveTab();
    }
}

function setupNavigation() {
    const navItems = document.querySelectorAll(".nav-item[data-tab]");
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.getAttribute("data-tab");
            switchTab(targetTab);
        });
    });

    const logoutBtn = document.getElementById("btn-logout");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
            localStorage.clear();
            window.location.href = "/login";
        });
    }

    const appSelect = document.getElementById("header-app-select");
    if (appSelect) {
        appSelect.addEventListener("change", (e) => {
            currentAppId = e.target.value ? parseInt(e.target.value) : null;
            if (currentAppId) {
                localStorage.setItem("selected_app_id", currentAppId);
            } else {
                localStorage.removeItem("selected_app_id");
            }
            updateBannerCredentials();
            loadActiveTab();
            updateSdkSnippets();
        });
    }
}

function switchTab(tabId) {
    document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".page-container").forEach(el => el.classList.remove("active"));

    const activeNav = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
    const activePage = document.getElementById(`page-${tabId}`);

    if (activeNav) activeNav.classList.add("active");
    if (activePage) activePage.classList.add("active");

    loadTabContent(tabId);
}

function loadActiveTab() {
    const activeNav = document.querySelector(".nav-item.active");
    if (activeNav) {
        const tabId = activeNav.getAttribute("data-tab");
        loadTabContent(tabId);
    }
}

function loadTabContent(tabId) {
    const isPaid = (window.currentUserPlan === "Paid" || window.currentUserPlan === "Developer" || window.currentUserPlan === "Pro");

    // Manage Resellers Locked vs Unlocked visibility
    const resLocked = document.getElementById("resellers-locked-paywall");
    const resUnlocked = document.getElementById("resellers-unlocked-content");
    if (resLocked && resUnlocked) {
        if (isPaid) {
            resLocked.style.display = "none";
            resUnlocked.style.display = "block";
        } else {
            resLocked.style.display = "flex";
            resUnlocked.style.display = "none";
        }
    }

    // Manage Webhooks Locked vs Unlocked visibility
    const hookLocked = document.getElementById("webhooks-locked-paywall");
    const hookUnlocked = document.getElementById("webhooks-unlocked-content");
    if (hookLocked && hookUnlocked) {
        if (isPaid) {
            hookLocked.style.display = "none";
            hookUnlocked.style.display = "block";
        } else {
            hookLocked.style.display = "flex";
            hookUnlocked.style.display = "none";
        }
    }

    if (tabId === "overview") {
        loadGlobalStats();
        updateBannerCredentials();
    } else if (tabId === "licenses") {
        loadLicenses();
    } else if (tabId === "users") {
        loadUsers();
    } else if (tabId === "tiers") {
        loadTiers();
    } else if (tabId === "variables") {
        loadVariables();
    } else if (tabId === "files") {
        loadFiles();
    } else if (tabId === "blacklists") {
        loadBlacklists();
    } else if (tabId === "resellers") {
        if (isPaid) loadResellers();
    } else if (tabId === "webhooks") {
        // Unlocked for paid users
    } else if (tabId === "notifications") {
        loadNotifications();
    } else if (tabId === "apps") {
        renderAppsPage();
    } else if (tabId === "settings") {
        renderActiveAppSettings();
    } else if (tabId === "logs") {
        loadAuditLogs();
    } else if (tabId === "sdk") {
        updateSdkSnippets();
    }
}

function renderAppsDropdowns() {
    const selects = [document.getElementById("overview-app-select"), document.getElementById("header-app-select")].filter(Boolean);
    if (selects.length === 0) return;

    selects.forEach(select => {
        select.innerHTML = "";
        if (appsList.length === 0) {
            select.innerHTML = `<option value="">No Apps Created</option>`;
        } else {
            appsList.forEach(app => {
                const opt = document.createElement("option");
                opt.value = app.id;
                opt.textContent = `${app.name} (v${app.version})`;
                select.appendChild(opt);
            });
        }
    });

    if (appsList.length === 0) {
        currentAppId = null;
        updateBannerCredentials();
        return;
    }

    const savedAppId = parseInt(localStorage.getItem("selected_app_id"));
    if (savedAppId && appsList.some(a => a.id === savedAppId)) {
        currentAppId = savedAppId;
    } else {
        currentAppId = appsList[0].id;
        localStorage.setItem("selected_app_id", currentAppId);
    }

    selects.forEach(select => {
        select.value = currentAppId;
        select.onchange = (e) => {
            currentAppId = e.target.value ? parseInt(e.target.value) : null;
            if (currentAppId) {
                localStorage.setItem("selected_app_id", currentAppId);
            } else {
                localStorage.removeItem("selected_app_id");
            }
            selects.forEach(s => { s.value = currentAppId; });
            updateBannerCredentials();
            loadGlobalStats();
            loadActiveTab();
        };
    });

    updateBannerCredentials();
}

// 1. Applications Loading
async function loadApps() {
    try {
        const data = await apiFetch("/api/v1/admin/apps");
        if (data && data.success) {
            appsList = data.apps || [];
            try {
                localStorage.setItem("cached_apps_list", JSON.stringify(appsList));
            } catch(e) {}
        }
    } catch (err) {
        console.error("loadApps error:", err);
    }
    renderAppsDropdowns();
}

function updateBannerCredentials() {
    const app = appsList.find(a => a.id === currentAppId);
    const select = document.getElementById("overview-app-select") || document.getElementById("header-app-select");
    const nameEl = document.getElementById("banner-app-name");
    const secretEl = document.getElementById("banner-app-secret");
    const verEl = document.getElementById("banner-app-version");

    if (select && currentAppId) {
        select.value = currentAppId;
    }

    if (!app) {
        if (nameEl) nameEl.textContent = "No App Selected";
        if (secretEl) secretEl.textContent = "Create an app to get Token";
        if (verEl) verEl.textContent = "v1.0";
        return;
    }

    if (nameEl) nameEl.textContent = app.name;
    if (secretEl) secretEl.textContent = app.secret;
    if (verEl) verEl.textContent = `v${app.version}`;

    const ownerIdEl = document.getElementById("banner-dev-owner-id");
    if (ownerIdEl) {
        ownerIdEl.textContent = devOwnerId || "Loading...";
    }

    const webhookInput = document.getElementById("discord-webhook-url-input");
    if (webhookInput && app.webhook_url) {
        webhookInput.value = app.webhook_url;
    }

    // Update Overview Emergency Status Badge & Button
    const statusBadge = document.getElementById("overview-app-status-badge");
    const toggleBtn = document.getElementById("btn-quick-toggle-maintenance");
    const isMaint = app.status === "maintenance" || app.status === "paused";

    if (statusBadge) {
        if (isMaint) {
            statusBadge.className = "badge badge-danger";
            statusBadge.innerHTML = `<span class="badge-dot"></span> 🚨 MAINTENANCE ACTIVE`;
        } else if (app.status === "disabled") {
            statusBadge.className = "badge badge-danger";
            statusBadge.innerHTML = `<span class="badge-dot"></span> 🚫 DISABLED`;
        } else {
            statusBadge.className = "badge badge-success";
            statusBadge.innerHTML = `<span class="badge-dot"></span> 🟢 ONLINE & ACTIVE`;
        }
    }

    if (toggleBtn) {
        if (isMaint) {
            toggleBtn.className = "btn btn-success btn-sm";
            toggleBtn.innerHTML = `<span>🟢 Resume Online (Turn OFF Maintenance)</span>`;
        } else {
            toggleBtn.className = "btn btn-danger btn-sm";
            toggleBtn.innerHTML = `<span>⏸️ Activate Maintenance Mode</span>`;
        }
    }
}

async function quickToggleMaintenance() {
    if (!currentAppId) {
        showToast("Please select an application first", "warning");
        return;
    }

    const app = appsList.find(a => a.id === currentAppId);
    const isCurrentlyMaint = app && (app.status === "maintenance" || app.status === "paused");
    const actionWord = isCurrentlyMaint ? "RESUME ONLINE" : "ACTIVATE EMERGENCY MAINTENANCE (Force-Block all running EXEs)";

    if (!await showConfirmDialog({ title: isCurrentlyMaint ? 'Resume Application' : 'Emergency Maintenance', message: `Are you sure you want to ${actionWord} for '${app?.name}'?`, icon: isCurrentlyMaint ? '🟢' : '🚨', okText: isCurrentlyMaint ? 'Resume' : 'Activate', isDanger: !isCurrentlyMaint })) return;

    showToast("Updating application mode...", "info");

    const res = await apiFetch(`/api/v1/admin/apps/${currentAppId}/toggle-maintenance`, {
        method: "POST"
    });

    if (res && res.success) {
        showToast(res.message, isCurrentlyMaint ? "success" : "error");
        await loadApps();
        updateBannerCredentials();
        renderAppsPage();
    } else {
        showToast(res?.detail || "Failed to toggle maintenance mode", "error");
    }
}

// 2. Global Overview & Stats
async function loadGlobalStats() {
    const data = await apiFetch("/api/v1/admin/stats");
    if (!data || !data.success) return;

    const stats = data.stats;
    document.getElementById("stat-total-users").textContent = stats.total_users;
    document.getElementById("stat-active-keys").textContent = stats.unused_licenses;
    document.getElementById("stat-logins-today").textContent = stats.logins_today;
    document.getElementById("stat-failed-attempts").textContent = stats.failed_logins_today;

    const container = document.getElementById("overview-recent-activity");
    if (container && data.recent_activity) {
        if (data.recent_activity.length === 0) {
            container.innerHTML = `<div style="padding: 30px; color: var(--text-dim); text-align: center;">No activity recorded yet for your workspace.</div>`;
            return;
        }

        container.innerHTML = data.recent_activity.map(item => `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border-subtle);">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span class="badge badge-${item.status === 'SUCCESS' ? 'success' : (item.status === 'DANGER' ? 'danger' : 'warning')}">
                        <span class="badge-dot"></span> ${item.action}
                    </span>
                    <div>
                        <strong style="font-size: 13px; color: #fff;">${item.username || 'Anonymous'}</strong>
                        <div style="font-size: 11px; color: var(--text-muted);">IP: ${item.ip || 'N/A'} • App: ${item.app_name}</div>
                    </div>
                </div>
                <span style="font-size: 12px; color: var(--text-muted);">${item.time}</span>
            </div>
        `).join("");
    }
}

// 3. Licenses Management
async function loadLicenses() {
    const tbody = document.getElementById("licenses-table-body");
    if (!tbody) return;

    if (!currentAppId) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 40px;">No application selected. Create an application first.</td></tr>`;
        return;
    }

    const search = document.getElementById("license-search-input")?.value || "";
    const filter = document.getElementById("license-status-filter")?.value || "";
    
    let url = `/api/v1/admin/licenses?app_id=${currentAppId}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (filter) url += `&status=${encodeURIComponent(filter)}`;

    const data = await apiFetch(url);
    if (!data || !data.licenses || data.licenses.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 40px;">No license keys found. Click "+ Generate Keys" to create license keys.</td></tr>`;
        return;
    }

    tbody.innerHTML = data.licenses.map(lic => {
        let statusBadge = `<span class="badge badge-success"><span class="badge-dot"></span> Unused</span>`;
        if (lic.status === "used") statusBadge = `<span class="badge badge-purple"><span class="badge-dot"></span> Used</span>`;
        if (lic.status === "paused") statusBadge = `<span class="badge badge-warning"><span class="badge-dot"></span> Paused</span>`;
        if (lic.status === "revoked") statusBadge = `<span class="badge badge-danger"><span class="badge-dot"></span> Revoked</span>`;

        return `
            <tr>
                <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="mono" style="font-weight: 700; color: #fff;">${lic.key}</span>
                        <button class="btn btn-secondary btn-sm" onclick="copyToClipboard('${lic.key}')" title="Copy Key">📋</button>
                    </div>
                </td>
                <td><span class="badge badge-cyan">${lic.level} (Rank ${lic.level_rank})</span></td>
                <td>${lic.duration_days === -1 || lic.duration_days > 90000 ? '<strong style="color: #10b981;">Lifetime</strong>' : `${lic.duration_days} Days`}</td>
                <td>${statusBadge}</td>
                <td>${lic.used_by ? `<strong style="color: #fff;">${lic.used_by}</strong>` : '<span style="color: var(--text-muted);">-</span>'}</td>
                <td>
                    <div style="display: flex; gap: 6px;">
                        <button class="btn btn-secondary btn-sm" onclick="toggleLicensePause(${lic.id})" title="${lic.status === 'paused' ? 'Unpause' : 'Pause'}">
                            ${lic.status === 'paused' ? '▶️ Unpause' : '⏸️ Pause'}
                        </button>
                        <button class="btn btn-danger btn-sm" onclick="deleteLicense(${lic.id})" title="Delete">🗑️</button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

async function generateKeysSubmit() {
    if (!currentAppId) {
        showToast("Please create or select an application first", "warning");
        return;
    }

    const count = parseInt(document.getElementById("gen-count").value) || 1;
    const duration = parseInt(document.getElementById("gen-duration").value) || 30;
    const level = document.getElementById("gen-level").value || "default";
    const mask = document.getElementById("gen-mask").value || "JOYST-XXXX-XXXX-XXXX";
    const notes = document.getElementById("gen-notes").value || "";

    const payload = {
        app_id: currentAppId,
        count: count,
        duration_days: duration,
        level: level,
        level_rank: 1,
        mask: mask,
        notes: notes
    };

    const res = await apiFetch("/api/v1/admin/licenses", {
        method: "POST",
        body: JSON.stringify(payload)
    });

    if (res && res.success) {
        showToast(res.message, "success");
        closeModal("modal-generate-keys");
        loadLicenses();
        loadGlobalStats();

        if (res.keys && res.keys.length > 0) {
            document.getElementById("generated-keys-output").value = res.keys.join("\n");
            openModal("modal-view-generated");
        }
    } else {
        showToast(res?.detail || "Failed to generate keys", "error");
    }
}

async function bulkDeleteLicenses(type) {
    if (!currentAppId) return;
    if (!await showConfirmDialog({ title: 'Delete License Keys', message: `Are you sure you want to delete all ${type} license keys?`, icon: '🗑️', okText: 'Delete Keys', isDanger: true })) return;
    const res = await apiFetch(`/api/v1/admin/licenses/bulk-delete?app_id=${currentAppId}&delete_type=${type}`, { method: "POST" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadLicenses();
        loadGlobalStats();
    }
}

async function exportLicensesTxt() {
    if (!currentAppId) return;
    const data = await apiFetch(`/api/v1/admin/licenses?app_id=${currentAppId}`);
    if (!data || !data.licenses || data.licenses.length === 0) {
        showToast("No licenses available to export", "warning");
        return;
    }

    const textContent = data.licenses.map(l => l.key).join("\n");
    const blob = new Blob([textContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `licenses_app_${currentAppId}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("Exported licenses to text file!", "success");
}

async function deleteLicense(licenseId) {
    if (!await showConfirmDialog({ title: 'Delete License Key', message: 'Are you sure you want to permanently delete this license key?', icon: '🗑️', okText: 'Delete Key', isDanger: true })) return;
    const res = await apiFetch(`/api/v1/admin/licenses/${licenseId}`, { method: "DELETE" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadLicenses();
        loadGlobalStats();
    }
}

async function toggleLicensePause(licenseId) {
    const res = await apiFetch(`/api/v1/admin/licenses/${licenseId}/toggle-pause`, { method: "POST" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadLicenses();
    }
}

// 4. Users & Strict HWID Management
let rawUsersList = [];

async function loadUsers() {
    const tbody = document.getElementById("users-table-body");
    if (!tbody) return;

    if (!currentAppId) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 40px;">No application selected.</td></tr>`;
        return;
    }

    const search = document.getElementById("user-search-input")?.value || "";
    let url = `/api/v1/admin/users?app_id=${currentAppId}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;

    const data = await apiFetch(url);
    if (!data || !data.users) return;

    rawUsersList = data.users || [];
    filterUsersTable();
}

function filterUsersTable() {
    const tbody = document.getElementById("users-table-body");
    if (!tbody) return;

    const q = (document.getElementById("user-search-input")?.value || "").toLowerCase().trim();
    const filter = document.getElementById("user-status-filter")?.value || "all";

    let filtered = rawUsersList.filter(u => {
        // Text search
        const matchText = !q || u.username.toLowerCase().includes(q) || 
                          (u.hwid && u.hwid.toLowerCase().includes(q)) || 
                          (u.last_ip && u.last_ip.toLowerCase().includes(q)) ||
                          (u.registered_ip && u.registered_ip.toLowerCase().includes(q));
        if (!matchText) return false;

        // Status filter
        if (filter === "active") return !u.is_expired && !u.is_banned;
        if (filter === "expired") return u.is_expired;
        if (filter === "banned") return u.is_banned;
        if (filter === "hwid_locked") return !!u.hwid;
        if (filter === "hwid_unlocked") return !u.hwid;
        return true;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 40px;">No users matching filter.</td></tr>`;
        updateBatchActionBar();
        return;
    }

    tbody.innerHTML = filtered.map(u => {
        let hwidStatus = `<span class="badge badge-success"><span class="badge-dot"></span> Locked</span>`;
        if (!u.hwid) hwidStatus = `<span class="badge badge-warning"><span class="badge-dot"></span> Open (Unbound)</span>`;

        let banBadge = u.is_banned 
            ? `<span class="badge badge-danger"><span class="badge-dot"></span> Banned</span>` 
            : (u.is_expired ? `<span class="badge badge-warning"><span class="badge-dot"></span> Expired</span>` : `<span class="badge badge-success"><span class="badge-dot"></span> Active</span>`);

        return `
            <tr>
                <td style="text-align: center;">
                    <input type="checkbox" class="user-row-chk" value="${u.id}" onchange="onUserCheckboxChange()" style="width: 16px; height: 16px; accent-color: #ff2a5f; cursor: pointer;">
                </td>
                <td>
                    <strong style="color: #fff; font-size: 14px;">${u.username}</strong>
                    <div style="font-size: 11px; color: var(--text-muted);">IP: <span style="color: #38bdf8;">${u.last_ip || u.registered_ip || 'N/A'}</span></div>
                </td>
                <td>
                    <div style="display: flex; flex-direction: column; gap: 4px;">
                        ${hwidStatus}
                        <span class="mono" style="font-size: 10.5px; color: var(--text-muted); max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${u.hwid || 'Will bind on login'}</span>
                    </div>
                </td>
                <td><span class="badge badge-purple">${u.subscription} (Lv.${u.level || 1})</span></td>
                <td><span style="${u.is_expired ? 'color: #ff4d79; font-weight: 800;' : 'color: #fff; font-weight: 600;'}">${u.time_left}</span></td>
                <td>${banBadge}</td>
                <td>
                    <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                        <button class="btn btn-secondary btn-sm" onclick="resetUserHwid(${u.id}, '${u.username}')" title="Reset HWID">🔒 Reset HWID</button>
                        <button class="btn btn-secondary btn-sm" onclick="openExtendModal(${u.id}, '${u.username}')" title="Add Time">⏳ Extend</button>
                        <button class="btn ${u.is_banned ? 'btn-success' : 'btn-danger'} btn-sm" onclick="toggleUserBan(${u.id}, '${u.username}', ${u.is_banned})">${u.is_banned ? '🔓 Unban' : '🚫 Ban'}</button>
                        <button class="btn btn-danger btn-sm" onclick="deleteUser(${u.id})" title="Delete">🗑️</button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");

    updateBatchActionBar();
}

function toggleSelectAllUsers(selectAllChk) {
    const rowCheckboxes = document.querySelectorAll(".user-row-chk");
    rowCheckboxes.forEach(chk => chk.checked = selectAllChk.checked);
    updateBatchActionBar();
}

function onUserCheckboxChange() {
    const rowCheckboxes = Array.from(document.querySelectorAll(".user-row-chk"));
    const allChecked = rowCheckboxes.length > 0 && rowCheckboxes.every(chk => chk.checked);
    const selectAll = document.getElementById("users-select-all-chk");
    if (selectAll) selectAll.checked = allChecked;
    updateBatchActionBar();
}

function getSelectedUserIds() {
    return Array.from(document.querySelectorAll(".user-row-chk:checked")).map(chk => parseInt(chk.value));
}

function updateBatchActionBar() {
    const selected = getSelectedUserIds();
    const bar = document.getElementById("users-batch-actions-bar");
    const countEl = document.getElementById("users-selected-count");
    if (!bar || !countEl) return;

    countEl.textContent = selected.length;
    if (selected.length > 0) {
        bar.style.display = "flex";
    } else {
        bar.style.display = "none";
    }
}

async function bulkResetAllHwidSubmit() {
    if (!currentAppId) return;
    if (!await showConfirmDialog({ title: 'Reset All HWIDs', message: 'Are you sure you want to RESET HWID lock for ALL users in this application?', icon: '🔄', okText: 'Reset All', isDanger: true })) return;

    const res = await apiFetch("/api/v1/admin/users/reset-all-hwid", {
        method: "POST",
        body: JSON.stringify({ app_id: currentAppId })
    });
    if (res && res.success) {
        showToast(res.message, "success");
        loadUsers();
    } else {
        showToast(res?.detail || "Failed to reset HWIDs", "error");
    }
}

async function bulkPurgeExpiredUsersSubmit() {
    if (!currentAppId) return;
    if (!await showConfirmDialog({ title: 'Purge Expired Users', message: 'Are you sure you want to permanently DELETE ALL EXPIRED user accounts?', icon: '🗑️', okText: 'Purge Expired', isDanger: true })) return;

    const res = await apiFetch("/api/v1/admin/users/purge-expired", {
        method: "POST",
        body: JSON.stringify({ app_id: currentAppId })
    });
    if (res && res.success) {
        showToast(res.message, "success");
        loadUsers();
        loadGlobalStats();
    } else {
        showToast(res?.detail || "Failed to purge expired users", "error");
    }
}

function toggleUsersBulkDeleteDropdown(e) {
    e.stopPropagation();
    const dd = document.getElementById("users-bulk-delete-dropdown");
    if (!dd) return;
    const isShown = dd.style.display === "block";
    closeAllDropdowns();
    dd.style.display = isShown ? "none" : "block";
}

function closeAllDropdowns() {
    document.querySelectorAll(".dropdown-menu-cyber").forEach(dd => {
        dd.style.display = "none";
    });
}

window.addEventListener("click", () => {
    closeAllDropdowns();
});

async function bulkDeleteAllUsersInApp() {
    if (!currentAppId) return;
    if (!await showConfirmDialog({ title: 'Delete All Users', message: 'DANGER: Are you sure you want to permanently delete ALL users in this application? This action cannot be undone!', icon: '🚨', okText: 'Delete All Users', isDanger: true })) return;

    if (rawUsersList.length === 0) {
        showToast("No users found to delete", "info");
        return;
    }

    const allIds = rawUsersList.map(u => u.id);
    const res = await apiFetch("/api/v1/admin/users/bulk-delete", {
        method: "POST",
        body: JSON.stringify({ user_ids: allIds })
    });

    if (res && res.success) {
        showToast(res.message, "success");
        loadUsers();
        loadGlobalStats();
    } else {
        showToast(res?.detail || "Failed to delete users", "error");
    }
}

function openBulkExtendUsersModal() {
    const selected = getSelectedUserIds();
    const scopeSelect = document.getElementById("bulk-extend-scope");
    if (scopeSelect) {
        if (selected.length > 0) {
            scopeSelect.value = "selected";
        } else {
            scopeSelect.value = "all";
        }
    }
    openModal("modal-bulk-extend-users");
}

async function submitBulkExtendUsers() {
    if (!currentAppId) return;
    const days = parseInt(document.getElementById("bulk-extend-days-input").value) || 7;
    const scope = document.getElementById("bulk-extend-scope").value;
    const selected = getSelectedUserIds();

    const payload = {
        app_id: currentAppId,
        days: days,
        user_ids: scope === "selected" ? selected : null
    };

    const res = await apiFetch("/api/v1/admin/users/bulk-extend", {
        method: "POST",
        body: JSON.stringify(payload)
    });

    if (res && res.success) {
        showToast(res.message, "success");
        closeModal("modal-bulk-extend-users");
        loadUsers();
    } else {
        showToast(res?.detail || "Failed to extend subscriptions", "error");
    }
}

async function batchDeleteSelected() {
    const selected = getSelectedUserIds();
    if (selected.length === 0) return;
    if (!await showConfirmDialog({ title: 'Delete Selected Users', message: `Are you sure you want to delete ${selected.length} selected user(s)?`, icon: '🗑️', okText: 'Delete', isDanger: true })) return;

    const res = await apiFetch("/api/v1/admin/users/bulk-delete", {
        method: "POST",
        body: JSON.stringify({ user_ids: selected })
    });

    if (res && res.success) {
        showToast(res.message, "success");
        loadUsers();
        loadGlobalStats();
    } else {
        showToast(res?.detail || "Failed to delete selected users", "error");
    }
}

async function batchBanSelected() {
    const selected = getSelectedUserIds();
    if (selected.length === 0) return;
    const reason =mpt(`Enter reason for banning ${selected.length} user(s):`, "Violation of terms");
    if (reason === null) return;

    const res = await apiFetch("/api/v1/admin/users/bulk-ban", {
        method: "POST",
        body: JSON.stringify({ user_ids: selected, reason: reason })
    });

    if (res && res.success) {
        showToast(res.message, "success");
        loadUsers();
    } else {
        showToast(res?.detail || "Failed to ban selected users", "error");
    }
}

async function batchResetHwidSelected() {
    const selected = getSelectedUserIds();
    if (selected.length === 0) return;
    if (!await showConfirmDialog({ title: 'Reset HWIDs', message: `Reset HWID for ${selected.length} selected user(s)?`, icon: '🔄', okText: 'Reset HWID', isDanger: false })) return;

    for (const uid of selected) {
        await apiFetch(`/api/v1/admin/users/${uid}/reset-hwid`, { method: "POST" });
    }
    showToast(`HWID reset for ${selected.length} user(s)!`, "success");
    loadUsers();
}

function exportUsersTxt() {
    if (rawUsersList.length === 0) {
        showToast("No users to export", "warning");
        return;
    }
    const lines = ["Username,Subscription,Level,ExpiresAt,HWID,LastIP,Status"];
    rawUsersList.forEach(u => {
        lines.push(`${u.username},${u.subscription},${u.level},${u.expires_at || 'Lifetime'},${u.hwid || 'None'},${u.last_ip || 'N/A'},${u.is_banned ? 'Banned' : (u.is_expired ? 'Expired' : 'Active')}`);
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `users_export_app_${currentAppId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("Exported users to CSV!", "success");
}

async function submitManualUser() {
    if (!currentAppId) {
        showToast("Please create or select an app first", "warning");
        return;
    }
    const username = document.getElementById("manual-user-name").value.trim();
    const password = document.getElementById("manual-user-pass").value;
    const days = parseInt(document.getElementById("manual-user-days").value) || 30;
    const tier = document.getElementById("manual-user-tier").value.trim() || "default";
    const hwid = document.getElementById("manual-user-hwid").value.trim();

    if (!username || !password) {
        showToast("Username and Password are required", "warning");
        return;
    }

    closeModal("modal-create-user-manual");
    showToast("Creating user...", "info");

    const res = await apiFetch("/api/v1/admin/users/manual-create", {
        method: "POST",
        body: JSON.stringify({
            app_id: currentAppId,
            username: username,
            password: password,
            duration_days: days,
            subscription_tier: tier,
            level: 1,
            hwid: hwid || null
        })
    });

    if (res && res.success) {
        showToast(res.message, "success");
        loadUsers();
        loadGlobalStats();
    } else {
        showToast(res?.detail || "Failed to create user", "error");
        loadUsers();
    }
}

async function resetUserHwid(userId, username) {
    if (!await showConfirmDialog({ title: 'Reset HWID', message: `Reset HWID lock for '${username}'? Account will lock to the next machine upon login.`, icon: '🔄', okText: 'Reset HWID', isDanger: false })) return;
    const res = await apiFetch(`/api/v1/admin/users/${userId}/reset-hwid`, { method: "POST" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadUsers();
    }
}

async function toggleUserBan(userId, username, isCurrentlyBanned) {
    if (!isCurrentlyBanned) {
        const reason =mpt(`Enter reason for banning '${username}':`, "Violation of terms");
        if (reason === null) return;
        const res = await apiFetch(`/api/v1/admin/users/${userId}/toggle-ban`, {
            method: "POST",
            body: JSON.stringify({ reason: reason })
        });
        if (res && res.success) {
            showToast(res.message, "success");
            loadUsers();
        }
    } else {
        const res = await apiFetch(`/api/v1/admin/users/${userId}/toggle-ban`, {
            method: "POST",
            body: JSON.stringify({ reason: "" })
        });
        if (res && res.success) {
            showToast(res.message, "success");
            loadUsers();
        }
    }
}

let extendTargetUserId = null;
function openExtendModal(userId, username) {
    extendTargetUserId = userId;
    document.getElementById("extend-username-label").textContent = username;
    openModal("modal-extend-user");
}

async function submitExtendUser() {
    if (!extendTargetUserId) return;
    const days = parseInt(document.getElementById("extend-days-input").value) || 30;
    const res = await apiFetch(`/api/v1/admin/users/${extendTargetUserId}/extend`, {
        method: "POST",
        body: JSON.stringify({ days: days })
    });
    if (res && res.success) {
        showToast(res.message, "success");
        closeModal("modal-extend-user");
        loadUsers();
    }
}

async function deleteUser(userId) {
    if (!await showConfirmDialog({ title: 'Delete User Account', message: 'Are you sure you want to permanently delete this user account?', icon: '🗑️', okText: 'Delete User', isDanger: true })) return;
    const res = await apiFetch(`/api/v1/admin/users/${userId}`, { method: "DELETE" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadUsers();
        loadGlobalStats();
    }
}

// 5. Subscriptions & Tiers
async function loadTiers() {
    const tbody = document.getElementById("tiers-table-body");
    if (!tbody) return;
    if (!currentAppId) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 30px;">No application selected.</td></tr>`;
        return;
    }
    const data = await apiFetch(`/api/v1/admin/tiers?app_id=${currentAppId}`);
    if (!data || !data.tiers || data.tiers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 30px;">No subscription tiers found. Click "+ Create Tier" to create ranks.</td></tr>`;
        return;
    }
    tbody.innerHTML = data.tiers.map(t => `
        <tr>
            <td><strong style="color: #fff;">${t.name}</strong></td>
            <td><span class="badge badge-cyan">Level ${t.level_rank}</span></td>
            <td><span style="color: var(--text-secondary);">${t.description || 'Standard Tier'}</span></td>
            <td>
                <button class="btn btn-danger btn-sm" onclick="deleteTier(${t.id})">🗑️ Delete</button>
            </td>
        </tr>
    `).join("");
}

async function createTierSubmit() {
    if (!currentAppId) return;
    const name = document.getElementById("tier-name").value.trim();
    const rank = parseInt(document.getElementById("tier-level").value) || 1;
    const desc = document.getElementById("tier-desc").value.trim();

    if (!name) return;
    const res = await apiFetch("/api/v1/admin/tiers", {
        method: "POST",
        body: JSON.stringify({ app_id: currentAppId, name: name, level_rank: rank, description: desc })
    });
    if (res && res.success) {
        showToast(res.message, "success");
        closeModal("modal-create-tier");
        loadTiers();
    }
}

async function deleteTier(tierId) {
    const res = await apiFetch(`/api/v1/admin/tiers/${tierId}`, { method: "DELETE" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadTiers();
    }
}

// 6. Cloud Variables
async function loadVariables() {
    const tbody = document.getElementById("variables-table-body");
    if (!tbody) return;

    if (!currentAppId) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 40px;">No application selected.</td></tr>`;
        return;
    }

    const data = await apiFetch(`/api/v1/admin/variables?app_id=${currentAppId}`);
    if (!data || !data.variables || data.variables.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 40px;">No cloud variables defined yet.</td></tr>`;
        return;
    }

    tbody.innerHTML = data.variables.map(v => `
        <tr>
            <td><strong class="mono" style="color: var(--brand-sky);">${v.name}</strong></td>
            <td><span class="mono" style="color: #fff; max-width: 300px; display: inline-block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${v.value}</span></td>
            <td><span class="badge badge-success"><span class="badge-dot"></span> Encrypted</span></td>
            <td>
                <button class="btn btn-danger btn-sm" onclick="deleteVariable(${v.id})">🗑️ Delete</button>
            </td>
        </tr>
    `).join("");
}

async function createVariableSubmit() {
    if (!currentAppId) return;
    const name = document.getElementById("var-name").value.trim();
    const val = document.getElementById("var-value").value.trim();

    if (!name || !val) {
        showToast("Variable name and value are required", "warning");
        return;
    }

    const res = await apiFetch("/api/v1/admin/variables", {
        method: "POST",
        body: JSON.stringify({ app_id: currentAppId, name: name, value: val, is_encrypted: true })
    });

    if (res && res.success) {
        showToast(res.message, "success");
        closeModal("modal-create-variable");
        loadVariables();
    }
}

async function deleteVariable(varId) {
    const res = await apiFetch(`/api/v1/admin/variables/${varId}`, { method: "DELETE" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadVariables();
    }
}

// 7. Files & CDN Loader
async function loadFiles() {
    const tbody = document.getElementById("files-table-body");
    if (!tbody) return;
    if (!currentAppId) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;">No application selected.</td></tr>`;
        return;
    }
    const data = await apiFetch(`/api/v1/admin/files?app_id=${currentAppId}`);
    if (!data || !data.files || data.files.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;">No files uploaded. Click "+ Add File" to distribute binaries.</td></tr>`;
        return;
    }
    tbody.innerHTML = data.files.map(f => `
        <tr>
            <td><strong class="mono" style="color: var(--brand-sky);">${f.file_id}</strong></td>
            <td><strong style="color: #fff;">${f.file_name}</strong></td>
            <td><a href="${f.file_url}" target="_blank" style="color: var(--brand-indigo); font-size: 12px; word-break: break-all;">${f.file_url}</a></td>
            <td><span class="badge badge-success"><span class="badge-dot"></span>tected</span></td>
            <td>
                <button class="btn btn-danger btn-sm" onclick="deleteFile(${f.id})">🗑️ Delete</button>
            </td>
        </tr>
    `).join("");
}

async function createFileSubmit() {
    if (!currentAppId) return;
    const fileId = document.getElementById("file-id-input").value.trim();
    const fileName = document.getElementById("file-name-input").value.trim();
    const fileUrl = document.getElementById("file-url-input").value.trim();

    if (!fileId || !fileName || !fileUrl) {
        showToast("All fields are required", "warning");
        return;
    }

    const res = await apiFetch("/api/v1/admin/files", {
        method: "POST",
        body: JSON.stringify({ app_id: currentAppId, file_id: fileId, file_name: fileName, file_url: fileUrl })
    });
    if (res && res.success) {
        showToast(res.message, "success");
        closeModal("modal-create-file");
        loadFiles();
    }
}

async function deleteFile(fileId) {
    const res = await apiFetch(`/api/v1/admin/files/${fileId}`, { method: "DELETE" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadFiles();
    }
}

// 8. Blacklists
async function loadBlacklists() {
    const tbody = document.getElementById("blacklists-table-body");
    if (!tbody) return;
    if (!currentAppId) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;">No application selected.</td></tr>`;
        return;
    }
    const data = await apiFetch(`/api/v1/admin/blacklists?app_id=${currentAppId}`);
    if (!data || !data.blacklists || data.blacklists.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;">No active blacklists.</td></tr>`;
        return;
    }
    tbody.innerHTML = data.blacklists.map(b => `
        <tr>
            <td><span class="badge badge-danger">${b.type.toUpperCase()}</span></td>
            <td><strong class="mono" style="color: #fff;">${b.data}</strong></td>
            <td><span>${b.reason}</span></td>
            <td><span style="font-size: 12px; color: var(--text-muted);">${b.created_at.substring(0, 10)}</span></td>
            <td>
                <button class="btn btn-danger btn-sm" onclick="deleteBlacklist(${b.id})">🗑️ Remove</button>
            </td>
        </tr>
    `).join("");
}

async function createBlacklistSubmit() {
    if (!currentAppId) return;
    const type = document.getElementById("bl-type").value;
    const data = document.getElementById("bl-data").value.trim();
    const reason = document.getElementById("bl-reason").value.trim();

    if (!data) return;
    const res = await apiFetch("/api/v1/admin/blacklists", {
        method: "POST",
        body: JSON.stringify({ app_id: currentAppId, type: type, data: data, reason: reason })
    });
    if (res && res.success) {
        showToast(res.message, "success");
        closeModal("modal-create-blacklist");
        loadBlacklists();
    }
}

async function deleteBlacklist(blId) {
    const res = await apiFetch(`/api/v1/admin/blacklists/${blId}`, { method: "DELETE" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadBlacklists();
    }
}

// 9. Resellers
function toggleAllResellerApps(allCheckbox) {
    const individualCheckboxes = document.querySelectorAll(".reseller-indiv-app-chk");
    individualCheckboxes.forEach(chk => {
        chk.checked = false;
        chk.disabled = allCheckbox.checked;
    });
}

function onIndividualResellerAppChange() {
    const allChk = document.getElementById("reseller-app-all");
    const individualCheckboxes = Array.from(document.querySelectorAll(".reseller-indiv-app-chk"));
    const anyChecked = individualCheckboxes.some(chk => chk.checked);
    if (anyChecked) {
        allChk.checked = false;
    }
}

async function loadResellers() {
    const tbody = document.getElementById("resellers-table-body");
    if (!tbody) return;

    // Populate multi-app checkboxes in modal
    const indContainer = document.getElementById("reseller-individual-apps");
    if (indContainer) {
        indContainer.innerHTML = "";
        appsList.forEach(a => {
            const lbl = document.createElement("label");
            lbl.style.cssText = "display: flex; align-items: center; gap: 8px; cursor: pointer; margin: 0; font-size: 13px;";
            lbl.innerHTML = `
                <input type="checkbox" class="reseller-indiv-app-chk" value="${a.name}" onchange="onIndividualResellerAppChange()" disabled style="width: 15px; height: 15px; accent-color: var(--brand-rose);">
                <span style="color: #fff; font-weight: 700;">📱 ${a.name} (v${a.version})</span>
            `;
            indContainer.appendChild(lbl);
        });
    }

    const data = await apiFetch("/api/v1/admin/resellers");
    if (!data || !data.resellers || data.resellers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;">No reseller accounts created yet. Click "+ Add Reseller" to create one.</td></tr>`;
        return;
    }
    tbody.innerHTML = data.resellers.map(r => `
        <tr>
            <td><strong style="color: #fff; font-size: 14px;">${r.username}</strong></td>
            <td>
                <span class="badge badge-success" style="font-size: 12.5px; font-weight: 800; cursor: pointer;" onclick="openManageResellerCreditsModal(${r.id}, '${r.username}', ${r.balance})" title="Click to adjust credits">
                    🪙 ${r.balance} Credits ✏️
                </span>
            </td>
            <td>
                <span style="color: #10b981; font-weight: 700;">${r.unused_keys || 0} Unused</span> / 
                <span style="color: var(--text-muted);">${r.total_keys || 0} Total</span>
            </td>
            <td><span class="badge badge-cyan" style="font-size: 11.5px; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${r.allowed_apps === 'all' ? '🌐 All Apps' : r.allowed_apps}</span></td>
            <td>
                <div style="display: flex; gap: 6px; align-items: center;">
                    <button class="btn btn-secondary btn-sm" onclick="openManageResellerCreditsModal(${r.id}, '${r.username}', ${r.balance})" title="Add/Deduct Credits">🪙 Credits</button>
                    <button class="btn btn-secondary btn-sm" onclick="openViewResellerKeysModal(${r.id}, '${r.username}')" title="Inspect Generated Keys">🔍 Keys</button>
                    <button class="btn btn-secondary btn-sm" onclick="openResetResellerPassModal(${r.id}, '${r.username}')" title="Reset Password">🔑 Pass</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteReseller(${r.id})" title="Delete Reseller">🗑️</button>
                </div>
            </td>
        </tr>
    `).join("");
}

function openManageResellerCreditsModal(id, username, currentBalance) {
    document.getElementById("credits-reseller-id").value = id;
    document.getElementById("credits-reseller-username").textContent = username;
    document.getElementById("credits-reseller-current").textContent = currentBalance;
    document.getElementById("credits-amount").value = 50;
    openModal("modal-manage-reseller-credits");
}

async function submitResellerCreditAdjustment() {
    const id = document.getElementById("credits-reseller-id").value;
    const op = document.getElementById("credits-operation").value;
    const amt = parseInt(document.getElementById("credits-amount").value) || 0;

    if (!id || amt <= 0) {
        showToast("Please enter a valid credit amount", "warning");
        return;
    }

    const res = await apiFetch(`/api/v1/admin/resellers/${id}/credits`, {
        method: "PATCH",
        body: JSON.stringify({ amount: amt, operation: op })
    });

    if (res && res.success) {
        showToast(res.message, "success");
        closeModal("modal-manage-reseller-credits");
        loadResellers();
    } else {
        showToast(res?.detail || "Failed to adjust credits", "error");
    }
}

async function openViewResellerKeysModal(id, username) {
    document.getElementById("audit-reseller-username").textContent = username;
    const tbody = document.getElementById("reseller-keys-audit-tbody");
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">Loading keys audit...</td></tr>`;
    openModal("modal-view-reseller-keys");

    const data = await apiFetch(`/api/v1/admin/resellers/${id}/licenses`);
    if (!data || !data.licenses || data.licenses.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">No keys generated by this reseller yet.</td></tr>`;
        return;
    }

    tbody.innerHTML = data.licenses.map(k => `
        <tr>
            <td><span class="mono" style="color: #ff4d79; font-weight: 700;">${k.key}</span></td>
            <td>${k.duration_days === -1 ? 'Lifetime' : k.duration_days + 'd'}</td>
            <td><span class="badge badge-${k.status === 'unused' ? 'success' : 'secondary'}">${k.status.toUpperCase()}</span></td>
            <td><span style="color: ${k.used_by !== '-' ? '#38bdf8' : 'var(--text-muted)'}; font-weight: 600;">${k.used_by}</span></td>
            <td style="color: var(--text-muted); font-size: 11px;">${k.created_at.substring(0, 10)}</td>
        </tr>
    `).join("");
}

function openResetResellerPassModal(id, username) {
    document.getElementById("reset-reseller-id-input").value = id;
    document.getElementById("reset-reseller-user-label").textContent = username;
    document.getElementById("reset-reseller-new-pass").value = "";
    openModal("modal-reset-reseller-pass");
}

async function submitResellerPassReset() {
    const id = document.getElementById("reset-reseller-id-input").value;
    const newPass = document.getElementById("reset-reseller-new-pass").value;

    if (!id || newPass.length < 4) {
        showToast("Password must be at least 4 characters", "warning");
        return;
    }

    const res = await apiFetch(`/api/v1/admin/resellers/${id}/password`, {
        method: "PATCH",
        body: JSON.stringify({ new_password: newPass })
    });

    if (res && res.success) {
        showToast(res.message, "success");
        closeModal("modal-reset-reseller-pass");
    } else {
        showToast(res?.detail || "Failed to update password", "error");
    }
}

async function createResellerSubmit() {
    const user = document.getElementById("reseller-user").value.trim();
    const pass = document.getElementById("reseller-pass").value;
    const bal = parseInt(document.getElementById("reseller-balance").value) || 50;

    const allChk = document.getElementById("reseller-app-all");
    let allowedAppString = "all";

    if (!allChk || !allChk.checked) {
        const checkedApps = Array.from(document.querySelectorAll(".reseller-indiv-app-chk:checked")).map(chk => chk.value);
        if (checkedApps.length === 0) {
            showToast("Please select at least one application or choose 'All Applications'", "warning");
            return;
        }
        allowedAppString = checkedApps.join(",");
    }

    if (!user || !pass) {
        showToast("Username and password are required", "warning");
        return;
    }

    const res = await apiFetch("/api/v1/admin/resellers", {
        method: "POST",
        body: JSON.stringify({
            username: user,
            password: pass,
            balance: bal,
            allowed_apps: allowedAppString
        })
    });

    if (res && res.success) {
        showToast(res.message, "success");
        closeModal("modal-create-reseller");
        loadResellers();
    } else {
        showToast(res?.detail || "Failed to create reseller", "error");
    }
}

async function deleteReseller(resellerId) {
    const res = await apiFetch(`/api/v1/admin/resellers/${resellerId}`, { method: "DELETE" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadResellers();
    }
}

// 10. Webhook Dispatcher & Bot Invite
function copyBotInviteLink() {
    const inviteUrl = "https://discord.com/api/oauth2/authorize?client_id=123456789012345678&permissions=8&scope=bot%20applications.commands";
    navigator.clipboard.writeText(inviteUrl);
    showToast("📋 Discord Bot invite link copied to clipboard!", "success");
}

async function saveDiscordWebhookUrl() {
    if (!currentAppId) {
        showToast("Please select an application first", "warning");
        return;
    }
    const url = document.getElementById("discord-webhook-url-input")?.value.trim() || "";
    const res = await apiFetch(`/api/v1/admin/apps/${currentAppId}`, {
        method: "PUT",
        body: JSON.stringify({ webhook_url: url })
    });
    if (res && res.success) {
        showToast("✅ Discord Webhook URL saved! All logs will now broadcast to your channel.", "success");
        loadApps();
    }
}

async function sendTestWebhook() {
    if (!currentAppId) return;
    const url = document.getElementById("discord-webhook-url-input")?.value.trim() || "";
    if (url) {
        await apiFetch(`/api/v1/admin/apps/${currentAppId}`, {
            method: "PUT",
            body: JSON.stringify({ webhook_url: url })
        });
    }

    const msg = "🧪 Test log from Joyst Corporation Auth! Discord channel connection is working 100%.";
    const res = await apiFetch("/api/v1/admin/webhooks/test", {
        method: "POST",
        body: JSON.stringify({ app_id: currentAppId, custom_message: msg })
    });
    if (res && res.success) {
        showToast("✅ Test Webhook dispatched! Check your Discord channel.", "success");
    } else {
        showToast(res?.detail || "Webhook failed. Make sure a valid Discord Webhook URL is entered.", "error");
    }
}

// 11. Plan Redeem Key
async function redeemPlanKeySubmit() {
    const keyInput = document.getElementById("redeem-plan-key-input");
    const key = keyInput ? keyInput.value.trim() : "";
    if (!key) {
        showToast("Please enter an Upgrade License Key", "warning");
        return;
    }
    const res = await apiFetch("/api/v1/admin/plan/redeem", {
        method: "POST",
        body: JSON.stringify({ key_code: key })
    });
    if (res && res.success) {
        showToast(res.message, "success");
        if (keyInput) keyInput.value = "";
        await loadUserProfile();
    } else {
        showToast(res?.detail || "Invalid Upgrade Key. Please check the key and try again.", "error");
    }
}

async function generatePlanKeysSubmit() {
    const targetPlan = document.getElementById("gen-plan-target")?.value || "Developer";
    const count = parseInt(document.getElementById("gen-plan-count")?.value) || 1;

    const res = await apiFetch("/api/v1/admin/plan/generate-keys", {
        method: "POST",
        body: JSON.stringify({ target_plan: targetPlan, count: count })
    });

    if (res && res.success) {
        showToast(res.message, "success");
        closeModal("modal-generate-plan-keys");
        if (res.keys && res.keys.length > 0) {
            document.getElementById("generated-keys-output").value = res.keys.join("\n");
            openModal("modal-view-generated");
        }
    } else {
        showToast(res?.detail || "Failed to generate upgrade keys", "error");
    }
}

// ==================== 12. IN-APP CLIENT NOTIFICATIONS (KEYAUTH STYLE) ====================
async function loadNotifications() {
    const tbody = document.getElementById("notifications-table-body");
    if (!tbody) return;

    if (!currentAppId) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 40px;">No application selected. Select or create an app first.</td></tr>`;
        return;
    }

    const data = await apiFetch(`/api/v1/admin/notifications?app_id=${currentAppId}`);
    if (!data || !data.notifications || data.notifications.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 40px;">
                    No client notifications created for this app. Click "<strong>➕ Create Notification</strong>" to broadcast an in-app notice or login alert!
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = data.notifications.map(n => {
        let badgeType = "badge-info";
        let icon = "ℹ️";
        if (n.type === "success") { badgeType = "badge-success"; icon = "🟢"; }
        else if (n.type === "warning") { badgeType = "badge-warning"; icon = "⚠️"; }
        else if (n.type === "danger") { badgeType = "badge-danger"; icon = "🚨"; }

        return `
            <tr>
                <td>
                    <span class="badge ${badgeType}">
                        <span class="badge-dot"></span> ${icon} ${n.type.toUpperCase()}
                    </span>
                </td>
                <td><strong style="color: #fff;">${escapeHtml(n.title)}</strong></td>
                <td style="max-width: 350px; font-size: 12.5px; color: var(--text-secondary); word-break: break-word;">
                    ${escapeHtml(n.message)}
                </td>
                <td>
                    <span class="badge badge-${n.show_on_login ? 'success' : 'purple'}">
                        ${n.show_on_login ? '✅ YES (Popup)' : 'NO (Quiet)'}
                    </span>
                </td>
                <td>
                    <span class="badge badge-${n.is_active ? 'success' : 'danger'}">
                        <span class="badge-dot"></span> ${n.is_active ? 'BROADCASTING' : 'DISABLED'}
                    </span>
                </td>
                <td>
                    <div style="display: flex; gap: 6px;">
                        <button class="btn btn-secondary btn-sm" onclick="toggleNotificationStatus(${n.id})" title="Toggle Active/Disabled">
                            ${n.is_active ? '⏸️ Pause' : '▶️ Activate'}
                        </button>
                        <button class="btn btn-danger btn-sm" onclick="deleteNotification(${n.id})" title="Delete Notification">
                            🗑️
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

async function createNotificationSubmit() {
    if (!currentAppId) {
        showToast("Please select an application first", "warning");
        return;
    }

    const title = document.getElementById("notif-title-input").value.trim();
    const type = document.getElementById("notif-type-select").value;
    const message = document.getElementById("notif-message-input").value.trim();
    const showOnLogin = document.getElementById("notif-show-login-check").checked;

    if (!title || !message) {
        showToast("Notification title and message are required", "warning");
        return;
    }

    closeModal("modal-create-notif");
    showToast("Broadcasting notification...", "info");

    const res = await apiFetch("/api/v1/admin/notifications", {
        method: "POST",
        body: JSON.stringify({
            app_id: currentAppId,
            title: title,
            type: type,
            message: message,
            show_on_login: showOnLogin
        })
    });

    if (res && res.success) {
        showToast(res.message, "success");
        document.getElementById("notif-title-input").value = "";
        document.getElementById("notif-message-input").value = "";
        loadNotifications();
    } else {
        showToast(res?.detail || "Failed to create notification", "error");
    }
}

async function toggleNotificationStatus(notifId) {
    const res = await apiFetch(`/api/v1/admin/notifications/${notifId}/toggle`, { method: "PATCH" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadNotifications();
    }
}

async function deleteNotification(notifId) {
    if (!await showConfirmDialog({ title: 'Delete Notification', message: 'Are you sure you want to delete this in-app notification?', icon: '🗑️', okText: 'Delete', isDanger: true })) return;
    const res = await apiFetch(`/api/v1/admin/notifications/${notifId}`, { method: "DELETE" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadNotifications();
    }
}

// ==================== 13. KEYAUTH-GRADE APPLICATION SETTINGS & SECURITY ====================
function renderAppsPage() {
    renderAllAppsList();
}

let currentSettingsSubTab = "account";

function switchSettingsSubTab(subtabId) {
    currentSettingsSubTab = subtabId;
    document.querySelectorAll(".settings-subtab-btn").forEach(btn => {
        btn.className = "btn btn-secondary btn-sm settings-subtab-btn";
    });
    const activeBtn = document.getElementById(`btn-subtab-${subtabId}`);
    if (activeBtn) activeBtn.className = "btn btn-primary btn-sm settings-subtab-btn";

    document.querySelectorAll(".settings-subtab-content").forEach(sec => {
        sec.style.display = "none";
    });
    const activeSec = document.getElementById(`settings-section-${subtabId}`);
    if (activeSec) activeSec.style.display = "block";

    if (subtabId !== "account") {
        renderActiveAppSettings();
    }
}

function renderActiveAppSettings() {
    const msgContainer = document.getElementById("settings-messages-container");
    const secContainer = document.getElementById("settings-security-container");
    const stateContainer = document.getElementById("settings-appstate-container");

    const app = appsList.find(a => a.id === currentAppId);

    if (!app) {
        const noAppHtml = `
            <div class="stat-card spotlight-card" style="padding: 30px; text-align: center; color: var(--text-muted);">
                <h3>No Application Selected</h3>
                <p style="margin-top: 6px;">Select an application from the top dropdown or click "➕ New App" to begin.</p>
            </div>
        `;
        if (msgContainer) msgContainer.innerHTML = noAppHtml;
        if (secContainer) secContainer.innerHTML = noAppHtml;
        if (stateContainer) stateContainer.innerHTML = noAppHtml;
        return;
    }

    const appSelectorHtml = `
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px; margin-bottom: 20px; background: rgba(0,0,0,0.3); padding: 16px 20px; border-radius: 12px; border: 1px solid var(--border-glass);">
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <span style="font-size: 13px; font-weight: 700; color: var(--text-secondary);">Application:</span>
                <select class="form-control" style="width: auto; min-width: 230px; font-weight: 800; background: rgba(14, 5, 10, 0.9); border-color: var(--brand-rose);" onchange="switchAppFromSettingsDropdown(this.value)">
                    ${appsList.map(a => `<option value="${a.id}" ${a.id === app.id ? 'selected' : ''}>${escapeHtml(a.name)} (v${a.version})</option>`).join('')}
                </select>
                <span class="badge badge-${app.status === 'enabled' ? 'success' : 'danger'}">
                    <span class="badge-dot"></span> ${app.status.toUpperCase()}
                </span>
            </div>
            <div style="display: flex; gap: 8px;">
                <button class="btn btn-primary btn-sm" onclick="saveAllAppSettings(${app.id})">💾 Save Settings</button>
                <button class="btn btn-secondary btn-sm" onclick="regenerateSecret(${app.id})">🔄 Reset Secret</button>
            </div>
        </div>
    `;

    // 1. Render Sub-Tab: 18 Custom Messages
    if (msgContainer) {
        msgContainer.innerHTML = `
            ${appSelectorHtml}
            <div class="stat-card spotlight-card" style="padding: 24px; border: 1px solid rgba(225, 29, 72, 0.35);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <h3 style="font-size: 17px; font-weight: 800; color: #fff; margin: 0; display: flex; align-items: center; gap: 8px;">
                            <span>💬 Master Custom Response Messages (18 Scenarios)</span>
                        </h3>
                        <p style="font-size: 12px; color: var(--text-secondary); margin-top: 4px; margin-bottom: 0;">
                            Configure exact custom strings returned to your clients and loaders:
                        </p>
                    </div>
                    <span class="badge badge-success">18 Configurable Responses</span>
                </div>

                <!-- Group 1: Login & Authentication -->
                <div style="margin-bottom: 22px;">
                    <div style="font-size: 12.5px; font-weight: 800; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; border-bottom: 1px solid var(--border-glass); padding-bottom: 6px;">
                        🟢 1. Login & Authentication
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">
                        <div class="form-group">
                            <label>Login Success</label>
                            <input type="text" id="setting-login-success-msg" class="form-control" value="${escapeHtml(app.login_success_message || 'Welcome back! Logged in successfully.')}">
                        </div>
                        <div class="form-group">
                            <label>Incorrect Password</label>
                            <input type="text" id="setting-login-failed-msg" class="form-control" value="${escapeHtml(app.login_failed_message || 'Invalid username or password.')}">
                        </div>
                        <div class="form-group">
                            <label>Username Not Found</label>
                            <input type="text" id="setting-user-not-found-msg" class="form-control" value="${escapeHtml(app.user_not_found_message || 'Username does not exist.')}">
                        </div>
                        <div class="form-group">
                            <label>Subscription Expired</label>
                            <input type="text" id="setting-expired-sub-msg" class="form-control" value="${escapeHtml(app.expired_sub_message || 'Your subscription has expired! Please renew.')}">
                        </div>
                    </div>
                </div>

                <!-- Group 2: Security & Anti-Cheat -->
                <div style="margin-bottom: 22px;">
                    <div style="font-size: 12.5px; font-weight: 800; color: #ff2a5f; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; border-bottom: 1px solid var(--border-glass); padding-bottom: 6px;">
                        🛡️ 2. Security & Anti-Cheat Enforcement
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">
                        <div class="form-group">
                            <label>HWID Mismatch Lock</label>
                            <input type="text" id="setting-hwid-mismatch-msg" class="form-control" value="${escapeHtml(app.hwid_mismatch_message || 'HWID Mismatch! Your account is locked to another computer.')}">
                        </div>
                        <div class="form-group">
                            <label>Banned Account Notice</label>
                            <input type="text" id="setting-banned-user-msg" class="form-control" value="${escapeHtml(app.banned_user_message || 'Account is banned!')}">
                        </div>
                        <div class="form-group">
                            <label>Brute-Force Auto-Ban (5+ Attempts)</label>
                            <input type="text" id="setting-brute-force-ban-msg" class="form-control" value="${escapeHtml(app.brute_force_ban_message || 'Too many invalid attempts! Your PC hardware and IP are permanently banned.')}">
                        </div>
                        <div class="form-group">
                            <label>Blacklisted IP / HWID</label>
                            <input type="text" id="setting-blacklist-msg" class="form-control" value="${escapeHtml(app.blacklist_message || 'Access Denied! Your IP or Machine HWID has been blacklisted.')}">
                        </div>
                        <div class="form-group">
                            <label>VPN / Proxy Block</label>
                            <input type="text" id="setting-vpn-blocked-msg" class="form-control" value="${escapeHtml(app.vpn_blocked_message || 'VPN or Proxy connections are strictly prohibited.')}">
                        </div>
                        <div class="form-group">
                            <label>Binary Integrity Hash Mismatch</label>
                            <input type="text" id="setting-hash-mismatch-msg" class="form-control" value="${escapeHtml(app.hash_mismatch_message || 'Executable integrity verification failed! Modified or cracked binary detected.')}">
                        </div>
                    </div>
                </div>

                <!-- Group 3: License Keys & User Registration -->
                <div style="margin-bottom: 22px;">
                    <div style="font-size: 12.5px; font-weight: 800; color: #a855f7; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; border-bottom: 1px solid var(--border-glass); padding-bottom: 6px;">
                        🔑 3. License Keys & Registration
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">
                        <div class="form-group">
                            <label>Registration Success</label>
                            <input type="text" id="setting-register-success-msg" class="form-control" value="${escapeHtml(app.register_success_message || 'Account created successfully! You are now logged in.')}">
                        </div>
                        <div class="form-group">
                            <label>License Login Success</label>
                            <input type="text" id="setting-license-login-success-msg" class="form-control" value="${escapeHtml(app.license_login_success_message || 'License authenticated successfully!')}">
                        </div>
                        <div class="form-group">
                            <label>Invalid License Key</label>
                            <input type="text" id="setting-invalid-license-msg" class="form-control" value="${escapeHtml(app.invalid_license_message || 'Invalid license key.')}">
                        </div>
                        <div class="form-group">
                            <label>Already Used Key</label>
                            <input type="text" id="setting-used-license-msg" class="form-control" value="${escapeHtml(app.used_license_message || 'This license key is already used.')}">
                        </div>
                        <div class="form-group">
                            <label>Paused License Key</label>
                            <input type="text" id="setting-paused-license-msg" class="form-control" value="${escapeHtml(app.paused_license_message || 'This license key is paused by administrator.')}">
                        </div>
                        <div class="form-group">
                            <label>Revoked License Key</label>
                            <input type="text" id="setting-revoked-license-msg" class="form-control" value="${escapeHtml(app.revoked_license_message || 'This license key has been revoked.')}">
                        </div>
                    </div>
                </div>

                <!-- Group 4: System & Maintenance -->
                <div style="margin-bottom: 22px;">
                    <div style="font-size: 12.5px; font-weight: 800; color: #f59e0b; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; border-bottom: 1px solid var(--border-glass); padding-bottom: 6px;">
                        ⏸️ 4. Maintenance & Version Control
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">
                        <div class="form-group">
                            <label>Maintenance Mode Message</label>
                            <input type="text" id="setting-maintenance-msg" class="form-control" value="${escapeHtml(app.maintenance_message || 'Application is under maintenance. Please check back soon.')}">
                        </div>
                        <div class="form-group">
                            <label>Version Update Required Notice</label>
                            <input type="text" id="setting-version-mismatch-msg" class="form-control" value="${escapeHtml(app.version_mismatch_message || 'Update required! Please download the latest version.')}">
                        </div>
                    </div>
                </div>

                <div style="display: flex; justify-content: flex-end; margin-top: 14px;">
                    <button class="btn btn-primary" style="padding: 10px 28px; font-size: 14px;" onclick="saveAllAppSettings(${app.id})">💾 Save All 18 Custom Messages</button>
                </div>
            </div>
        `;
    }

    // 2. Render Sub-Tab: Security & HWID
    if (secContainer) {
        secContainer.innerHTML = `
            ${appSelectorHtml}
            <div class="stat-card spotlight-card" style="padding: 24px; border: 1px solid rgba(225, 29, 72, 0.35); margin-bottom: 24px;">
                <h3 style="font-size: 17px; font-weight: 800; color: #ff4d79; margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
                    <span>🔒 Hardware Binding & Anti-Share Protection</span>
                </h3>

                <div style="display: flex; flex-direction: column; gap: 16px; margin-bottom: 24px;">
                    <label style="display: flex; align-items: center; justify-content: space-between; cursor: pointer; background: rgba(0,0,0,0.3); padding: 14px 18px; border-radius: 10px; border: 1px solid var(--border-glass);">
                        <div>
                            <strong style="color: #fff; font-size: 13.5px;">Force Strict Motherboard HWID Lock</strong>
                            <div style="color: var(--text-muted); font-size: 12px; margin-top: 2px;">Blocks accounts from running on different computer hardware</div>
                        </div>
                        <input type="checkbox" id="setting-hwid-lock" ${app.hwid_lock_enabled ? 'checked' : ''} style="width: 22px; height: 22px; accent-color: #ff2a5f; cursor: pointer;">
                    </label>

                    <label style="display: flex; align-items: center; justify-content: space-between; cursor: pointer; background: rgba(0,0,0,0.3); padding: 14px 18px; border-radius: 10px; border: 1px solid var(--border-glass);">
                        <div>
                            <strong style="color: #fff; font-size: 13.5px;">Allow User Self HWID Reset</strong>
                            <div style="color: var(--text-muted); font-size: 12px; margin-top: 2px;">Permit users to reset HWID once or require admin reset</div>
                        </div>
                        <input type="checkbox" id="setting-user-hwid-reset" ${app.allow_user_hwid_reset ? 'checked' : ''} style="width: 22px; height: 22px; accent-color: #ff2a5f; cursor: pointer;">
                    </label>

                    <label style="display: flex; align-items: center; justify-content: space-between; cursor: pointer; background: rgba(0,0,0,0.3); padding: 14px 18px; border-radius: 10px; border: 1px solid var(--border-glass);">
                        <div>
                            <strong style="color: #fff; font-size: 13.5px;">VPN & Proxy Blocker</strong>
                            <div style="color: var(--text-muted); font-size: 12px; margin-top: 2px;">Block connections originating from VPNs, datacenter proxies & Tor</div>
                        </div>
                        <input type="checkbox" id="setting-vpn-block" ${app.vpn_block_enabled ? 'checked' : ''} style="width: 22px; height: 22px; accent-color: #ff2a5f; cursor: pointer;">
                    </label>
                </div>

                <h4 style="font-size: 15px; font-weight: 800; color: #8b5cf6; margin-bottom: 12px;">
                    📦 Version Enforcement & Binary Integrity Hash
                </h4>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 20px;">
                    <div class="form-group">
                        <label>Target Application Version</label>
                        <input type="text" id="setting-version" class="form-control mono" value="${escapeHtml(app.version || '1.0')}">
                    </div>

                    <div class="form-group">
                        <label>Auto-Update Direct Download Link</label>
                        <input type="url" id="setting-download-url" class="form-control mono" value="${escapeHtml(app.download_link || '')}" placeholder="https://mysite.com/update.exe">
                    </div>

                    <div class="form-group" style="grid-column: 1 / -1;">
                        <label style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                            <span>Binary Integrity Hash (MD5 / SHA256)</span>
                            <span style="font-size: 11px; color: var(--text-muted);">Blocks cracked modified executables</span>
                        </label>
                        <div style="display: flex; gap: 10px; align-items: center;">
                            <input type="text" id="setting-app-hash" class="form-control mono" value="${escapeHtml(app.app_hash || '')}" placeholder="e.g. 7f8a9b4c...">
                            <label style="display: flex; align-items: center; gap: 8px; font-size: 12px; white-space: nowrap; color: #fff; cursor: pointer;">
                                <input type="checkbox" id="setting-hash-check-toggle" ${app.hash_check_enabled ? 'checked' : ''} style="width: 17px; height: 17px; accent-color: #ff2a5f;">
                                Enable Hash Check
                            </label>
                        </div>
                    </div>
                </div>

                <div style="display: flex; justify-content: flex-end;">
                    <button class="btn btn-primary" style="padding: 10px 28px; font-size: 14px;" onclick="saveAllAppSettings(${app.id})">💾 Save Security Policies</button>
                </div>
            </div>
        `;
    }

    // 3. Render Sub-Tab: App State & Killswitch
    if (stateContainer) {
        stateContainer.innerHTML = `
            ${appSelectorHtml}
            <div class="stat-card spotlight-card" style="padding: 24px; border: 1px solid rgba(225, 29, 72, 0.35);">
                <h3 style="font-size: 17px; font-weight: 800; color: #38bdf8; margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
                    <span>⚡ Application State, Killswitch & Tokens</span>
                </h3>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px;">
                    <div class="form-group">
                        <label>Application Master Switch</label>
                        <select id="setting-app-status" class="form-control" style="font-weight: 800;">
                            <option value="enabled" ${app.status === 'enabled' ? 'selected' : ''}>🟢 Enabled (Normal Operations)</option>
                            <option value="paused" ${app.status === 'paused' || app.status === 'maintenance' ? 'selected' : ''}>⏸️ Maintenance / Paused</option>
                            <option value="disabled" ${app.status === 'disabled' ? 'selected' : ''}>🚫 Disabled (Emergency Lock)</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label>Application Operational Status</label>
                        <select id="setting-custom-status" class="form-control" style="font-weight: 800;">
                            <option value="ONLINE" ${app.custom_status === 'ONLINE' || app.custom_status === 'UNDETECTED' ? 'selected' : ''}>🟢 Operational & Online</option>
                            <option value="UPDATING" ${app.custom_status === 'UPDATING' ? 'selected' : ''}>🟡 Maintenance / Update in Progress</option>
                            <option value="MAINTENANCE" ${app.custom_status === 'MAINTENANCE' ? 'selected' : ''}>🔴 Emergency Maintenance</option>
                            <option value="OFFLINE" ${app.custom_status === 'OFFLINE' ? 'selected' : ''}>⛔ Offline</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label>Session Timeout (Minutes)</label>
                        <input type="number" id="setting-session-timeout" class="form-control" value="${app.session_timeout_minutes || 60}" min="5" max="1440">
                    </div>
                </div>

                <div class="form-group" style="margin-bottom: 24px;">
                    <label>Master App Secret Token</label>
                    <div style="display: flex; gap: 10px;">
                        <input type="text" value="${app.secret}" id="token-setting-${app.id}" class="form-control mono" readonly style="color: #38bdf8; font-weight: 700;">
                        <button class="btn btn-secondary" onclick="copyToClipboard('${app.secret}')">📋 Copy</button>
                        <button class="btn btn-danger" onclick="regenerateSecret(${app.id})">🔄 Reset Secret</button>
                    </div>
                </div>

                <div style="display: flex; justify-content: flex-end;">
                    <button class="btn btn-primary" style="padding: 10px 28px; font-size: 14px;" onclick="saveAllAppSettings(${app.id})">💾 Save App State</button>
                </div>
            </div>
        `;
    }
}

function renderAllAppsList() {
    const container = document.getElementById("apps-grid-container");
    if (!container) return;

    if (appsList.length === 0) {
        container.innerHTML = `
            <div class="stat-card spotlight-card" style="padding: 40px; text-align: center; color: var(--text-muted); grid-column: 1 / -1;">
                <h3 style="color: #fff; font-size: 18px; margin-bottom: 8px;">No Applications Registered</h3>
                <p style="margin-bottom: 16px;">Create your first application to get your App Secret and start integrating authentication.</p>
                <button class="btn btn-primary btn-sm" onclick="openModal('modal-create-app')">➕ Create Application</button>
            </div>
        `;
        return;
    }

    container.innerHTML = appsList.map(app => `
        <div class="stat-card spotlight-card" style="padding: 24px; border: 1px solid var(--border-glass); background: rgba(14, 5, 10, 0.75);">
            <!-- Header: App Name & Version -->
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; border-bottom: 1px solid var(--border-glass); padding-bottom: 14px;">
                <div>
                    <h3 style="font-size: 18px; font-weight: 800; color: #fff; margin: 0; display: flex; align-items: center; gap: 8px;">
                        <span>📱 ${escapeHtml(app.name)}</span>
                    </h3>
                    <div style="display: flex; gap: 6px; margin-top: 6px; align-items: center;">
                        <span class="badge badge-cyan" style="font-size: 11px;">v${escapeHtml(app.version || '1.0')}</span>
                        <span class="badge badge-${app.status === 'enabled' ? 'success' : 'danger'}" style="font-size: 11px;">
                            <span class="badge-dot"></span> ${app.status === 'enabled' ? 'ACTIVE' : app.status.toUpperCase()}
                        </span>
                    </div>
                </div>
                <button class="btn btn-danger btn-sm" title="Delete Application" onclick="deleteApp(${app.id})" style="padding: 6px 10px;">🗑️</button>
            </div>

            <!-- Credentials & Parameters for Easy Implementation -->
            <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 18px;">
                <!-- Application Name -->
                <div class="form-group" style="margin-bottom: 0;">
                    <label style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); font-weight: 700;">Application Name</label>
                    <div style="display: flex; gap: 6px;">
                        <input type="text" value="${escapeHtml(app.name)}" id="appname-${app.id}" class="form-control mono" readonly style="font-size: 12px; color: #fff; background: rgba(0,0,0,0.4);">
                        <button class="btn btn-secondary btn-sm" onclick="copyToClipboard('${escapeHtml(app.name)}')">📋</button>
                    </div>
                </div>

                <!-- App Secret Token -->
                <div class="form-group" style="margin-bottom: 0;">
                    <label style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); font-weight: 700;">App Secret (Token)</label>
                    <div style="display: flex; gap: 6px;">
                        <input type="password" value="${app.secret}" id="token-${app.id}" class="form-control mono" readonly style="font-size: 12px; color: #38bdf8; background: rgba(0,0,0,0.4);">
                        <button class="btn btn-secondary btn-sm" onclick="toggleSecretVisibility('token-${app.id}')">👁️</button>
                        <button class="btn btn-secondary btn-sm" onclick="copyToClipboard('${app.secret}')">📋</button>
                    </div>
                </div>
            </div>

            <!-- Security Parameters -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 18px; background: rgba(0,0,0,0.3); padding: 12px 14px; border-radius: 8px; border: 1px solid var(--border-subtle); font-size: 12px;">
                <div>
                    <span style="color: var(--text-muted);">HWID Lock:</span>
                    <strong style="color: ${app.hwid_lock_enabled ? '#10b981' : '#ef4444'}; margin-left: 4px;">${app.hwid_lock_enabled ? 'ENABLED' : 'DISABLED'}</strong>
                </div>
                <div>
                    <span style="color: var(--text-muted);">VPN Blocker:</span>
                    <strong style="color: ${app.vpn_block_enabled ? '#10b981' : '#ef4444'}; margin-left: 4px;">${app.vpn_block_enabled ? 'ENABLED' : 'DISABLED'}</strong>
                </div>
            </div>

            <!-- Action Navigation Buttons -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 14px; border-top: 1px solid var(--border-glass); padding-top: 14px;">
                <button class="btn btn-secondary btn-sm" style="font-size: 12px;" onclick="goToAppKeys(${app.id})">
                    🔑 License Keys
                </button>
                <button class="btn btn-primary btn-sm" style="font-size: 12px;" onclick="goToAppSettings(${app.id})">
                    ⚙️ App Settings
                </button>
            </div>
        </div>
    `).join("");
}

function goToAppSettings(appId) {
    currentAppId = appId;
    localStorage.setItem("selected_app_id", appId);
    updateBannerCredentials();
    switchTab('settings');
    switchSettingsSubTab('messages');
    showToast(`Configuring settings for ${appsList.find(a => a.id === appId)?.name}`, "info");
}

function goToAppKeys(appId) {
    currentAppId = appId;
    localStorage.setItem("selected_app_id", appId);
    updateBannerCredentials();
    switchTab('licenses');
    showToast(`Viewing license keys for ${appsList.find(a => a.id === appId)?.name}`, "info");
}

function switchAppFromSettingsDropdown(appId) {
    if (!appId) return;
    currentAppId = parseInt(appId);
    localStorage.setItem("selected_app_id", currentAppId);
    updateBannerCredentials();
    renderActiveAppSettings();
    showToast(`Switched settings view to ${appsList.find(a => a.id === currentAppId)?.name}`, "info");
}

function selectAppFromCard(appId) {
    currentAppId = appId;
    localStorage.setItem("selected_app_id", appId);
    updateBannerCredentials();
    switchTab('settings');
    showToast(`Switched active application to ${appsList.find(a => a.id === appId)?.name}`, "info");
}

async function saveAllAppSettings(appId) {
    const hwidLock = document.getElementById("setting-hwid-lock")?.checked;
    const userHwidReset = document.getElementById("setting-user-hwid-reset")?.checked;
    const vpnBlock = document.getElementById("setting-vpn-block")?.checked;
    const appStatus = document.getElementById("setting-app-status")?.value;
    const customStatus = document.getElementById("setting-custom-status")?.value;
    const sessionTimeout = parseInt(document.getElementById("setting-session-timeout")?.value || "60");

    // All 18 Custom Response Messages
    const loginSuccessMsg = document.getElementById("setting-login-success-msg")?.value.trim();
    const loginFailedMsg = document.getElementById("setting-login-failed-msg")?.value.trim();
    const userNotFoundMsg = document.getElementById("setting-user-not-found-msg")?.value.trim();
    const expiredSubMsg = document.getElementById("setting-expired-sub-msg")?.value.trim();
    const hwidMismatchMsg = document.getElementById("setting-hwid-mismatch-msg")?.value.trim();
    const bannedUserMsg = document.getElementById("setting-banned-user-msg")?.value.trim();
    const bruteForceBanMsg = document.getElementById("setting-brute-force-ban-msg")?.value.trim();
    const blacklistMsg = document.getElementById("setting-blacklist-msg")?.value.trim();
    const vpnBlockedMsg = document.getElementById("setting-vpn-blocked-msg")?.value.trim();
    const hashMismatchMsg = document.getElementById("setting-hash-mismatch-msg")?.value.trim();
    const registerSuccessMsg = document.getElementById("setting-register-success-msg")?.value.trim();
    const licenseLoginSuccessMsg = document.getElementById("setting-license-login-success-msg")?.value.trim();
    const invalidLicenseMsg = document.getElementById("setting-invalid-license-msg")?.value.trim();
    const usedLicenseMsg = document.getElementById("setting-used-license-msg")?.value.trim();
    const pausedLicenseMsg = document.getElementById("setting-paused-license-msg")?.value.trim();
    const revokedLicenseMsg = document.getElementById("setting-revoked-license-msg")?.value.trim();
    const maintenanceMsg = document.getElementById("setting-maintenance-msg")?.value.trim();
    const versionMismatchMsg = document.getElementById("setting-version-mismatch-msg")?.value.trim();

    const version = document.getElementById("setting-version")?.value.trim();
    const downloadUrl = document.getElementById("setting-download-url")?.value.trim();
    const appHash = document.getElementById("setting-app-hash")?.value.trim();
    const hashCheckToggle = document.getElementById("setting-hash-check-toggle")?.checked;

    showToast("Saving application settings...", "info");

    const res = await apiFetch(`/api/v1/admin/apps/${appId}`, {
        method: "PUT",
        body: JSON.stringify({
            hwid_lock_enabled: hwidLock,
            allow_user_hwid_reset: userHwidReset,
            vpn_block_enabled: vpnBlock,
            status: appStatus,
            custom_status: customStatus,
            session_timeout_minutes: sessionTimeout,
            login_success_message: loginSuccessMsg,
            login_failed_message: loginFailedMsg,
            user_not_found_message: userNotFoundMsg,
            expired_sub_message: expiredSubMsg,
            hwid_mismatch_message: hwidMismatchMsg,
            banned_user_message: bannedUserMsg,
            brute_force_ban_message: bruteForceBanMsg,
            blacklist_message: blacklistMsg,
            vpn_blocked_message: vpnBlockedMsg,
            hash_mismatch_message: hashMismatchMsg,
            register_success_message: registerSuccessMsg,
            license_login_success_message: licenseLoginSuccessMsg,
            invalid_license_message: invalidLicenseMsg,
            used_license_message: usedLicenseMsg,
            paused_license_message: pausedLicenseMsg,
            revoked_license_message: revokedLicenseMsg,
            maintenance_message: maintenanceMsg,
            version_mismatch_message: versionMismatchMsg,
            version: version,
            download_link: downloadUrl,
            app_hash: appHash,
            hash_check_enabled: hashCheckToggle
        })
    });

    if (res && res.success) {
        showToast("✅ Application settings and login notifications saved successfully!", "success");
        await loadApps();
        renderAppsPage();
    } else {
        showToast(res?.detail || "Failed to save settings", "error");
    }
}

async function createAppSubmit() {
    const name = document.getElementById("new-app-name").value.trim();
    const version = document.getElementById("new-app-version").value.trim() || "1.0";
    const hwidLock = document.getElementById("new-app-hwid-lock").checked;
    const webhook = document.getElementById("new-app-webhook").value.trim();

    if (!name) {
        showToast("Application name is required", "warning");
        return;
    }

    closeModal("modal-create-app");
    showToast("Creating application...", "info");

    const res = await apiFetch("/api/v1/admin/apps", {
        method: "POST",
        body: JSON.stringify({
            name: name,
            version: version,
            hwid_lock_enabled: hwidLock,
            webhook_url: webhook
        })
    });

    if (res && res.success) {
        showToast(res.message, "success");
        await loadApps();
        renderAppsPage();
        loadGlobalStats();
    } else {
        showToast(res?.detail || "Failed to create app", "error");
        await loadApps();
    }
}

async function regenerateSecret(appId) {
    if (!await showConfirmDialog({ title: 'Reset App Secret', message: 'Regenerating the App Secret will disconnect all existing SDK clients until updated with the new token. Proceed?', icon: '⚠️', okText: 'Reset Secret', isDanger: true })) return;
    const res = await apiFetch(`/api/v1/admin/apps/${appId}/regenerate-secret`, { method: "POST" });
    if (res && res.success) {
        showToast(res.message, "success");
        await loadApps();
        renderAppsPage();
    }
}

async function deleteApp(appId) {
    if (!await showConfirmDialog({ title: 'Delete Application', message: 'DANGER: Deleting this app will delete ALL associated users, keys, variables, and logs permanently!', icon: '🚨', okText: 'Delete App', isDanger: true })) return;
    const res = await apiFetch(`/api/v1/admin/apps/${appId}`, { method: "DELETE" });
    if (res && res.success) {
        showToast(res.message, "success");
        await loadApps();
        renderAppsPage();
        loadGlobalStats();
    }
}

// 13. Live Audit & IP Logs
async function loadAuditLogs() {
    const tbody = document.getElementById("logs-table-body");
    if (!tbody) return;

    if (!currentAppId) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 40px;">No application selected.</td></tr>`;
        return;
    }

    const search = document.getElementById("logs-search-input")?.value || "";
    let url = `/api/v1/admin/logs?app_id=${currentAppId}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;

    const data = await apiFetch(url);
    if (!data || !data.logs || data.logs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 40px;">No audit events recorded yet.</td></tr>`;
        return;
    }

    tbody.innerHTML = data.logs.map(log => {
        let badgeClass = "success";
        if (log.status === "WARNING") badgeClass = "warning";
        if (log.status === "DANGER" || log.status === "ERROR") badgeClass = "danger";

        return `
            <tr>
                <td><span style="font-size: 12px; color: var(--text-muted);">${log.timestamp.replace('T', ' ').substring(0, 19)}</span></td>
                <td><span class="badge badge-${badgeClass}"><span class="badge-dot"></span> ${log.action}</span></td>
                <td><strong style="color: #fff;">${log.username || '-'}</strong></td>
                <td><span class="mono" style="color: var(--brand-sky);">${log.ip_address || 'Unknown'}</span></td>
                <td><span class="mono" style="font-size: 11px; color: var(--text-muted);">${log.hwid ? log.hwid.substring(0, 12) + '...' : '-'}</span></td>
                <td><span style="font-size: 12px; color: var(--text-primary);">${log.details || '-'}</span></td>
            </tr>
        `;
    }).join("");
}

async function clearAuditLogs() {
    if (!currentAppId) return;
    if (!await showConfirmDialog({ title: 'Clear Audit Logs', message: 'Are you sure you want to clear all audit logs for this application?', icon: '🗑️', okText: 'Clear Logs', isDanger: true })) return;
    const res = await apiFetch(`/api/v1/admin/logs/clear?app_id=${currentAppId}`, { method: "DELETE" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadAuditLogs();
    }
}

// 14. SDK Code Snippet Generator
function updateSdkSnippets() {
    const currentApp = appsList.find(a => a.id === currentAppId) || { name: "YourAppName", owner_id: devOwnerId, secret: "your_secret_key", version: "1.0" };
    const appName = currentApp.name;
    const appToken = currentApp.secret;
    const version = currentApp.version || "1.0";
    const apiUrl = window.location.origin;

    const pythonCode = `# ================== JOYST CORPORATION PYTHON SDK ==================
from joystauth import JoystAuth

# 1. Initialize with App Name and Master App Token
app = JoystAuth("${appName}", "${appToken}")

# 2. Authenticate (Choose ONE method):
# --- Method A: Login with Username & Password ---
if app.login("testuser", "password123"):
    print(f"✅ {app.response.message}")
    print(f"User: {app.user_data.username} | Rank: {app.user_data.subscription} | Expires: {app.user_data.expiry}")
    
    # Optional: Fetch encrypted server variable (Offsets / Secrets)
    # secret_value = app.var("MY_SECRET_VAR")
else:
    print(f"❌ {app.response.message}")

# --- Method B: Direct License Key Login ---
# if app.license("JOYST-XXXX-XXXX"):
#     print(f"✅ License Valid! Logged in as: {app.user_data.username}")

# --- Method C: Register New User with Key ---
# if app.register("newUser", "newPass", "JOYST-XXXX-XXXX"):
#     print(f"✅ Registered: {app.response.message}")
`;

    const csharpCode = `// ================== JOYST CORPORATION C# .NET SDK ==================
using System;
using System.Threading.Tasks;
using JoystAuth;

class Program
{
    static async Task Main(string[] args)
    {
        // 1. Initialize Joyst Auth (App Name + Master App Token)
        var auth = new api("${appName}", "${appToken}");
        await auth.init();

        // 2. Authenticate (Choose ONE method):
        // --- Method A: Login with Username & Password ---
        if (await auth.login("testuser", "password123"))
        {
            Console.WriteLine("✅ " + auth.response.message);
            Console.WriteLine("User: " + auth.user_data.username + " | Rank: " + auth.user_data.subscription + " | Expires: " + auth.user_data.expiry);

            // Optional: Fetch secure server variable
            // string secretKey = await auth.var("MY_SECRET_VAR");
        }
        else
        {
            Console.WriteLine("❌ " + auth.response.message);
        }

        // --- Method B: Direct License Key Login ---
        // if (await auth.license("JOYST-XXXX-XXXX")) {
        //     Console.WriteLine("✅ Logged in via Key! Rank: " + auth.user_data.subscription);
        // }

        // --- Method C: Register New Account ---
        // if (await auth.register("newUser", "newPass", "JOYST-XXXX-XXXX")) {
        //     Console.WriteLine("✅ Registered successfully!");
        // }
    }
}`;

    const cppCode = `// ================== JOYST CORPORATION C++ SDK ==================
#include "JoystAuth.hpp"
#include <iostream>

int main() {
    // 1. Initialize Header-Only SDK (App Name + Master App Token)
    JoystAuth::api auth("${appName}", "${appToken}");

    if (!auth.init()) {
        std::cout << "Init failed: " << auth.response.message << "\\n";
        return 1;
    }

    // 2. Authenticate (Choose ONE method):
    // --- Method A: Username & Password Login ---
    if (auth.login("testuser", "password123")) {
        std::cout << "✅ " << auth.response.message << "\\n";
        std::cout << "User: " << auth.user_data.username << " | Rank: " << auth.user_data.subscription << "\\n";

        // Optional: Fetch remote secret variable
        // std::string secret = auth.var("MY_SECRET_VAR");
    } else {
        std::cout << "❌ " << auth.response.message << "\\n";
    }

    // --- Method B: Direct License Key Login ---
    // if (auth.license("JOYST-XXXX-XXXX")) {
    //     std::cout << "✅ Valid Key! Rank: " << auth.user_data.subscription << "\\n";
    // }

    // --- Method C: Register New User ---
    // if (auth.register_user("newUser", "newPass", "JOYST-XXXX-XXXX")) {
    //     std::cout << "✅ Account created successfully!\\n";
    // }

    return 0;
}`;

    const javaCode = `// ================== JOYST CORPORATION JAVA SDK ==================
import com.joyst.api;

public class Main {
    public static void main(String[] args) {
        api auth = new api("${appName}", "${appToken}");
        auth.init();

        // 1. Login with Username & Password
        if (auth.login("testuser", "password123")) {
            System.out.println("✅ " + auth.response.message);
            System.out.println("User: " + auth.userData.username + " | Rank: " + auth.userData.subscription);
        } else {
            System.out.println("❌ " + auth.response.message);
        }

        // Direct Key Login:
        // if (auth.license("JOYST-XXXX-XXXX")) { ... }
    }
}`;

    const rustCode = `// ================== JOYST CORPORATION RUST SDK ==================
use joyst_auth::api;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut auth = api::new("${appName}", "${appToken}", "1.0", "${apiUrl}");
    auth.init().await?;

    if auth.login("testuser", "password123").await? {
        println!("✅ {}", auth.response.message);
        println!("User: {} | Rank: {}", auth.user_data.username, auth.user_data.subscription);
    } else {
        println!("❌ {}", auth.response.message);
    }
    Ok(())
}`;

    const nodejsCode = `// ================== JOYST CORPORATION NODE.JS SDK ==================
const JoystAuth = require('./joystauth');

async function main() {
    const auth = new JoystAuth("${appName}", "${appToken}");

    const ok = await auth.init();
    if (!ok) {
        console.error("Init failed:", auth.response.message);
        return;
    }

    // Login with Username & Password
    const loggedIn = await auth.login("testuser", "password123");
    if (loggedIn) {
        console.log("✅ " + auth.response.message);
        console.log("User: " + auth.userData.username + " | Rank: " + auth.userData.subscription);
    } else {
        console.log("❌ " + auth.response.message);
    }

    // Direct Key Login:
    // const keyOk = await auth.license("JOYST-XXXX-XXXX");
}

main();`;

    const codeBlocks = {
        cpp: cppCode,
        python: pythonCode,
        csharp: csharpCode,
        nodejs: nodejsCode,
        java: javaCode,
        rust: rustCode
    };

    window.currentSnippets = codeBlocks;
    const activeTab = document.querySelector(".code-tab-btn.active")?.getAttribute("data-lang") || "cpp";
    setSnippetLang(activeTab);
}

const sdkLangMeta = {
    cpp: {
        icon: "⚡",
        title: "C++ Windows Native SDK",
        badge: "Header-Only (Release)",
        desc: "File: <code class='mono' style='color:#38bdf8;'>JoystAuth.hpp</code> (Drop directly into Visual Studio project)",
        downloadUrl: "/static/sdks/cpp/JoystAuth.hpp",
        downloadName: "JoystAuth.hpp"
    },
    python: {
        icon: "🐍",
        title: "Python 3 Standalone SDK",
        badge: "1-File Script",
        desc: "File: <code class='mono' style='color:#38bdf8;'>joystauth.py</code> (Place in Python project folder)",
        downloadUrl: "/static/sdks/python/joystauth.py",
        downloadName: "joystauth.py"
    },
    csharp: {
        icon: "🔷",
        title: "C# .NET / Unity / WPF SDK",
        badge: ".NET 8 / C#",
        desc: "File: <code class='mono' style='color:#38bdf8;'>JoystAuth.cs</code> (Add to Solution Explorer)",
        downloadUrl: "/static/sdks/csharp/JoystAuth.cs",
        downloadName: "JoystAuth.cs"
    },
    nodejs: {
        icon: "🟢",
        title: "Node.js / Electron / Web SDK",
        badge: "Zero-NPM Deps",
        desc: "File: <code class='mono' style='color:#38bdf8;'>joystauth.js</code> (Pure vanilla Node.js crypto)",
        downloadUrl: "/static/sdks/nodejs/joystauth.js",
        downloadName: "joystauth.js"
    },
    java: {
        icon: "☕",
        title: "Java Standalone SDK",
        badge: "Java 8+",
        desc: "File: <code class='mono' style='color:#38bdf8;'>JoystAuth.java</code> (Place in src folder)",
        downloadUrl: "/static/sdks/java/JoystAuth.java",
        downloadName: "JoystAuth.java"
    },
    rust: {
        icon: "🦀",
        title: "Rust Async SDK",
        badge: "Tokio Async",
        desc: "File: <code class='mono' style='color:#38bdf8;'>src/main.rs</code> (Include in Cargo workspace)",
        downloadUrl: "/static/sdks/rust/src/main.rs",
        downloadName: "main.rs"
    }
};

function setSnippetLang(lang) {
    document.querySelectorAll(".code-tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-lang") === lang);
    });

    const block = document.getElementById("sdk-code-display");
    if (block && window.currentSnippets) {
        block.textContent = window.currentSnippets[lang] || "";
    }

    const meta = sdkLangMeta[lang];
    if (meta) {
        const iconEl = document.getElementById("sdk-lang-icon");
        const titleEl = document.getElementById("sdk-lang-title");
        const badgeEl = document.getElementById("sdk-lang-badge");
        const descEl = document.getElementById("sdk-lang-desc");
        const btnEl = document.getElementById("sdk-dynamic-download-btn");

        if (iconEl) iconEl.textContent = meta.icon;
        if (titleEl) titleEl.textContent = meta.title;
        if (badgeEl) badgeEl.textContent = meta.badge;
        if (descEl) descEl.innerHTML = meta.desc;
        if (btnEl) {
            btnEl.href = meta.downloadUrl;
            btnEl.download = meta.downloadName;
            btnEl.textContent = `⬇️ Download ${meta.downloadName}`;
        }
    }
}

function copyCurrentSdkSnippet() {
    const block = document.getElementById("sdk-code-display");
    if (block && block.textContent) {
        navigator.clipboard.writeText(block.textContent);
        showToast("📋 SDK implementation code copied to clipboard!", "success");
    }
}

// 15. Change Password
function setupChangePassword() {
    const form = document.getElementById("form-change-password");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const curPass = document.getElementById("current-password").value;
        const newPass = document.getElementById("new-password").value;

        const res = await apiFetch("/api/v1/auth/change-password", {
            method: "POST",
            body: JSON.stringify({ current_password: curPass, new_password: newPass })
        });

        if (res && res.success) {
            showToast(res.message, "success");
            form.reset();
        } else {
            showToast(res?.detail || "Failed to change password", "error");
        }
    });
}

function setupModals() {
    document.querySelectorAll(".modal-close, [data-close-modal]").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("active"));
        });
    });
}

function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add("active");
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove("active");
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast("Copied to clipboard!", "info");
    });
}

function toggleSecretVisibility(inputId) {
    const input = document.getElementById(inputId);
    if (input) {
        input.type = input.type === "password" ? "text" : "password";
    }
}

// Window Global Bindings for HTML Inline Handlers
window.switchTab = switchTab;
window.loadActiveTab = loadActiveTab;
window.openModal = openModal;
window.closeModal = closeModal;
window.quickToggleMaintenance = quickToggleMaintenance;
window.saveAllAppSettings = saveAllAppSettings;
window.createAppSubmit = createAppSubmit;
window.copyToClipboard = copyToClipboard;
window.copyCurrentSdkSnippet = copyCurrentSdkSnippet;
window.copyAppToken = copyAppToken;
window.redeemPlanKeySubmit = typeof redeemPlanKeySubmit !== "undefined" ? redeemPlanKeySubmit : () => {};
window.loadGlobalStats = loadGlobalStats;
window.loadLicenses = typeof loadLicenses !== "undefined" ? loadLicenses : () => {};
window.loadUsers = typeof loadUsers !== "undefined" ? loadUsers : () => {};
window.loadTiers = typeof loadTiers !== "undefined" ? loadTiers : () => {};
window.loadBlacklists = typeof loadBlacklists !== "undefined" ? loadBlacklists : () => {};
window.loadResellers = typeof loadResellers !== "undefined" ? loadResellers : () => {};
window.loadNotifications = typeof loadNotifications !== "undefined" ? loadNotifications : () => {};
window.loadAuditLogs = typeof loadAuditLogs !== "undefined" ? loadAuditLogs : () => {};
window.clearAuditLogs = typeof clearAuditLogs !== "undefined" ? clearAuditLogs : () => {};
window.renderAppsPage = renderAppsPage;
window.renderActiveAppSettings = renderActiveAppSettings;
window.switchSettingsSubTab = switchSettingsSubTab;
window.switchAppFromSettingsDropdown = switchAppFromSettingsDropdown;
window.goToAppSettings = goToAppSettings;
window.goToAppKeys = goToAppKeys;
window.selectAppFromCard = typeof selectAppFromCard !== "undefined" ? selectAppFromCard : () => {};
window.setSnippetLang = typeof setSnippetLang !== "undefined" ? setSnippetLang : () => {};
window.showToast = showToast;
window.toggleSecretVisibility = toggleSecretVisibility;
window.escapeHtml = escapeHtml;
window.showConfirmDialog = showConfirmDialog;
window.regenerateSecret = typeof regenerateSecret !== "undefined" ? regenerateSecret : () => {};

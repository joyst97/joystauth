// Joyst Corporation Enterprise Developer Dashboard Controller
let currentAppId = null;
let appsList = [];
let devOwnerId = localStorage.getItem("dev_owner_id") || "Loading...";
let devUsername = localStorage.getItem("dev_username") || "Developer";
let authToken = localStorage.getItem("auth_admin_token");

if (!authToken && window.location.pathname.includes("/dashboard")) {
    window.location.href = "/login";
}

document.addEventListener("DOMContentLoaded", () => {
    if (authToken && window.location.pathname.includes("/dashboard")) {
        initDashboard();
    }
});

function getHeaders() {
    return {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
    };
}

async function apiFetch(url, options = {}) {
    options.headers = { ...getHeaders(), ...(options.headers || {}) };
    try {
        const res = await fetch(url, options);
        if (res.status === 401) {
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
    await loadUserProfile();
    await loadApps();
    await loadGlobalStats();
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

        if (nameEl) nameEl.textContent = devUsername;
        if (ownerEl) ownerEl.innerHTML = `<span class="badge-dot" style="background: #10b981;"></span> Server Online`;
        if (avatarEl) avatarEl.textContent = devUsername.charAt(0).toUpperCase();
        const activePlan = data.plan || 'Free';
        window.currentUserPlan = activePlan;
        if (planBadge) planBadge.textContent = `${activePlan} Plan`;

        // Highlight active plan card
        document.querySelectorAll(".plan-card").forEach(c => c.classList.remove("active-plan"));
        const isPaid = activePlan === "Paid" || activePlan === "Developer" || activePlan === "Enterprise";
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
            localStorage.removeItem("auth_admin_token");
            localStorage.removeItem("dev_owner_id");
            localStorage.removeItem("dev_username");
            window.location.href = "/login";
        });
    }

    const appSelect = document.getElementById("header-app-select");
    if (appSelect) {
        appSelect.addEventListener("change", (e) => {
            currentAppId = parseInt(e.target.value);
            localStorage.setItem("selected_app_id", currentAppId);
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
    const isPaid = (window.currentUserPlan === "Paid" || window.currentUserPlan === "Developer" || window.currentUserPlan === "Enterprise");

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
    } else if (tabId === "apps") {
        renderAppsPage();
    } else if (tabId === "logs") {
        loadAuditLogs();
    } else if (tabId === "sdk") {
        updateSdkSnippets();
    }
}

// 1. Applications Loading
async function loadApps() {
    const data = await apiFetch("/api/v1/admin/apps");
    if (!data || !data.success) return;

    appsList = data.apps || [];
    const select = document.getElementById("overview-app-select") || document.getElementById("header-app-select");
    if (!select) return;

    select.innerHTML = "";
    if (appsList.length === 0) {
        select.innerHTML = `<option value="">No Apps Created</option>`;
        currentAppId = null;
        updateBannerCredentials();
        return;
    }

    appsList.forEach(app => {
        const opt = document.createElement("option");
        opt.value = app.id;
        opt.textContent = `${app.name} (v${app.version})`;
        select.appendChild(opt);
    });

    const savedAppId = parseInt(localStorage.getItem("selected_app_id"));
    if (savedAppId && appsList.some(a => a.id === savedAppId)) {
        currentAppId = savedAppId;
    } else {
        currentAppId = appsList[0].id;
    }
    select.value = currentAppId;

    select.onchange = (e) => {
        currentAppId = parseInt(e.target.value);
        localStorage.setItem("selected_app_id", currentAppId);
        updateBannerCredentials();
        loadGlobalStats();
        if (currentTab === 'licenses') loadLicenses();
        if (currentTab === 'users') loadUsers();
        if (currentTab === 'blacklists') loadBlacklists();
        if (currentTab === 'tiers') loadTiers();
        if (currentTab === 'sdk') updateSdkSnippets();
    };

    updateBannerCredentials();
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

    const webhookInput = document.getElementById("discord-webhook-url-input");
    if (webhookInput && app.webhook_url) {
        webhookInput.value = app.webhook_url;
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
    if (!confirm(`Are you sure you want to delete all ${type} license keys?`)) return;
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
    if (!confirm("Are you sure you want to permanently delete this license key?")) return;
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
    if (!confirm("Are you sure you want to RESET HWID lock for ALL users in this application?")) return;

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
    if (!confirm("Are you sure you want to permanently DELETE ALL EXPIRED user accounts?")) return;

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
    if (!confirm("⚠️ DANGER: Are you sure you want to permanently delete ALL users in this application? This action cannot be undone!")) return;

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
    if (!confirm(`Are you sure you want to delete ${selected.length} selected user(s)?`)) return;

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
    const reason = prompt(`Enter reason for banning ${selected.length} user(s):`, "Violation of terms");
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
    if (!confirm(`Reset HWID for ${selected.length} selected user(s)?`)) return;

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
        closeModal("modal-create-user-manual");
        loadUsers();
        loadGlobalStats();
    } else {
        showToast(res?.detail || "Failed to create user", "error");
    }
}

async function resetUserHwid(userId, username) {
    if (!confirm(`Reset HWID lock for '${username}'? Account will lock to the next machine.`)) return;
    const res = await apiFetch(`/api/v1/admin/users/${userId}/reset-hwid`, { method: "POST" });
    if (res && res.success) {
        showToast(res.message, "success");
        loadUsers();
    }
}

async function toggleUserBan(userId, username, isCurrentlyBanned) {
    if (!isCurrentlyBanned) {
        const reason = prompt(`Enter reason for banning '${username}':`, "Violation of terms");
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
    if (!confirm("Are you sure you want to permanently delete this user account?")) return;
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
            <td><span class="badge badge-success"><span class="badge-dot"></span> Protected</span></td>
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

// 12. Applications Management Page
function renderAppsPage() {
    const container = document.getElementById("apps-grid-container");
    if (!container) return;

    if (appsList.length === 0) {
        container.innerHTML = `
            <div style="color: var(--text-muted); text-align: center; grid-column: 1/-1; padding: 60px; background: var(--bg-card); border-radius: 16px; border: 1px dashed var(--border-subtle);">
                <div style="font-size: 36px; margin-bottom: 12px;">📦</div>
                <h3 style="color: #fff; font-size: 18px; margin-bottom: 8px;">No Applications Yet</h3>
                <p style="font-size: 13px; margin-bottom: 20px;">Create your first software application to generate license keys and start authenticating clients.</p>
                <button class="btn btn-primary" onclick="openModal('modal-create-app')">➕ Create Your First App</button>
            </div>
        `;
        return;
    }

    container.innerHTML = appsList.map(app => `
        <div class="stat-card spotlight-card" style="padding: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
                <div>
                    <h3 style="font-size: 18px; font-weight: 800; color: #fff;">${app.name}</h3>
                    <span class="badge badge-cyan" style="margin-top: 4px;">Active: v${app.version}</span>
                </div>
                <span class="badge badge-${app.status === 'enabled' ? 'success' : 'danger'}">
                    <span class="badge-dot"></span> ${app.status.toUpperCase()}
                </span>
            </div>

            <div class="form-group" style="margin-bottom: 10px;">
                <label>⚡ Unified Master Token (1-Token SDK Key)</label>
                <div style="display: flex; gap: 8px;">
                    <input type="password" value="${app.secret}" id="token-${app.id}" class="form-control mono" readonly style="font-size: 12px; color: #38bdf8;">
                    <button class="btn btn-secondary btn-sm" onclick="toggleSecretVisibility('token-${app.id}')">👁️</button>
                    <button class="btn btn-secondary btn-sm" onclick="copyToClipboard('${app.secret}')">📋</button>
                </div>
            </div>

            <div class="form-group" style="margin-bottom: 12px;">
                <label>🏷️ Application Version (Strict Update Enforcement)</label>
                <div style="display: flex; gap: 8px;">
                    <input type="text" value="${app.version || '1.0'}" id="ver-input-${app.id}" class="form-control mono" style="font-size: 12px; font-weight: bold; color: #fff;" placeholder="e.g. 1.0, 1.1">
                    <button class="btn btn-primary btn-sm" onclick="updateAppVersionSubmit(${app.id})">💾 Save Version</button>
                </div>
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Changing version will immediately force old .exe clients to update.</div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 16px 0; font-size: 12px; color: var(--text-muted);">
                <div>Total Users: <strong style="color: #fff;">${app.stats?.total_users || 0}</strong></div>
                <div>Unused Keys: <strong style="color: #10b981;">${app.stats?.unused_licenses || 0}</strong></div>
                <div>HWID Lock: <strong style="color: ${app.hwid_lock_enabled ? '#10b981' : '#ef4444'};">${app.hwid_lock_enabled ? 'ENABLED' : 'DISABLED'}</strong></div>
                <div>Timeout: <strong style="color: #fff;">${app.session_timeout_minutes} min</strong></div>
            </div>

            <div style="display: flex; gap: 8px; margin-top: 18px; border-top: 1px solid var(--border-subtle); padding-top: 16px;">
                <button class="btn btn-secondary btn-sm" style="flex: 1;" onclick="regenerateSecret(${app.id})">🔄 New Secret</button>
                <button class="btn btn-danger btn-sm" onclick="deleteApp(${app.id})">🗑️ Delete</button>
            </div>
        </div>
    `).join("");
}

async function updateAppVersionSubmit(appId) {
    const verInput = document.getElementById(`ver-input-${appId}`);
    const newVer = verInput ? verInput.value.trim() : "1.0";
    if (!newVer) {
        showToast("Version cannot be empty", "warning");
        return;
    }
    const res = await apiFetch(`/api/v1/admin/apps/${appId}`, {
        method: "PUT",
        body: JSON.stringify({ version: newVer })
    });
    if (res && res.success) {
        showToast(`✅ App version updated to v${newVer}! Old .exe clients are now blocked.`, "success");
        await loadApps();
        renderAppsPage();
    } else {
        showToast(res?.detail || "Failed to update version", "error");
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
        closeModal("modal-create-app");
        await loadApps();
        renderAppsPage();
        loadGlobalStats();
    } else {
        showToast(res?.detail || "Failed to create app", "error");
    }
}

async function regenerateSecret(appId) {
    if (!confirm("Regenerating the App Secret will disconnect all existing SDK clients until updated. Proceed?")) return;
    const res = await apiFetch(`/api/v1/admin/apps/${appId}/regenerate-secret`, { method: "POST" });
    if (res && res.success) {
        showToast(res.message, "success");
        await loadApps();
        renderAppsPage();
    }
}

async function deleteApp(appId) {
    if (!confirm("DANGER: Deleting this app will delete ALL associated users, keys, variables, and logs permanently!")) return;
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
    if (!confirm("Are you sure you want to clear all audit logs for this application?")) return;
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
    const ownerId = currentApp.owner_id || devOwnerId;
    const appSecret = currentApp.secret;
    const version = currentApp.version || "1.0";
    const apiUrl = window.location.origin;

    const pythonCode = `# ================== JOYST CORPORATION PYTHON SDK ==================
from auth_client import api

# 1. Initialize Joyst Auth (Exact KeyAuth parameters)
auth = api(
    name="${appName}",
    ownerid="${ownerId}",
    secret="${appSecret}",
    version="${version}",
    url="${apiUrl}"
)

# 2. Login with Username & Password (Strict HWID Lock)
if auth.login("testuser", "password123"):
    print(f"Login Success! Welcome {auth.user_data.username}")
    print(f"Subscription: {auth.user_data.subscription}")
    print(f"HWID: {auth.user_data.hwid}")
    
    # 3. Fetch Remote Encrypted Cloud Variable
    # cheat_offset = auth.var("GAME_OFFSET")
else:
    print(f"Login Failed: {auth.response.message}")
`;

    const csharpCode = `// ================== JOYST CORPORATION C# .NET SDK ==================
using System;
using System.Threading.Tasks;
using JoystAuth;

class Program
{
    static async Task Main(string[] args)
    {
        // Initialize with Unified Master Token & Version
        var auth = new api("${appSecret}", "${version}", "${apiUrl}");

        await auth.init();

        if (await auth.login("testuser", "password123"))
        {
            Console.WriteLine($"✅ Login Success! Welcome {auth.user_data.username}!");
            Console.WriteLine($"💎 Subscription: {auth.user_data.subscription}");
            Console.WriteLine($"⏳ Expiry: {auth.user_data.expiry}");
            
            // Start automatic 30s session watchdog (Zero CPU)
            auth.start_heartbeat(30);
        }
        else
        {
            Console.WriteLine($"❌ Error: {auth.response.message}");
        }
    }
}`;

    const cppCode = `// ================== JOYST CORPORATION C++ SDK ==================
#include "AuthClient.hpp"
#include <iostream>

int main() {
    // Header-Only (Zero External .lib dependencies!)
    JoystAuth::api auth("${appSecret}", "${version}", "${apiUrl}");

    auth.init();

    if (auth.login("testuser", "password123")) {
        std::cout << "✅ Login Success! Welcome " << auth.user_data.username << "\\n";
        std::cout << "💎 Subscription: " << auth.user_data.subscription << "\\n";
    } else {
        std::cout << "❌ Login Failed: " << auth.response.message << "\\n";
    }
    return 0;
}`;

    const javaCode = `// ================== JOYST CORPORATION JAVA SDK ==================
import com.joyst.api;

public class Main {
    public static void main(String[] args) {
        api auth = new api("${appSecret}", "${version}", "${apiUrl}");

        auth.init();

        if (auth.login("testuser", "password123")) {
            System.out.println("✅ Login Success! Welcome " + auth.userData.username);
        } else {
            System.out.println("❌ Login Failed: " + auth.response.message);
        }
    }
}`;

    const rustCode = `// ================== JOYST CORPORATION RUST SDK ==================
use joyst_auth::api;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut auth = api::new("${appSecret}", "${version}", "${apiUrl}");

    auth.init().await?;

    if auth.login("testuser", "password123").await? {
        println!("✅ Login Success! Welcome {:?}", auth.user_data.username);
    } else {
        println!("❌ Login Failed: {}", auth.response.message);
    }
    Ok(())
}`;

    const nodejsCode = `// ================== JOYST CORPORATION NODE.JS SDK ==================
const JoystAuth = require('./joyst_auth');

async function main() {
    const auth = new JoystAuth("${appSecret}", "${version}", "${apiUrl}");

    // 1. Initialize
    const ok = await auth.init();
    if (!ok) {
        console.error("Init failed:", auth.response.message);
        return;
    }

    // 2. Login User
    const loggedIn = await auth.login("testuser", "password123");
    if (loggedIn) {
        console.log("✅ Login Success! Welcome " + auth.userData.username);
        console.log("💎 Subscription: " + auth.userData.subscription);
    } else {
        console.log("❌ Login Failed: " + auth.response.message);
    }
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
        desc: "File: <code class='mono' style='color:#38bdf8;'>AuthClient.hpp</code> (Drop directly into Visual Studio project)",
        downloadUrl: "/static/sdks/cpp/AuthClient.hpp",
        downloadName: "AuthClient.hpp"
    },
    python: {
        icon: "🐍",
        title: "Python 3 Standalone SDK",
        badge: "1-File Script",
        desc: "File: <code class='mono' style='color:#38bdf8;'>auth_client.py</code> (Place in Python project folder)",
        downloadUrl: "/static/sdks/python/auth_client.py",
        downloadName: "auth_client.py"
    },
    csharp: {
        icon: "🔷",
        title: "C# .NET / Unity / WPF SDK",
        badge: ".NET 8 / C#",
        desc: "File: <code class='mono' style='color:#38bdf8;'>AuthClient.cs</code> (Add to Solution Explorer)",
        downloadUrl: "/static/sdks/csharp/AuthClient.cs",
        downloadName: "AuthClient.cs"
    },
    nodejs: {
        icon: "🟢",
        title: "Node.js / Electron / Web SDK",
        badge: "Zero-NPM Deps",
        desc: "File: <code class='mono' style='color:#38bdf8;'>joyst_auth.js</code> (Pure vanilla Node.js crypto)",
        downloadUrl: "/static/sdks/nodejs/joyst_auth.js",
        downloadName: "joyst_auth.js"
    },
    java: {
        icon: "☕",
        title: "Java Standalone SDK",
        badge: "Java 8+",
        desc: "File: <code class='mono' style='color:#38bdf8;'>AuthClient.java</code> (Place in src folder)",
        downloadUrl: "/static/sdks/java/AuthClient.java",
        downloadName: "AuthClient.java"
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

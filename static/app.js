const state = {
    hookId: null,
    ws: null,
    requests: [],
    selectedRequestId: null,
    activeTab: "headers",
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function init() {
    const params = new URLSearchParams(window.location.search);
    const hookId = params.get("hook");

    if (hookId) {
        loadHook(hookId);
    }

    $("#newHookBtn").addEventListener("click", createHook);
    $("#emptyNewHookBtn").addEventListener("click", createHook);
}

async function createHook() {
    try {
        const resp = await fetch("/hook", { method: "POST" });
        const data = await resp.json();
        state.hookId = data.id;
        window.history.replaceState({}, "", `?hook=${data.id}`);
        loadHook(data.id);
    } catch (err) {
        console.error("Failed to create hook:", err);
    }
}

function loadHook(hookId) {
    state.hookId = hookId;
    state.requests = [];
    state.selectedRequestId = null;

    const baseUrl = window.location.origin;
    $("#hookUrl").textContent = `${baseUrl}/hook/${hookId}`;
    $("#emptyState").classList.add("hidden");
    $("#hookView").classList.remove("hidden");

    connectWs(hookId);
    fetchRequests(hookId);
}

let reconnectAttempts = 0;
const MAX_RECONNECT_DELAY = 30000;

function connectWs(hookId) {
    if (state.ws) {
        state.ws.close();
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/hook/${hookId}/ws`;

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        reconnectAttempts = 0;
        $("#wsStatus").textContent = "Live";
        $("#wsIndicator").style.background = "var(--accent)";
    };

    state.ws.onclose = () => {
        $("#wsStatus").textContent = "Disconnected";
        $("#wsIndicator").style.background = "var(--method-delete)";
        const delay = Math.min(3000 * 2 ** reconnectAttempts, MAX_RECONNECT_DELAY);
        reconnectAttempts++;
        setTimeout(() => connectWs(hookId), delay);
    };

    state.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "new_request") {
            state.requests.unshift(msg.data);
            renderRequestList();
            updateRequestCount();
        } else if (msg.type === "hook_deleted") {
            state.hookId = null;
            state.requests = [];
            $("#emptyState").classList.remove("hidden");
            $("#hookView").classList.add("hidden");
        }
    };
}

async function fetchRequests(hookId) {
    try {
        const resp = await fetch(`/hook/${hookId}`);
        const data = await resp.json();
        state.requests = data.requests || [];
        renderRequestList();
        updateRequestCount();
    } catch (err) {
        console.error("Failed to fetch requests:", err);
    }
}

function renderRequestList() {
    const container = $("#requestList");

    if (state.requests.length === 0) {
        container.innerHTML = `<div class="flex items-center justify-center h-full" style="color: var(--text-secondary)"><span class="text-sm">Waiting for requests...</span></div>`;
        return;
    }

    container.innerHTML = state.requests.map((req) => {
        const methodClass = `method-${req.method}` in getMethodClasses() ? `method-${req.method}` : "method-other";
        const active = req.id === state.selectedRequestId ? "active" : "";
        const time = new Date(req.received_at).toLocaleTimeString();
        return `
            <div class="request-row ${active} px-4 py-3 slide-in" style="border-bottom: 1px solid var(--border)" onclick="selectRequest(${req.id})">
                <div class="flex items-center gap-3">
                    <span class="method-badge ${methodClass}">${req.method}</span>
                    <span class="font-mono text-xs truncate flex-1" style="color: var(--text-primary)">${escapeHtml(req.path)}</span>
                    <span class="text-xs font-mono" style="color: var(--text-secondary)">${time}</span>
                </div>
                ${req.content_type ? `<div class="mt-1 text-xs font-mono truncate" style="color: var(--text-secondary)">${escapeHtml(req.content_type)}</div>` : ""}
            </div>
        `;
    }).join("");
}

function getMethodClasses() {
    return { "method-GET": true, "method-POST": true, "method-PUT": true, "method-PATCH": true, "method-DELETE": true };
}

function selectRequest(requestId) {
    state.selectedRequestId = requestId;
    const req = state.requests.find((r) => r.id === requestId);
    if (!req) return;

    renderRequestList();
    renderDetail(req);
}

function renderDetail(req) {
    const container = $("#requestDetail");
    const tab = state.activeTab;

    let content = "";

    if (tab === "headers") {
        const headers = req.headers || {};
        const rows = Object.entries(headers).map(([k, v]) => `
            <div class="flex gap-4 py-1.5" style="border-bottom: 1px solid var(--border)">
                <span class="font-mono text-xs font-semibold" style="color: var(--accent); min-width: 200px">${escapeHtml(k)}</span>
                <span class="font-mono text-xs" style="color: var(--text-primary)">${escapeHtml(v)}</span>
            </div>
        `).join("");
        content = `
            <div class="mb-4 flex items-center gap-3">
                <span class="method-badge method-${req.method}">${req.method}</span>
                <span class="font-mono text-sm" style="color: var(--text-primary)">${escapeHtml(req.path)}</span>
            </div>
            <div class="mb-3 text-xs font-mono" style="color: var(--text-secondary)">
                <span>From: ${escapeHtml(req.source_ip || "unknown")}</span>
            </div>
            ${rows || '<span style="color: var(--text-secondary)">No headers</span>'}
        `;
    } else if (tab === "body") {
        let body = req.body || "";
        let isJson = false;
        try {
            const parsed = JSON.parse(body);
            body = JSON.stringify(parsed, null, 2);
            isJson = true;
        } catch {
            // not JSON, keep as-is
        }
        const display = isJson ? syntaxHighlight(body) : escapeHtml(body);
        content = `
            <pre class="font-mono p-3 rounded-lg" style="background: var(--bg-primary); color: var(--text-primary); max-height: 100%; overflow: auto">${display || '<span style="color: var(--text-secondary)">No body</span>'}</pre>
        `;
    } else if (tab === "query") {
        const qs = req.query_string || "";
        if (!qs) {
            content = `<span style="color: var(--text-secondary)" class="text-sm">No query parameters</span>`;
        } else {
            const params = new URLSearchParams(qs);
            const rows = Array.from(params.entries()).map(([k, v]) => `
                <div class="flex gap-4 py-1.5" style="border-bottom: 1px solid var(--border)">
                    <span class="font-mono text-xs font-semibold" style="color: var(--accent); min-width: 200px">${escapeHtml(k)}</span>
                    <span class="font-mono text-xs" style="color: var(--text-primary)">${escapeHtml(v)}</span>
                </div>
            `).join("");
            content = rows;
        }
    }

    container.innerHTML = content;
}

function switchTab(tab) {
    state.activeTab = tab;
    $$(".detail-tab").forEach((el) => {
        if (el.dataset.tab === tab) {
            el.style.background = "var(--accent-dim)";
            el.style.color = "var(--accent)";
        } else {
            el.style.background = "var(--bg-elevated)";
            el.style.color = "var(--text-secondary)";
        }
    });
    const req = state.requests.find((r) => r.id === state.selectedRequestId);
    if (req) renderDetail(req);
}

function updateRequestCount() {
    $("#requestCount").textContent = state.requests.length;
}

async function deleteHook() {
    if (!state.hookId) return;
    if (!confirm("Delete this hook and all its requests?")) return;

    try {
        await fetch(`/hook/${state.hookId}`, { method: "DELETE" });
        state.hookId = null;
        state.requests = [];
        if (state.ws) state.ws.close();
        window.history.replaceState({}, "", window.location.pathname);
        $("#emptyState").classList.remove("hidden");
        $("#hookView").classList.add("hidden");
    } catch (err) {
        console.error("Failed to delete hook:", err);
    }
}

function copyHookUrl() {
    const url = $("#hookUrl").textContent;
    navigator.clipboard.writeText(url);
    const btn = $(".copy-btn");
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = "Copy"; }, 1500);
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function syntaxHighlight(json) {
    if (typeof json !== "string") json = JSON.stringify(json, null, 2);
    json = json.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return json.replace(
        /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
        function (match) {
            let cls = "json-number";
            if (/^"/.test(match)) {
                if (/:$/.test(match)) cls = "json-key";
                else cls = "json-string";
            } else if (/true|false/.test(match)) {
                cls = "json-boolean";
            } else if (/null/.test(match)) {
                cls = "json-null";
            }
            return `<span class="${cls}">${match}</span>`;
        }
    );
}

function copyAsCurl() {
    const req = state.requests.find((r) => r.id === state.selectedRequestId);
    if (!req) return;
    const url = `${window.location.origin}/hook/${req.hook_id}${req.path}${req.query_string ? "?" + req.query_string : ""}`;
    let cmd = `curl -X ${req.method}`;
    for (const [k, v] of Object.entries(req.headers || {})) {
        cmd += ` -H "${k}: ${v}"`;
    }
    if (req.body) {
        cmd += ` -d '${req.body.replace(/'/g, "'\\''")}'`;
    }
    cmd += ` "${url}"`;
    navigator.clipboard.writeText(cmd);
    const btn = event.target;
    const original = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = original; }, 1500);
}

async function replayRequest() {
    const req = state.requests.find((r) => r.id === state.selectedRequestId);
    if (!req) return;
    const target = prompt("Target URL to replay to:", "http://localhost:3000/webhook");
    if (!target) return;
    try {
        const resp = await fetch(`/hook/${state.hookId}/${req.id}/replay`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target_url: target }),
        });
        const data = await resp.json();
        if (resp.ok) {
            alert(`Replayed! Target responded with ${data.status_code}`);
        } else {
            alert(`Replay failed: ${data.error || resp.statusText}`);
        }
    } catch (err) {
        alert(`Replay error: ${err.message}`);
    }
}

async function exportHook() {
    if (!state.hookId) return;
    try {
        const resp = await fetch(`/hook/${state.hookId}/export`);
        if (!resp.ok) throw new Error(resp.statusText);
        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `hookbox-${state.hookId}-export.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    } catch (err) {
        console.error("Export failed:", err);
    }
}

async function deleteSelectedRequest() {
    const req = state.requests.find((r) => r.id === state.selectedRequestId);
    if (!req) return;
    if (!confirm("Delete this request?")) return;
    try {
        await fetch(`/hook/${state.hookId}/${req.id}`, { method: "DELETE" });
        state.requests = state.requests.filter((r) => r.id !== req.id);
        state.selectedRequestId = null;
        renderRequestList();
        $("#requestDetail").innerHTML = `<div class="flex items-center justify-center h-full" style="color: var(--text-secondary)"><span class="text-sm">Select a request to inspect</span></div>`;
        updateRequestCount();
    } catch (err) {
        console.error("Failed to delete request:", err);
    }
}

document.addEventListener("DOMContentLoaded", init);

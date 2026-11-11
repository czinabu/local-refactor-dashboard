// Refactor dashboard: file open/drop, model picker, instruction presets, streamed output,
// side-by-side diff, change summary and local history.
(() => {
    "use strict";

    const $ = (id) => document.getElementById(id);
    const els = {
        code: $("codeInput"),
        lang: $("langInput"),
        model: $("modelInput"),
        reloadModels: $("reloadModels"),
        modelStatus: $("modelStatus"),
        presets: $("presetGroup"),
        custom: $("customInstruction"),
        run: $("refactorButton"),
        stop: $("stopButton"),
        status: $("status"),
        stats: $("stats"),
        thinking: $("thinking"),
        thinkingText: $("thinkingText"),
        live: $("liveOutput"),
        diff: $("diffView"),
        codeView: $("codeView"),
        copy: $("copyButton"),
        download: $("downloadButton"),
        tabs: document.querySelectorAll("[role=tab]"),
        openFile: $("openFileButton"),
        fileInput: $("fileInput"),
        fileName: $("fileName"),
        clearFile: $("clearFile"),
        summary: $("summary"),
        summaryText: $("summaryText"),
        historyList: $("historyList"),
        historyHint: $("historyHint"),
        clearHistory: $("clearHistory"),
    };

    // File extension -> language value in the Language picker.
    const EXTENSIONS = {
        py: "python", js: "javascript", mjs: "javascript", cjs: "javascript", jsx: "javascript",
        ts: "typescript", tsx: "typescript", go: "go", rs: "rust", java: "java", kt: "kotlin",
        c: "c", h: "c", cpp: "cpp", cc: "cpp", hpp: "cpp", cs: "csharp", rb: "ruby", php: "php",
        swift: "swift", sh: "bash", bash: "bash", sql: "sql",
    };
    const MAX_FILE_BYTES = 512 * 1024;

    const state = {
        preset: null,
        controller: null,
        original: "",
        language: "",
        finalCode: "",
        summary: "",
        filename: null, // name of the opened file, sent along and kept in history
        historyId: null, // history entry currently shown
    };

    // ---------- models & presets ----------

    async function loadModels() {
        setHint("Loading models…");
        let data;
        try {
            const res = await fetch("/api/models");
            data = await res.json();
        } catch (e) {
            setHint("Could not load models: " + e.message, true);
            return;
        }

        const models = data.models || [];
        const names = models.map((m) => m.name);
        els.model.innerHTML = "";
        for (const m of models) {
            const label = m.parameter_size ? `${m.name} · ${m.parameter_size}` : m.name;
            els.model.add(new Option(label, m.name));
        }
        // Keep the configured default selectable even if Ollama is down or it isn't installed.
        if (data.default && !names.includes(data.default)) {
            const suffix = data.error ? "" : " (not installed)";
            els.model.add(new Option(data.default + suffix, data.default), 0);
            names.unshift(data.default);
        }
        const saved = storageGet("model");
        els.model.value = saved && names.includes(saved) ? saved : data.default || names[0] || "";

        if (data.error) setHint(data.error, true);
        else setHint(`${models.length} model${models.length === 1 ? "" : "s"} installed`);
    }

    async function loadPresets() {
        let data;
        try {
            data = await (await fetch("/api/presets")).json();
        } catch (e) {
            setStatus("Could not load presets: " + e.message, "error");
            return;
        }
        els.presets.innerHTML = "";
        for (const p of data.presets) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "chip";
            btn.textContent = p.label;
            btn.dataset.preset = p.id;
            btn.title = p.instruction || "Write your own instruction";
            btn.addEventListener("click", () => selectPreset(p.id, true));
            els.presets.appendChild(btn);
        }
        const saved = storageGet("preset");
        selectPreset(data.presets.some((p) => p.id === saved) ? saved : data.default, false);
        const savedCustom = storageGet("customInstruction");
        if (savedCustom) els.custom.value = savedCustom;
    }

    function selectPreset(id, focus) {
        state.preset = id;
        for (const b of els.presets.querySelectorAll(".chip")) {
            b.setAttribute("aria-pressed", String(b.dataset.preset === id));
        }
        els.custom.hidden = id !== "custom";
        if (id === "custom" && focus) els.custom.focus();
        storageSet("preset", id);
    }

    // ---------- running a refactor ----------

    async function refactor() {
        if (state.controller) return;
        const code = els.code.value;
        if (!code.trim()) {
            setStatus("Please enter some code to refactor.", "error");
            return;
        }
        const custom = state.preset === "custom";
        if (custom && !els.custom.value.trim()) {
            setStatus("Describe what you want for the Custom goal.", "error");
            els.custom.focus();
            return;
        }

        state.original = code;
        state.language = els.lang.value;
        state.finalCode = "";
        storageSet("model", els.model.value);
        if (custom) storageSet("customInstruction", els.custom.value);

        resetOutput();
        setRunning(true);
        setStatus("Waiting for the model…");

        state.controller = new AbortController();
        try {
            const res = await fetch("/refactor/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    code,
                    language: state.language,
                    model: els.model.value || null,
                    preset: state.preset,
                    instruction: custom ? els.custom.value : null,
                    filename: state.filename,
                }),
                signal: state.controller.signal,
            });
            if (!res.ok || !res.body) throw new Error(await errorMessage(res));
            await readNdjson(res.body, handleEvent);
        } catch (e) {
            if (e.name === "AbortError") setStatus("Stopped.");
            else setStatus("Error: " + e.message, "error");
        } finally {
            setRunning(false);
            state.controller = null;
        }
    }

    async function errorMessage(res) {
        try {
            const data = await res.json();
            const detail = data.detail || data.message;
            if (Array.isArray(detail)) return detail.map((d) => d.msg).join("; ");
            if (detail) return String(detail);
        } catch (_) {
            // not JSON
        }
        return `Server error ${res.status}`;
    }

    async function readNdjson(body, onEvent) {
        const reader = body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            let nl;
            while ((nl = buf.indexOf("\n")) >= 0) {
                const line = buf.slice(0, nl).trim();
                buf = buf.slice(nl + 1);
                if (line) onEvent(JSON.parse(line));
            }
        }
        buf += decoder.decode();
        if (buf.trim()) onEvent(JSON.parse(buf));
    }

    function handleEvent(evt) {
        switch (evt.type) {
            case "start":
                setStatus(`Generating with ${evt.model}…`);
                break;
            case "thinking":
                els.thinking.hidden = false;
                els.thinkingText.textContent += evt.text;
                els.thinkingText.scrollTop = els.thinkingText.scrollHeight;
                setStatus("Model is reasoning…");
                break;
            case "token": {
                const atBottom = els.live.scrollHeight - els.live.scrollTop - els.live.clientHeight < 40;
                // Skip the blank lines models often emit after their reasoning.
                els.live.textContent += els.live.textContent ? evt.text : evt.text.trimStart();
                if (atBottom) els.live.scrollTop = els.live.scrollHeight;
                if (els.status.textContent === "Model is reasoning…") setStatus("Writing code…");
                break;
            }
            case "done":
                state.finalCode = evt.code;
                state.summary = evt.summary || "";
                state.historyId = evt.history_id ?? null;
                showStats(evt.stats);
                setStatus("Done.", "ok");
                showResult();
                if (state.historyId !== null) loadHistory();
                break;
            case "error":
                setStatus("Error: " + evt.message, "error");
                break;
        }
    }

    function showStats(s) {
        if (!s) return;
        const parts = [];
        if (s.eval_count) parts.push(`${s.eval_count} tokens`);
        if (s.duration_ms) parts.push(`${(s.duration_ms / 1000).toFixed(1)}s`);
        if (s.tokens_per_second) parts.push(`${s.tokens_per_second} tok/s`);
        els.stats.textContent = parts.join(" · ");
    }

    // ---------- output panes ----------

    function resetOutput() {
        els.live.textContent = "";
        els.thinkingText.textContent = "";
        els.thinking.hidden = true;
        els.thinking.open = false;
        els.stats.textContent = "";
        els.diff.innerHTML = "";
        els.codeView.firstElementChild.innerHTML = "";
        els.copy.disabled = true;
        els.download.disabled = true;
        els.summary.hidden = true;
        els.summaryText.innerHTML = "";
        state.summary = "";
        state.historyId = null;
        markActiveHistory();
        setTabEnabled("diff", false);
        setTabEnabled("code", false);
        showTab("live");
    }

    function showResult() {
        els.diff.appendChild(renderSideBySide(state.original, state.finalCode, state.language));
        els.codeView.firstElementChild.innerHTML = highlight(state.finalCode, state.language);
        els.copy.disabled = !state.finalCode;
        els.download.disabled = !state.finalCode;
        showSummary(state.summary);
        markActiveHistory();
        setTabEnabled("diff", true);
        setTabEnabled("code", true);
        showTab("diff");
    }

    function setTabEnabled(name, enabled) {
        for (const t of els.tabs) if (t.dataset.tab === name) t.disabled = !enabled;
    }

    function showTab(name) {
        for (const t of els.tabs) {
            const active = t.dataset.tab === name;
            t.setAttribute("aria-selected", String(active));
            $(t.getAttribute("aria-controls")).hidden = !active;
        }
    }

    async function copyResult() {
        const text = state.finalCode;
        try {
            await navigator.clipboard.writeText(text);
        } catch (_) {
            // navigator.clipboard needs a secure context; plain http on a LAN/Tailscale IP isn't one.
            const ta = document.createElement("textarea");
            ta.value = text;
            ta.style.position = "fixed";
            ta.style.opacity = "0";
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            ta.remove();
        }
        const label = els.copy.textContent;
        els.copy.textContent = "Copied ✓";
        setTimeout(() => (els.copy.textContent = label), 1500);
    }

    function downloadResult() {
        const name = state.filename || `refactored.${extensionFor(state.language)}`;
        const blob = new Blob([state.finalCode.replace(/\n*$/, "\n")], { type: "text/plain" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    }

    function extensionFor(language) {
        return Object.keys(EXTENSIONS).find((ext) => EXTENSIONS[ext] === language) || "txt";
    }

    // ---------- "what changed" summary ----------

    function showSummary(text) {
        els.summaryText.innerHTML = text ? renderSummary(text) : "";
        els.summary.hidden = !text;
    }

    /** Tiny markdown subset for the model's summary: bullet/numbered lists, `code`, **bold**. */
    function renderSummary(text) {
        const inline = (s) =>
            escapeHtml(s)
                .replace(/`([^`]+)`/g, "<code>$1</code>")
                .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        let html = "";
        let inList = false;
        for (const raw of text.split("\n")) {
            const line = raw.trim();
            if (!line) continue;
            const item = line.match(/^(?:[-*•]|\d+[.)])\s+(.*)$/);
            if (item) {
                if (!inList) html += "<ul>";
                inList = true;
                html += `<li>${inline(item[1])}</li>`;
            } else {
                if (inList) html += "</ul>";
                inList = false;
                html += `<p>${inline(line)}</p>`;
            }
        }
        return html + (inList ? "</ul>" : "");
    }

    // ---------- opening files ----------

    async function openFile(file) {
        if (!file) return;
        if (file.size > MAX_FILE_BYTES) {
            setStatus(`${file.name} is too large (max ${MAX_FILE_BYTES / 1024} KB).`, "error");
            return;
        }
        let text;
        try {
            text = await file.text();
        } catch (e) {
            setStatus(`Could not read ${file.name}: ${e.message}`, "error");
            return;
        }
        if (text.includes("\u0000")) {
            setStatus(`${file.name} looks like a binary file.`, "error");
            return;
        }
        els.code.value = text;
        setFilename(file.name);
        const ext = file.name.includes(".") ? file.name.split(".").pop().toLowerCase() : "";
        const lang = EXTENSIONS[ext];
        if (lang && [...els.lang.options].some((o) => o.value === lang)) els.lang.value = lang;
        setStatus(`Opened ${file.name}.`);
    }

    function setFilename(name) {
        state.filename = name || null;
        els.fileName.textContent = name || "";
        els.fileName.hidden = !name;
        els.clearFile.hidden = !name;
    }

    // ---------- history ----------

    async function loadHistory() {
        let data;
        try {
            const res = await fetch("/api/history?limit=100");
            data = await res.json();
        } catch (e) {
            els.historyHint.textContent = "Could not load history: " + e.message;
            return;
        }
        els.historyList.innerHTML = "";
        els.clearHistory.hidden = !data.enabled || !data.items.length;
        if (!data.enabled) {
            els.historyHint.textContent = "History is turned off (HISTORY_ENABLED=false).";
            return;
        }
        els.historyHint.textContent = "Past refactors are saved on this machine.";
        if (!data.items.length) {
            const li = document.createElement("li");
            li.className = "empty";
            li.textContent = "No refactors yet. Finished runs from here and from the refactor CLI show up here.";
            els.historyList.appendChild(li);
            return;
        }
        for (const item of data.items) els.historyList.appendChild(historyRow(item));
        markActiveHistory();
    }

    function historyRow(item) {
        const li = document.createElement("li");
        li.dataset.id = item.id;

        const open = document.createElement("button");
        open.type = "button";
        open.className = "history-open";
        const name = item.filename ? item.filename.split(/[\\/]/).pop() : `Pasted ${item.language}`;
        const when = new Date(item.created_at).toLocaleString();
        const via = item.source === "cli" ? " · CLI" : "";
        open.innerHTML =
            `<span class="history-title">${escapeHtml(name)} — ${escapeHtml(item.instruction)}</span>` +
            `<span class="history-meta">${escapeHtml(when)} · ${escapeHtml(item.model || "")}${via}</span>`;
        open.title = item.summary || item.instruction;
        open.addEventListener("click", () => openHistory(item.id));

        const del = document.createElement("button");
        del.type = "button";
        del.className = "history-delete";
        del.textContent = "×";
        del.title = "Delete from history";
        del.setAttribute("aria-label", `Delete ${name} from history`);
        del.addEventListener("click", () => deleteHistory(item.id));

        li.append(open, del);
        return li;
    }

    async function openHistory(id) {
        if (state.controller) return;
        let entry;
        try {
            const res = await fetch(`/api/history/${id}`);
            if (!res.ok) throw new Error(await errorMessage(res));
            entry = await res.json();
        } catch (e) {
            setStatus("Could not open refactor: " + e.message, "error");
            return;
        }
        els.code.value = entry.original_code;
        if ([...els.lang.options].some((o) => o.value === entry.language)) els.lang.value = entry.language;
        setFilename(entry.filename ? entry.filename.split(/[\\/]/).pop() : null);

        resetOutput();
        state.original = entry.original_code;
        state.language = entry.language;
        state.finalCode = entry.refactored_code;
        state.summary = entry.summary;
        state.historyId = entry.id;
        els.live.textContent = entry.refactored_code;
        showResult();
        setStatus(`Showing refactor from ${new Date(entry.created_at).toLocaleString()}.`);
        els.summary.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    async function deleteHistory(id) {
        try {
            const res = await fetch(`/api/history/${id}`, { method: "DELETE" });
            if (!res.ok && res.status !== 404) throw new Error(await errorMessage(res));
        } catch (e) {
            setStatus("Could not delete: " + e.message, "error");
            return;
        }
        if (state.historyId === id) state.historyId = null;
        loadHistory();
    }

    async function clearAllHistory() {
        if (!window.confirm("Delete all saved refactors from this machine?")) return;
        try {
            await fetch("/api/history", { method: "DELETE" });
        } catch (e) {
            setStatus("Could not clear history: " + e.message, "error");
            return;
        }
        state.historyId = null;
        loadHistory();
    }

    function markActiveHistory() {
        for (const li of els.historyList.children) {
            li.classList.toggle("active", li.dataset.id !== undefined && Number(li.dataset.id) === state.historyId);
        }
    }

    // ---------- side-by-side diff ----------

    function splitLines(text) {
        const lines = text.split("\n");
        if (lines.length && lines[lines.length - 1] === "") lines.pop();
        return lines;
    }

    /** Align a line diff into rows of {left, right, kind}; kind is same | del | add | mod. */
    function diffRows(a, b) {
        const withNl = (s) => (s.endsWith("\n") ? s : s + "\n");
        const parts = Diff.diffLines(withNl(a), withNl(b));
        const rows = [];
        let ln = 1;
        let rn = 1;
        for (let i = 0; i < parts.length; i++) {
            const lines = splitLines(parts[i].value);
            if (!parts[i].added && !parts[i].removed) {
                for (const t of lines) rows.push({ kind: "same", left: { n: ln++, t }, right: { n: rn++, t } });
            } else if (parts[i].removed && parts[i + 1] && parts[i + 1].added) {
                // A removal followed by an addition is a modification: show them side by side.
                const added = splitLines(parts[++i].value);
                const n = Math.max(lines.length, added.length);
                for (let k = 0; k < n; k++) {
                    rows.push({
                        kind: "mod",
                        left: k < lines.length ? { n: ln++, t: lines[k] } : null,
                        right: k < added.length ? { n: rn++, t: added[k] } : null,
                    });
                }
            } else if (parts[i].removed) {
                for (const t of lines) rows.push({ kind: "del", left: { n: ln++, t }, right: null });
            } else {
                for (const t of lines) rows.push({ kind: "add", left: null, right: { n: rn++, t } });
            }
        }
        return rows;
    }

    function renderSideBySide(a, b, language) {
        const rows = diffRows(a, b);
        const table = document.createElement("table");
        table.className = "diff";
        table.innerHTML =
            '<colgroup><col class="ln"><col><col class="ln"><col></colgroup>' +
            '<thead><tr><th colspan="2">Original</th><th colspan="2">Refactored</th></tr></thead>';
        const tbody = table.createTBody();
        const changed = rows.filter((r) => r.kind !== "same").length;
        if (!changed) {
            const td = tbody.insertRow().insertCell();
            td.colSpan = 4;
            td.className = "nochange";
            td.textContent = "No changes: the model returned the same code.";
        }
        for (const row of rows) {
            const tr = tbody.insertRow();
            const changedRow = row.kind !== "same";
            addSide(tr, row.left, changedRow ? "del" : "", language);
            addSide(tr, row.right, changedRow ? "add" : "", language);
        }
        return table;
    }

    function addSide(tr, side, cls, language) {
        const num = tr.insertCell();
        num.className = "ln";
        const code = tr.insertCell();
        code.className = "code " + (side ? cls : "empty");
        if (side) {
            num.textContent = side.n;
            code.innerHTML = highlight(side.t, language) || " ";
        }
    }

    // ---------- helpers ----------

    function highlight(text, language) {
        if (window.hljs && hljs.getLanguage(language)) {
            return hljs.highlight(text, { language, ignoreIllegals: true }).value;
        }
        return escapeHtml(text);
    }

    function escapeHtml(s) {
        const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
        return s.replace(/[&<>"']/g, (c) => map[c]);
    }

    function setRunning(running) {
        els.run.disabled = running;
        els.stop.hidden = !running;
    }

    function setStatus(text, kind) {
        els.status.textContent = text;
        els.status.className = "status" + (kind ? " " + kind : "");
    }

    function setHint(text, isError) {
        els.modelStatus.textContent = text;
        els.modelStatus.className = "hint" + (isError ? " error" : "");
    }

    function storageGet(key) {
        try {
            return localStorage.getItem("refactor." + key);
        } catch (_) {
            return null;
        }
    }

    function storageSet(key, value) {
        try {
            localStorage.setItem("refactor." + key, value);
        } catch (_) {
            // storage unavailable (private mode etc.)
        }
    }

    // ---------- wiring ----------

    els.run.addEventListener("click", refactor);
    els.stop.addEventListener("click", () => state.controller && state.controller.abort());
    els.copy.addEventListener("click", copyResult);
    els.download.addEventListener("click", downloadResult);
    els.openFile.addEventListener("click", () => els.fileInput.click());
    els.fileInput.addEventListener("change", () => {
        openFile(els.fileInput.files[0]);
        els.fileInput.value = ""; // allow re-opening the same file
    });
    els.clearFile.addEventListener("click", () => setFilename(null));
    els.code.addEventListener("dragover", (e) => {
        if (![...e.dataTransfer.types].includes("Files")) return;
        e.preventDefault();
        els.code.classList.add("dragover");
    });
    els.code.addEventListener("dragleave", () => els.code.classList.remove("dragover"));
    els.code.addEventListener("drop", (e) => {
        els.code.classList.remove("dragover");
        if (!e.dataTransfer.files.length) return;
        e.preventDefault();
        openFile(e.dataTransfer.files[0]);
    });
    els.clearHistory.addEventListener("click", clearAllHistory);
    els.reloadModels.addEventListener("click", loadModels);
    els.model.addEventListener("change", () => storageSet("model", els.model.value));
    for (const t of els.tabs) t.addEventListener("click", () => showTab(t.dataset.tab));
    for (const el of [els.code, els.custom]) {
        el.addEventListener("keydown", (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") refactor();
        });
    }

    loadModels();
    loadPresets();
    loadHistory();
})();

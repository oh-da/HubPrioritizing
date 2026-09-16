// Front-end logic for the Run Model GUI.
// Communicates with the Python backend via window.pywebview.api.

let FIELDS = [];          // [{field,label,required}]
const selected = {};      // field -> path
let pollTimer = null;

function $(id) { return document.getElementById(id); }

// Wait until pywebview has injected the API
window.addEventListener('pywebviewready', init);

async function init() {
    FIELDS = await window.pywebview.api.get_input_fields();
    buildFileRows();
    $('outputDir').value = await window.pywebview.api.default_output_dir();

    document.querySelectorAll('input[name="mode"]').forEach(r =>
        r.addEventListener('change', applyMode));
    applyMode();
}

function applyMode() {
    const mode = document.querySelector('input[name="mode"]:checked').value;
    $('dirMode').style.display = (mode === 'dir') ? 'block' : 'none';
    // In directory mode the per-file Browse buttons are hidden (auto-detected);
    // in files mode they are shown.
    document.querySelectorAll('.fileBrowse').forEach(b => {
        b.style.display = (mode === 'files') ? 'inline-block' : 'none';
    });
}

function buildFileRows() {
    const tbody = $('fileRows');
    tbody.innerHTML = '';
    FIELDS.forEach(f => {
        const tr = document.createElement('tr');
        const tag = f.required
            ? '<span class="tag req">required</span>'
            : '<span class="tag opt">optional</span>';
        tr.innerHTML = `
            <td>${f.label}${tag}</td>
            <td><span class="filename missing" id="fn_${f.field}">— not selected —</span></td>
            <td><button class="btn ghost fileBrowse" onclick="browseFile('${f.field}')">Browse…</button></td>
        `;
        tbody.appendChild(tr);
    });
}

function setFile(field, path) {
    selected[field] = path || null;
    const el = $('fn_' + field);
    if (path) {
        el.textContent = path;
        el.classList.remove('missing');
    } else {
        el.textContent = '— not selected —';
        el.classList.add('missing');
    }
}

async function browseFile(field) {
    const path = await window.pywebview.api.pick_file(field);
    if (path) setFile(field, path);
}

async function browseDir() {
    const dir = await window.pywebview.api.pick_folder();
    if (!dir) return;
    $('dirPath').value = dir;
    await rescan();
}

async function rescan() {
    const dir = $('dirPath').value;
    if (!dir) { alert('Choose a directory first.'); return; }
    const res = await window.pywebview.api.scan_directory(dir);
    if (!res.ok) { alert('Scan failed: ' + res.error); return; }
    FIELDS.forEach(f => setFile(f.field, res.matches[f.field]));
}

async function browseOutput() {
    const dir = await window.pywebview.api.pick_folder();
    if (dir) $('outputDir').value = dir;
}

async function runModel() {
    const runBy = $('runBy').value.trim();
    if (!runBy) { alert('Please enter your name before running.'); return; }

    // Validate required inputs are present
    const missing = FIELDS.filter(f => f.required && !selected[f.field]).map(f => f.label);
    if (missing.length) { alert('Missing required inputs:\n- ' + missing.join('\n- ')); return; }

    const payload = {
        inputs: { ...selected },
        output_dir: $('outputDir').value.trim(),
        run_by: runBy,
        remarks: $('remarks').value,
        skip_demand_data: $('skip_demand_data').checked,
        skip_spatial_layers: $('skip_spatial_layers').checked,
        skip_demographics: $('skip_demographics').checked,
        run_mc_distribution: $('run_mc_distribution').checked,
    };

    const res = await window.pywebview.api.start_run(payload);
    if (!res.ok) { setStatus(res.error, 'err'); return; }

    $('runBtn').disabled = true;
    $('progressCard').style.display = 'block';
    $('resultPanel').style.display = 'none';
    $('logBox').textContent = '';
    setStatus('Running…');
    pollTimer = setInterval(poll, 1000);
}

function setStatus(text, kind) {
    const el = $('runStatus');
    el.textContent = text || '';
    el.className = 'status' + (kind ? ' ' + kind : '');
}

async function poll() {
    const s = await window.pywebview.api.poll();
    const box = $('logBox');
    box.textContent = s.log || '';
    box.scrollTop = box.scrollHeight;

    if (s.done) {
        clearInterval(pollTimer);
        $('runBtn').disabled = false;
        if (s.error) {
            setStatus('Run failed', 'err');
        } else {
            setStatus('Run complete', 'ok');
        }
        renderResult(s.manifest, s.error);
    }
}

function renderResult(manifest, error) {
    const panel = $('resultPanel');
    panel.style.display = 'block';
    if (!manifest) {
        panel.innerHTML = `<div class="banner err">Run finished but no run log was found.${
            error ? ' Error: ' + escapeHtml(error) : ''}</div>`;
        return;
    }

    const ok = manifest.status === 'success';
    let html = `<div class="banner ${ok ? 'ok' : 'err'}">
        ${ok ? '✅ Pipeline complete' : '❌ Pipeline failed'} —
        run ${escapeHtml(manifest.run_id)} by ${escapeHtml(manifest.run_by)}
        (${manifest.duration_seconds}s)
        ${manifest.error_message ? '<br>' + escapeHtml(manifest.error_message) : ''}
    </div>`;

    const sum = manifest.results_summary || {};
    if (sum.total_hubs != null) {
        html += '<div class="summary">';
        html += `<div class="stat"><b>${sum.total_hubs}</b><span>total hubs</span></div>`;
        const byTier = sum.hubs_by_tier || {};
        Object.keys(byTier).forEach(t => {
            html += `<div class="stat"><b>${byTier[t]}</b><span>${escapeHtml(t)}</span></div>`;
        });
        html += '</div>';
    }

    html += `<p class="hint">Output directory:</p>
        <ul class="outlist">
        <li><span class="filename">${escapeHtml(manifest.output_dir)}</span>
            <button class="btn ghost" onclick="openPath('${jsstr(manifest.output_dir)}')">Open folder</button></li>`;
    (manifest.outputs || []).forEach(p => {
        html += `<li><span class="filename">${escapeHtml(p)}</span>
            <button class="btn ghost" onclick="openPath('${jsstr(p)}')">Open</button></li>`;
    });
    html += '</ul>';

    panel.innerHTML = html;
}

async function openPath(path) {
    await window.pywebview.api.open_path(path);
}

function escapeHtml(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function jsstr(s) {
    return String(s == null ? '' : s).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

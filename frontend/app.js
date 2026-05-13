/* ── CONFIG ─────────────────────────────────────── */
const API = '';
const CHUNK_SIZE = 20 * 1024 * 1024; // 20MB chunks

/* ── STATE ──────────────────────────────────────── */
let token = localStorage.getItem('token') || null;
let currentUser = null;
let wsConn = null;
let downloads = {}; // { id: { name, size, loaded, speed, status, controller, chunks } }
let uploadControllers = {}; // { uploadId: AbortController }

/* ── API ─────────────────────────────────────────── */
async function api(method, path, body = null, isForm = false, signal = null) {
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (body && !isForm) headers['Content-Type'] = 'application/json';
  const res = await fetch(`${API}${path}`, {
    method, headers, signal,
    body: isForm ? body : (body ? JSON.stringify(body) : null),
  });
  if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
  const text = await res.text();
  try {
    const data = JSON.parse(text);
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    return data;
  } catch (e) {
    if (!res.ok) throw new Error(text || 'Request failed');
    return text;
  }
}

/* ── TOAST ───────────────────────────────────────── */
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

/* ── UTILS ───────────────────────────────────────── */
function fileIcon(name) {
  const ext = (name.split('.').pop() || '').toLowerCase();
  const m = { pdf:'📄', doc:'📝', docx:'📝', txt:'📃', xls:'📊', xlsx:'📊', csv:'📊', png:'🖼', jpg:'🖼', jpeg:'🖼', gif:'🖼', webp:'🖼', mp4:'🎬', mov:'🎬', avi:'🎬', mkv:'🎬', mp3:'🎵', wav:'🎵', flac:'🎵', zip:'📦', rar:'📦', tar:'📦', gz:'📦', py:'🐍', js:'⚡', ts:'⚡', html:'🌐', css:'🎨', pptx:'📊', ppt:'📊' };
  return m[ext] || '📁';
}

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' });
}

function fmtSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB';
  if (bytes < 1024*1024*1024) return (bytes/1024/1024).toFixed(1) + ' MB';
  return (bytes/1024/1024/1024).toFixed(2) + ' GB';
}

function fmtSpeed(bps) {
  if (bps < 1024*1024) return (bps/1024).toFixed(0) + ' KB/s';
  return (bps/1024/1024).toFixed(1) + ' MB/s';
}

/* ── SCREENS & VIEWS ─────────────────────────────── */
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(`view-${id}`).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === id));
}

/* ── MODALS ──────────────────────────────────────── */
function openModal(id) {
  document.getElementById('modal-backdrop').classList.add('open');
  document.querySelectorAll('.modal').forEach(m => m.classList.remove('open'));
  document.getElementById(`modal-${id}`).classList.add('open');
}

function closeModals() {
  document.getElementById('modal-backdrop').classList.remove('open');
  document.querySelectorAll('.modal').forEach(m => m.classList.remove('open'));
}

/* ── AUTH ────────────────────────────────────────── */
async function login() {
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const err = document.getElementById('login-error');
  err.textContent = '';
  try {
    const data = await api('POST', '/auth/login', { email, password });
    token = data.token;
    localStorage.setItem('token', token);
    await initApp();
  } catch (e) { err.textContent = e.message; }
}

async function register() {
  const username = document.getElementById('reg-username').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  const err = document.getElementById('reg-error');
  err.textContent = '';
  try {
    const data = await api('POST', '/auth/register', { username, email, password });
    token = data.token;
    localStorage.setItem('token', token);
    await initApp();
  } catch (e) { err.textContent = e.message; }
}

function logout() {
  token = null; currentUser = null;
  localStorage.removeItem('token');
  if (wsConn) wsConn.close();
  showScreen('auth-screen');
}

/* ── INIT ────────────────────────────────────────── */
async function initApp() {
  try {
    currentUser = await api('GET', '/auth/me');
    document.getElementById('user-name').textContent = currentUser.username;
    document.getElementById('user-avatar').textContent = currentUser.username[0].toUpperCase();
    showScreen('app-screen');
    showView('files');
    loadWorkspaces().catch(e => console.warn('workspaces:', e)); // ← non-fatal
  } catch (e) {
    console.error('initApp failed:', e);
    logout();
  }
}

/* ── WORKSPACES ──────────────────────────────────── */
async function loadWorkspaces() {
  const data = await api('GET', '/workspaces');
  const workspaces = data.workspaces || [];

  // sidebar selects
  const wsSelect = document.getElementById('workspace-select');
  const searchWsSelect = document.getElementById('search-ws-select');
  const prev = wsSelect.value;

  wsSelect.innerHTML = '<option value="">Select workspace</option>';
  searchWsSelect.innerHTML = '<option value="">All workspaces</option>';

  workspaces.forEach(w => {
    wsSelect.innerHTML += `<option value="${w.workspace_id}">${w.workspace_name}</option>`;
    searchWsSelect.innerHTML += `<option value="${w.workspace_id}">${w.workspace_name}</option>`;
  });

  if (prev) wsSelect.value = prev;

  // grid
  const grid = document.getElementById('workspaces-grid');
  if (!workspaces.length) {
    grid.innerHTML = '<div class="files-empty">No workspaces yet. Create one to get started.</div>';
  } else {
    grid.innerHTML = workspaces.map(w => `
      <div class="ws-card">
        <div class="ws-card-top">
          <div class="ws-icon">🏢</div>
          <span class="role-pill role-${w.role}">${w.role}</span>
        </div>
        <div class="ws-name">${w.workspace_name}</div>
        <div class="ws-id">ID: ${w.workspace_id}</div>
        <div class="ws-actions">
          <button class="btn-file" onclick="openAddMember(${w.workspace_id}, '${w.workspace_name}')">+ Member</button>
        </div>
      </div>
    `).join('');
  }

  // storage indicator
  document.getElementById('storage-count').textContent = `${workspaces.length} workspace${workspaces.length !== 1 ? 's' : ''}`;

  return workspaces;
}

async function createWorkspace() {
  const name = document.getElementById('ws-name').value.trim();
  const err = document.getElementById('ws-error');
  err.textContent = '';
  if (!name) { err.textContent = 'Name is required'; return; }
  try {
    await api('POST', '/workspaces', { workspace_name: name });
    closeModals();
    document.getElementById('ws-name').value = '';
    await loadWorkspaces();
    toast('Workspace created!', 'success');
  } catch (e) { err.textContent = e.message; }
}

let memberTargetId = null;
function openAddMember(wsId, wsName) {
  memberTargetId = wsId;
  document.getElementById('member-ws-name').textContent = wsName;
  document.getElementById('member-panel').style.display = 'flex';
  document.getElementById('member-panel').style.flexDirection = 'column';
}

async function addMember() {
  const userId = parseInt(document.getElementById('member-user-id').value);
  const role = document.getElementById('member-role').value;
  const err = document.getElementById('member-error');
  err.textContent = '';
  if (!userId) { err.textContent = 'User ID required'; return; }
  try {
    await api('POST', `/workspaces/${memberTargetId}/members`, { user_id: userId, role });
    toast('Member added!', 'success');
    document.getElementById('member-user-id').value = '';
    document.getElementById('member-panel').style.display = 'none';
  } catch (e) { err.textContent = e.message; }
}

/* ── FOLDERS ─────────────────────────────────────── */
async function loadFolders(wsId) {
  try {
    const data = await api('GET', `/workspaces/${wsId}/folders`);
    const folders = data.folders || [];
    const sel = document.getElementById('folder-select');
    sel.innerHTML = '<option value="">Select folder</option>';
    folders.forEach(f => {
      sel.innerHTML += `<option value="${f.folder_id}">${f.folder_name}</option>`;
    });
    // also save to localStorage as cache
    localStorage.setItem(`folders_${wsId}`, JSON.stringify(folders));
  } catch (e) {
    // fallback to localStorage
    const saved = JSON.parse(localStorage.getItem(`folders_${wsId}`) || '[]');
    const sel = document.getElementById('folder-select');
    sel.innerHTML = '<option value="">Select folder</option>';
    saved.forEach(f => { sel.innerHTML += `<option value="${f.folder_id}">${f.folder_name}</option>`; });
  }
}

async function createFolder() {
  const name = document.getElementById('folder-name').value.trim();
  const wsId = document.getElementById('workspace-select').value;
  const err = document.getElementById('folder-error');
  err.textContent = '';
  if (!name) { err.textContent = 'Name is required'; return; }
  if (!wsId) { err.textContent = 'Select a workspace first'; return; }
  try {
    const data = await api('POST', '/folders', { folder_name: name, workspace_id: parseInt(wsId) });
    const saved = JSON.parse(localStorage.getItem(`folders_${wsId}`) || '[]');
    saved.push({ folder_id: data.folder_id, folder_name: data.folder_name });
    localStorage.setItem(`folders_${wsId}`, JSON.stringify(saved));
    closeModals();
    document.getElementById('folder-name').value = '';
    await loadFolders(wsId);
    toast('Folder created!', 'success');
  } catch (e) { err.textContent = e.message; }
}

/* ── FILES ───────────────────────────────────────── */
async function loadFiles() {
  const wsId = document.getElementById('workspace-select').value;
  const folderId = document.getElementById('folder-select').value;
  const list = document.getElementById('files-list');
  const crumb = document.getElementById('files-breadcrumb');

  if (!wsId || !folderId) {
    list.innerHTML = '<div class="files-empty">Select a workspace and folder to view files</div>';
    crumb.textContent = 'Select a workspace and folder';
    return;
  }

  const wsName = document.getElementById('workspace-select').options[document.getElementById('workspace-select').selectedIndex].text;
  const folderName = document.getElementById('folder-select').options[document.getElementById('folder-select').selectedIndex].text;
  crumb.textContent = `${wsName} / ${folderName}`;

  list.innerHTML = '<div class="files-empty"><div class="spinner"></div></div>';

  try {
    const data = await api('GET', `/workspaces/${wsId}/files?folder_id=${folderId}`);
    const files = data.files || [];

    if (!files.length) {
      list.innerHTML = '<div class="files-empty">No files yet — upload something!</div>';
      return;
    }

    list.innerHTML = files.map(f => `
      <div class="file-row">
        <div class="file-name-cell">
          <div class="file-type-icon">${fileIcon(f.filename)}</div>
          <span class="file-name-text" title="${f.filename}">${f.filename}</span>
        </div>
        <span class="file-date">${fmtDate(f.uploaded_at)}</span>
        <span class="file-mime">${f.mime_type || '—'}</span>
        <div class="file-actions">
          <button class="btn-file" onclick="startDownload('${f.file_id}', '${f.filename}')">↓ Download</button>
          <button class="btn-file danger" onclick="deleteFile('${f.file_id}', '${f.filename}')">Delete</button>
        </div>
      </div>
    `).join('');

    connectWS(wsId);
  } catch (e) {
    list.innerHTML = `<div class="files-empty">${e.message}</div>`;
  }
}

async function deleteFile(fileId, filename) {
  if (!confirm(`Delete "${filename}"?`)) return;
  try {
    await api('DELETE', `/files/${fileId}/delete`);
    toast(`${filename} deleted`, 'success');
    loadFiles();
  } catch (e) { toast(e.message, 'error'); }
}

/* ── UPLOAD ──────────────────────────────────────── */
async function uploadFile(file) {
  const wsId = document.getElementById('workspace-select').value;
  const folderId = document.getElementById('folder-select').value;
  if (!wsId || !folderId) { toast('Select workspace and folder first', 'error'); return; }

  const itemId = `up-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const queue = document.getElementById('upload-queue');

  queue.insertAdjacentHTML('beforeend', `
    <div class="upload-item" id="${itemId}">
      <div class="upload-item-left">
        <div class="upload-item-name">${file.name}</div>
        <div class="upload-item-bar"><div class="upload-item-fill" id="fill-${itemId}" style="width:0%"></div></div>
        <div class="upload-item-meta">
          <span class="upload-item-status" id="stat-${itemId}">Preparing...</span>
        </div>
      </div>
      <div class="upload-item-right">
        <button class="upload-cancel" id="cancel-${itemId}" title="Cancel">✕</button>
      </div>
    </div>
  `);

  const fill = document.getElementById(`fill-${itemId}`);
  const stat = document.getElementById(`stat-${itemId}`);
  const cancelBtn = document.getElementById(`cancel-${itemId}`);

  let cancelled = false;
  let uploadId = null;

  cancelBtn.onclick = async () => {
    cancelled = true;
    stat.textContent = 'Cancelled';
    stat.className = 'upload-item-status error';
    fill.style.background = 'var(--red)';
    cancelBtn.remove();
    setTimeout(() => document.getElementById(itemId)?.remove(), 2000);
  };

  const totalMB = (file.size / 1024 / 1024).toFixed(1);
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

  try {
    stat.textContent = 'Initializing...';
    const init = await api('POST', `/files/upload/init?filename=${encodeURIComponent(file.name)}&workspace_id=${wsId}&folder_id=${folderId}`);
    uploadId = init.upload_id;

    let uploaded = 0;
    const startTime = Date.now();

    for (let i = 0; i < totalChunks; i++) {
      if (cancelled) return;

      const start = i * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, file.size);
      const chunk = file.slice(start, end);

      const fd = new FormData();
      fd.append('chunk', chunk, file.name);

      await fetch(`${API}/files/upload/${uploadId}/chunk/${i + 1}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}` },
        body: fd,
      });

      if (cancelled) return;

      uploaded += (end - start);
      const elapsed = (Date.now() - startTime) / 1000;
      const speed = uploaded / elapsed;
      const pct = Math.round((uploaded / file.size) * 100);
      const loadedMB = (uploaded / 1024 / 1024).toFixed(1);

      fill.style.width = `${pct}%`;
      stat.textContent = `${loadedMB} / ${totalMB} MB  ·  ${fmtSpeed(speed)}  ·  ${pct}%`;
    }

    if (cancelled) return;

    stat.textContent = 'Finalizing...';
    fill.style.width = '99%';

    await api('POST', `/files/upload/${uploadId}/complete`);

    fill.style.width = '100%';
    fill.style.background = 'var(--green)';
    stat.textContent = `Done — ${totalMB} MB`;
    stat.className = 'upload-item-status done';
    cancelBtn.remove();
    toast(`${file.name} uploaded!`, 'success');
    loadFiles();
    setTimeout(() => document.getElementById(itemId)?.remove(), 4000);

  } catch (e) {
    if (cancelled) return;
    stat.textContent = `Failed: ${e.message}`;
    stat.className = 'upload-item-status error';
    fill.style.background = 'var(--red)';
    toast(`Upload failed: ${e.message}`, 'error');
  }
}

/* ── DOWNLOADS ───────────────────────────────────── */
function startDownload(fileId, filename) {
  const dlId = `dl-${Date.now()}`;

  downloads[dlId] = {
    fileId, filename,
    status: 'active',
    loaded: 0,
    total: 0,
    speed: 0,
    startTime: Date.now(),
    abortController: new AbortController(),
  };

  updateDownloadsBadge();
  renderDownloads();

  // switch to downloads tab
  showView('downloads');

  // start the actual download
  fetchAndDownload(dlId, fileId, filename);
}

async function fetchAndDownload(dlId, fileId, filename) {
  const dl = downloads[dlId];
  const statusEl = () => document.getElementById(`dl-status-${dlId}`);
  const barEl = () => document.getElementById(`dl-bar-${dlId}`);
  const progEl = () => document.getElementById(`dl-prog-${dlId}`);

  try {
    const res = await fetch(`${API}/files/${fileId}/download`, {
      headers: { 'Authorization': `Bearer ${token}` },
      signal: dl.abortController.signal,
    });

    if (!res.ok) throw new Error('Download failed');

    const contentLength = res.headers.get('content-length');
    dl.total = contentLength ? parseInt(contentLength) : 0;

    const reader = res.body.getReader();
    const chunks = [];
    let loaded = 0;
    let lastTime = Date.now();
    let lastLoaded = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      if (downloads[dlId]?.status === 'cancelled') {
        reader.cancel();
        return;
      }

      chunks.push(value);
      loaded += value.length;
      dl.loaded = loaded;

      // speed calc every 500ms
      const now = Date.now();
      if (now - lastTime > 500) {
        dl.speed = (loaded - lastLoaded) / ((now - lastTime) / 1000);
        lastTime = now;
        lastLoaded = loaded;
      }

      // update UI
      const pct = dl.total ? Math.round((loaded / dl.total) * 100) : 0;
      const loadedStr = fmtSize(loaded);
      const totalStr = dl.total ? fmtSize(dl.total) : '?';
      const speedStr = fmtSpeed(dl.speed);

      if (barEl()) barEl().style.width = `${pct}%`;
      if (progEl()) progEl().textContent = `${loadedStr} / ${totalStr}`;
      if (statusEl()) statusEl().textContent = `${speedStr}  ·  ${pct}%`;
    }

    // assemble blob and trigger save
    const blob = new Blob(chunks);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    a.click();
    URL.revokeObjectURL(url);

    dl.status = 'done';
    dl.loaded = dl.total || loaded;
    if (barEl()) { barEl().style.width = '100%'; barEl().className = 'download-bar done'; }
    if (statusEl()) { statusEl().textContent = `Complete — ${fmtSize(dl.loaded)}`; statusEl().className = 'download-status done'; }
    if (progEl()) progEl().textContent = fmtSize(dl.loaded);
    toast(`${filename} downloaded!`, 'success');
    renderDownloads();

  } catch (e) {
    if (e.name === 'AbortError' || downloads[dlId]?.status === 'cancelled') return;
    dl.status = 'error';
    if (barEl()) barEl().className = 'download-bar error';
    if (statusEl()) { statusEl().textContent = `Failed: ${e.message}`; statusEl().className = 'download-status error'; }
    toast(`Download failed: ${e.message}`, 'error');
    renderDownloads();
  }

  updateDownloadsBadge();
}

function cancelDownload(dlId) {
  const dl = downloads[dlId];
  if (!dl) return;
  dl.status = 'cancelled';
  dl.abortController.abort();
  delete downloads[dlId];
  renderDownloads();
  updateDownloadsBadge();
  toast('Download cancelled', 'info');
}

function clearCompletedDownloads() {
  Object.keys(downloads).forEach(id => {
    if (downloads[id].status === 'done' || downloads[id].status === 'error') {
      delete downloads[id];
    }
  });
  renderDownloads();
  updateDownloadsBadge();
}

function updateDownloadsBadge() {
  const active = Object.values(downloads).filter(d => d.status === 'active').length;
  const badge = document.getElementById('downloads-badge');
  if (active > 0) { badge.style.display = 'inline'; badge.textContent = active; }
  else { badge.style.display = 'none'; }
}

function renderDownloads() {
  const list = document.getElementById('downloads-list');
  const entries = Object.entries(downloads);

  if (!entries.length) {
    list.innerHTML = '<div class="files-empty">No downloads yet</div>';
    return;
  }

  list.innerHTML = entries.map(([dlId, dl]) => {
    const pct = dl.total ? Math.round((dl.loaded / dl.total) * 100) : 0;
    const isActive = dl.status === 'active';
    return `
      <div class="download-item" id="dl-item-${dlId}">
        <div class="download-header">
          <div class="download-file-icon">${fileIcon(dl.filename)}</div>
          <div class="download-info">
            <div class="download-name">${dl.filename}</div>
            <div class="download-size">${dl.total ? fmtSize(dl.total) : 'Calculating...'}</div>
          </div>
          <div class="download-controls">
            ${isActive ? `<button class="btn-download-control cancel" onclick="cancelDownload('${dlId}')">Cancel</button>` : ''}
          </div>
        </div>
        <div class="download-bar-wrap">
          <div class="download-bar ${dl.status === 'done' ? 'done' : dl.status === 'error' ? 'error' : ''}"
               id="dl-bar-${dlId}" style="width:${pct}%"></div>
        </div>
        <div class="download-meta">
          <span class="download-progress-text" id="dl-prog-${dlId}">
            ${fmtSize(dl.loaded)} ${dl.total ? '/ ' + fmtSize(dl.total) : ''}
          </span>
          <span class="download-status ${dl.status === 'done' ? 'done' : dl.status === 'error' ? 'error' : 'active'}"
                id="dl-status-${dlId}">
            ${dl.status === 'done' ? `Complete — ${fmtSize(dl.loaded)}` :
              dl.status === 'error' ? 'Failed' :
              fmtSpeed(dl.speed) + '  ·  ' + pct + '%'}
          </span>
        </div>
      </div>
    `;
  }).join('');
}

/* ── SEARCH ──────────────────────────────────────── */
async function search() {
  const query = document.getElementById('search-input').value.trim();
  const wsId = document.getElementById('search-ws-select').value;
  const results = document.getElementById('search-results');

  if (!query) { toast('Enter a search query', 'error'); return; }

  results.innerHTML = `
    <div class="search-empty">
      <div class="spinner" style="width:28px;height:28px;border-width:3px;"></div>
    </div>
  `;

  try {
    const params = new URLSearchParams({ query });
    if (wsId) params.append('workspace_id', wsId);
    const data = await api('GET', `/search?${params}`);
    const items = data.results || [];

    if (!items.length) {
      results.innerHTML = `
        <div class="search-empty">
          <div class="search-empty-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg></div>
          <p>No results found</p>
          <span>Try different keywords or upload more files</span>
        </div>
      `;
      return;
    }

    results.innerHTML = items.map((r, i) => {
      const sim = Math.round(r.similarity * 100);
      const cls = sim >= 60 ? 'similarity-high' : sim >= 30 ? 'similarity-mid' : 'similarity-low';
      return `
        <div class="search-result" style="animation-delay:${i*0.04}s">
          <div class="search-result-icon">${fileIcon(r.filename)}</div>
          <div class="search-result-info">
            <div class="search-result-name">${r.filename}</div>
            <div class="search-result-id">ID: ${r.file_id}</div>
          </div>
          <span class="similarity-pill ${cls}">${sim}% match</span>
        </div>
      `;
    }).join('');

  } catch (e) {
    results.innerHTML = `<div class="search-empty"><p style="color:var(--red)">${e.message}</p></div>`;
  }
}

/* ── WEBSOCKET ────────────────────────────────────── */
function connectWS(wsId) {
  if (wsConn) wsConn.close();
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  wsConn = new WebSocket(`${proto}://${location.host}/ws/workspace/${wsId}`);
  wsConn.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.event === 'file_uploaded') { toast(`📁 ${data.filename} uploaded by ${data.uploaded_by}`, 'info'); loadFiles(); }
    else if (data.event === 'file_deleted') { toast('🗑 File deleted by teammate', 'info'); loadFiles(); }
  };
  wsConn.onerror = () => {};
  wsConn.onclose = () => {};
}

/* ── EVENTS ──────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {

  // auth tabs
  document.querySelectorAll('.auth-tab').forEach(tab => {
    tab.onclick = () => {
      document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.auth-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`panel-${tab.dataset.tab}`).classList.add('active');
    };
  });

  // auth actions
  document.getElementById('btn-login').onclick = login;
  document.getElementById('btn-register').onclick = register;
  document.getElementById('btn-logout').onclick = logout;

  ['login-email', 'login-password'].forEach(id => {
    document.getElementById(id).addEventListener('keydown', e => { if (e.key === 'Enter') login(); });
  });
  ['reg-username', 'reg-email', 'reg-password'].forEach(id => {
    document.getElementById(id).addEventListener('keydown', e => { if (e.key === 'Enter') register(); });
  });

  // nav
  document.querySelectorAll('.nav-item').forEach(item => {
    item.onclick = () => showView(item.dataset.view);
  });

  // workspace select
  document.getElementById('workspace-select').onchange = async (e) => {
    const wsId = e.target.value;
    if (wsId) await loadFolders(wsId);
    else document.getElementById('folder-select').innerHTML = '<option value="">Select folder</option>';
    loadFiles();
  };

  document.getElementById('folder-select').onchange = loadFiles;
  document.getElementById('btn-refresh-files').onclick = loadFiles;

  // upload zone
  const zone = document.getElementById('upload-zone');
  const fileInput = document.getElementById('file-input');

  zone.onclick = (e) => { if (!e.target.classList.contains('drop-link')) fileInput.click(); };
  zone.ondragover = (e) => { e.preventDefault(); zone.classList.add('over'); };
  zone.ondragleave = () => zone.classList.remove('over');
  zone.ondrop = (e) => {
    e.preventDefault(); zone.classList.remove('over');
    Array.from(e.dataTransfer.files).forEach(uploadFile);
  };
  fileInput.onchange = () => { Array.from(fileInput.files).forEach(uploadFile); fileInput.value = ''; };
  document.getElementById('btn-upload-trigger').onclick = () => fileInput.click();

  // workspace modal
  document.getElementById('btn-new-workspace').onclick = () => openModal('workspace');
  document.getElementById('btn-create-ws').onclick = createWorkspace;
  document.getElementById('ws-name').addEventListener('keydown', e => { if (e.key === 'Enter') createWorkspace(); });

  // folder modal
  document.getElementById('btn-new-folder').onclick = () => openModal('folder');
  document.getElementById('btn-create-folder').onclick = createFolder;
  document.getElementById('folder-name').addEventListener('keydown', e => { if (e.key === 'Enter') createFolder(); });

  // modal close
  document.getElementById('modal-backdrop').onclick = (e) => { if (e.target === document.getElementById('modal-backdrop')) closeModals(); };
  document.querySelectorAll('[data-close]').forEach(btn => btn.onclick = closeModals);

  // member panel
  document.getElementById('btn-add-member').onclick = addMember;
  document.getElementById('btn-close-member').onclick = () => { document.getElementById('member-panel').style.display = 'none'; };

  // search
  document.getElementById('btn-search').onclick = search;
  document.getElementById('search-input').addEventListener('keydown', e => { if (e.key === 'Enter') search(); });

  // downloads
  document.getElementById('btn-clear-downloads').onclick = clearCompletedDownloads;

  // boot
  if (token) initApp();
  else showScreen('auth-screen');
});
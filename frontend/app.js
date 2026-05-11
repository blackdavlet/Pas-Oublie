/* ─── CONFIG ────────────────────────────────────────── */
const API = '';  // empty = same origin (goes through Nginx)
const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB chunks

/* ─── STATE ─────────────────────────────────────────── */
let token = localStorage.getItem('token') || null;
let currentUser = null;
let currentWorkspaceId = null;
let currentFolderSelect = null;
let memberTargetWsId = null;
let ws = null; // WebSocket connection

/* ─── HELPERS ───────────────────────────────────────── */
async function api(method, path, body = null, isForm = false) {
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (body && !isForm) headers['Content-Type'] = 'application/json';

  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: isForm ? body : (body ? JSON.stringify(body) : null),
  });

  if (res.status === 401) {
    logout();
    throw new Error('Unauthorized');
  }

  const text = await res.text();
  try {
    const data = JSON.parse(text);
    if (!res.ok) throw new Error(data.detail || 'Request failed');
    return data;
  } catch (e) {
    if (!res.ok) throw new Error(text || 'Request failed');
    return text;
  }
}

function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function fileIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  const map = {
    pdf: '📄', doc: '📝', docx: '📝', txt: '📃',
    xls: '📊', xlsx: '📊', csv: '📊',
    png: '🖼', jpg: '🖼', jpeg: '🖼', gif: '🖼', webp: '🖼',
    mp4: '🎬', mov: '🎬', avi: '🎬',
    mp3: '🎵', wav: '🎵',
    zip: '📦', rar: '📦', tar: '📦',
    py: '🐍', js: '⚡', ts: '⚡', html: '🌐', css: '🎨',
  };
  return map[ext] || '📁';
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(`view-${id}`).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => {
    n.classList.toggle('active', n.dataset.view === id);
  });
}

function showModal(id) {
  document.getElementById('modal-overlay').classList.add('active');
  document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
  document.getElementById(`modal-${id}`).classList.add('active');
}

function closeModals() {
  document.getElementById('modal-overlay').classList.remove('active');
  document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
}

/* ─── AUTH ──────────────────────────────────────────── */
async function login() {
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const errEl = document.getElementById('login-error');
  errEl.textContent = '';

  try {
    const data = await api('POST', '/auth/login', { email, password });
    token = data.token;
    localStorage.setItem('token', token);
    await initApp();
  } catch (e) {
    errEl.textContent = e.message;
  }
}

async function register() {
  const username = document.getElementById('reg-username').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  const errEl = document.getElementById('reg-error');
  errEl.textContent = '';

  try {
    const data = await api('POST', '/auth/register', { username, email, password });
    token = data.token;
    localStorage.setItem('token', token);
    await initApp();
  } catch (e) {
    errEl.textContent = e.message;
  }
}

function logout() {
  token = null;
  currentUser = null;
  localStorage.removeItem('token');
  if (ws) ws.close();
  showScreen('auth-screen');
}

/* ─── INIT APP ──────────────────────────────────────── */
async function initApp() {
  try {
    currentUser = await api('GET', '/auth/me');
    document.getElementById('user-name').textContent = currentUser.username;
    document.getElementById('user-avatar').textContent = currentUser.username[0].toUpperCase();
    showScreen('app-screen');
    await loadWorkspaces();
    showView('files');
  } catch (e) {
    logout();
  }
}

/* ─── WORKSPACES ────────────────────────────────────── */
async function loadWorkspaces() {
  const data = await api('GET', '/workspaces');
  const workspaces = data.workspaces || [];

  // populate grid
  const grid = document.getElementById('workspaces-grid');
  if (workspaces.length === 0) {
    grid.innerHTML = '<div class="ws-empty">No workspaces yet. Create one to get started.</div>';
  } else {
    grid.innerHTML = workspaces.map(w => `
      <div class="ws-card" data-ws-id="${w.workspace_id}">
        <div class="ws-card-top">
          <div class="ws-card-icon">🏢</div>
          <span class="ws-role-badge ${w.role}">${w.role}</span>
        </div>
        <div>
          <div class="ws-card-name">${w.workspace_name}</div>
          <div class="ws-card-id">ID: ${w.workspace_id}</div>
        </div>
        <div class="ws-card-actions">
          <button class="btn-file-action" onclick="openAddMember(${w.workspace_id}, '${w.workspace_name}')">+ Member</button>
        </div>
      </div>
    `).join('');
  }

  // populate workspace selects
  const wsSelect = document.getElementById('workspace-select');
  const searchWsSelect = document.getElementById('search-workspace-select');

  wsSelect.innerHTML = '<option value="">— select workspace —</option>';
  searchWsSelect.innerHTML = '<option value="">All workspaces</option>';

  workspaces.forEach(w => {
    wsSelect.innerHTML += `<option value="${w.workspace_id}">${w.workspace_name}</option>`;
    searchWsSelect.innerHTML += `<option value="${w.workspace_id}">${w.workspace_name}</option>`;
  });

  return workspaces;
}

async function createWorkspace() {
  const name = document.getElementById('ws-name-input').value.trim();
  const errEl = document.getElementById('ws-error');
  errEl.textContent = '';

  if (!name) { errEl.textContent = 'Workspace name is required'; return; }

  try {
    await api('POST', '/workspaces', { workspace_name: name });
    closeModals();
    document.getElementById('ws-name-input').value = '';
    await loadWorkspaces();
    toast('Workspace created!', 'success');
  } catch (e) {
    errEl.textContent = e.message;
  }
}

function openAddMember(wsId, wsName) {
  memberTargetWsId = wsId;
  document.getElementById('member-panel-ws-name').textContent = wsName;
  document.getElementById('member-panel').style.display = 'flex';
  document.getElementById('member-panel').style.flexDirection = 'column';
}

async function addMember() {
  const userId = parseInt(document.getElementById('member-user-id').value);
  const role = document.getElementById('member-role').value;
  const errEl = document.getElementById('member-error');
  errEl.textContent = '';

  if (!userId) { errEl.textContent = 'User ID is required'; return; }

  try {
    await api('POST', `/workspaces/${memberTargetWsId}/members`, { user_id: userId, role });
    toast('Member added!', 'success');
    document.getElementById('member-user-id').value = '';
    document.getElementById('member-panel').style.display = 'none';
  } catch (e) {
    errEl.textContent = e.message;
  }
}

/* ─── FOLDERS ───────────────────────────────────────── */
async function loadFolders(workspaceId) {
  // There's no GET /folders endpoint so we track created folders
  // For demo purposes, load from localStorage per workspace
  const saved = JSON.parse(localStorage.getItem(`folders_${workspaceId}`) || '[]');
  const folderSelect = document.getElementById('folder-select');
  folderSelect.innerHTML = '<option value="">— select folder —</option>';
  saved.forEach(f => {
    folderSelect.innerHTML += `<option value="${f.folder_id}">${f.folder_name}</option>`;
  });
}

async function createFolder() {
  const name = document.getElementById('folder-name-input').value.trim();
  const wsId = document.getElementById('workspace-select').value;
  const errEl = document.getElementById('folder-error');
  errEl.textContent = '';

  if (!name) { errEl.textContent = 'Folder name is required'; return; }
  if (!wsId) { errEl.textContent = 'Select a workspace first'; return; }

  try {
    const data = await api('POST', '/folders', { folder_name: name, workspace_id: parseInt(wsId) });
    
    // save to localStorage for UI
    const saved = JSON.parse(localStorage.getItem(`folders_${wsId}`) || '[]');
    saved.push({ folder_id: data.folder_id, folder_name: data.folder_name });
    localStorage.setItem(`folders_${wsId}`, JSON.stringify(saved));

    closeModals();
    document.getElementById('folder-name-input').value = '';
    await loadFolders(wsId);
    toast('Folder created!', 'success');
  } catch (e) {
    errEl.textContent = e.message;
  }
}

/* ─── FILES ─────────────────────────────────────────── */
async function loadFiles() {
  const wsId = document.getElementById('workspace-select').value;
  const folderId = document.getElementById('folder-select').value;
  const tbody = document.getElementById('files-tbody');
  const breadcrumb = document.getElementById('files-breadcrumb');

  if (!wsId || !folderId) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="4">Select a workspace and folder to see files</td></tr>';
    return;
  }

  breadcrumb.textContent = `workspace ${wsId} / folder ${folderId}`;
  tbody.innerHTML = '<tr class="empty-row"><td colspan="4"><div class="spinner"></div></td></tr>';

  try {
    const data = await api('GET', `/workspaces/${wsId}/files?folder_id=${folderId}`);
    const files = data.files || [];

    if (files.length === 0) {
      tbody.innerHTML = '<tr class="empty-row"><td colspan="4">No files yet. Upload something!</td></tr>';
      return;
    }

    tbody.innerHTML = files.map(f => `
      <tr>
        <td>
          <div class="file-name-cell">
            <div class="file-icon">${fileIcon(f.filename)}</div>
            <span class="file-name-text">${f.filename}</span>
          </div>
        </td>
        <td><span class="file-date">${formatDate(f.uploaded_at)}</span></td>
        <td><span class="file-mime">${f.mime_type || '—'}</span></td>
        <td>
          <div class="file-actions">
            <button class="btn-file-action" onclick="downloadFile('${f.file_id}', '${f.filename}')">↓ Download</button>
            <button class="btn-file-action danger" onclick="deleteFile('${f.file_id}')">Delete</button>
          </div>
        </td>
      </tr>
    `).join('');

    // connect WebSocket for live updates
    connectWS(wsId);
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="4">${e.message}</td></tr>`;
  }
}

async function downloadFile(fileId, filename) {
  try {
    const res = await fetch(`${API}/files/${fileId}/download`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) throw new Error('Download failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    toast(`Downloaded ${filename}`, 'success');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function deleteFile(fileId) {
  if (!confirm('Delete this file?')) return;
  try {
    await api('DELETE', `/files/${fileId}/delete`);
    toast('File deleted', 'success');
    await loadFiles();
  } catch (e) {
    toast(e.message, 'error');
  }
}

/* ─── CHUNKED UPLOAD ────────────────────────────────── */
async function uploadFile(file) {
  const wsId = document.getElementById('workspace-select').value;
  const folderId = document.getElementById('folder-select').value;

  if (!wsId || !folderId) {
    toast('Select a workspace and folder first', 'error');
    return;
  }

  // create progress item
  const progressList = document.getElementById('upload-progress-list');
  const itemId = `upload-${Date.now()}`;
  progressList.innerHTML += `
    <div class="upload-progress-item" id="${itemId}">
      <div class="upload-progress-name">${file.name}</div>
      <div class="upload-progress-bar-wrap">
        <div class="upload-progress-bar" id="bar-${itemId}" style="width:0%"></div>
      </div>
      <div class="upload-progress-status" id="status-${itemId}">Starting...</div>
    </div>
  `;

  const bar = document.getElementById(`bar-${itemId}`);
  const status = document.getElementById(`status-${itemId}`);

  function setProgress(pct, label) {
    bar.style.width = `${pct}%`;
    status.textContent = label;
  }

  try {
    // STEP 1: init
    setProgress(5, 'Initializing...');
    const initData = await api('POST',
      `/files/upload/init?filename=${encodeURIComponent(file.name)}&workspace_id=${wsId}&folder_id=${folderId}`
    );
    const uploadId = initData.upload_id;

    // STEP 2: split into chunks and upload
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
    for (let i = 0; i < totalChunks; i++) {
      const start = i * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, file.size);
      const chunk = file.slice(start, end);

      const formData = new FormData();
      formData.append('chunk', chunk, file.name);

      await fetch(`${API}/files/upload/${uploadId}/chunk/${i + 1}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });

      const pct = Math.round(((i + 1) / totalChunks) * 80) + 10;
      setProgress(pct, `Chunk ${i + 1}/${totalChunks}`);
    }

    // STEP 3: complete
    setProgress(95, 'Finalizing...');
    await api('POST', `/files/upload/${uploadId}/complete`);

    setProgress(100, 'Done ✓');
    status.className = 'upload-progress-status done';
    toast(`${file.name} uploaded!`, 'success');

    // refresh files list
    await loadFiles();

    // remove progress item after delay
    setTimeout(() => {
      document.getElementById(itemId)?.remove();
    }, 3000);

  } catch (e) {
    status.textContent = 'Failed';
    status.className = 'upload-progress-status error';
    toast(`Upload failed: ${e.message}`, 'error');
  }
}

/* ─── SEARCH ────────────────────────────────────────── */
async function search() {
  const query = document.getElementById('search-input').value.trim();
  const wsId = document.getElementById('search-workspace-select').value;
  const resultsEl = document.getElementById('search-results');

  if (!query) { toast('Enter a search query', 'error'); return; }

  resultsEl.innerHTML = `
    <div class="search-empty">
      <div class="spinner" style="width:28px;height:28px;border-width:3px;margin-bottom:12px;"></div>
      <p style="color:var(--text2)">Searching with AI...</p>
    </div>
  `;

  try {
    const params = new URLSearchParams({ query });
    if (wsId) params.append('workspace_id', wsId);

    const data = await api('GET', `/search?${params}`);
    const results = data.results || [];

    if (results.length === 0) {
      resultsEl.innerHTML = `
        <div class="search-empty">
          <div class="search-empty-icon">◎</div>
          <p>No results found</p>
          <span>Try different keywords or upload more files</span>
        </div>
      `;
      return;
    }

    resultsEl.innerHTML = results.map((r, i) => `
      <div class="search-result-item" style="animation-delay:${i * 0.05}s">
        <div class="search-result-icon">${fileIcon(r.filename)}</div>
        <div class="search-result-info">
          <div class="search-result-name">${r.filename}</div>
          <div class="search-result-meta">ID: ${r.file_id}</div>
        </div>
        <div class="similarity-badge">${Math.round(r.similarity * 100)}% match</div>
      </div>
    `).join('');

  } catch (e) {
    resultsEl.innerHTML = `
      <div class="search-empty">
        <p style="color:var(--danger)">${e.message}</p>
      </div>
    `;
  }
}

/* ─── WEBSOCKET ─────────────────────────────────────── */
function connectWS(workspaceId) {
  if (ws) ws.close();
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/workspace/${workspaceId}`);

  ws.onopen = () => console.log('WS connected');

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.event === 'file_uploaded') {
      toast(`📁 ${data.filename} uploaded by ${data.uploaded_by}`, 'info');
      loadFiles();
    } else if (data.event === 'file_deleted') {
      toast(`🗑 File deleted`, 'info');
      loadFiles();
    }
  };

  ws.onerror = () => console.warn('WS error');
  ws.onclose = () => console.log('WS closed');
}

/* ─── EVENT LISTENERS ───────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {

  // auth tabs
  document.querySelectorAll('.auth-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.auth-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`panel-${tab.dataset.tab}`).classList.add('active');
    });
  });

  // auth buttons
  document.getElementById('btn-login').addEventListener('click', login);
  document.getElementById('btn-register').addEventListener('click', register);
  document.getElementById('btn-logout').addEventListener('click', logout);

  // enter key on auth inputs
  ['login-email', 'login-password'].forEach(id => {
    document.getElementById(id).addEventListener('keydown', e => {
      if (e.key === 'Enter') login();
    });
  });
  ['reg-username', 'reg-email', 'reg-password'].forEach(id => {
    document.getElementById(id).addEventListener('keydown', e => {
      if (e.key === 'Enter') register();
    });
  });

  // nav
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => showView(item.dataset.view));
  });

  // workspace select
  document.getElementById('workspace-select').addEventListener('change', async (e) => {
    const wsId = e.target.value;
    currentWorkspaceId = wsId;
    if (wsId) {
      await loadFolders(wsId);
    } else {
      document.getElementById('folder-select').innerHTML = '<option value="">— select folder —</option>';
    }
    await loadFiles();
  });

  document.getElementById('folder-select').addEventListener('change', loadFiles);
  document.getElementById('btn-refresh-files').addEventListener('click', loadFiles);

  // upload zone
  const uploadZone = document.getElementById('upload-zone');
  const fileInput = document.getElementById('file-input');

  uploadZone.addEventListener('click', () => fileInput.click());
  uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
  });
  uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
  uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    Array.from(e.dataTransfer.files).forEach(uploadFile);
  });

  fileInput.addEventListener('change', () => {
    Array.from(fileInput.files).forEach(uploadFile);
    fileInput.value = '';
  });

  document.getElementById('btn-upload-trigger').addEventListener('click', () => fileInput.click());

  // workspace buttons
  document.getElementById('btn-new-workspace').addEventListener('click', () => showModal('workspace'));
  document.getElementById('btn-create-workspace').addEventListener('click', createWorkspace);

  // folder buttons
  document.getElementById('btn-new-folder').addEventListener('click', () => showModal('folder'));
  document.getElementById('btn-create-folder').addEventListener('click', createFolder);

  // member panel
  document.getElementById('btn-add-member').addEventListener('click', addMember);
  document.getElementById('btn-close-member-panel').addEventListener('click', () => {
    document.getElementById('member-panel').style.display = 'none';
  });

  // search
  document.getElementById('btn-search').addEventListener('click', search);
  document.getElementById('search-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') search();
  });

  // close modals
  document.getElementById('modal-overlay').addEventListener('click', (e) => {
    if (e.target === document.getElementById('modal-overlay')) closeModals();
  });
  document.querySelectorAll('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', closeModals);
  });

  // enter on modals
  document.getElementById('ws-name-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') createWorkspace();
  });
  document.getElementById('folder-name-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') createFolder();
  });

  // check if already logged in
  if (token) {
    initApp();
  } else {
    showScreen('auth-screen');
  }
});

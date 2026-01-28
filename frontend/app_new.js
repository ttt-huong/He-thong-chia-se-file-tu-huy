const API_URL = 'http://localhost:5000/api';
const HEALTH_URL = 'http://localhost:5000/health';

let uploadedFiles = [];

// --- UPLOAD LOGIC ---
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const uploadStatus = document.getElementById('uploadStatus');
const downloadLimit = document.getElementById('downloadLimit');
const ttlSeconds = document.getElementById('ttlSeconds');

uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        fileInput.files = files;
        uploadBtn.disabled = false;
    }
});

fileInput.addEventListener('change', () => {
    uploadBtn.disabled = fileInput.files.length === 0;
    if (fileInput.files.length > 0) {
        const fileName = fileInput.files[0].name;
        uploadZone.querySelector('.upload-text').textContent = `✅ ${fileName}`;
    }
});

uploadBtn.addEventListener('click', async () => {
    if (fileInput.files.length === 0) return;
    
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Uploading...';
    showStatus('loading', '⏳ Đang upload...');
    
    try {
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('download_limit', downloadLimit.value);
        formData.append('ttl_seconds', ttlSeconds.value);
        
        const response = await fetch(`${API_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showStatus('success', `✅ Upload thành công! File ID: ${data.file_id.substring(0, 8)}...`);
            showToast('success', 'File uploaded successfully!');
            fileInput.value = '';
            uploadZone.querySelector('.upload-text').textContent = 'Kéo thả file hoặc click để chọn';
            loadFilesGallery();
        } else {
            showStatus('error', `❌ ${data.error || 'Upload failed'}`);
            showToast('error', data.error || 'Upload failed');
        }
    } catch (error) {
        showStatus('error', `❌ Lỗi: ${error.message}`);
        showToast('error', `Network error: ${error.message}`);
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Upload File';
    }
});

function showStatus(type, message) {
    uploadStatus.className = `status show ${type}`;
    uploadStatus.textContent = message;
    setTimeout(() => {
        uploadStatus.classList.remove('show');
    }, 5000);
}

// --- HEALTH CHECK ---
async function loadHealth() {
    try {
        const response = await fetch(HEALTH_URL);
        const data = await response.json();
        
        const healthStatus = document.getElementById('healthStatus');
        const components = data.components || {};
        
        const healthMap = {
            'database': { label: 'Database', icon: '💾' },
            'redis': { label: 'Redis', icon: '🔴' },
            'rabbitmq': { label: 'RabbitMQ', icon: '🐰' }
        };
        
        let html = '';
        for (const [key, info] of Object.entries(healthMap)) {
            const status = components[key] === 'ok' ? 'ok' : 'error';
            const statusText = components[key] === 'ok' ? 'Online' : 'Offline';
            html += `
                <div class="health-item ${status}">
                    <div class="health-icon">${info.icon}</div>
                    <div class="health-label">${info.label}</div>
                    <div class="health-status">${statusText}</div>
                </div>
            `;
        }
        
        healthStatus.innerHTML = html;
        document.getElementById('lastUpdate').textContent = `Last update: ${new Date().toLocaleTimeString()}`;
    } catch (error) {
        console.error('Health check error:', error);
        document.getElementById('healthStatus').innerHTML = '<div class="error-text">Cannot connect to server</div>';
    }
}

document.getElementById('refreshHealth').addEventListener('click', loadHealth);

// --- NODES ---
async function loadNodes() {
    try {
        const response = await fetch(`${API_URL}/nodes`);
        const data = await response.json();
        
        const nodesGrid = document.getElementById('nodesGrid');
        nodesGrid.innerHTML = '';
        
        data.nodes.forEach(node => {
            const isOnline = node.is_online;
            const nodeEl = document.createElement('div');
            nodeEl.className = `node-card ${isOnline ? 'online' : 'offline'}`;
            nodeEl.innerHTML = `
                <div class="node-header">
                    <span class="node-name">${node.node_id}</span>
                    <span class="node-badge ${isOnline ? 'badge-success' : 'badge-error'}">
                        ${isOnline ? '🟢 Online' : '🔴 Offline'}
                    </span>
                </div>
                <div class="node-stats">
                    <div class="node-stat">
                        <span class="stat-label">Files:</span>
                        <span class="stat-value">${node.file_count}</span>
                    </div>
                    <div class="node-stat">
                        <span class="stat-label">Free:</span>
                        <span class="stat-value">${node.available_space_gb} GB</span>
                    </div>
                </div>
                <div class="node-endpoint">${node.host}:${node.port}</div>
            `;
            nodesGrid.appendChild(nodeEl);
        });
    } catch (error) {
        console.error('Nodes error:', error);
    }
}

// --- FILES GALLERY (MASONRY) ---
async function loadFilesGallery() {
    try {
        const response = await fetch(`${API_URL}/files`);
        const data = await response.json();
        
        const gallery = document.getElementById('filesGallery');
        const stats = document.getElementById('galleryStats');
        
        stats.textContent = `${data.count} files`;
        
        if (data.files.length === 0) {
            gallery.innerHTML = '<div class="empty-state">📭 No files yet. Upload your first image!</div>';
            return;
        }
        
        gallery.innerHTML = '';
        
        data.files.forEach(file => {
            const card = document.createElement('div');
            card.className = 'file-card';
            
            const bgColor = file.color_hex || '#e0e0e0';
            const width = file.width || 400;
            const height = file.height || 300;
            const aspectRatio = height / width;
            
            card.style.backgroundColor = bgColor;
            card.style.paddingBottom = `${aspectRatio * 100}%`;
            
            const downloadUrl = `${API_URL}/download/${file.file_id}`;
            
            card.innerHTML = `
                <div class="file-overlay">
                    <div class="file-info">
                        <div class="file-name">${file.original_name}</div>
                        <div class="file-meta">
                            ${width} × ${height} • ${(file.file_size / 1024).toFixed(1)} KB
                        </div>
                        <div class="file-badges">
                            ${file.is_compressed ? '<span class="badge badge-success">Compressed</span>' : ''}
                            ${file.has_thumbnail ? '<span class="badge badge-info">Thumbnail</span>' : ''}
                        </div>
                    </div>
                    <div class="file-actions">
                        <a href="${downloadUrl}" class="btn-small btn-primary" download>Download</a>
                        <button class="btn-small btn-secondary" onclick="copyLink('${downloadUrl}')">Copy Link</button>
                    </div>
                </div>
            `;
            
            gallery.appendChild(card);
        });
    } catch (error) {
        console.error('Gallery error:', error);
    }
}

function copyLink(url) {
    navigator.clipboard.writeText(url);
    showToast('success', 'Link copied to clipboard!');
}

// --- TOAST NOTIFICATIONS ---
function showToast(type, message) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icons = {
        success: '✅',
        error: '❌',
        info: 'ℹ️',
        warning: '⚠️'
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 10);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// --- INIT ---
loadHealth();
loadNodes();
loadFilesGallery();

setInterval(loadHealth, 10000);
setInterval(loadNodes, 15000);
setInterval(loadFilesGallery, 20000);

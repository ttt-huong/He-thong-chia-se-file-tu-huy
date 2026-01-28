const API_URL = 'http://localhost:5000/api';

// Upload handling
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const downloadLimit = document.getElementById('downloadLimit');
const uploadStatus = document.getElementById('uploadStatus');

uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        fileInput.files = files;
        uploadBtn.disabled = false;
    }
});

fileInput.addEventListener('change', () => {
    uploadBtn.disabled = fileInput.files.length === 0;
});

uploadBtn.addEventListener('click', async () => {
    if (fileInput.files.length === 0) return;
    
    uploadBtn.disabled = true;
    showStatus('loading', 'Đang upload...');
    
    try {
        const file = fileInput.files[0];
        // Nếu file lớn hơn 5MB thì dùng chunked upload để demo phân mảnh
        if (file.size > 5 * 1024 * 1024) {
            await uploadInChunks(file);
        } else {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('download_limit', downloadLimit.value);
            const response = await fetch(`${API_URL}/upload`, { method: 'POST', body: formData });
            if (response.ok) {
                const data = await response.json();
                showStatus('success', `✅ Upload thành công! File ID: ${data.file_id.substring(0, 8)}...`);
                fileInput.value = '';
                uploadBtn.disabled = true;
                loadFileList();
            } else {
                showStatus('error', '❌ Upload thất bại. Vui lòng thử lại.');
            }
        }
    } catch (error) {
        showStatus('error', `❌ Lỗi: ${error.message}`);
    }
    
    uploadBtn.disabled = false;
});

function showStatus(type, message) {
    uploadStatus.className = `status show ${type}`;
    uploadStatus.textContent = message;
}

// Load data
async function loadData() {
    await Promise.all([
        loadHealthCheck(),
        loadNodes(),
        loadFileList()
    ]);
}

async function loadHealthCheck() {
    try {
        const response = await fetch(`${API_URL.replace('/api', '')}/health`);
        if (response.ok) {
            const data = await response.json();
            const status = data.status === 'healthy';
            document.getElementById('healthStatus').innerHTML = status ?
                '<p>✅ <strong>System Healthy</strong></p><p style="font-size:12px; margin-top:10px;">DB: OK | Redis: OK</p>' :
                '<p>❌ <strong>System Unhealthy</strong></p>';
        }
    } catch (error) {
        document.getElementById('healthStatus').innerHTML = '<p>❌ Cannot connect to server</p>';
    }
}

async function loadNodes() {
    try {
        const response = await fetch(`${API_URL}/nodes`);
        const data = await response.json();
        
        const nodesGrid = document.getElementById('nodesGrid');
        nodesGrid.innerHTML = '';
        
        data.nodes.forEach(node => {
            const isOnline = node.is_online;
            const nodeHtml = `
                <div class="node-card ${isOnline ? 'online' : 'offline'}">
                    <div class="node-name">${node.node_id}</div>
                    <div class="node-status">
                        <span class="status-indicator ${isOnline ? 'online' : 'offline'}"></span>
                        ${isOnline ? 'Online' : 'Offline'}
                    </div>
                    <div class="node-info">
                        <div>📦 ${node.file_count} files</div>
                        <div>💾 ${node.available_space_gb}GB free</div>
                        <div>🖥️ ${node.host}:${node.port}</div>
                    </div>
                </div>
            `;
            nodesGrid.innerHTML += nodeHtml;
        });
    } catch (error) {
        console.error('Error loading nodes:', error);
    }
}

async function loadFileList() {
    try {
        const res = await fetch(`${API_URL}/files`);
        if (!res.ok) return;
        const data = await res.json();
        const gallery = document.getElementById('gallery');
        gallery.innerHTML = '';

        data.files.forEach(item => {
            const w = item.width || 300;
            const h = item.height ? Math.round((item.height / (item.width || 1)) * 300) : 200;
            const color = item.color_hex || '#e0e0e0';

            const wrapper = document.createElement('div');
            wrapper.className = 'masonry-item';

            const placeholder = document.createElement('div');
            placeholder.className = 'placeholder';
            placeholder.style.background = color;
            placeholder.style.height = `${h}px`;
            wrapper.appendChild(placeholder);

            const img = new Image();
            img.className = 'image-loaded';
            img.style.display = 'none';
            img.style.borderRadius = '6px';
            img.src = `${API_URL.replace('/api','')}${item.download_url}`;
            img.onload = () => { img.style.display = 'block'; };
            wrapper.appendChild(img);

            const badge = document.createElement('div');
            badge.className = item.has_thumbnail || item.is_compressed ? 'ready-badge' : 'processing-badge';
            badge.textContent = item.has_thumbnail || item.is_compressed ? '🟢 Sẵn sàng' : '🟡 Đang xử lý...';
            wrapper.appendChild(badge);

            const dbg = document.createElement('div');
            dbg.className = 'debug-info';
            dbg.innerHTML = `Ảnh: ${item.original_name}<br>
                Size: ${(item.file_size/1024/1024).toFixed(2)} MB${item.is_compressed ? ` → (Đã nén)` : ''}<br>
                Lưu tại: ${item.primary_node}<br>`;
            wrapper.appendChild(dbg);

            gallery.appendChild(wrapper);

            // Polling status mỗi 2s cho đến khi sẵn sàng
            if (!(item.has_thumbnail || item.is_compressed)) {
                const interval = setInterval(async () => {
                    try {
                        const infoRes = await fetch(`${API_URL}/files/${item.file_id}`);
                        if (infoRes.ok) {
                            const info = await infoRes.json();
                            if (info.has_thumbnail || info.is_compressed) {
                                badge.className = 'ready-badge';
                                badge.textContent = '🟢 Sẵn sàng';
                                clearInterval(interval);
                            }
                        }
                    } catch {}
                }, 2000);
            }
        });

        // Refresh every 10s
        setTimeout(loadFileList, 10000);
    } catch (error) {
        console.error('Error loading files:', error);
    }
}

// Initial load
loadData();

// Refresh every 10 seconds
setInterval(loadData, 10000);

// =========================
// Chunked Upload (Demo phân mảnh)
// =========================

async function uploadInChunks(file) {
    try {
        const chunkSize = 5 * 1024 * 1024; // 5MB
        const totalParts = Math.ceil(file.size / chunkSize);
        const initRes = await fetch(`${API_URL}/chunk/init`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: file.name, size: file.size, mime_type: file.type, chunk_size: chunkSize })
        });
        if (!initRes.ok) {
            showStatus('error', '❌ Không khởi tạo được phiên upload theo chunk');
            return;
        }
        const initData = await initRes.json();
        const uploadId = initData.upload_id;

        showStatus('loading', `🔹 Bắt đầu phân mảnh: ${totalParts} phần`);
        const progressBar = document.getElementById('progressBar');
        progressBar.style.width = '0%';

        let sent = 0;
        for (let part = 0; part < totalParts; part++) {
            const start = part * chunkSize;
            const end = Math.min(start + chunkSize, file.size);
            const blob = file.slice(start, end);
            const buf = await blob.arrayBuffer();
            const bytes = new Uint8Array(buf);

            let res = await fetch(`${API_URL}/chunk/upload?upload_id=${uploadId}&part_number=${part + 1}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/octet-stream' },
                body: bytes
            });
            if (!res.ok) {
                // Retry once for robustness
                res = await fetch(`${API_URL}/chunk/upload?upload_id=${uploadId}&part_number=${part + 1}`, {
                    method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: bytes
                });
                if (!res.ok) {
                    showStatus('error', `❌ Lỗi ở phần ${part + 1}`);
                    return;
                }
            }
            const data = await res.json();
            sent = data.received;
            const pct = Math.round((sent / totalParts) * 100);
            showStatus('loading', `📦 Đã gửi ${sent}/${totalParts} phần (${pct}%)`);
            progressBar.style.width = `${pct}%`;
        }

        // Hoàn tất và ghép file
        const completeRes = await fetch(`${API_URL}/chunk/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ upload_id: uploadId, download_limit: Number(downloadLimit.value) })
        });

        if (!completeRes.ok) {
            showStatus('error', '❌ Ghép file thất bại');
            return;
        }
        const finalData = await completeRes.json();
        showStatus('success', `✅ Chunked upload xong! File ID: ${finalData.file_id.substring(0, 8)}...`);
        document.getElementById('progressBar').style.width = '100%';
        fileInput.value = '';
        uploadBtn.disabled = true;
        loadFileList();
    } catch (e) {
        showStatus('error', `❌ Lỗi chunked upload: ${e.message}`);
    }
}

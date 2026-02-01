// ==========================================
// File Management API & UI
// ==========================================

const API_BASE = 'http://localhost:5000/api';

/**
 * Upload file
 */
async function uploadFile(file, isPublic = false) {
    const token = getToken();
    if (!token) {
        showAlert('Phiên đăng nhập hết hạn', 'error');
        return null;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('is_public', isPublic ? 'true' : 'false');

    try {
        const response = await fetch(`${API_BASE}/files/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            return data.file;
        } else {
            const error = await response.json();
            showAlert(error.message || 'Upload thất bại', 'error');
            return null;
        }
    } catch (error) {
        console.error('Upload error:', error);
        showAlert('Lỗi upload: ' + error.message, 'error');
        return null;
    }
}

/**
 * Get user files and public files
 */
async function getFiles() {
    const token = getToken();
    if (!token) {
        showAlert('Phiên đăng nhập hết hạn', 'error');
        return [];
    }

    try {
        const response = await fetch(`${API_BASE}/files`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const data = await response.json();
            return data.files || [];
        } else if (response.status === 401) {
            showSessionExpiredAlert();
            return [];
        } else {
            const error = await response.json();
            console.error('Get files error:', error);
            return [];
        }
    } catch (error) {
        console.error('Get files error:', error);
        showAlert('Lỗi tải danh sách file: ' + error.message, 'error');
        return [];
    }
}

/**
 * Delete file
 */
async function deleteFile(fileId) {
    const token = getToken();
    if (!token) {
        showAlert('Phiên đăng nhập hết hạn', 'error');
        return false;
    }

    try {
        const response = await fetch(`${API_BASE}/files/${fileId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            return true;
        } else if (response.status === 401) {
            showSessionExpiredAlert();
            return false;
        } else {
            const error = await response.json();
            showAlert(error.message || 'Xóa file thất bại', 'error');
            return false;
        }
    } catch (error) {
        console.error('Delete error:', error);
        showAlert('Lỗi xóa file: ' + error.message, 'error');
        return false;
    }
}

/**
 * Toggle file public/private
 */
async function toggleFilePermissions(fileId, isPublic) {
    const token = getToken();
    if (!token) {
        showAlert('Phiên đăng nhập hết hạn', 'error');
        return false;
    }

    try {
        const response = await fetch(`${API_BASE}/files/${fileId}/permissions`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                is_public: isPublic
            })
        });

        if (response.ok) {
            return true;
        } else if (response.status === 401) {
            showSessionExpiredAlert();
            return false;
        } else {
            const error = await response.json();
            showAlert(error.message || 'Cập nhật quyền thất bại', 'error');
            return false;
        }
    } catch (error) {
        console.error('Toggle permissions error:', error);
        showAlert('Lỗi cập nhật quyền: ' + error.message, 'error');
        return false;
    }
}

/**
 * Get file info (for download)
 */
async function getFileInfo(fileId) {
    const token = getToken();
    if (!token) {
        return null;
    }

    try {
        const response = await fetch(`${API_BASE}/files/${fileId}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('Get file info error:', error);
        return null;
    }
}

/**
 * Display file list
 */
async function displayFileList() {
    const files = await getFiles();
    const user = getCurrentUser();
    
    if (!files || files.length === 0) {
        const emptyMsg = document.getElementById('emptyMessage');
        if (emptyMsg) {
            emptyMsg.style.display = 'block';
        }
        return;
    }

    const container = document.getElementById('fileListContainer');
    if (!container) return;

    container.innerHTML = '';

    files.forEach(file => {
        const isOwner = file.user_id === user.userId;
        const fileCard = createFileCard(file, isOwner);
        container.appendChild(fileCard);
    });
}

/**
 * Create file card element
 */
function createFileCard(file, isOwner) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.cssText = `
        background: white;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-left: 4px solid ${isOwner ? '#4CAF50' : '#2196F3'};
    `;

    const fileInfo = document.createElement('div');
    fileInfo.style.cssText = 'flex: 1; margin-right: 20px;';
    fileInfo.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="fa-solid fa-file" style="font-size: 24px; color: #666;"></i>
            <div style="flex: 1;">
                <div style="font-weight: 600; color: #333; margin-bottom: 4px;">
                    ${escapeHtml(file.original_name || file.filename)}
                </div>
                <div style="font-size: 12px; color: #999;">
                    <span>${formatFileSize(file.size || 0)}</span>
                    <span style="margin: 0 8px;">•</span>
                    <span>${formatDate(file.created_at)}</span>
                    <span style="margin: 0 8px;">•</span>
                    <span>${file.is_public ? '🌍 Công khai' : '🔒 Riêng tư'}</span>
                    ${isOwner ? '' : `<span style="margin: 0 8px;">•</span><span>👤 ${escapeHtml(file.owner_username || 'Unknown')}</span>`}
                </div>
            </div>
        </div>
    `;

    const actions = document.createElement('div');
    actions.style.cssText = 'display: flex; gap: 8px; align-items: center;';

    // Download button
    const downloadBtn = document.createElement('button');
    downloadBtn.innerHTML = '<i class="fa-solid fa-download"></i>';
    downloadBtn.title = 'Tải xuống';
    downloadBtn.style.cssText = `
        padding: 8px 12px;
        background: #2196F3;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background 0.3s;
    `;
    downloadBtn.onmouseover = () => downloadBtn.style.background = '#1976D2';
    downloadBtn.onmouseout = () => downloadBtn.style.background = '#2196F3';
    downloadBtn.onclick = () => downloadFile(file.id, file.original_name || file.filename);
    actions.appendChild(downloadBtn);

    // Owner-only actions
    if (isOwner) {
        // Toggle permission button
        const toggleBtn = document.createElement('button');
        toggleBtn.innerHTML = file.is_public ? '<i class="fa-solid fa-lock-open"></i>' : '<i class="fa-solid fa-lock"></i>';
        toggleBtn.title = file.is_public ? 'Chuyển về riêng tư' : 'Chuyển về công khai';
        toggleBtn.style.cssText = `
            padding: 8px 12px;
            background: #FF9800;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.3s;
        `;
        toggleBtn.onmouseover = () => toggleBtn.style.background = '#F57C00';
        toggleBtn.onmouseout = () => toggleBtn.style.background = '#FF9800';
        toggleBtn.onclick = async () => {
            toggleBtn.disabled = true;
            const newStatus = !file.is_public;
            if (await toggleFilePermissions(file.id, newStatus)) {
                file.is_public = newStatus;
                toggleBtn.innerHTML = newStatus ? '<i class="fa-solid fa-lock-open"></i>' : '<i class="fa-solid fa-lock"></i>';
                toggleBtn.title = newStatus ? 'Chuyển về riêng tư' : 'Chuyển về công khai';
                showAlert(newStatus ? 'Đã chuyển về công khai' : 'Đã chuyển về riêng tư', 'success');
            }
            toggleBtn.disabled = false;
        };
        actions.appendChild(toggleBtn);

        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
        deleteBtn.title = 'Xóa file';
        deleteBtn.style.cssText = `
            padding: 8px 12px;
            background: #f44336;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.3s;
        `;
        deleteBtn.onmouseover = () => deleteBtn.style.background = '#da190b';
        deleteBtn.onmouseout = () => deleteBtn.style.background = '#f44336';
        deleteBtn.onclick = async () => {
            if (confirm('Bạn chắc chắn muốn xóa file này?')) {
                deleteBtn.disabled = true;
                if (await deleteFile(file.id)) {
                    card.remove();
                    showAlert('File đã được xóa', 'success');
                } else {
                    deleteBtn.disabled = false;
                }
            }
        };
        actions.appendChild(deleteBtn);
    }

    card.appendChild(fileInfo);
    card.appendChild(actions);
    return card;
}

/**
 * Download file
 */
function downloadFile(fileId, filename) {
    const token = getToken();
    if (!token) {
        showAlert('Phiên đăng nhập hết hạn', 'error');
        return;
    }

    // Create download link
    const link = document.createElement('a');
    link.href = `${API_BASE}/files/${fileId}?token=${token}`;
    link.download = filename || 'file';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * Utility: Format file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Utility: Format date
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Vừa xong';
    if (diffMins < 60) return `${diffMins} phút trước`;
    if (diffHours < 24) return `${diffHours} giờ trước`;
    if (diffDays < 7) return `${diffDays} ngày trước`;
    
    return date.toLocaleDateString('vi-VN');
}

/**
 * Utility: Escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show alert
 */
function showAlert(message, type = 'info') {
    const alert = document.createElement('div');
    alert.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 20px;
        border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        font-weight: 500;
        max-width: 400px;
        word-wrap: break-word;
    `;

    if (type === 'error') {
        alert.style.backgroundColor = '#ffebee';
        alert.style.color = '#c62828';
        alert.style.borderLeft = '4px solid #d32f2f';
    } else if (type === 'success') {
        alert.style.backgroundColor = '#e8f5e9';
        alert.style.color = '#2e7d32';
        alert.style.borderLeft = '4px solid #4CAF50';
    } else {
        alert.style.backgroundColor = '#e3f2fd';
        alert.style.color = '#1565c0';
        alert.style.borderLeft = '4px solid #2196F3';
    }

    alert.textContent = message;
    document.body.appendChild(alert);

    setTimeout(() => {
        alert.remove();
    }, 4000);
}

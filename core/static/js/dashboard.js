let currentGraphBase64 = '';
let currentGraphTitle = '';
let isZoomed = false;
function openGraphModal(base64Image, title) {
    currentGraphBase64 = base64Image;
    currentGraphTitle = title;
    
    const modalImage = document.getElementById('modalGraphImage');
    const modalLabel = document.getElementById('graphModalLabel');
    
    modalImage.src = `data:image/png;base64,${base64Image}`;
    modalLabel.textContent = title;
    modalImage.classList.remove('zoomed');
    isZoomed = false;
    
    const modal = new bootstrap.Modal(document.getElementById('graphModal'));
    modal.show();
}
function toggleZoom() {
    const modalImage = document.getElementById('modalGraphImage');
    modalImage.classList.toggle('zoomed');
    isZoomed = !isZoomed;
    
    const zoomButton = document.querySelector('.modal-footer .btn-secondary');
    zoomButton.innerHTML = isZoomed ? 
        '<i class="fas fa-search-minus me-2"></i>Уменьшить' : 
        '<i class="fas fa-search-plus me-2"></i>Увеличить';
}
function downloadGraph() {
    if (!currentGraphBase64) return;
    
    const link = document.createElement('a');
    const timestamp = new Date().toISOString().slice(0,19).replace(/:/g, '-');
    const filename = `graph_${currentGraphTitle.replace(/\s+/g, '_')}_${timestamp}.png`;
    
    link.download = filename;
    link.href = `data:image/png;base64,${currentGraphBase64}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showNotification('График скачивается...', 'success');
}
function printGraph() {
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <html>
            <head>
                <title>Печать: ${currentGraphTitle}</title>
                <style>
                    body { 
                        margin: 0; 
                        padding: 20px; 
                        text-align: center; 
                        font-family: Arial, sans-serif;
                    }
                    img { 
                        max-width: 100%; 
                        height: auto; 
                        margin: 20px 0;
                    }
                    .header {
                        text-align: center;
                        margin-bottom: 30px;
                        border-bottom: 2px solid #333;
                        padding-bottom: 10px;
                    }
                    .footer {
                        margin-top: 30px;
                        color: #666;
                        font-size: 12px;
                    }
                    @media print {
                        .no-print { display: none; }
                    }
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>${currentGraphTitle}</h2>
                    <p>Дашборд аналитики - ЕкбТранспорт+</p>
                    <p>Сформировано: ${new Date().toLocaleString('ru-RU')}</p>
                </div>
                <img src="data:image/png;base64,${currentGraphBase64}" alt="${currentGraphTitle}">
                <div class="footer">
                    <p>© ЕкбТранспорт+ - Планировщик поездок</p>
                </div>
                <button class="no-print" onclick="window.print()" style="padding: 10px 20px; margin: 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    🖨️ Напечатать
                </button>
                <button class="no-print" onclick="window.close()" style="padding: 10px 20px; margin: 20px; background: #dc3545; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    ❌ Закрыть
                </button>
            </body>
        </html>
    `);
    printWindow.document.close();
}
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} notification position-fixed`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        min-width: 300px;
    `;
    notification.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <span>${message}</span>
            <button type="button" class="btn-close" onclick="this.parentElement.parentElement.remove()"></button>
        </div>
    `;
    
    document.body.appendChild(notification);
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 3000);
}
function updateTime() {
    const now = new Date();
    const timeElement = document.getElementById('current-time');
    if (timeElement) {
        timeElement.textContent = now.toLocaleTimeString('ru-RU', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
}
function setupAutoRefresh() {
    setTimeout(function() {
        window.location.href = '?refresh=1';
    }, 300000); // 5 минут
}
document.addEventListener('DOMContentLoaded', function() {
    const tableRows = document.querySelectorAll('.dashboard-table tbody tr');
    tableRows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
            this.style.transition = 'all 0.2s ease';
        });
        row.addEventListener('mouseleave', function() {
            this.style.boxShadow = 'none';
        });
    });
    const modalImage = document.getElementById('modalGraphImage');
    if (modalImage) {
        modalImage.addEventListener('dblclick', function() {
            toggleZoom();
        });
    }
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const modal = bootstrap.Modal.getInstance(document.getElementById('graphModal'));
            if (modal) modal.hide();
        }
    });
    setInterval(updateTime, 60000);
    updateTime();
    setupAutoRefresh();
});
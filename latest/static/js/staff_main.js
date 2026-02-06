$(document).ready(function() {
    // Initialize tooltips
    $('[data-bs-toggle="tooltip"]').tooltip();
    
    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        $('.alert').alert('close');
    }, 5000);
    
    // Form validation
    $('form').on('submit', function(e) {
        const requiredFields = $(this).find('[required]');
        let isValid = true;
        
        requiredFields.each(function() {
            if (!$(this).val().trim()) {
                $(this).addClass('is-invalid');
                isValid = false;
            } else {
                $(this).removeClass('is-invalid');
            }
        });
        
        if (!isValid) {
            e.preventDefault();
            showToast('Please fill in all required fields', 'warning');
        }
    });
    
    // Real-time input validation
    $('input[type="number"]').on('input', function() {
        const min = $(this).attr('min');
        const max = $(this).attr('max');
        const value = parseInt($(this).val());
        
        if (min && value < min) {
            $(this).val(min);
        }
        if (max && value > max) {
            $(this).val(max);
        }
    });
    
    // Blood type badge coloring
    $('.blood-type-badge').each(function() {
        const bloodType = $(this).text();
        let color = 'bg-secondary';
        
        if (bloodType.includes('A')) color = 'bg-danger';
        else if (bloodType.includes('B')) color = 'bg-success';
        else if (bloodType.includes('AB')) color = 'bg-primary';
        else if (bloodType.includes('O')) color = 'bg-purple';
        
        $(this).removeClass('bg-secondary').addClass(color);
    });
    
    // Update current time
    function updateDateTime() {
        const now = new Date();
        const options = { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        };
        $('#currentDateTime').text(now.toLocaleDateString('en-US', options));
    }
    
    updateDateTime();
    setInterval(updateDateTime, 60000); // Update every minute
    
    // Inventory low stock warning
    function checkLowStock() {
        $('.inventory-quantity').each(function() {
            const quantity = parseInt($(this).text());
            const row = $(this).closest('tr');
            
            if (quantity < 5) {
                row.addClass('table-danger pulse');
            } else if (quantity < 15) {
                row.addClass('table-warning');
            } else {
                row.removeClass('table-danger table-warning pulse');
            }
        });
    }
    
    // Check low stock on inventory pages
    if ($('.inventory-quantity').length) {
        checkLowStock();
        setInterval(checkLowStock, 30000); // Check every 30 seconds
    }
    
    // AJAX error handling
    $(document).ajaxError(function(event, jqxhr, settings, thrownError) {
        console.error('AJAX Error:', thrownError);
        showToast('Network error occurred. Please try again.', 'danger');
    });
    
    // Session timeout warning
    let idleTime = 0;
    const idleInterval = setInterval(timerIncrement, 60000); // 1 minute
    
    function timerIncrement() {
        idleTime++;
        if (idleTime > 25) { // 25 minutes
            showToast('Session will expire in 5 minutes due to inactivity', 'warning');
        }
        if (idleTime > 30) { // 30 minutes
            window.location.href = '/logout?timeout=true';
        }
    }
    
    $(document).on('mousemove keypress scroll click', function() {
        idleTime = 0;
    });
    
    // Export functionality
    $('.export-btn').click(function() {
        const format = $(this).data('format');
        const tableId = $(this).data('table');
        exportTable(format, tableId);
    });
    
    // Quick stats update
    function updateQuickStats() {
        $.ajax({
            url: '/api/stats/quick',
            success: function(data) {
                $('#pendingRequestsCount').text(data.pending_requests);
                $('#lowStockCount').text(data.low_stock);
                $('#pendingEligibilityCount').text(data.pending_eligibility);
            }
        });
    }
    
    // Update stats every 2 minutes if on dashboard
    if (window.location.pathname === '/staff/dashboard') {
        updateQuickStats();
        setInterval(updateQuickStats, 120000);
    }
});

// Sidebar toggle function
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    
    if (!sidebar) return;
    
    if (sidebar.classList.contains('active')) {
        // Close sidebar
        sidebar.classList.remove('active');
        if (overlay) {
            overlay.classList.remove('active');
            setTimeout(() => {
                overlay.style.display = 'none';
            }, 300);
        }
    } else {
        // Open sidebar
        sidebar.classList.add('active');
        if (overlay) {
            overlay.style.display = 'block';
            // Trigger reflow for animation
            void overlay.offsetWidth;
            overlay.classList.add('active');
        }
    }
}

// Close sidebar when clicking overlay
document.addEventListener('DOMContentLoaded', function() {
    // Create overlay if it doesn't exist
    let overlay = document.querySelector('.sidebar-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        overlay.addEventListener('click', toggleSidebar);
        document.body.appendChild(overlay);
    }
    
    // Close sidebar on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const sidebar = document.getElementById('sidebar');
            if (sidebar && sidebar.classList.contains('active')) {
                toggleSidebar();
            }
        }
    });
    
    // Auto-close sidebar on mobile when clicking a link
    if (window.innerWidth <= 991) {
        const sidebarLinks = document.querySelectorAll('.sidebar-nav a:not(.logout-link)');
        sidebarLinks.forEach(link => {
            link.addEventListener('click', function() {
                toggleSidebar();
            });
        });
    }
});

// Toast notification function
function showToast(message, type = 'info') {
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-bg-${type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    $('#toastContainer').append(toastHtml);
    const toast = new bootstrap.Toast(document.getElementById(toastId));
    toast.show();
    
    // Remove toast after hiding
    document.getElementById(toastId).addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}

// Export table data
function exportTable(format, tableId) {
    const table = document.getElementById(tableId);
    let data, filename, link;
    
    if (format === 'csv') {
        data = tableToCSV(table);
        filename = 'export.csv';
        link = document.createElement('a');
        link.setAttribute('href', 'data:text/csv;charset=utf-8,' + encodeURIComponent(data));
    } else if (format === 'excel') {
        data = tableToExcel(table);
        filename = 'export.xls';
        link = document.createElement('a');
        link.setAttribute('href', 'data:application/vnd.ms-excel;charset=utf-8,' + encodeURIComponent(data));
    } else if (format === 'pdf') {
        // PDF export would require a library like jsPDF
        showToast('PDF export requires additional setup', 'info');
        return;
    }
    
    link.setAttribute('download', filename);
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function tableToCSV(table) {
    const rows = table.querySelectorAll('tr');
    const csv = [];
    
    for (let i = 0; i < rows.length; i++) {
        const row = [], cols = rows[i].querySelectorAll('td, th');
        
        for (let j = 0; j < cols.length; j++) {
            // Clean data and escape commas
            let data = cols[j].innerText.replace(/(\r\n|\n|\r)/gm, '').replace(/(\s\s)/gm, ' ');
            data = data.replace(/"/g, '""');
            row.push('"' + data + '"');
        }
        
        csv.push(row.join(','));
    }
    
    return csv.join('\n');
}

function tableToExcel(table) {
    const html = table.outerHTML;
    return `<html xmlns:o="urn:schemas-microsoft-com:office:office" 
            xmlns:x="urn:schemas-microsoft-com:office:excel" 
            xmlns="http://www.w3.org/TR/REC-html40">
            <head><meta charset="UTF-8"></head>
            <body>${html}</body></html>`;
}

// Date formatting helper
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Time since helper
function timeSince(dateString) {
    const date = new Date(dateString);
    const seconds = Math.floor((new Date() - date) / 1000);
    
    let interval = seconds / 31536000;
    if (interval > 1) return Math.floor(interval) + ' years ago';
    
    interval = seconds / 2592000;
    if (interval > 1) return Math.floor(interval) + ' months ago';
    
    interval = seconds / 86400;
    if (interval > 1) return Math.floor(interval) + ' days ago';
    
    interval = seconds / 3600;
    if (interval > 1) return Math.floor(interval) + ' hours ago';
    
    interval = seconds / 60;
    if (interval > 1) return Math.floor(interval) + ' minutes ago';
    
    return Math.floor(seconds) + ' seconds ago';
}

function handleNotifyDonors(button) {
    const requestId = button.getAttribute('data-request-id');
    const bloodType = button.getAttribute('data-blood-type');
    
    if (!confirm(`Send urgent notifications to all eligible donors with ${bloodType} blood type?`)) {
        return;
    }
    
    // Show loading state
    const originalHTML = button.innerHTML;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    button.disabled = true;
    
    // Make the API call
    fetch(`/staff/requests/${requestId}/notify-donors`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show success message
            showNotification(`✅ ${data.message}`, 'success');
            
            // Log donor details to console for debugging
            if (data.donor_details && data.donor_details.length > 0) {
                console.log('Donors notified:', data.donor_details);
            }
        } else {
            // Show error message
            showNotification(`❌ Error: ${data.error || 'Failed to send notifications'}`, 'error');
        }
        
        // Restore button state
        button.innerHTML = originalHTML;
        button.disabled = false;
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('❌ Network error. Please try again.', 'error');
        button.innerHTML = originalHTML;
        button.disabled = false;
    });
}

// Function to show notification toast
function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 8px;
        color: white;
        font-weight: bold;
        z-index: 9999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        animation: slideIn 0.3s ease-out;
    `;
    
    if (type === 'success') {
        toast.style.backgroundColor = '#28a745';
    } else if (type === 'error') {
        toast.style.backgroundColor = '#dc3545';
    } else if (type === 'warning') {
        toast.style.backgroundColor = '#ffc107';
        toast.style.color = '#212529';
    } else {
        toast.style.backgroundColor = '#17a2b8';
    }
    
    toast.innerHTML = `<i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i> ${message}`;
    
    document.body.appendChild(toast);
    
    // Add CSS for animation if not already present
    if (!document.getElementById('toast-animations')) {
        const style = document.createElement('style');
        style.id = 'toast-animations';
        style.innerHTML = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
    
    // Remove after 5 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 5000);
}

// Add event listeners to all notify-donors buttons
document.addEventListener('DOMContentLoaded', function() {
    const notifyButtons = document.querySelectorAll('.notify-donors');
    
    notifyButtons.forEach(button => {
        button.addEventListener('click', function() {
            handleNotifyDonors(this);
        });
    });
});

// Notify donors button click handler
document.querySelectorAll('.notify-donors').forEach(button => {
    button.addEventListener('click', async function() {
        const requestId = this.getAttribute('data-request-id');
        const bloodType = this.getAttribute('data-blood-type');
        
        console.log(`DEBUG: Notify button clicked for request ${requestId}, blood type ${bloodType}`);
        
        if (!confirm(`Send urgent notifications to all eligible donors with ${bloodType} blood type?`)) {
            return;
        }
        
        // Show loading state
        const originalHTML = this.innerHTML;
        this.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        this.disabled = true;
        
        try {
            const response = await fetch(`/staff/requests/${requestId}/notify`, {
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
            });
            
            console.log(`DEBUG: Response status: ${response.status}`);
            
            const result = await response.json();
            console.log(`DEBUG: Response data:`, result);
            
            if (result.success) {
                showToast(`✅ ${result.message}`, 'success');
                
                // Log donor details to console for debugging
                if (result.donor_details && result.donor_details.length > 0) {
                    console.log('Donors notified:', result.donor_details);
                }
            } else {
                showToast(`❌ Error: ${result.error || 'Failed to send notifications'}`, 'error');
            }
            
        } catch (error) {
            console.error('DEBUG: Fetch error:', error);
            showToast('❌ Network error. Please check console for details.', 'error');
        } finally {
            // Restore button state
            this.innerHTML = originalHTML;
            this.disabled = false;
        }
    });
});

// Toast notification function
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 8px;
        color: white;
        font-weight: bold;
        z-index: 9999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        animation: slideIn 0.3s ease-out;
    `;
    
    if (type === 'success') {
        toast.style.backgroundColor = '#28a745';
    } else if (type === 'error') {
        toast.style.backgroundColor = '#dc3545';
    } else if (type === 'warning') {
        toast.style.backgroundColor = '#ffc107';
        toast.style.color = '#212529';
    } else {
        toast.style.backgroundColor = '#17a2b8';
    }
    
    toast.innerHTML = `<i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i> ${message}`;
    
    document.body.appendChild(toast);
    
    // Add animation styles if not already present
    if (!document.getElementById('toast-animations')) {
        const style = document.createElement('style');
        style.id = 'toast-animations';
        style.innerHTML = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
    
    // Remove after 5 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 5000);
}

// Add global helper functions
window.formatDate = formatDate;
window.timeSince = timeSince;
window.toggleSidebar = toggleSidebar;
window.showToast = showToast;
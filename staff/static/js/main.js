// Main JavaScript for BloodLink Hospital Staff Portal

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

// Add global helper functions
window.formatDate = formatDate;
window.timeSince = timeSince;

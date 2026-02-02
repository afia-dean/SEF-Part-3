// script.js - FIXED VERSION
// Sidebar Toggle Logic
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    
    if (!sidebar) return;
    
    if (sidebar.classList.contains('active')) {
        sidebar.classList.remove('active');
        if (overlay) {
            overlay.classList.remove('active');
            overlay.style.display = 'none';
        }
    } else {
        sidebar.classList.add('active');
        if (overlay) {
            overlay.classList.add('active');
            overlay.style.display = 'block';
        }
    }
}

// Close sidebar when clicking on overlay
document.addEventListener('DOMContentLoaded', function() {
    // Create overlay if it doesn't exist
    let overlay = document.querySelector('.sidebar-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        document.body.appendChild(overlay);
    }
    
    // Set up overlay click
    overlay.addEventListener('click', toggleSidebar);
    
    // Close sidebar with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const sidebar = document.getElementById('sidebar');
            if (sidebar && sidebar.classList.contains('active')) {
                toggleSidebar();
            }
        }
    });
    
    // Donor Dashboard specific setup
    const donorDashboard = document.querySelector('#main-content');
    if (donorDashboard) {
        // For donor.html, we need to handle the overlay differently
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.background = 'rgba(0, 0, 0, 0.5)';
        overlay.style.zIndex = '1998';
        overlay.style.display = 'none';
    }
    
    // Appointment form setup
    const dateInput = document.getElementById('date');
    if (dateInput) {
        const today = new Date().toISOString().split('T')[0];
        dateInput.min = today;
        if (!dateInput.value) {
            dateInput.value = today;
        }
    }
    
    const timeInput = document.getElementById('time');
    if (timeInput && !timeInput.value) {
        const now = new Date();
        const nextHour = now.getHours() + 1;
        timeInput.value = nextHour.toString().padStart(2, '0') + ':00';
    }
});

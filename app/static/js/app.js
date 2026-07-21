/**
 * MultiTool AI — Application-level utilities
 * Theme toggle, CSRF helper, formatters, sidebar toggle.
 */
(function () {
    'use strict';

    /* ===== CSRF Token Helper ===== */
    function getCSRFToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    /* ===== HTML Escape ===== */
    function escapeHtml(text) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(text));
        return div.innerHTML;
    }

    /* ===== Relative Timestamp Formatter ===== */
    function formatTimestamp(iso) {
        if (!iso) return '';

        var date = new Date(iso);
        var now = new Date();
        var diffMs = now - date;
        var diffSec = Math.floor(diffMs / 1000);
        var diffMin = Math.floor(diffSec / 60);
        var diffHr = Math.floor(diffMin / 60);
        var diffDay = Math.floor(diffHr / 24);

        if (diffSec < 10) return 'just now';
        if (diffSec < 60) return diffSec + 's ago';
        if (diffMin < 60) return diffMin + ' min ago';
        if (diffHr < 24) return diffHr + 'h ago';
        if (diffDay === 1) return 'yesterday';
        if (diffDay < 7) return diffDay + ' days ago';

        /* Older: show formatted date */
        var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        var month = months[date.getMonth()];
        var day = date.getDate();

        if (date.getFullYear() === now.getFullYear()) {
            return month + ' ' + day;
        }
        return month + ' ' + day + ', ' + date.getFullYear();
    }

    /* ===== Theme Management ===== */
    function getPreferredTheme() {
        var saved = localStorage.getItem('multitool-theme');
        if (saved) return saved;
        return 'dark';
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.body.setAttribute('data-theme', theme);
        localStorage.setItem('multitool-theme', theme);
        updateThemeToggleUI(theme);
    }

    function toggleTheme() {
        var current = document.documentElement.getAttribute('data-theme') || 'dark';
        var next = current === 'dark' ? 'light' : 'dark';
        applyTheme(next);
    }

    function updateThemeToggleUI(theme) {
        var btn = document.getElementById('btn-theme-toggle');
        if (!btn) return;
        var icon = btn.querySelector('.theme-icon');
        var label = btn.querySelector('.theme-label');
        if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
        if (label) label.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
    }

    /* ===== Sidebar Toggle (Mobile) ===== */
    function openSidebar() {
        document.body.classList.add('sidebar-open');
    }

    function closeSidebar() {
        document.body.classList.remove('sidebar-open');
    }

    function toggleSidebar() {
        document.body.classList.toggle('sidebar-open');
    }

    /* ===== Toast Notifications ===== */
    function showToast(message, type) {
        type = type || 'success';
        var container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        var toast = document.createElement('div');
        toast.className = 'custom-toast ' + type;

        var iconMap = { success: '✓', error: '✗', info: 'ℹ' };
        toast.innerHTML = '<span>' + (iconMap[type] || '') + '</span><span>' + escapeHtml(message) + '</span>';

        container.appendChild(toast);

        setTimeout(function () {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 3000);
    }

    /* ===== Debounce Utility ===== */
    function debounce(fn, delay) {
        var timer;
        return function () {
            var context = this;
            var args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function () {
                fn.apply(context, args);
            }, delay);
        };
    }

    /* ===== Initialization ===== */
    function init() {
        /* Apply saved theme */
        applyTheme(getPreferredTheme());

        /* Theme toggle button */
        var themeBtn = document.getElementById('btn-theme-toggle');
        if (themeBtn) {
            themeBtn.addEventListener('click', toggleTheme);
        }

        /* Sidebar toggle for mobile */
        var sidebarToggle = document.getElementById('btn-sidebar-toggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', function (e) {
                e.stopPropagation();
                toggleSidebar();
            });
        }

        /* Sidebar overlay click to close */
        var overlay = document.getElementById('sidebar-overlay');
        if (overlay) {
            overlay.addEventListener('click', closeSidebar);
        }

        /* Close sidebar on window resize to desktop */
        window.addEventListener('resize', function () {
            if (window.innerWidth > 768) {
                closeSidebar();
            }
        });
    }

    /* Wait for DOM */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    /* ===== Expose Globals ===== */
    window.getCSRFToken = getCSRFToken;
    window.escapeHtml = escapeHtml;
    window.formatTimestamp = formatTimestamp;
    window.showToast = showToast;
    window.debounce = debounce;
    window.openSidebar = openSidebar;
    window.closeSidebar = closeSidebar;
    window.toggleSidebar = toggleSidebar;
})();

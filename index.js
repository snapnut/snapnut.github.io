
function setup() {
}

function showView(viewId) {
    const views = document.querySelectorAll('.view');
    
    views.forEach(view => {
        view.style.display = 'none';
    });

    const targetView = document.getElementById(viewId);
    if (targetView) {
        targetView.style.display = 'block';
    }
}

function toggleBar() {
    const dock = document.getElementById('media-bar');
    const icon = document.getElementById('toggle-icon');
    dock.classList.toggle('is-hidden');
    icon.innerText = dock.classList.contains('is-hidden') ? '▲' : '▼';
}

if (document.readyState === 'loading') {
    window.addEventListener("DOMContentLoaded", setup);
} else {
    setup();
}

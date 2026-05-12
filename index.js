
function setup() {
}

function toggleBar() {
    const dock = document.getElementById('media-bar');
    const icon = document.getElementById('toggle-icon');

    dock.classList.toggle('is-hidden');
    
    if (dock.classList.contains('is-hidden')) {
        icon.innerText = '▲';
    } else {
        icon.innerText = '▼';
    }
}

if (document.readyState === 'loading') {
    window.addEventListener("DOMContentLoaded", setup);
} else {
    setup();
}

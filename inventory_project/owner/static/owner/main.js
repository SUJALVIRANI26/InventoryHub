document.addEventListener('DOMContentLoaded', function () {
    const path = window.location.pathname;
    document.querySelectorAll('.menu-item').forEach((item) => {
        if (item.getAttribute('href') && path === item.getAttribute('href')) {
            item.classList.add('active');
        }
    });
});

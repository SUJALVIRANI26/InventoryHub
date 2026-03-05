document.addEventListener('DOMContentLoaded', function () {
    const path = window.location.pathname;
    document.querySelectorAll('.menu-item').forEach((item) => {
        if (item.getAttribute('href') && path === item.getAttribute('href')) {
            item.classList.add('active');
        }
    });

    if (typeof Chart === 'undefined') {
        return;
    }

    const readJSON = function (id, fallback) {
        const node = document.getElementById(id);
        if (!node) {
            return fallback;
        }
        try {
            return JSON.parse(node.textContent);
        } catch (error) {
            return fallback;
        }
    };

    const defaultTrendLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const defaultTrendValues = [3200, 3900, 3700, 4450, 4800, 4300, 5100];
    const defaultMixLabels = ['Sales', 'Purchase', 'Stock Value'];
    const defaultMixValues = [58, 27, 15];

    const trendLabels = readJSON('trend-labels', defaultTrendLabels);
    const trendValues = readJSON('trend-values', defaultTrendValues);
    const mixLabels = readJSON('mix-labels', defaultMixLabels);
    const mixValues = readJSON('mix-values', defaultMixValues);

    const chartEl = document.getElementById('ownerTrendChart');
    if (chartEl) {
        new Chart(chartEl, {
            type: 'line',
            data: {
                labels: trendLabels,
                datasets: [{
                    label: 'Revenue',
                    data: trendValues,
                    borderColor: '#2e63f0',
                    backgroundColor: 'rgba(46, 99, 240, 0.14)',
                    fill: true,
                    tension: 0.34,
                    pointRadius: 3,
                    pointHoverRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, labels: { usePointStyle: true } }
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: '#eef2ff' } },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    const pieEl = document.getElementById('ownerMixChart');
    if (pieEl) {
        new Chart(pieEl, {
            type: 'doughnut',
            data: {
                labels: mixLabels,
                datasets: [{
                    data: mixValues,
                    backgroundColor: ['#2e63f0', '#16a34a', '#f59e0b'],
                    borderWidth: 0,
                    hoverOffset: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { position: 'bottom', labels: { usePointStyle: true } }
                }
            }
        });
    }
});

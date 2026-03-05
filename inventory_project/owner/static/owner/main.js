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

    const chartEl = document.getElementById('ownerTrendChart');
    if (chartEl) {
        const labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const values = [3200, 3900, 3700, 4450, 4800, 4300, 5100];

        new Chart(chartEl, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Revenue',
                    data: values,
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
                labels: ['Sales', 'Purchase', 'Stock Holding'],
                datasets: [{
                    data: [58, 27, 15],
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

/**
 * Rock Chatbot - Admin Analytics Dashboard
 *
 * This script handles the analytics dashboard functionality in the admin dashboard.
 * It provides visualizations and statistics for chatbot usage.
 */

/**
 * Load analytics data
 */
window.loadAnalytics = function() {
    // Show loading indicator
    const analyticsTab = document.getElementById('analytics');
    analyticsTab.innerHTML = '<div class="loading">Loading analytics data...</div>';

    // Fetch analytics data from API
    fetch('/api/admin/analytics_data')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Create analytics dashboard
                let html = `
                    <div class="dashboard-header">
                        <h1>Analytics Dashboard</h1>
                        <div>
                            <button class="btn" id="refresh-analytics"><i class="fas fa-sync"></i> Refresh</button>
                        </div>
                    </div>

                    <div class="stats-container">
                        <div class="stat-card">
                            <h3>Total Sessions</h3>
                            <div class="stat-value">${data.total_sessions}</div>
                        </div>
                        <div class="stat-card">
                            <h3>Active Users</h3>
                            <div class="stat-value">${data.active_users}</div>
                        </div>
                        <div class="stat-card">
                            <h3>Total Messages</h3>
                            <div class="stat-value">${data.total_messages}</div>
                        </div>
                        <div class="stat-card">
                            <h3>Avg. Session Duration</h3>
                            <div class="stat-value">${formatDuration(data.avg_session_duration)}</div>
                        </div>
                    </div>

                    <div class="row">
                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-header">
                                    <h2>Sessions by Day</h2>
                                </div>
                                <div class="card-body">
                                    <canvas id="sessions-chart" height="300"></canvas>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-header">
                                    <h2>Top Intents</h2>
                                </div>
                                <div class="card-body">
                                    <canvas id="intents-chart" height="300"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="row">
                        <div class="col-md-12">
                            <div class="card">
                                <div class="card-header">
                                    <h2>User Satisfaction</h2>
                                </div>
                                <div class="card-body">
                                    <canvas id="satisfaction-chart" height="300"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-header">
                            <h2>Top Products</h2>
                        </div>
                        <div class="table-container">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Product</th>
                                        <th>Views</th>
                                        <th>Orders</th>
                                        <th>Revenue</th>
                                    </tr>
                                </thead>
                                <tbody id="top-products-table">
                `;

                // Add top products to table
                data.top_products.forEach(product => {
                    html += `
                        <tr>
                            <td>${product.name}</td>
                            <td>${product.views}</td>
                            <td>${product.orders}</td>
                            <td>RM${parseFloat(product.revenue).toFixed(2)}</td>
                        </tr>
                    `;
                });

                html += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;

                // Update analytics tab content
                analyticsTab.innerHTML = html;

                // Add event listener to refresh button
                const refreshBtn = document.getElementById('refresh-analytics');
                if (refreshBtn) {
                    refreshBtn.addEventListener('click', loadAnalytics);
                }

                // Create charts
                createSessionsChart(data.sessions_by_day);
                createIntentsChart(data.top_intents);
                createSatisfactionChart(data.satisfaction_ratings);
            } else {
                analyticsTab.innerHTML = `<div class="error">Error loading analytics data: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading analytics data:', error);
            analyticsTab.innerHTML = '<div class="error">Error loading analytics data. Please try again.</div>';
        });
}

/**
 * Format duration in seconds to a human-readable string
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration
 */
function formatDuration(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
}

/**
 * Create sessions by day chart
 * @param {Array} data - Sessions by day data
 */
function createSessionsChart(data) {
    const ctx = document.getElementById('sessions-chart').getContext('2d');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(item => item.date),
            datasets: [{
                label: 'Sessions',
                data: data.map(item => item.count),
                backgroundColor: 'rgba(52, 152, 219, 0.2)',
                borderColor: 'rgba(52, 152, 219, 1)',
                borderWidth: 2,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
}

/**
 * Create top intents chart
 * @param {Array} data - Top intents data
 */
function createIntentsChart(data) {
    const ctx = document.getElementById('intents-chart').getContext('2d');

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(item => item.intent_name),
            datasets: [{
                label: 'Usage Count',
                data: data.map(item => item.count),
                backgroundColor: 'rgba(46, 204, 113, 0.2)',
                borderColor: 'rgba(46, 204, 113, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
}



/**
 * Create satisfaction ratings chart
 * @param {Array} data - Satisfaction ratings data
 */
function createSatisfactionChart(data) {
    const ctx = document.getElementById('satisfaction-chart').getContext('2d');

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['1 Star', '2 Stars', '3 Stars', '4 Stars', '5 Stars'],
            datasets: [{
                data: [
                    data.filter(item => item.rating === 1).length,
                    data.filter(item => item.rating === 2).length,
                    data.filter(item => item.rating === 3).length,
                    data.filter(item => item.rating === 4).length,
                    data.filter(item => item.rating === 5).length
                ],
                backgroundColor: [
                    'rgba(231, 76, 60, 0.7)',
                    'rgba(230, 126, 34, 0.7)',
                    'rgba(241, 196, 15, 0.7)',
                    'rgba(46, 204, 113, 0.7)',
                    'rgba(52, 152, 219, 0.7)'
                ],
                borderColor: [
                    'rgba(231, 76, 60, 1)',
                    'rgba(230, 126, 34, 1)',
                    'rgba(241, 196, 15, 1)',
                    'rgba(46, 204, 113, 1)',
                    'rgba(52, 152, 219, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}



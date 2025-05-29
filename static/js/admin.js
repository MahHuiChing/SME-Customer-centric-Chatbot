/**
 * Rock Chatbot - Admin Dashboard
 *
 * This script handles the admin dashboard functionality for managers and agents.
 * It provides CRUD operations for products, FAQs, promotions, and user management.
 *
 * This is the main admin script that coordinates the different modules:
 * - admin_products.js: Product management
 * - admin_faqs.js: FAQ management
 * - admin_promotions.js: Promotion management
 * - admin_analytics.js: Analytics dashboard
 */

// Global variables
let currentTab = 'dashboard';
let currentPage = {
    products: 1,
    faqs: 1,
    promotions: 1,
    users: 1,
    sessions: 1
};
const perPage = 10;

// DOM elements
const tabLinks = document.querySelectorAll('.sidebar-menu a');
const tabContents = document.querySelectorAll('.tab-content');
const refreshStatsBtn = document.getElementById('refresh-stats');

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', () => {
    // Set up tab navigation
    tabLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = link.getAttribute('data-tab');
            switchTab(tabId);
        });
    });

    // Set up View All buttons
    document.querySelectorAll('.view-all-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = btn.getAttribute('data-tab');
            switchTab(tabId);
        });
    });

    // Load initial dashboard data
    loadDashboardStats();
    loadRecentSessions();
    loadRecentUsers();

    // Check for pending FAQs
    if (userInfo.role === 'manager') {
        checkPendingFaqs();
        // Check every 5 minutes
        setInterval(checkPendingFaqs, 5 * 60 * 1000);
    }

    // Set up refresh button
    if (refreshStatsBtn) {
        refreshStatsBtn.addEventListener('click', loadDashboardStats);
    }

    // Set up modal close buttons
    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.modal').forEach(modal => {
                modal.style.display = 'none';
            });
        });
    });

    // Set up product form
    const productForm = document.getElementById('product-form');
    if (productForm) {
        productForm.addEventListener('submit', function(event) {
            if (typeof handleProductFormSubmit === 'function') {
                handleProductFormSubmit(event);
            } else {
                console.error('handleProductFormSubmit is not defined');
            }
        });
    }
});

/**
 * Switch between tabs
 * @param {string} tabId - The ID of the tab to switch to
 */
function switchTab(tabId) {
    // Update active tab link
    tabLinks.forEach(link => {
        if (link.getAttribute('data-tab') === tabId) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    // Update visible tab content
    tabContents.forEach(content => {
        if (content.id === tabId) {
            content.style.display = 'block';
        } else {
            content.style.display = 'none';
        }
    });

    // Save current tab
    currentTab = tabId;

    // Load tab-specific data if needed
    if (tabId === 'dashboard') {
        loadDashboardStats();
        loadRecentSessions();
        loadRecentUsers();
    } else if (tabId === 'products' && document.getElementById('products').innerHTML === '') {
        loadProducts();
    } else if (tabId === 'faqs' && document.getElementById('faqs').innerHTML === '') {
        if (typeof window.loadFaqs === 'function') {
            window.loadFaqs();
        } else {
            console.error('loadFaqs function is not defined');
            document.getElementById('faqs').innerHTML = '<div class="error">Error loading FAQs. Please refresh the page and try again.</div>';
        }
    } else if (tabId === 'promotions' && document.getElementById('promotions').innerHTML === '') {
        loadPromotions();
    } else if (tabId === 'users' && document.getElementById('users').innerHTML === '') {
        loadUsers();
    } else if (tabId === 'sessions' && document.getElementById('sessions').innerHTML === '') {
        loadSessions();
    } else if (tabId === 'active-chats' && document.getElementById('active-chats').innerHTML === '') {
        loadActiveChats();
    } else if (tabId === 'analytics' && document.getElementById('analytics').innerHTML === '') {
        loadAnalytics();
    }
}

/**
 * Load dashboard statistics
 */
function loadDashboardStats() {
    fetch('/api/admin/dashboard_stats')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('active-sessions-count').textContent = data.active_sessions;
                document.getElementById('total-users-count').textContent = data.total_users;
                document.getElementById('products-count').textContent = data.products;
                document.getElementById('faqs-count').textContent = data.faqs;
            } else {
                console.error('Error loading dashboard stats:', data.message);
            }
        })
        .catch(error => {
            console.error('Error loading dashboard stats:', error);
        });
}

/**
 * Load recent chat sessions
 */
function loadRecentSessions() {
    fetch('/api/admin/recent_sessions?limit=5')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const tableBody = document.getElementById('recent-sessions-table');
                tableBody.innerHTML = '';

                data.sessions.forEach(session => {
                    const row = document.createElement('tr');

                    // Session ID
                    const idCell = document.createElement('td');
                    idCell.textContent = session.session_id;
                    row.appendChild(idCell);

                    // User
                    const userCell = document.createElement('td');
                    userCell.textContent = session.username || session.first_name || 'Guest User';
                    row.appendChild(userCell);

                    // Start Time
                    const startCell = document.createElement('td');
                    startCell.textContent = new Date(session.session_start).toLocaleString();
                    row.appendChild(startCell);

                    // Status
                    const statusCell = document.createElement('td');
                    statusCell.textContent = session.session_end ? 'Ended' : 'Active';
                    statusCell.style.color = session.session_end ? 'var(--danger-color)' : 'var(--success-color)';
                    row.appendChild(statusCell);

                    // Actions
                    const actionsCell = document.createElement('td');
                    const viewBtn = document.createElement('button');
                    viewBtn.className = 'action-btn edit-btn';
                    viewBtn.textContent = 'View';
                    viewBtn.addEventListener('click', () => {
                        // Create modal for session details
                        const modal = document.createElement('div');
                        modal.className = 'modal';
                        modal.id = 'session-details-modal';
                        modal.style.display = 'flex';

                        const modalContent = document.createElement('div');
                        modalContent.className = 'modal-content';

                        // Modal header
                        const modalHeader = document.createElement('div');
                        modalHeader.className = 'modal-header';

                        const modalTitle = document.createElement('h2');
                        modalTitle.textContent = `Session #${session.session_id} Details`;

                        const closeBtn = document.createElement('button');
                        closeBtn.className = 'close-modal';
                        closeBtn.innerHTML = '&times;';
                        closeBtn.addEventListener('click', () => {
                            document.body.removeChild(modal);
                        });

                        modalHeader.appendChild(modalTitle);
                        modalHeader.appendChild(closeBtn);

                        // Modal body
                        const modalBody = document.createElement('div');
                        modalBody.innerHTML = '<p>Loading session details...</p>';

                        modalContent.appendChild(modalHeader);
                        modalContent.appendChild(modalBody);
                        modal.appendChild(modalContent);

                        document.body.appendChild(modal);

                        // Fetch session details
                        fetch(`/api/admin/session_messages?session_id=${session.session_id}`)
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    const messages = data.messages || [];

                                    let html = `
                                        <div class="session-info">
                                            <h3>Session Information</h3>
                                            <div><strong>Session ID:</strong> ${session.session_id}</div>
                                            <div><strong>User:</strong> ${session.username || session.first_name || 'Guest User'}</div>
                                            <div><strong>Start Time:</strong> ${new Date(session.session_start).toLocaleString()}</div>
                                            <div><strong>Status:</strong> ${session.session_end ? 'Ended' : 'Active'}</div>
                                            <div><strong>Language:</strong> ${session.language || 'en'}</div>
                                        </div>

                                        <div class="session-messages">
                                            <h3>Messages</h3>
                                    `;

                                    if (messages.length > 0) {
                                        html += '<div class="chat-messages-container">';

                                        messages.forEach(message => {
                                            const messageClass = message.sender_type === 'user' ? 'user-message' : 'bot-message';
                                            const senderName = message.sender_type === 'agent' ? `<strong>Agent ${message.sender_name || ''}:</strong> ` : '';

                                            html += `
                                                <div class="message ${messageClass}">
                                                    <div>${senderName}${message.message_text}</div>
                                                    <div class="message-time">${new Date(message.timestamp).toLocaleString()}</div>
                                                </div>
                                            `;
                                        });

                                        html += '</div>';
                                    } else {
                                        html += '<p>No messages found for this session.</p>';
                                    }

                                    html += '</div>';

                                    modalBody.innerHTML = html;
                                } else {
                                    modalBody.innerHTML = `<p>Error loading session details: ${data.message}</p>`;
                                }
                            })
                            .catch(error => {
                                console.error('Error loading session details:', error);
                                modalBody.innerHTML = '<p>Error loading session details. Please try again.</p>';
                            });
                    });
                    actionsCell.appendChild(viewBtn);
                    row.appendChild(actionsCell);

                    tableBody.appendChild(row);
                });
            } else {
                console.error('Error loading recent sessions:', data.message);
            }
        })
        .catch(error => {
            console.error('Error loading recent sessions:', error);
        });
}

/**
 * Load recent users
 */
function loadRecentUsers() {
    fetch('/api/admin/recent_users?limit=5')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const tableBody = document.getElementById('recent-users-table');
                tableBody.innerHTML = '';

                data.users.forEach(user => {
                    const row = document.createElement('tr');

                    // ID
                    const idCell = document.createElement('td');
                    idCell.textContent = user.id;
                    row.appendChild(idCell);

                    // Username
                    const usernameCell = document.createElement('td');
                    usernameCell.textContent = user.username;
                    row.appendChild(usernameCell);

                    // Name
                    const nameCell = document.createElement('td');
                    nameCell.textContent = `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'N/A';
                    row.appendChild(nameCell);

                    // Role
                    const roleCell = document.createElement('td');
                    roleCell.textContent = user.role.charAt(0).toUpperCase() + user.role.slice(1);
                    row.appendChild(roleCell);

                    // Joined
                    const joinedCell = document.createElement('td');
                    joinedCell.textContent = new Date(user.created_at).toLocaleDateString();
                    row.appendChild(joinedCell);

                    tableBody.appendChild(row);
                });
            } else {
                console.error('Error loading recent users:', data.message);
            }
        })
        .catch(error => {
            console.error('Error loading recent users:', error);
        });
}

/**
 * Check for pending FAQs and update notification badge
 */
function checkPendingFaqs() {
    if (userInfo.role !== 'manager') return;

    fetch('/api/admin/pending_faqs?status=pending')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const pendingCount = data.pending_faqs.length;
                const badge = document.getElementById('pending-faqs-badge');

                if (pendingCount > 0) {
                    badge.textContent = pendingCount;
                    badge.style.display = 'inline-flex';

                    // Show notification if not already on the FAQs tab
                    if (currentTab !== 'faqs') {
                        showNotification(`You have ${pendingCount} pending FAQ${pendingCount > 1 ? 's' : ''} to review`, 'info');
                    }
                } else {
                    badge.style.display = 'none';
                }
            }
        })
        .catch(error => {
            console.error('Error checking pending FAQs:', error);
        });
}

/**
 * View customer details including order history
 * @param {number} customerId - The ID of the customer
 */
function viewCustomerDetails(customerId) {
    // Create modal for customer details
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'customer-details-modal';
    modal.style.display = 'flex';

    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';

    // Modal header
    const modalHeader = document.createElement('div');
    modalHeader.className = 'modal-header';

    const modalTitle = document.createElement('h2');
    modalTitle.textContent = 'Customer Details';

    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-modal';
    closeBtn.innerHTML = '&times;';
    closeBtn.addEventListener('click', () => {
        document.body.removeChild(modal);
    });

    modalHeader.appendChild(modalTitle);
    modalHeader.appendChild(closeBtn);

    // Modal body
    const modalBody = document.createElement('div');
    modalBody.innerHTML = '<p>Loading customer details...</p>';

    modalContent.appendChild(modalHeader);
    modalContent.appendChild(modalBody);
    modal.appendChild(modalContent);

    document.body.appendChild(modal);

    // Fetch customer details
    fetch(`/api/admin/customer_details?customer_id=${customerId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const customer = data.customer;
                const orders = data.orders || [];

                let html = `
                    <div class="customer-profile">
                        <h3>Profile Information</h3>
                        <div><strong>ID:</strong> ${customer.customer_id}</div>
                        <div><strong>Username:</strong> ${customer.username}</div>
                        <div><strong>Email:</strong> ${customer.email}</div>
                        <div><strong>Name:</strong> ${customer.first_name || ''} ${customer.last_name || ''}</div>
                        <div><strong>Phone:</strong> ${customer.phone_number || 'N/A'}</div>
                        <div><strong>Joined:</strong> ${new Date(customer.created_at).toLocaleDateString()}</div>
                        <div><strong>Last Login:</strong> ${customer.last_login ? new Date(customer.last_login).toLocaleString() : 'Never'}</div>
                    </div>

                    <div class="customer-orders">
                        <h3>Order History</h3>
                `;

                if (orders.length > 0) {
                    html += `
                        <table>
                            <thead>
                                <tr>
                                    <th>Order ID</th>
                                    <th>Date</th>
                                    <th>Total</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                    `;

                    orders.forEach(order => {
                        html += `
                            <tr>
                                <td>${order.order_id}</td>
                                <td>${new Date(order.order_date).toLocaleDateString()}</td>
                                <td>$${order.total_amount.toFixed(2)}</td>
                                <td>${order.status}</td>
                                <td>
                                    <button class="action-btn edit-btn" onclick="viewOrderDetails(${order.order_id})">View</button>
                                </td>
                            </tr>
                        `;
                    });

                    html += `
                            </tbody>
                        </table>
                    `;
                } else {
                    html += '<p>No orders found for this customer.</p>';
                }

                html += '</div>';

                modalBody.innerHTML = html;
            } else {
                modalBody.innerHTML = `<p>Error loading customer details: ${data.message}</p>`;
            }
        })
        .catch(error => {
            console.error('Error loading customer details:', error);
            modalBody.innerHTML = '<p>Error loading customer details. Please try again.</p>';
        });
}

/**
 * Show a notification message
 * @param {string} message - The message to display
 * @param {string} type - The type of notification (success, error, info, warning)
 * @param {number} duration - How long to show the notification in milliseconds
 */
function showNotification(message, type = 'info', duration = 5000) {
    // Check if notification container exists, create if not
    let container = document.getElementById('notification-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notification-container';
        container.style.position = 'fixed';
        container.style.top = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        container.style.display = 'flex';
        container.style.flexDirection = 'column';
        container.style.alignItems = 'flex-end';
        container.style.gap = '10px';
        document.body.appendChild(container);
    }

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.backgroundColor = type === 'success' ? '#4CAF50' :
                                        type === 'error' ? '#F44336' :
                                        type === 'warning' ? '#FF9800' : '#2196F3';
    notification.style.color = 'white';
    notification.style.padding = '12px 20px';
    notification.style.borderRadius = '4px';
    notification.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
    notification.style.marginBottom = '10px';
    notification.style.minWidth = '250px';
    notification.style.maxWidth = '400px';
    notification.style.animation = 'slideInRight 0.3s ease-out forwards';
    notification.style.display = 'flex';
    notification.style.justifyContent = 'space-between';
    notification.style.alignItems = 'center';

    // Add message
    const messageSpan = document.createElement('span');
    messageSpan.textContent = message;
    notification.appendChild(messageSpan);

    // Add close button
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '&times;';
    closeBtn.style.background = 'none';
    closeBtn.style.border = 'none';
    closeBtn.style.color = 'white';
    closeBtn.style.fontSize = '20px';
    closeBtn.style.cursor = 'pointer';
    closeBtn.style.marginLeft = '10px';
    closeBtn.onclick = () => {
        notification.style.animation = 'slideOutRight 0.3s ease-out forwards';
        setTimeout(() => {
            container.removeChild(notification);
        }, 300);
    };
    notification.appendChild(closeBtn);

    // Add to container
    container.appendChild(notification);

    // Auto remove after duration
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.animation = 'slideOutRight 0.3s ease-out forwards';
            setTimeout(() => {
                if (notification.parentNode) {
                    container.removeChild(notification);
                }
            }, 300);
        }
    }, duration);

    // Add CSS animations if not already added
    if (!document.getElementById('notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOutRight {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
}

function viewOrderDetails(orderId) {
    // Create modal for order details
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'order-details-modal';
    modal.style.display = 'flex';

    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';

    // Modal header
    const modalHeader = document.createElement('div');
    modalHeader.className = 'modal-header';

    const modalTitle = document.createElement('h2');
    modalTitle.textContent = `Order #${orderId} Details`;

    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-modal';
    closeBtn.innerHTML = '&times;';
    closeBtn.addEventListener('click', () => {
        document.body.removeChild(modal);
    });

    modalHeader.appendChild(modalTitle);
    modalHeader.appendChild(closeBtn);

    // Modal body
    const modalBody = document.createElement('div');
    modalBody.innerHTML = '<p>Loading order details...</p>';

    modalContent.appendChild(modalHeader);
    modalContent.appendChild(modalBody);
    modal.appendChild(modalContent);

    document.body.appendChild(modal);

    // Fetch order details
    fetch(`/api/admin/order_details?order_id=${orderId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const order = data.order;
                const items = data.items || [];

                let html = `
                    <div class="order-info">
                        <h3>Order Information</h3>
                        <div><strong>Order ID:</strong> ${order.order_id}</div>
                        <div><strong>Date:</strong> ${new Date(order.order_date).toLocaleString()}</div>
                        <div><strong>Customer:</strong> ${order.customer_name || 'N/A'}</div>
                        <div><strong>Total Amount:</strong> $${order.total_amount.toFixed(2)}</div>
                        <div><strong>Status:</strong> ${order.status}</div>
                        <div><strong>Payment Method:</strong> ${order.payment_method || 'N/A'}</div>
                        <div><strong>Payment Status:</strong> ${order.payment_status}</div>
                        <div><strong>Shipping Address:</strong> ${order.shipping_address || 'N/A'}</div>
                        <div><strong>Tracking Number:</strong> ${order.tracking_number || 'N/A'}</div>
                    </div>

                    <div class="order-items">
                        <h3>Order Items</h3>
                `;

                if (items.length > 0) {
                    html += `
                        <table>
                            <thead>
                                <tr>
                                    <th>Product</th>
                                    <th>Quantity</th>
                                    <th>Unit Price</th>
                                    <th>Subtotal</th>
                                </tr>
                            </thead>
                            <tbody>
                    `;

                    items.forEach(item => {
                        html += `
                            <tr>
                                <td>${item.product_name}</td>
                                <td>${item.quantity}</td>
                                <td>$${item.unit_price.toFixed(2)}</td>
                                <td>$${item.subtotal.toFixed(2)}</td>
                            </tr>
                        `;
                    });

                    html += `
                            </tbody>
                        </table>
                    `;
                } else {
                    html += '<p>No items found for this order.</p>';
                }

                html += '</div>';

                modalBody.innerHTML = html;
            } else {
                modalBody.innerHTML = `<p>Error loading order details: ${data.message}</p>`;
            }
        })
        .catch(error => {
            console.error('Error loading order details:', error);
            modalBody.innerHTML = '<p>Error loading order details. Please try again.</p>';
        });
}

/**
 * Load sessions
 */
function loadSessions() {
    const sessionsTab = document.getElementById('sessions');
    sessionsTab.innerHTML = '<div class="tab-header"><h1>Chat Sessions</h1></div>';

    // Create a container for the sessions table
    const tableContainer = document.createElement('div');
    tableContainer.className = 'table-container';

    // Create a loading message
    const loadingMessage = document.createElement('p');
    loadingMessage.textContent = 'Loading sessions...';
    tableContainer.appendChild(loadingMessage);

    sessionsTab.appendChild(tableContainer);

    // Fetch all sessions
    fetch('/api/admin/all_sessions')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Clear the loading message
                tableContainer.innerHTML = '';

                // Create the table
                const table = document.createElement('table');

                // Create the table header
                const thead = document.createElement('thead');
                const headerRow = document.createElement('tr');

                const headers = ['ID', 'User', 'Start Time', 'End Time', 'Language', 'Status', 'Actions'];
                headers.forEach(headerText => {
                    const th = document.createElement('th');
                    th.textContent = headerText;
                    headerRow.appendChild(th);
                });

                thead.appendChild(headerRow);
                table.appendChild(thead);

                // Create the table body
                const tbody = document.createElement('tbody');

                data.sessions.forEach(session => {
                    const row = document.createElement('tr');

                    // ID
                    const idCell = document.createElement('td');
                    idCell.textContent = session.session_id;
                    row.appendChild(idCell);

                    // User
                    const userCell = document.createElement('td');
                    userCell.textContent = session.username || session.first_name || 'Guest User';
                    row.appendChild(userCell);

                    // Start Time
                    const startCell = document.createElement('td');
                    startCell.textContent = new Date(session.session_start).toLocaleString();
                    row.appendChild(startCell);

                    // End Time
                    const endCell = document.createElement('td');
                    endCell.textContent = session.session_end ? new Date(session.session_end).toLocaleString() : 'Active';
                    row.appendChild(endCell);

                    // Language
                    const langCell = document.createElement('td');
                    langCell.textContent = session.language || 'en';
                    row.appendChild(langCell);

                    // Status
                    const statusCell = document.createElement('td');
                    statusCell.textContent = session.session_end ? 'Ended' : 'Active';
                    statusCell.style.color = session.session_end ? 'var(--danger-color)' : 'var(--success-color)';
                    row.appendChild(statusCell);

                    // Actions
                    const actionsCell = document.createElement('td');
                    const viewBtn = document.createElement('button');
                    viewBtn.className = 'action-btn edit-btn';
                    viewBtn.textContent = 'View';
                    viewBtn.addEventListener('click', () => {
                        // Create modal for session details
                        const modal = document.createElement('div');
                        modal.className = 'modal';
                        modal.id = 'session-details-modal';
                        modal.style.display = 'flex';

                        const modalContent = document.createElement('div');
                        modalContent.className = 'modal-content';

                        // Modal header
                        const modalHeader = document.createElement('div');
                        modalHeader.className = 'modal-header';

                        const modalTitle = document.createElement('h2');
                        modalTitle.textContent = `Session #${session.session_id} Details`;

                        const closeBtn = document.createElement('button');
                        closeBtn.className = 'close-modal';
                        closeBtn.innerHTML = '&times;';
                        closeBtn.addEventListener('click', () => {
                            document.body.removeChild(modal);
                        });

                        modalHeader.appendChild(modalTitle);
                        modalHeader.appendChild(closeBtn);

                        // Modal body
                        const modalBody = document.createElement('div');
                        modalBody.innerHTML = '<p>Loading session details...</p>';

                        modalContent.appendChild(modalHeader);
                        modalContent.appendChild(modalBody);
                        modal.appendChild(modalContent);

                        document.body.appendChild(modal);

                        // Fetch session details
                        fetch(`/api/admin/session_messages?session_id=${session.session_id}`)
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    const messages = data.messages || [];

                                    let html = `
                                        <div class="session-info">
                                            <h3>Session Information</h3>
                                            <div><strong>Session ID:</strong> ${session.session_id}</div>
                                            <div><strong>User:</strong> ${session.username || session.first_name || 'Guest User'}</div>
                                            <div><strong>Start Time:</strong> ${new Date(session.session_start).toLocaleString()}</div>
                                            <div><strong>Status:</strong> ${session.session_end ? 'Ended' : 'Active'}</div>
                                            <div><strong>Language:</strong> ${session.language || 'en'}</div>
                                        </div>

                                        <div class="session-messages">
                                            <h3>Messages</h3>
                                    `;

                                    if (messages.length > 0) {
                                        html += '<div class="chat-messages-container">';

                                        messages.forEach(message => {
                                            const messageClass = message.sender_type === 'user' ? 'user-message' : 'bot-message';
                                            const senderName = message.sender_type === 'agent' ? `<strong>Agent ${message.sender_name || ''}:</strong> ` : '';

                                            html += `
                                                <div class="message ${messageClass}">
                                                    <div>${senderName}${message.message_text}</div>
                                                    <div class="message-time">${new Date(message.timestamp).toLocaleString()}</div>
                                                </div>
                                            `;
                                        });

                                        html += '</div>';
                                    } else {
                                        html += '<p>No messages found for this session.</p>';
                                    }

                                    html += '</div>';

                                    modalBody.innerHTML = html;
                                } else {
                                    modalBody.innerHTML = `<p>Error loading session details: ${data.message}</p>`;
                                }
                            })
                            .catch(error => {
                                console.error('Error loading session details:', error);
                                modalBody.innerHTML = '<p>Error loading session details. Please try again.</p>';
                            });
                    });
                    actionsCell.appendChild(viewBtn);
                    row.appendChild(actionsCell);

                    tbody.appendChild(row);
                });

                table.appendChild(tbody);
                tableContainer.appendChild(table);
            } else {
                tableContainer.innerHTML = `<p>Error loading sessions: ${data.message}</p>`;
            }
        })
        .catch(error => {
            console.error('Error loading sessions:', error);
            tableContainer.innerHTML = '<p>Error loading sessions. Please try again.</p>';
        });
}

/**
 * Load users
 */
function loadUsers() {
    const usersTab = document.getElementById('users');
    usersTab.innerHTML = '<div class="tab-header"><h1>Users</h1></div>';

    // Create a container for the users table
    const tableContainer = document.createElement('div');
    tableContainer.className = 'table-container';

    // Create a loading message
    const loadingMessage = document.createElement('p');
    loadingMessage.textContent = 'Loading users...';
    tableContainer.appendChild(loadingMessage);

    usersTab.appendChild(tableContainer);

    // Fetch all users
    fetch('/api/admin/all_users')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Clear the loading message
                tableContainer.innerHTML = '';

                // Create the table
                const table = document.createElement('table');

                // Create the table header
                const thead = document.createElement('thead');
                const headerRow = document.createElement('tr');

                const headers = ['ID', 'Username', 'Name', 'Email', 'Role', 'Joined', 'Last Login', 'Status'];
                headers.forEach(headerText => {
                    const th = document.createElement('th');
                    th.textContent = headerText;
                    headerRow.appendChild(th);
                });

                thead.appendChild(headerRow);
                table.appendChild(thead);

                // Create the table body
                const tbody = document.createElement('tbody');

                data.users.forEach(user => {
                    const row = document.createElement('tr');

                    // ID
                    const idCell = document.createElement('td');
                    idCell.textContent = user.id;
                    row.appendChild(idCell);

                    // Username
                    const usernameCell = document.createElement('td');
                    usernameCell.textContent = user.username;
                    row.appendChild(usernameCell);

                    // Name
                    const nameCell = document.createElement('td');
                    nameCell.textContent = `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'N/A';
                    row.appendChild(nameCell);

                    // Email
                    const emailCell = document.createElement('td');
                    emailCell.textContent = user.email;
                    row.appendChild(emailCell);

                    // Role
                    const roleCell = document.createElement('td');
                    roleCell.textContent = user.role.charAt(0).toUpperCase() + user.role.slice(1);
                    row.appendChild(roleCell);

                    // Joined
                    const joinedCell = document.createElement('td');
                    joinedCell.textContent = new Date(user.created_at).toLocaleDateString();
                    row.appendChild(joinedCell);

                    // Last Login
                    const lastLoginCell = document.createElement('td');
                    lastLoginCell.textContent = user.last_login ? new Date(user.last_login).toLocaleString() : 'Never';
                    row.appendChild(lastLoginCell);

                    // Status
                    const statusCell = document.createElement('td');
                    statusCell.textContent = user.is_active ? 'Active' : 'Inactive';
                    statusCell.style.color = user.is_active ? 'var(--success-color)' : 'var(--danger-color)';
                    row.appendChild(statusCell);

                    tbody.appendChild(row);
                });

                table.appendChild(tbody);
                tableContainer.appendChild(table);
            } else {
                tableContainer.innerHTML = `<p>Error loading users: ${data.message}</p>`;
            }
        })
        .catch(error => {
            console.error('Error loading users:', error);
            tableContainer.innerHTML = '<p>Error loading users. Please try again.</p>';
        });
}

/**
 * Load active chats
 */
function loadActiveChats() {
    const activeChatsTab = document.getElementById('active-chats');
    activeChatsTab.innerHTML = '<div class="tab-header"><h1>Active Chats</h1></div>';

    // Create a container for the active chats table
    const tableContainer = document.createElement('div');
    tableContainer.className = 'table-container';

    // Create a loading message
    const loadingMessage = document.createElement('p');
    loadingMessage.textContent = 'Loading active chats...';
    tableContainer.appendChild(loadingMessage);

    activeChatsTab.appendChild(tableContainer);

    // Fetch active chats
    fetch('/api/agent/active_chats')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Clear the loading message
                tableContainer.innerHTML = '';

                if (data.chats && data.chats.length > 0) {
                    // Create the table
                    const table = document.createElement('table');

                    // Create the table header
                    const thead = document.createElement('thead');
                    const headerRow = document.createElement('tr');

                    const headers = ['ID', 'User', 'Start Time', 'Language', 'Actions'];
                    headers.forEach(headerText => {
                        const th = document.createElement('th');
                        th.textContent = headerText;
                        headerRow.appendChild(th);
                    });

                    thead.appendChild(headerRow);
                    table.appendChild(thead);

                    // Create the table body
                    const tbody = document.createElement('tbody');

                    data.chats.forEach(chat => {
                        const row = document.createElement('tr');

                        // ID
                        const idCell = document.createElement('td');
                        idCell.textContent = chat.session_id;
                        row.appendChild(idCell);

                        // User
                        const userCell = document.createElement('td');
                        userCell.textContent = chat.username || chat.first_name || 'Guest User';
                        row.appendChild(userCell);

                        // Start Time
                        const startCell = document.createElement('td');
                        startCell.textContent = new Date(chat.session_start).toLocaleString();
                        row.appendChild(startCell);

                        // Language
                        const langCell = document.createElement('td');
                        langCell.textContent = chat.language || 'en';
                        row.appendChild(langCell);

                        // Actions
                        const actionsCell = document.createElement('td');

                        // View button
                        const viewBtn = document.createElement('button');
                        viewBtn.className = 'action-btn edit-btn';
                        viewBtn.textContent = 'View';
                        viewBtn.addEventListener('click', () => {
                            // Create modal for chat details
                            const modal = document.createElement('div');
                            modal.className = 'modal';
                            modal.id = 'chat-details-modal';
                            modal.style.display = 'flex';

                            const modalContent = document.createElement('div');
                            modalContent.className = 'modal-content';

                            // Modal header
                            const modalHeader = document.createElement('div');
                            modalHeader.className = 'modal-header';

                            const modalTitle = document.createElement('h2');
                            modalTitle.textContent = `Chat #${chat.session_id} Details`;

                            const closeBtn = document.createElement('button');
                            closeBtn.className = 'close-modal';
                            closeBtn.innerHTML = '&times;';
                            closeBtn.addEventListener('click', () => {
                                document.body.removeChild(modal);
                            });

                            modalHeader.appendChild(modalTitle);
                            modalHeader.appendChild(closeBtn);

                            // Modal body
                            const modalBody = document.createElement('div');
                            modalBody.innerHTML = '<p>Loading chat details...</p>';

                            modalContent.appendChild(modalHeader);
                            modalContent.appendChild(modalBody);
                            modal.appendChild(modalContent);

                            document.body.appendChild(modal);

                            // Fetch chat messages
                            fetch(`/api/agent/chat_messages?session_id=${chat.session_id}`)
                                .then(response => response.json())
                                .then(data => {
                                    if (data.success) {
                                        const messages = data.messages || [];

                                        let html = `
                                            <div class="chat-info">
                                                <h3>Chat Information</h3>
                                                <div><strong>Session ID:</strong> ${chat.session_id}</div>
                                                <div><strong>User:</strong> ${chat.username || chat.first_name || 'Guest User'}</div>
                                                <div><strong>Start Time:</strong> ${new Date(chat.session_start).toLocaleString()}</div>
                                                <div><strong>Language:</strong> ${chat.language || 'en'}</div>
                                            </div>

                                            <div class="chat-messages">
                                                <h3>Messages</h3>
                                        `;

                                        if (messages.length > 0) {
                                            html += '<div class="chat-messages-container">';

                                            messages.forEach(message => {
                                                const messageClass = message.sender_type === 'customer' ? 'user-message' : 'bot-message';
                                                const senderName = message.sender_type === 'agent' ? `<strong>Agent ${message.sender_name || ''}:</strong> ` : '';

                                                html += `
                                                    <div class="message ${messageClass}">
                                                        <div>${senderName}${message.message_text}</div>
                                                        <div class="message-time">${new Date(message.timestamp).toLocaleString()}</div>
                                                    </div>
                                                `;
                                            });

                                            html += '</div>';
                                        } else {
                                            html += '<p>No messages found for this chat.</p>';
                                        }

                                        html += '</div>';

                                        // Add agent response form
                                        html += `
                                            <div class="agent-response">
                                                <h3>Respond as Agent</h3>
                                                <form id="agent-response-form">
                                                    <input type="hidden" id="agent-session-id" value="${chat.session_id}">
                                                    <div class="form-group">
                                                        <textarea id="agent-message" class="form-control" rows="3" placeholder="Type your response here..."></textarea>
                                                    </div>
                                                    <button type="submit" class="btn btn-primary">Send</button>
                                                </form>
                                            </div>
                                        `;

                                        modalBody.innerHTML = html;

                                        // Set up agent response form
                                        const responseForm = document.getElementById('agent-response-form');
                                        if (responseForm) {
                                            responseForm.addEventListener('submit', (e) => {
                                                e.preventDefault();

                                                const sessionId = document.getElementById('agent-session-id').value;
                                                const message = document.getElementById('agent-message').value;

                                                if (!message.trim()) {
                                                    alert('Please enter a message');
                                                    return;
                                                }

                                                // Send agent response
                                                fetch('/api/agent/send_message', {
                                                    method: 'POST',
                                                    headers: {
                                                        'Content-Type': 'application/json'
                                                    },
                                                    body: JSON.stringify({
                                                        session_id: sessionId,
                                                        message: message
                                                    })
                                                })
                                                .then(response => response.json())
                                                .then(data => {
                                                    if (data.success) {
                                                        // Clear the message input
                                                        document.getElementById('agent-message').value = '';

                                                        // Refresh the messages
                                                        fetch(`/api/agent/chat_messages?session_id=${sessionId}`)
                                                            .then(response => response.json())
                                                            .then(data => {
                                                                if (data.success) {
                                                                    const messages = data.messages || [];

                                                                    let messagesHtml = '<h3>Messages</h3>';

                                                                    if (messages.length > 0) {
                                                                        messagesHtml += '<div class="chat-messages-container">';

                                                                        messages.forEach(message => {
                                                                            const messageClass = message.sender_type === 'customer' ? 'user-message' : 'bot-message';
                                                                            const senderName = message.sender_type === 'agent' ? `<strong>Agent ${message.sender_name || ''}:</strong> ` : '';

                                                                            messagesHtml += `
                                                                                <div class="message ${messageClass}">
                                                                                    <div>${senderName}${message.message_text}</div>
                                                                                    <div class="message-time">${new Date(message.timestamp).toLocaleString()}</div>
                                                                                </div>
                                                                            `;
                                                                        });

                                                                        messagesHtml += '</div>';
                                                                    } else {
                                                                        messagesHtml += '<p>No messages found for this chat.</p>';
                                                                    }

                                                                    document.querySelector('.chat-messages').innerHTML = messagesHtml;
                                                                }
                                                            })
                                                            .catch(error => {
                                                                console.error('Error refreshing messages:', error);
                                                            });
                                                    } else {
                                                        alert(`Error sending message: ${data.message}`);
                                                    }
                                                })
                                                .catch(error => {
                                                    console.error('Error sending agent message:', error);
                                                    alert('Error sending message. Please try again.');
                                                });
                                            });
                                        }
                                    } else {
                                        modalBody.innerHTML = `<p>Error loading chat details: ${data.message}</p>`;
                                    }
                                })
                                .catch(error => {
                                    console.error('Error loading chat details:', error);
                                    modalBody.innerHTML = '<p>Error loading chat details. Please try again.</p>';
                                });
                        });

                        actionsCell.appendChild(viewBtn);

                        // Take over button
                        const takeOverBtn = document.createElement('button');
                        takeOverBtn.className = 'action-btn';
                        takeOverBtn.textContent = 'Take Over';
                        takeOverBtn.style.backgroundColor = 'var(--primary-color)';
                        takeOverBtn.style.color = 'white';
                        takeOverBtn.style.marginLeft = '5px';
                        takeOverBtn.addEventListener('click', () => {
                            // Take over the chat
                            fetch('/api/agent/take_over', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({
                                    session_id: chat.session_id
                                })
                            })
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    alert('You have taken over this chat. You can now respond to the customer.');

                                    // Refresh the active chats
                                    loadActiveChats();
                                } else {
                                    alert(`Error taking over chat: ${data.message}`);
                                }
                            })
                            .catch(error => {
                                console.error('Error taking over chat:', error);
                                alert('Error taking over chat. Please try again.');
                            });
                        });

                        actionsCell.appendChild(takeOverBtn);
                        row.appendChild(actionsCell);

                        tbody.appendChild(row);
                    });

                    table.appendChild(tbody);
                    tableContainer.appendChild(table);
                } else {
                    tableContainer.innerHTML = '<p>No active chats found.</p>';
                }
            } else {
                tableContainer.innerHTML = `<p>Error loading active chats: ${data.message}</p>`;
            }
        })
        .catch(error => {
            console.error('Error loading active chats:', error);
            tableContainer.innerHTML = '<p>Error loading active chats. Please try again.</p>';
        });
}

/**
 * Load promotions
 */
function loadPromotions() {
    // This function is implemented in admin_promotions.js
    // Just call the function from there
    if (typeof window.loadPromotions === 'function') {
        window.loadPromotions();
    } else {
        const promotionsTab = document.getElementById('promotions');
        promotionsTab.innerHTML = '<div class="tab-header"><h1>Promotions</h1></div><p>Promotions functionality is not available. Please check the console for errors.</p>';
        console.error('loadPromotions function not found. Make sure admin_promotions.js is properly loaded.');
    }
}

/**
 * Load analytics
 */
function loadAnalytics() {
    // This function is implemented in admin_analytics.js
    // Just call the function from there
    if (typeof window.loadAnalytics === 'function') {
        window.loadAnalytics();
    } else {
        const analyticsTab = document.getElementById('analytics');
        analyticsTab.innerHTML = '<div class="tab-header"><h1>Analytics</h1></div><p>Analytics functionality is not available. Please check the console for errors.</p>';
        console.error('loadAnalytics function not found. Make sure admin_analytics.js is properly loaded.');
    }
}

/**
 * Load products
 */
function loadProducts() {
    // This function is implemented in admin_products.js
    // Just call the function from there
    if (typeof window.loadProducts === 'function') {
        window.loadProducts();
    } else {
        const productsTab = document.getElementById('products');
        productsTab.innerHTML = '<div class="tab-header"><h1>Products</h1></div><p>Products functionality is not available. Please check the console for errors.</p>';
        console.error('loadProducts function not found. Make sure admin_products.js is properly loaded.');
    }
}
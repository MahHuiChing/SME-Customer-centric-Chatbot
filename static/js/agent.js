/**
 * Rock Chatbot - Agent Interface
 *
 * This script handles the agent interface for taking over customer chats.
 * It provides functionality for agents to:
 * 1. View active chats
 * 2. Handle multiple customer chats simultaneously
 * 3. Set online/offline status
 * 4. Transfer chats to other online agents
 * 5. View customer details and order history
 */

// Global variables
let currentSessionId = null;
let currentCustomerId = null;
let pollingInterval = null;
let activeSessions = [];
let isOnline = true;
let pendingFaqs = [];
let socket = null;

// Real-time status tracking
let lastActivityTime = Date.now();
let heartbeatInterval = null;
let inactivityCheckInterval = null;
let connectionCheckInterval = null;
let isPageVisible = true;

// Configuration
const HEARTBEAT_INTERVAL = 30000; // 30 seconds
const INACTIVITY_TIMEOUT = 10 * 60 * 1000; // 10 minutes
const CONNECTION_CHECK_INTERVAL = 60000; // 1 minute
const ACTIVITY_UPDATE_INTERVAL = 10000; // 10 seconds

// Array of colors for category tags
const colors = [
    '#4361ee', '#3a0ca3', '#7209b7', '#f72585', '#4cc9f0',
    '#f77f00', '#2b9348', '#ff9e00', '#9d4edd', '#06d6a0',
    '#118ab2', '#073b4c', '#fb8500', '#457b9d', '#6c757d'
];

/**
 * Generate a hash code from a string
 * @param {string} str - The string to hash
 * @returns {number} A hash code
 */
function hashCode(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32bit integer
    }
    return hash;
}

// DOM elements
const activeChats = document.getElementById('active-chats');
const customerDetails = document.getElementById('customer-details');
const chatMessages = document.getElementById('agent-chat-messages');
const messageInput = document.getElementById('agent-message-input');
const sendButton = document.getElementById('send-agent-message');
const endChatBtn = document.getElementById('end-chat-btn');
const transferChatBtn = document.getElementById('transfer-chat-btn');
const chatCustomerName = document.getElementById('chat-customer-name');
const statusToggle = document.getElementById('agent-status-toggle');

// Initialize the agent interface
document.addEventListener('DOMContentLoaded', () => {
    // Initialize WebSocket connection
    initializeWebSocket();

    // Set agent as online
    setAgentStatus(true);

    // Load active chats
    loadActiveChats();

    // Load my assigned sessions
    loadMyAssignedSessions();

    // Load my active sessions list
    loadMyActiveSessions();

    // Set up polling for active chats (every 10 seconds)
    pollingInterval = setInterval(() => {
        loadActiveChats();
        loadMyAssignedSessions();
        loadMyActiveSessions();
        updateAgentActivity();
    }, ACTIVITY_UPDATE_INTERVAL);

    // Initialize real-time status monitoring
    initializeRealTimeStatus();

    // Check for pending FAQs
    loadPendingFAQs();

    // Check for pending FAQs periodically (every 5 minutes)
    setInterval(checkPendingFAQs, 5 * 60 * 1000);

    // Set up event listeners
    if (sendButton) {
        sendButton.addEventListener('click', sendAgentMessage);
    }

    if (messageInput) {
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendAgentMessage();
            }
        });
    }

    if (endChatBtn) {
        endChatBtn.addEventListener('click', endChat);
    }

    if (transferChatBtn) {
        transferChatBtn.addEventListener('click', transferChat);
    }

    if (statusToggle) {
        statusToggle.addEventListener('change', function() {
            setAgentStatus(this.checked);
        });
    }

    // Add event listeners to quick response buttons
    document.querySelectorAll('.quick-response-btn').forEach(button => {
        // Single click to insert the response
        button.addEventListener('click', function() {
            const messageInput = document.getElementById('agent-message-input');
            messageInput.value = this.dataset.response;
            messageInput.focus();
            // Trigger the auto-resize
            autoResizeTextarea(messageInput);
        });

        // Double click to edit the quick response
        button.addEventListener('dblclick', function(e) {
            e.preventDefault();
            e.stopPropagation();

            // Get the current response text
            const currentText = this.dataset.response;
            const buttonLabel = this.textContent;

            // Create a modal for editing
            const modal = document.createElement('div');
            modal.className = 'modal';
            modal.style.display = 'flex';

            modal.innerHTML = `
                <div class="modal-content" style="max-width: 500px;">
                    <div class="modal-header">
                        <h2>Edit Quick Response</h2>
                        <button class="close-modal">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label>Response Label</label>
                            <input type="text" id="quick-response-label" value="${buttonLabel}" class="form-control">
                        </div>
                        <div class="form-group">
                            <label>Response Text</label>
                            <textarea id="quick-response-text" rows="5" class="form-control">${currentText}</textarea>
                        </div>
                        <div class="form-actions">
                            <button type="button" class="btn btn-secondary cancel-edit">Cancel</button>
                            <button type="button" class="btn save-quick-response">Save</button>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            // Add event listeners to the modal buttons
            modal.querySelector('.close-modal').addEventListener('click', () => {
                document.body.removeChild(modal);
            });

            modal.querySelector('.cancel-edit').addEventListener('click', () => {
                document.body.removeChild(modal);
            });

            modal.querySelector('.save-quick-response').addEventListener('click', () => {
                const newLabel = document.getElementById('quick-response-label').value.trim();
                const newText = document.getElementById('quick-response-text').value.trim();

                if (newLabel && newText) {
                    // Update the button
                    this.textContent = newLabel;
                    this.dataset.response = newText;

                    // Save to localStorage for persistence
                    saveQuickResponses();

                    // Show notification
                    showNotification('Quick response updated', 'success');
                }

                document.body.removeChild(modal);
            });
        });
    });

    // Function to save quick responses to localStorage
    function saveQuickResponses() {
        const responses = [];
        document.querySelectorAll('.quick-response-btn').forEach(button => {
            responses.push({
                label: button.textContent,
                text: button.dataset.response
            });
        });
        localStorage.setItem('quickResponses', JSON.stringify(responses));
    }

    // Auto-resize textarea when typing
    if (messageInput) {
        messageInput.addEventListener('input', function() {
            autoResizeTextarea(this);
        });

        // Initial resize
        autoResizeTextarea(messageInput);
    }

    // Set up initial chat (using the first active chat)
    const firstChat = document.querySelector('.chat-item');
    if (firstChat) {
        firstChat.click();
    }

    // Initialize knowledge base
    initKnowledgeBase();

    // Set up category select change handler for FAQ form
    const categorySelect = document.getElementById('faq-category');
    if (categorySelect) {
        categorySelect.addEventListener('change', function() {
            const newCategoryContainer = document.getElementById('new-category-container');
            if (this.value === 'new') {
                newCategoryContainer.style.display = 'block';
                document.getElementById('new-faq-category').focus();
            } else {
                newCategoryContainer.style.display = 'none';
            }
        });
    }
});

/**
 * Initialize real-time status monitoring
 */
function initializeRealTimeStatus() {
    console.log('Initializing real-time status monitoring...');

    // Set up heartbeat to server
    startHeartbeat();

    // Set up inactivity monitoring
    startInactivityMonitoring();

    // Set up connection monitoring
    startConnectionMonitoring();

    // Set up page visibility monitoring
    setupPageVisibilityMonitoring();

    // Set up activity tracking
    setupActivityTracking();

    // Set up browser close detection
    setupBrowserCloseDetection();
}

/**
 * Start heartbeat to server
 */
function startHeartbeat() {
    heartbeatInterval = setInterval(() => {
        if (isOnline && isPageVisible) {
            sendHeartbeat();
        }
    }, HEARTBEAT_INTERVAL);
}

/**
 * Send heartbeat to server
 */
function sendHeartbeat() {
    fetch('/api/agent/heartbeat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            timestamp: Date.now()
        })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            console.warn('Heartbeat failed:', data.message);
            // If heartbeat fails, try to reconnect
            handleConnectionLoss();
        }
    })
    .catch(error => {
        console.error('Heartbeat error:', error);
        handleConnectionLoss();
    });
}

/**
 * Start inactivity monitoring
 */
function startInactivityMonitoring() {
    inactivityCheckInterval = setInterval(() => {
        const timeSinceLastActivity = Date.now() - lastActivityTime;

        if (timeSinceLastActivity > INACTIVITY_TIMEOUT && isOnline) {
            console.log('Agent inactive for too long, setting offline');
            setAgentStatus(false, 'Automatically set offline due to inactivity');
            showNotification('You have been set offline due to inactivity', 'warning');
        }
    }, 60000); // Check every minute
}

/**
 * Start connection monitoring
 */
function startConnectionMonitoring() {
    connectionCheckInterval = setInterval(() => {
        if (isOnline) {
            checkConnection();
        }
    }, CONNECTION_CHECK_INTERVAL);
}

/**
 * Check connection to server
 */
function checkConnection() {
    fetch('/api/agent/ping', {
        method: 'GET',
        cache: 'no-cache'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Connection check failed');
        }
        return response.json();
    })
    .then(data => {
        if (!data.success) {
            handleConnectionLoss();
        }
    })
    .catch(error => {
        console.error('Connection check failed:', error);
        handleConnectionLoss();
    });
}

/**
 * Handle connection loss
 */
function handleConnectionLoss() {
    if (isOnline) {
        console.log('Connection lost, attempting to reconnect...');
        showNotification('Connection lost. Attempting to reconnect...', 'warning');

        // Try to reconnect after a delay
        setTimeout(() => {
            if (isOnline) {
                setAgentStatus(true, 'Reconnecting after connection loss');
            }
        }, 5000);
    }
}

/**
 * Setup page visibility monitoring
 */
function setupPageVisibilityMonitoring() {
    // Handle page visibility changes
    document.addEventListener('visibilitychange', () => {
        isPageVisible = !document.hidden;

        if (isPageVisible) {
            console.log('Page became visible');
            updateActivity();
            // Resume heartbeat if online
            if (isOnline && !heartbeatInterval) {
                startHeartbeat();
            }
        } else {
            console.log('Page became hidden');
            // Don't immediately go offline, but stop heartbeat
            if (heartbeatInterval) {
                clearInterval(heartbeatInterval);
                heartbeatInterval = null;
            }
        }
    });
}

/**
 * Setup activity tracking
 */
function setupActivityTracking() {
    // Track various user activities
    const activityEvents = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];

    activityEvents.forEach(event => {
        document.addEventListener(event, updateActivity, true);
    });
}

/**
 * Update activity timestamp
 */
function updateActivity() {
    lastActivityTime = Date.now();
}

/**
 * Setup browser close detection
 */
function setupBrowserCloseDetection() {
    // Handle browser/tab close
    window.addEventListener('beforeunload', (event) => {
        if (isOnline) {
            // Set agent offline immediately
            navigator.sendBeacon('/api/agent/set_offline', JSON.stringify({
                reason: 'Browser closed'
            }));
        }
    });

    // Handle page unload
    window.addEventListener('unload', () => {
        if (isOnline) {
            navigator.sendBeacon('/api/agent/set_offline', JSON.stringify({
                reason: 'Page unloaded'
            }));
        }
    });
}

/**
 * Cleanup intervals when going offline
 */
function cleanupIntervals() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }
    if (inactivityCheckInterval) {
        clearInterval(inactivityCheckInterval);
        inactivityCheckInterval = null;
    }
    if (connectionCheckInterval) {
        clearInterval(connectionCheckInterval);
        connectionCheckInterval = null;
    }
}

/**
 * Set agent online/offline status
 * @param {boolean} online - Whether the agent is online
 * @param {string} reason - Optional reason for status change
 */
function setAgentStatus(online, reason = '') {
    const previousStatus = isOnline;
    isOnline = online;

    // Update activity timestamp
    updateActivity();

    // Update UI
    if (statusToggle) {
        statusToggle.checked = online;
    }

    // Update status text
    const statusText = document.getElementById('status-text');
    if (statusText) {
        statusText.textContent = online ? 'Online' : 'Offline';
        statusText.style.color = online ? '#4CAF50' : '#f44336';
    }

    // Manage real-time monitoring based on status
    if (online && !previousStatus) {
        // Going online - start monitoring
        console.log('Going online, starting real-time monitoring');
        startHeartbeat();
        startInactivityMonitoring();
        startConnectionMonitoring();
    } else if (!online && previousStatus) {
        // Going offline - cleanup monitoring
        console.log('Going offline, stopping real-time monitoring');
        cleanupIntervals();
    }

    // Update status in the database
    fetch('/api/agent/set_status', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            is_online: online,
            reason: reason
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`Agent status set to ${online ? 'online' : 'offline'}${reason ? ` (${reason})` : ''}`);
            if (reason) {
                showNotification(`Status changed: ${reason}`, online ? 'success' : 'info');
            }
        } else {
            console.error('Error setting agent status:', data.message);
            // Revert status and UI if there was an error
            isOnline = previousStatus;
            if (statusToggle) {
                statusToggle.checked = previousStatus;
            }
            if (statusText) {
                statusText.textContent = previousStatus ? 'Online' : 'Offline';
                statusText.style.color = previousStatus ? '#4CAF50' : '#f44336';
            }
            showNotification('Failed to update status', 'error');
        }
    })
    .catch(error => {
        console.error('Error setting agent status:', error);
        // Revert status and UI if there was an error
        isOnline = previousStatus;
        if (statusToggle) {
            statusToggle.checked = previousStatus;
        }
        if (statusText) {
            statusText.textContent = previousStatus ? 'Online' : 'Offline';
            statusText.style.color = previousStatus ? '#4CAF50' : '#f44336';
        }
        showNotification('Failed to update status', 'error');
    });
}

/**
 * Update agent activity timestamp
 */
function updateAgentActivity() {
    // Update local activity timestamp
    updateActivity();

    // Update server activity timestamp
    fetch('/api/agent/update_activity', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            timestamp: Date.now()
        })
    })
    .catch(error => {
        console.error('Error updating agent activity:', error);
    });
}

/**
 * Show notification to user
 * @param {string} message - The notification message
 * @param {string} type - The notification type (success, error, warning, info)
 */
function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.agent-notification');
    existingNotifications.forEach(notification => notification.remove());

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `agent-notification ${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-message">${message}</span>
            <button class="notification-close">&times;</button>
        </div>
    `;

    // Add styles
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${getNotificationColor(type)};
        color: white;
        padding: 12px 16px;
        border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        max-width: 400px;
        font-size: 14px;
        transform: translateX(100%);
        transition: transform 0.3s ease-out;
    `;

    // Add animation styles to document if not already added
    if (!document.getElementById('notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            .agent-notification {
                display: flex;
                align-items: center;
            }
            .notification-content {
                display: flex;
                align-items: center;
                justify-content: space-between;
                width: 100%;
            }
            .notification-close {
                background: none;
                border: none;
                color: white;
                font-size: 18px;
                cursor: pointer;
                margin-left: 10px;
                padding: 0;
                line-height: 1;
            }
            .notification-close:hover {
                opacity: 0.7;
            }
        `;
        document.head.appendChild(style);
    }

    // Add close functionality
    const closeBtn = notification.querySelector('.notification-close');
    closeBtn.addEventListener('click', () => {
        notification.remove();
    });

    // Add to page
    document.body.appendChild(notification);

    // Trigger animation
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 10);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 300);
        }
    }, 5000);
}

/**
 * Get notification color based on type
 * @param {string} type - The notification type
 * @returns {string} The color for the notification
 */
function getNotificationColor(type) {
    switch (type) {
        case 'success': return '#4CAF50';
        case 'error': return '#f44336';
        case 'warning': return '#ff9800';
        case 'info':
        default: return '#2196F3';
    }
}

/**
 * Load active chats that need agent assistance
 */
function loadActiveChats() {
    fetch('/api/agent/active_chats')
        .then(response => {
            if (response.status === 401 || response.status === 403) {
                // Unauthorized - redirect to login
                window.location.href = '/login';
                return;
            }
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (!data) return; // Handle case where we redirected

            if (data.success) {
                // Clear existing chats
                activeChats.innerHTML = '';

                if (data.chats.length === 0) {
                    activeChats.innerHTML = '<p>No active chats at the moment.</p>';
                    return;
                }

                // Add each chat to the list
                data.chats.forEach(chat => {
                    // Skip chats that are already assigned to an agent
                    if (chat.agent_id && !activeSessions.includes(chat.session_id)) {
                        return;
                    }

                    const chatItem = document.createElement('div');
                    chatItem.className = 'chat-item';
                    if (chat.session_id === currentSessionId) {
                        chatItem.classList.add('active');
                    }
                    if (activeSessions.includes(parseInt(chat.session_id))) {
                        chatItem.classList.add('assigned');
                    }
                    chatItem.dataset.sessionId = chat.session_id;
                    chatItem.dataset.customerId = chat.customer_id;

                    // Use the enhanced display name from server
                    let customerName = chat.display_name || chat.customer_name || `Guest-${chat.session_id}`;

                    // Add user type indicator
                    const userType = chat.is_guest ? ' (Guest)' : ' (Registered)';
                    const displayName = customerName + userType;

                    const userDiv = document.createElement('div');
                    userDiv.innerHTML = `<strong>User:</strong> ${displayName}`;

                    const timeDiv = document.createElement('div');
                    const startTime = new Date(chat.session_start);
                    const timeAgo = getTimeAgo(startTime);
                    timeDiv.innerHTML = `<small>Started: ${timeAgo}</small>`;

                    // Add status indicator
                    const statusDiv = document.createElement('div');
                    if (activeSessions.includes(parseInt(chat.session_id))) {
                        statusDiv.innerHTML = '<span class="status-badge assigned">Assigned to you</span>';
                    } else if (chat.needs_agent) {
                        statusDiv.innerHTML = '<span class="status-badge needs-agent">Needs agent</span>';
                    }

                    chatItem.appendChild(userDiv);
                    chatItem.appendChild(timeDiv);
                    if (statusDiv.innerHTML) {
                        chatItem.appendChild(statusDiv);
                    }

                    // Add click event to load chat
                    chatItem.addEventListener('click', () => {
                        // Update active chat
                        document.querySelectorAll('.chat-item').forEach(item => {
                            item.classList.remove('active');
                        });
                        chatItem.classList.add('active');

                        // Load chat details
                        loadChatDetails(chat.session_id, chat.customer_id);
                    });

                    activeChats.appendChild(chatItem);
                });
            } else {
                console.error('Error loading active chats:', data.message);
                if (data.message === 'Unauthorized') {
                    window.location.href = '/login';
                    return;
                }
                activeChats.innerHTML = '<p>Error loading chats. Please refresh the page.</p>';
            }
        })
        .catch(error => {
            console.error('Error loading active chats:', error);
            activeChats.innerHTML = '<p>Error loading chats. Please check your connection and refresh the page.</p>';
        });
}

/**
 * Load sessions assigned to the current agent
 */
function loadMyAssignedSessions() {
    fetch('/api/agent/my_sessions')
        .then(response => {
            if (response.status === 401 || response.status === 403) {
                window.location.href = '/login';
                return;
            }
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (!data) return;

            if (data.success) {
                // Update active sessions list
                activeSessions = data.sessions.map(session => parseInt(session.session_id));

                // Update active sessions count
                const activeSessionsCount = document.getElementById('active-sessions-count');
                if (activeSessionsCount) {
                    activeSessionsCount.textContent = activeSessions.length;
                }

                // Update UI to show which chats are assigned to this agent
                document.querySelectorAll('.chat-item').forEach(item => {
                    const sessionId = parseInt(item.dataset.sessionId);
                    if (activeSessions.includes(sessionId)) {
                        item.classList.add('assigned');
                    } else {
                        item.classList.remove('assigned');
                    }
                });
            } else {
                console.error('Error loading assigned sessions:', data.message);
            }
        })
        .catch(error => {
            console.error('Error loading assigned sessions:', error);
        });
}

/**
 * Load my active sessions for the take-over list
 */
function loadMyActiveSessions() {
    const mySessionsList = document.getElementById('my-sessions-list');

    if (!mySessionsList) {
        return;
    }

    fetch('/api/agent/my_sessions')
        .then(response => {
            if (response.status === 401 || response.status === 403) {
                window.location.href = '/login';
                return;
            }
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (!data) return;

            if (data.success) {
                // Clear the list
                mySessionsList.innerHTML = '';

                if (data.sessions.length === 0) {
                    mySessionsList.innerHTML = '<div class="no-results">No active sessions</div>';
                    return;
                }

                // Sort sessions by most recent first
                data.sessions.sort((a, b) => {
                    return new Date(b.last_message_time || 0) - new Date(a.last_message_time || 0);
                });

                // Add each session to the list
                data.sessions.forEach(session => {
                    const sessionItem = document.createElement('div');
                    sessionItem.className = 'session-item';
                    if (session.session_id === currentSessionId) {
                        sessionItem.classList.add('active');
                    }

                    // Create a more identifiable customer name
                    let customerName = '';
                    if (session.first_name || session.last_name) {
                        customerName = `${session.first_name || ''} ${session.last_name || ''}`.trim();
                    } else if (session.username) {
                        customerName = session.username;
                    } else if (session.email) {
                        // Use email prefix as a fallback
                        customerName = session.email.split('@')[0];
                    } else {
                        // Add session ID to make it unique
                        customerName = `Guest-${session.session_id}`;
                    }

                    const sessionTime = session.last_activity ?
                        new Date(session.last_activity).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) :
                        'New';

                    sessionItem.innerHTML = `
                        <div class="session-customer">${customerName}</div>
                        <div class="session-time">${sessionTime}</div>
                    `;

                    // Add click event to switch to this session
                    sessionItem.addEventListener('click', () => {
                        loadChatDetails(session.session_id, session.customer_id);

                        // Update active class
                        document.querySelectorAll('.session-item').forEach(item => {
                            item.classList.remove('active');
                        });
                        sessionItem.classList.add('active');
                    });

                    mySessionsList.appendChild(sessionItem);
                });
            } else {
                mySessionsList.innerHTML = `<div class="error">Error: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading my active sessions:', error);
            mySessionsList.innerHTML = '<div class="error">Failed to load sessions</div>';
        });
}

/**
 * Load chat details
 * @param {number} sessionId - The ID of the chat session
 * @param {number} customerId - The ID of the customer
 */
function loadChatDetails(sessionId, customerId) {
    console.log(`Loading chat details for session ${sessionId}, customer ${customerId}`);
    // Save current session and customer IDs
    currentSessionId = sessionId;
    currentCustomerId = customerId;

    // Check if this session is already assigned to this agent
    const isAssigned = activeSessions.includes(parseInt(sessionId));
    console.log(`Session ${sessionId} - isAssigned: ${isAssigned}, isOnline: ${isOnline}, activeSessions:`, activeSessions);

    // If not assigned and agent is online, take over the chat
    if (!isAssigned && isOnline) {
        console.log(`Taking over unassigned session ${sessionId}`);
        takeOverChat(sessionId);
    } else if (isAssigned) {
        console.log(`Session ${sessionId} already assigned, loading messages directly`);
        // If already assigned, join the WebSocket room immediately
        joinSessionRoom(sessionId);
        // Load complete chat messages with a small delay to ensure WebSocket connection
        setTimeout(() => {
            loadChatMessages(sessionId);
        }, 100);
    } else {
        console.log(`Loading messages for session ${sessionId} (viewing only)`);
        // Load chat messages even if not taking over (for viewing purposes)
        loadChatMessages(sessionId);
    }

    // Load customer details
    loadCustomerDetails(customerId);

    // Update customer recommendations
    if (customerId) {
        updateCustomerRecommendations(customerId);
    }
}

/**
 * Take over a chat session
 * @param {number} sessionId - The ID of the chat session
 */
function takeOverChat(sessionId) {
    console.log(`Taking over chat session ${sessionId}`);
    fetch('/api/agent/take_over_chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            session_id: sessionId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`Successfully took over chat ${sessionId}`);

            // Add to active sessions
            if (!activeSessions.includes(parseInt(sessionId))) {
                activeSessions.push(parseInt(sessionId));
            }

            // Update UI
            const chatItem = document.querySelector(`.chat-item[data-session-id="${sessionId}"]`);
            if (chatItem) {
                chatItem.classList.add('assigned');
            }

            // Set as current session and load complete chat history
            currentSessionId = parseInt(sessionId);

            // Join WebSocket room for this session first
            joinSessionRoom(sessionId);

            // Load complete chat history with a small delay to ensure WebSocket connection
            setTimeout(() => {
                loadChatMessages(sessionId);
            }, 100);

            // Load customer details for the session
            const customerId = chatItem ? chatItem.dataset.customerId : null;
            if (customerId && customerId !== 'null') {
                loadCustomerDetails(parseInt(customerId));
            } else {
                loadCustomerDetails(null); // Guest user
            }

            // Notify other users that agent joined
            if (socket) {
                socket.emit('agent_takeover', {
                    session_id: sessionId,
                    agent_name: userInfo.username || 'Agent'
                });
            }

            // Show success message
            showNotification('Successfully took over chat session', 'success');
        } else {
            console.error('Error taking over chat:', data.message);
            showNotification('Failed to take over chat: ' + data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error taking over chat:', error);
    });
}

/**
 * Load chat messages
 * @param {number} sessionId - The ID of the chat session
 */
function loadChatMessages(sessionId) {
    console.log(`Loading chat messages for session ${sessionId}`);
    fetch(`/api/agent/chat_messages?session_id=${sessionId}`)
        .then(response => response.json())
        .then(data => {
            console.log(`Received ${data.messages ? data.messages.length : 0} messages for session ${sessionId}:`, data);
            if (data.success) {
                // Clear existing messages
                chatMessages.innerHTML = '';

                // No need to track timestamps with WebSocket

                // Add each message to the chat
                data.messages.forEach((message, index) => {
                    const messageElement = document.createElement('div');
                    messageElement.className = 'message';

                    if (message.sender_type === 'customer') {
                        messageElement.classList.add('user-message');
                    } else if (message.sender_type === 'system') {
                        messageElement.classList.add('system-message');
                    } else {
                        messageElement.classList.add('bot-message');
                    }

                    const messageText = document.createElement('div');

                    // Handle different message types
                    if (message.sender_type === 'agent') {
                        messageText.innerHTML = `<strong>Agent ${message.sender_name || ''}:</strong> ${message.message_text}`;
                    } else if (message.sender_type === 'system') {
                        messageText.innerHTML = `<em style="color: #666; font-style: italic;">${message.message_text}</em>`;
                    } else {
                        messageText.textContent = message.message_text;
                    }

                    const messageTime = document.createElement('div');
                    messageTime.className = 'message-time';
                    messageTime.textContent = new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                    messageElement.appendChild(messageText);
                    messageElement.appendChild(messageTime);

                    chatMessages.appendChild(messageElement);

                    // WebSocket handles real-time updates
                });

                // WebSocket handles real-time messaging, no need for timestamp tracking

                // Scroll to the bottom
                chatMessages.scrollTop = chatMessages.scrollHeight;

                // Update customer name in the header
                if (data.customer_name) {
                    chatCustomerName.textContent = data.customer_name;
                } else {
                    chatCustomerName.textContent = 'Guest User';
                }
            } else {
                console.error('Error loading chat messages:', data.message);
            }
        })
        .catch(error => {
            console.error('Error loading chat messages:', error);
        });
}

/**
 * Load customer details including order history
 * @param {number} customerId - The ID of the customer
 */
function loadCustomerDetails(customerId) {
    if (!customerId || customerId === null || customerId === undefined) {
        // Handle guest user
        customerDetails.innerHTML = `
            <div><strong>Name:</strong> <span id="customer-name">Guest User</span></div>
            <div><strong>Email:</strong> <span id="customer-email">N/A</span></div>
            <div><strong>Phone:</strong> <span id="customer-phone">N/A</span></div>
            <div><strong>Joined:</strong> <span id="customer-joined">N/A</span></div>
            <div><strong>Orders:</strong> <span id="customer-orders">0</span></div>
            <div class="no-orders-message">No order history available for guest users.</div>
        `;
        return;
    }

    // Show loading indicator
    customerDetails.innerHTML = '<div class="loading">Loading customer details...</div>';

    fetch(`/api/agent/customer_details?customer_id=${customerId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const customer = data.customer;
                const orders = data.orders || [];

                let customerName = '';
                if (customer.first_name || customer.last_name) {
                    customerName = `${customer.first_name || ''} ${customer.last_name || ''}`.trim();
                } else {
                    customerName = customer.username || 'Unknown';
                }

                // Create basic customer info HTML
                let html = '';
                html += `<div><strong>Name:</strong> <span id="customer-name">${customerName}</span></div>`;
                html += `<div><strong>Email:</strong> <span id="customer-email">${customer.email || 'N/A'}</span></div>`;
                html += `<div><strong>Phone:</strong> <span id="customer-phone">${customer.phone_number || 'N/A'}</span></div>`;
                html += `<div><strong>Joined:</strong> <span id="customer-joined">${new Date(customer.created_at).toLocaleDateString()}</span></div>`;
                html += `<div><strong>Orders:</strong> <span id="customer-orders">${orders.length}</span></div>`;

                // Add customer preferences if available
                if (customer.preferences) {
                    html += `<div class="customer-preferences">`;
                    html += `<strong>Health Goals:</strong>`;

                    const goals = customer.preferences.goals || [];
                    if (goals.length > 0) {
                        html += `<div class="preference-tags">`;
                        goals.forEach(goal => {
                            html += `<span class="preference-tag">${goal}</span>`;
                        });
                        html += `</div>`;
                    } else {
                        html += `<span>No goals specified</span>`;
                    }

                    html += `</div>`;
                }

                // Add order history section
                if (orders.length > 0) {
                    html += '<div class="order-history">';
                    html += '<h3>Recent Orders</h3>';
                    html += '<table>';
                    html += '<thead>';
                    html += '<tr>';
                    html += '<th>ID</th>';
                    html += '<th>Date</th>';
                    html += '<th>Total</th>';
                    html += '<th>Status</th>';
                    html += '<th>Actions</th>';
                    html += '</tr>';
                    html += '</thead>';
                    html += '<tbody>';

                    // Show up to 3 most recent orders
                    const recentOrders = orders.slice(0, 3);

                    recentOrders.forEach(order => {
                        html += '<tr>';
                        html += `<td>${order.order_id}</td>`;
                        html += `<td>${new Date(order.order_date).toLocaleDateString()}</td>`;
                        html += `<td>RM ${parseFloat(order.total_amount).toFixed(2)}</td>`;
                        html += `<td>${order.status}</td>`;
                        html += `<td><button class="btn btn-sm" onclick="viewOrderDetails(${order.order_id})">Details</button></td>`;
                        html += '</tr>';
                    });

                    html += '</tbody>';
                    html += '</table>';
                    html += '<div style="margin-top: 10px; text-align: center;">';
                    html += `<button class="btn" onclick="viewAllOrders(${customerId})">View All Orders</button>`;
                    html += '</div>';
                    html += '</div>';
                } else {
                    html += '<div class="no-results">No order history available for this customer.</div>';
                }

                // Update customer details
                customerDetails.innerHTML = html;
            } else {
                console.error('Error loading customer details:', data.message);
                customerDetails.innerHTML = '<div class="error">Error loading customer details: ' + data.message + '</div>';
            }
        })
        .catch(error => {
            console.error('Error loading customer details:', error);
            customerDetails.innerHTML = '<div class="error">Failed to load customer details. Please try again.</div>';
        });
}

/**
 * View all orders for a customer
 * @param {number} customerId - The ID of the customer
 */
function viewAllOrders(customerId) {
    // Remove any existing modals
    const existingModal = document.getElementById('order-history-modal');
    if (existingModal) {
        document.body.removeChild(existingModal);
    }

    // Create modal for order history
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'order-history-modal';
    modal.style.display = 'flex';

    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';

    // Modal header
    const modalHeader = document.createElement('div');
    modalHeader.className = 'modal-header';

    const modalTitle = document.createElement('h2');
    modalTitle.textContent = 'Customer Order History';

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
    modalBody.className = 'modal-body';
    modalBody.innerHTML = '<div class="loading">Loading order history...</div>';

    modalContent.appendChild(modalHeader);
    modalContent.appendChild(modalBody);
    modal.appendChild(modalContent);

    document.body.appendChild(modal);

    // Add keyboard event listener to close modal with Escape key
    const handleKeyDown = (e) => {
        if (e.key === 'Escape') {
            document.body.removeChild(modal);
            document.removeEventListener('keydown', handleKeyDown);
        }
    };
    document.addEventListener('keydown', handleKeyDown);

    // Fetch order history
    fetch('/api/agent/customer_orders?customer_id=' + customerId)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const orders = data.orders || [];

                if (orders.length > 0) {
                    let html = '<div class="order-list-container" style="max-height: 60vh; overflow-y: auto;">';
                    html += '<table>';
                    html += '<thead>';
                    html += '<tr>';
                    html += '<th>Order ID</th>';
                    html += '<th>Date</th>';
                    html += '<th>Total</th>';
                    html += '<th>Status</th>';
                    html += '<th>Actions</th>';
                    html += '</tr>';
                    html += '</thead>';
                    html += '<tbody>';

                    orders.forEach(order => {
                        html += '<tr>';
                        html += '<td>' + order.order_id + '</td>';
                        html += '<td>' + new Date(order.order_date).toLocaleDateString() + '</td>';
                        html += '<td>RM ' + parseFloat(order.total_amount).toFixed(2) + '</td>';
                        html += '<td>' + order.status + '</td>';
                        html += '<td>';
                        html += '<button class="btn btn-sm" onclick="viewOrderDetails(' + order.order_id + ')">Details</button>';
                        html += '</td>';
                        html += '</tr>';
                    });

                    html += '</tbody>';
                    html += '</table>';
                    html += '</div>';
                    html += '<div style="margin-top: 15px; text-align: right;">';
                    html += '<button class="btn" onclick="document.body.removeChild(document.getElementById(\'order-history-modal\'))">Close</button>';
                    html += '</div>';

                    modalBody.innerHTML = html;
                } else {
                    modalBody.innerHTML = '<div class="no-results">No orders found for this customer.</div>';
                }
            } else {
                modalBody.innerHTML = '<div class="error">Error loading order history: ' + data.message + '</div>';
            }
        })
        .catch(error => {
            console.error('Error loading order history:', error);
            modalBody.innerHTML = '<div class="error">Error loading order history. Please try again.</div>';
        });
}

/**
 * View order details
 * @param {number} orderId - The ID of the order
 */
function viewOrderDetails(orderId) {
    // Remove any existing modals
    const existingModal = document.getElementById('order-details-modal');
    if (existingModal) {
        document.body.removeChild(existingModal);
    }

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
    modalTitle.textContent = 'Order #' + orderId + ' Details';

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
    modalBody.className = 'modal-body';
    modalBody.innerHTML = '<div class="loading">Loading order details...</div>';

    modalContent.appendChild(modalHeader);
    modalContent.appendChild(modalBody);
    modal.appendChild(modalContent);

    document.body.appendChild(modal);

    // Add keyboard event listener to close modal with Escape key
    const handleKeyDown = (e) => {
        if (e.key === 'Escape') {
            document.body.removeChild(modal);
            document.removeEventListener('keydown', handleKeyDown);
        }
    };
    document.addEventListener('keydown', handleKeyDown);

    // Fetch order details
    fetch('/api/admin/order_details?order_id=' + orderId)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const order = data.order;
                const items = data.items || [];

                let html = '<div class="order-details">';

                // Order info section
                html += '<div class="order-info">';
                html += '<h3>Order Information</h3>';
                html += '<div><strong>Order ID:</strong> ' + order.order_id + '</div>';
                html += '<div><strong>Customer:</strong> ' + (order.customer_name || 'N/A') + '</div>';
                html += '<div><strong>Date:</strong> ' + new Date(order.order_date).toLocaleDateString() + '</div>';
                html += '<div><strong>Total Amount:</strong> RM ' + parseFloat(order.total_amount).toFixed(2) + '</div>';
                html += '<div><strong>Status:</strong> ' + order.status + '</div>';
                html += '<div><strong>Payment Method:</strong> ' + (order.payment_method || 'N/A') + '</div>';
                html += '<div><strong>Payment Status:</strong> ' + (order.payment_status || 'N/A') + '</div>';
                html += '<div><strong>Shipping Address:</strong> ' + (order.shipping_address || 'N/A') + '</div>';
                html += '<div><strong>Tracking Number:</strong> ' + (order.tracking_number || 'N/A') + '</div>';
                html += '</div>';

                // Order items section
                html += '<div class="order-items">';
                html += '<h3>Order Items</h3>';

                if (items && items.length > 0) {
                    html += '<table>';
                    html += '<thead>';
                    html += '<tr>';
                    html += '<th>Product</th>';
                    html += '<th>Quantity</th>';
                    html += '<th>Unit Price</th>';
                    html += '<th>Subtotal</th>';
                    html += '</tr>';
                    html += '</thead>';
                    html += '<tbody>';

                    items.forEach(item => {
                        html += '<tr>';
                        html += '<td>' + item.product_name + '</td>';
                        html += '<td>' + item.quantity + '</td>';
                        html += '<td>RM ' + parseFloat(item.unit_price).toFixed(2) + '</td>';
                        html += '<td>RM ' + parseFloat(item.subtotal).toFixed(2) + '</td>';
                        html += '</tr>';
                    });

                    html += '</tbody>';
                    html += '</table>';
                } else {
                    html += '<p>No items found for this order.</p>';
                }

                html += '</div>';

                // Action buttons
                html += '<div class="order-actions">';
                html += '<button class="btn" onclick="copyOrderDetailsToMessage(' + orderId + ')">Copy to Message</button>';
                html += '<button class="btn" onclick="document.body.removeChild(document.getElementById(\'order-details-modal\'))">Close</button>';
                html += '</div>';

                html += '</div>';

                modalBody.innerHTML = html;
            } else {
                modalBody.innerHTML = '<div class="error">Error loading order details: ' + data.message + '</div>';
            }
        })
        .catch(error => {
            console.error('Error loading order details:', error);
            modalBody.innerHTML = '<div class="error">Error loading order details. Please try again.</div>';
        });
}

/**
 * Copy order details to message input
 * @param {number} orderId - The ID of the order
 */
function copyOrderDetailsToMessage(orderId) {
    fetch('/api/admin/order_details?order_id=' + orderId)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const order = data.order;
                const items = data.items || [];

                let messageText = 'Order #' + order.order_id + ' Details:\n';
                messageText += 'Date: ' + new Date(order.order_date).toLocaleDateString() + '\n';
                messageText += 'Status: ' + order.status + '\n';
                messageText += 'Total: RM ' + parseFloat(order.total_amount).toFixed(2) + '\n';

                if (order.tracking_number) {
                    messageText += 'Tracking Number: ' + order.tracking_number + '\n';
                }

                if (items && items.length > 0) {
                    messageText += '\nItems:\n';
                    items.forEach(item => {
                        messageText += '- ' + item.product_name + ' (' + item.quantity + ') - RM ' + parseFloat(item.subtotal).toFixed(2) + '\n';
                    });
                }

                // Set the message input value
                const messageInput = document.getElementById('agent-message-input');
                if (messageInput) {
                    messageInput.value = messageText;
                    messageInput.focus();
                }

                // Close the modal
                const modal = document.getElementById('order-details-modal');
                if (modal) {
                    document.body.removeChild(modal);
                }
            }
        })
        .catch(error => {
            console.error('Error copying order details:', error);
            alert('Failed to copy order details. Please try again.');
        });
}

/**
 * Send a message as an agent
 */
function sendAgentMessage() {
    if (!currentSessionId) {
        alert('No active chat selected');
        return;
    }

    const messageText = messageInput.value.trim();
    if (!messageText) {
        return;
    }

    // Clear the input field
    messageInput.value = '';

    // Add the message to the UI immediately (optimistic UI update)
    const timestamp = new Date();
    const messageElement = document.createElement('div');
    messageElement.className = 'message bot-message';

    const messageTextDiv = document.createElement('div');
    messageTextDiv.innerHTML = `<strong>Agent ${userInfo.username || ''}:</strong> ${messageText}`;

    const messageTimeDiv = document.createElement('div');
    messageTimeDiv.className = 'message-time';
    messageTimeDiv.textContent = timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    messageElement.appendChild(messageTextDiv);
    messageElement.appendChild(messageTimeDiv);

    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Send the message via WebSocket
    if (socket) {
        socket.emit('send_message', {
            session_id: currentSessionId,
            message: messageText,
            sender_type: 'agent',
            sender_name: userInfo.username || 'Agent'
        });
    } else {
        console.error('WebSocket not connected');
        alert('Connection error. Please refresh the page.');
    }
}

/**
 * End the current chat
 */
function endChat() {
    if (!currentSessionId) {
        alert('No active chat selected');
        return;
    }

    if (!confirm('Are you sure you want to end this chat?')) {
        return;
    }

    fetch('/api/agent/end_chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            session_id: currentSessionId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Chat ended successfully');

            // Leave WebSocket room for this session
            if (currentSessionId) {
                leaveSessionRoom(currentSessionId);

                // Notify other users that agent left
                if (socket) {
                    socket.emit('agent_end_chat', {
                        session_id: currentSessionId,
                        agent_name: userInfo.username || 'Agent'
                    });
                }
            }

            // Reload active chats
            loadActiveChats();

            // Clear current chat
            currentSessionId = null;
            currentCustomerId = null;

            // Clear chat messages
            chatMessages.innerHTML = '<div class="no-chat-selected">No chat selected</div>';

            // Clear customer details
            customerDetails.innerHTML = '<div class="no-customer-selected">No customer selected</div>';

            // Update chat header
            chatCustomerName.textContent = 'No Customer';
        } else {
            console.error('Error ending chat:', data.message);

            // Check if the error is because the chat is already ended
            if (data.message && data.message.includes('already ended')) {
                // Chat was already ended, just clean up the UI
                alert('Chat has already been ended.');

                // Leave WebSocket room for this session
                if (currentSessionId) {
                    leaveSessionRoom(currentSessionId);
                }

                // Reload active chats
                loadActiveChats();

                // Clear current chat
                currentSessionId = null;
                currentCustomerId = null;

                // Clear chat messages
                chatMessages.innerHTML = '<div class="no-chat-selected">No chat selected</div>';

                // Clear customer details
                customerDetails.innerHTML = '<div class="no-customer-selected">No customer selected</div>';

                // Update chat header
                chatCustomerName.textContent = 'No Customer';
            } else {
                alert('Failed to end chat: ' + (data.message || 'Unknown error'));
            }
        }
    })
    .catch(error => {
        console.error('Error ending chat:', error);
        alert('Failed to end chat. Please try again.');
    });
}

/**
 * Transfer the current chat to another agent
 */
function transferChat() {
    if (!currentSessionId) {
        alert('No active chat selected');
        return;
    }

    // Create modal for agent selection
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'transfer-chat-modal';
    modal.style.display = 'flex';

    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';

    // Modal header
    const modalHeader = document.createElement('div');
    modalHeader.className = 'modal-header';

    const modalTitle = document.createElement('h2');
    modalTitle.textContent = 'Transfer Chat';

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
    modalBody.innerHTML = '<p>Loading available agents...</p>';

    modalContent.appendChild(modalHeader);
    modalContent.appendChild(modalBody);
    modal.appendChild(modalContent);

    document.body.appendChild(modal);

    // Fetch available agents
    fetch('/api/agent/available_agents')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const agents = data.agents || [];

                if (agents.length > 0) {
                    let html = `
                        <p>Select an agent to transfer this chat to:</p>
                        <div class="agent-list">
                    `;

                    agents.forEach(agent => {
                        if (agent.staff_id !== userInfo.userId) {
                            const isOnline = agent.online_status === 1;
                            const activeChats = agent.active_chats || 0;
                            const lastActivity = agent.last_activity ? new Date(agent.last_activity) : null;
                            const lastActivityText = lastActivity ? getTimeAgo(lastActivity) : 'Unknown';

                            html += `
                                <div class="agent-item ${isOnline ? 'online' : 'offline'}" data-agent-id="${agent.staff_id}">
                                    <div class="agent-name">
                                        <span class="status-indicator ${isOnline ? 'online' : 'offline'}"></span>
                                        ${agent.first_name} ${agent.last_name}
                                    </div>
                                    <div class="agent-info">
                                        <small>Status: ${isOnline ? 'Online' : 'Offline'} | Active chats: ${activeChats} | Last activity: ${lastActivityText}</small>
                                    </div>
                                    <button class="btn" onclick="transferChatToAgent(${currentSessionId}, ${agent.staff_id})" ${!isOnline ? 'disabled' : ''}>
                                        ${isOnline ? 'Transfer' : 'Offline'}
                                    </button>
                                </div>
                            `;
                        }
                    });

                    html += `
                        </div>
                    `;

                    modalBody.innerHTML = html;
                } else {
                    modalBody.innerHTML = '<p>No other agents are available for transfer.</p>';
                }
            } else {
                modalBody.innerHTML = `<p>Error loading agents: ${data.message}</p>`;
            }
        })
        .catch(error => {
            console.error('Error loading agents:', error);
            modalBody.innerHTML = '<p>Error loading agents. Please try again.</p>';
        });
}

/**
 * Transfer a chat to a specific agent
 * @param {number} sessionId - The ID of the chat session
 * @param {number} agentId - The ID of the agent to transfer to
 */
function transferChatToAgent(sessionId, agentId) {
    fetch('/api/agent/transfer_chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            session_id: sessionId,
            agent_id: agentId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Chat transferred successfully', 'success');

            // Close the modal
            const modal = document.getElementById('transfer-chat-modal');
            if (modal) {
                document.body.removeChild(modal);
            }

            // Leave the WebSocket room for this session
            if (currentSessionId) {
                leaveSessionRoom(currentSessionId);
            }

            // Reload active chats
            loadActiveChats();

            // Clear current chat
            currentSessionId = null;
            currentCustomerId = null;

            // Clear chat messages
            chatMessages.innerHTML = '<div class="no-chat-selected">No chat selected</div>';

            // Clear customer details
            customerDetails.innerHTML = '<div class="no-customer-selected">No customer selected</div>';

            // Update chat header
            chatCustomerName.textContent = 'No Customer';
        } else {
            console.error('Error transferring chat:', data.message);
            showNotification('Failed to transfer chat: ' + data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error transferring chat:', error);
        alert('Failed to transfer chat. Please try again.');
    });
}

/**
 * Get a human-readable time ago string
 * @param {Date} date - The date to get the time ago for
 * @returns {string} A human-readable time ago string
 */
function getTimeAgo(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffDay > 0) {
        return `${diffDay} day${diffDay > 1 ? 's' : ''} ago`;
    } else if (diffHour > 0) {
        return `${diffHour} hour${diffHour > 1 ? 's' : ''} ago`;
    } else if (diffMin > 0) {
        return `${diffMin} minute${diffMin > 1 ? 's' : ''} ago`;
    } else {
        return 'Just now';
    }
}

/**
 * Knowledge Base Functions
 */

// Current page for each tab
const currentPage = {
    products: 1,
    faqs: 1,
    promotions: 1
};

// Items per page
const itemsPerPage = 10;

// Initialize knowledge base
function initKnowledgeBase() {
    // Add event listeners to tab buttons
    document.querySelectorAll('.tab-button').forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.dataset.tab;
            switchTab(tabId);
        });
    });

    // Load initial data
    loadProducts(1);
    loadCategories();
    loadFAQCategories();
    loadPopularProducts();

    // Add event listeners to search inputs
    document.getElementById('product-search').addEventListener('input', debounce(() => {
        loadProducts(1);
    }, 300));

    document.getElementById('faq-search').addEventListener('input', debounce(() => {
        loadFAQs(1);
    }, 300));

    // Add event listeners to filter selects
    document.getElementById('product-category-filter').addEventListener('change', () => {
        loadProducts(1);
    });

    document.getElementById('faq-category-filter').addEventListener('change', () => {
        loadFAQs(1);
    });

    // Add event listener for the Add FAQ button
    document.getElementById('add-faq-btn').addEventListener('click', () => {
        document.getElementById('add-faq-modal').style.display = 'flex';
    });

    // Add event listener for the Add FAQ form submission
    document.getElementById('add-faq-form').addEventListener('submit', (e) => {
        e.preventDefault();
        addNewFAQ();
    });
}

// Switch between tabs
function switchTab(tabId) {
    // Update active tab button
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.toggle('active', button.dataset.tab === tabId);
    });

    // Update active tab pane
    document.querySelectorAll('.tab-pane').forEach(pane => {
        const isActive = pane.id === `${tabId}-tab`;
        pane.classList.toggle('active', isActive);

        // Load data if tab is activated and not already loaded
        if (isActive) {
            if (tabId === 'products' && document.getElementById('products-list').innerHTML.includes('Loading')) {
                loadProducts(currentPage.products);
            } else if (tabId === 'faqs' && document.getElementById('faqs-list').innerHTML.includes('Loading')) {
                loadFAQs(currentPage.faqs);
            } else if (tabId === 'pending-faqs') {
                loadPendingFAQs();
            } else if (tabId === 'promotions' && document.getElementById('promotions-list').innerHTML.includes('Loading')) {
                loadPromotions(currentPage.promotions);
            } else if (tabId === 'chat-history') {
                loadChatHistory(1);
            }
        }
    });
}

// Load product categories and health goals
function loadCategories() {
    // Use the updated API endpoint with parameters to get only active categories with products
    fetch('/api/admin/all_categories?only_with_products=true&only_active=true')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const categorySelect = document.getElementById('product-category-filter');

                // Clear existing options except the first one
                while (categorySelect.options.length > 1) {
                    categorySelect.remove(1);
                }

                // Add a separator for categories
                const categorySeparator = document.createElement('optgroup');
                categorySeparator.label = "Product Categories";
                categorySelect.appendChild(categorySeparator);

                // Add categories
                data.categories.forEach(category => {
                    const option = document.createElement('option');
                    option.value = category.category_id;
                    option.textContent = category.name;
                    option.dataset.type = 'category';
                    categorySeparator.appendChild(option);
                });

                // Now add health goals
                // First fetch the health goals
                fetch('/api/health_goals')
                    .then(response => response.json())
                    .then(goalData => {
                        if (goalData.success && goalData.goals && goalData.goals.length > 0) {
                            // Add a separator for health goals
                            const goalSeparator = document.createElement('optgroup');
                            goalSeparator.label = "Health Goals";
                            categorySelect.appendChild(goalSeparator);

                            // Add each health goal
                            goalData.goals.forEach(goal => {
                                const option = document.createElement('option');
                                option.value = 'goal_' + goal.id; // Prefix with 'goal_' to distinguish from category IDs
                                option.textContent = goal.name;
                                option.dataset.type = 'goal';
                                option.dataset.goalId = goal.id;
                                goalSeparator.appendChild(option);
                            });
                        }
                    })
                    .catch(error => {
                        console.error('Error loading health goals:', error);
                    });
            }
        })
        .catch(error => {
            console.error('Error loading categories:', error);
        });
}

// Load FAQ categories
function loadFAQCategories() {
    fetch('/api/admin/faq_categories')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const categorySelect = document.getElementById('faq-category-filter');
                const modalCategorySelect = document.getElementById('faq-category');

                // Clear existing options except the first one in the filter dropdown
                while (categorySelect.options.length > 1) {
                    categorySelect.remove(1);
                }

                // Clear existing options in the modal dropdown except the last one (Add New Category)
                while (modalCategorySelect.options.length > 1) {
                    if (modalCategorySelect.options[modalCategorySelect.options.length - 1].value === 'new') {
                        // Keep the "Add New Category" option
                        const newCategoryOption = modalCategorySelect.options[modalCategorySelect.options.length - 1];
                        modalCategorySelect.innerHTML = '';
                        modalCategorySelect.appendChild(newCategoryOption);
                    } else {
                        modalCategorySelect.remove(1);
                    }
                }

                // Add categories to both dropdowns
                data.categories.forEach(category => {
                    // Add to filter dropdown
                    const filterOption = document.createElement('option');
                    filterOption.value = category;
                    filterOption.textContent = category;
                    categorySelect.appendChild(filterOption);

                    // Add to modal dropdown (before the "Add New Category" option)
                    const modalOption = document.createElement('option');
                    modalOption.value = category;
                    modalOption.textContent = category;

                    // Insert before the last option (which should be "Add New Category")
                    if (modalCategorySelect.options.length > 0 &&
                        modalCategorySelect.options[modalCategorySelect.options.length - 1].value === 'new') {
                        modalCategorySelect.insertBefore(modalOption, modalCategorySelect.options[modalCategorySelect.options.length - 1]);
                    } else {
                        modalCategorySelect.appendChild(modalOption);
                    }
                });
            }
        })
        .catch(error => {
            console.error('Error loading FAQ categories:', error);
        });
}

// Load products
function loadProducts(page) {
    currentPage.products = page;
    const searchTerm = document.getElementById('product-search').value.trim();
    const filterValue = document.getElementById('product-category-filter').value;
    const productsContainer = document.getElementById('products-list');

    productsContainer.innerHTML = '<div class="loading">Loading products...</div>';

    // Check if we're filtering by goal or category
    if (filterValue && filterValue.startsWith('goal_')) {
        // We're filtering by health goal
        const goalId = filterValue.replace('goal_', '');

        // Use the chatbot recommendation endpoint to get products by goal
        fetch(`/api/recommendations?goal_id=${goalId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.products) {
                    // Display the products
                    displayProducts(data.products, {
                        page: 1,
                        total_pages: 1,
                        total_items: data.products.length,
                        per_page: data.products.length
                    });
                } else {
                    productsContainer.innerHTML = `<div class="error">Error: ${data.message || 'No products found for this health goal'}</div>`;
                    document.getElementById('products-pagination').innerHTML = '';
                }
            })
            .catch(error => {
                console.error('Error loading products by goal:', error);
                productsContainer.innerHTML = '<div class="error">Failed to load products. Please try again.</div>';
                document.getElementById('products-pagination').innerHTML = '';
            });
    } else {
        // Regular category filtering
        let url = `/api/admin/all_products?page=${page}&per_page=${itemsPerPage}&search=${encodeURIComponent(searchTerm)}`;

        if (filterValue) {
            url += `&category_id=${filterValue}`;
        }

        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayProducts(data.products, data.pagination);
                } else {
                    productsContainer.innerHTML = `<div class="error">Error: ${data.message}</div>`;
                }
            })
            .catch(error => {
                console.error('Error loading products:', error);
                productsContainer.innerHTML = '<div class="error">Failed to load products. Please try again.</div>';
            });
    }
}

// Display products
function displayProducts(products, pagination) {
    const productsContainer = document.getElementById('products-list');
    const paginationContainer = document.getElementById('products-pagination');

    if (products.length === 0) {
        productsContainer.innerHTML = '<div class="no-results">No products found</div>';
        paginationContainer.innerHTML = '';
        return;
    }

    let html = '';

    products.forEach(product => {
        // Default to in-stock if stock_quantity is not provided
        const stockQuantity = product.stock_quantity !== undefined ? product.stock_quantity : 20;
        const stockStatus = getStockStatus(stockQuantity);

        html += '<div class="knowledge-item" data-id="' + product.product_id + '">';
        html += '<h3>' + product.name + '</h3>';

        html += '<div class="product-details">';

        // Add product image if available
        const logoPath = '/static/images/5w2fl3vb.svg'; // Store logo path in a variable for consistency

        if (product.image_url && product.image_url.trim() !== '') {
            // Check if image_url is a full URL or a local path
            const imgSrc = product.image_url.startsWith('http')
                ? product.image_url
                : `/static/images/products/${product.image_url}`;
            html += `<img src="${imgSrc}" alt="${product.name}" class="product-image" onerror="this.src='${logoPath}'">`;
        } else {
            html += `<img src="${logoPath}" alt="${product.name}" class="product-image">`;
        }

        html += '<div class="product-info">';
        html += '<p>' + (product.description || 'No description') + '</p>';

        // Add brand if available
        if (product.brand && product.brand.trim() !== '') {
            html += '<p><strong>Brand:</strong> ' + product.brand + '</p>';
        }

        // Add ingredients if available
        if (product.ingredients && product.ingredients.trim() !== '') {
            html += '<p><strong>Ingredients:</strong> ' + product.ingredients + '</p>';
        }

        // Add usage instructions if available
        if (product.usage_instructions && product.usage_instructions.trim() !== '') {
            html += '<p><strong>Usage Instructions:</strong> ' + product.usage_instructions + '</p>';
        }

        // Add health benefits if available
        if (product.health_benefits && product.health_benefits.trim() !== '') {
            html += '<p><strong>Benefits:</strong> ' + product.health_benefits + '</p>';
        }

        // Fetch and display detailed health benefits
        fetchProductBenefits(product.product_id, function(benefits) {
            if (benefits && benefits.length > 0) {
                const benefitsContainer = document.createElement('div');
                benefitsContainer.className = 'product-benefits';

                let benefitsHtml = '<p><strong>Detailed Benefits:</strong></p>';
                benefitsHtml += '<ul class="benefits-list">';

                benefits.forEach(benefit => {
                    benefitsHtml += `<li><strong>${benefit.name}</strong>: ${benefit.description}</li>`;
                });

                benefitsHtml += '</ul>';
                benefitsContainer.innerHTML = benefitsHtml;

                // Find the product item and append the benefits
                const productItem = document.querySelector(`.knowledge-item[data-id="${product.product_id}"]`);
                if (productItem) {
                    const productInfo = productItem.querySelector('.product-info');
                    if (productInfo) {
                        productInfo.appendChild(benefitsContainer);
                    }
                }
            }
        });

        html += '<div class="product-meta">';
        // Format price, handling both number and string types
        const price = typeof product.price === 'number' ? product.price.toFixed(2) : parseFloat(product.price).toFixed(2);
        html += '<span class="product-price">RM ' + price + '</span>';
        html += '<span class="product-stock ' + stockStatus.class + '">' + stockStatus.text + '</span>';
        html += '</div>';

        html += '</div>'; // End product-info
        html += '</div>'; // End product-details
        html += '</div>'; // End knowledge-item
    });

    productsContainer.innerHTML = html;

    // Add click event to copy product info to message input
    productsContainer.querySelectorAll('.knowledge-item').forEach(item => {
        item.addEventListener('click', () => {
            const productId = item.dataset.id;
            const product = products.find(p => p.product_id == productId);

            if (product) {
                const messageInput = document.getElementById('agent-message-input');
                let productInfo = `Product: ${product.name}\n`;
                // Format price, handling both number and string types
                const price = typeof product.price === 'number' ? product.price.toFixed(2) : parseFloat(product.price).toFixed(2);
                productInfo += `Price: RM ${price}\n`;

                if (product.description) {
                    productInfo += `Description: ${product.description}\n`;
                }

                if (product.brand) {
                    productInfo += `Brand: ${product.brand}\n`;
                }

                if (product.ingredients) {
                    productInfo += `Ingredients: ${product.ingredients}\n`;
                }

                if (product.usage_instructions) {
                    productInfo += `Usage Instructions: ${product.usage_instructions}\n`;
                }

                if (product.health_benefits) {
                    productInfo += `Benefits: ${product.health_benefits}\n`;
                }

                const stockStatus = getStockStatus(product.stock_quantity);
                productInfo += `Availability: ${stockStatus.text}`;

                // Get detailed health benefits
                fetchProductBenefits(product.product_id, function(benefits) {
                    if (benefits && benefits.length > 0) {
                        productInfo += '\n\nDetailed Health Benefits:';
                        benefits.forEach(benefit => {
                            productInfo += `\n• ${benefit.name}: ${benefit.description}`;
                        });

                        messageInput.value = productInfo;
                        messageInput.focus();
                        // Trigger resize after setting value
                        autoResizeTextarea(messageInput);
                    } else {
                        messageInput.value = productInfo;
                        messageInput.focus();
                        // Trigger resize after setting value
                        autoResizeTextarea(messageInput);
                    }
                });
            }
        });
    });

    // Create pagination
    createPagination(paginationContainer, pagination, 'products');
}

// Get stock status text and class
function getStockStatus(quantity) {
    if (quantity <= 0) {
        return { text: 'Out of Stock', class: 'out-of-stock' };
    } else if (quantity < 10) {
        return { text: 'Low Stock (' + quantity + ')', class: 'low-stock' };
    } else {
        return { text: 'In Stock (' + quantity + ')', class: 'in-stock' };
    }
}

// Load FAQs
function loadFAQs(page) {
    currentPage.faqs = page;
    const searchTerm = document.getElementById('faq-search').value.trim();
    const categoryFilter = document.getElementById('faq-category-filter').value;

    document.getElementById('faqs-list').innerHTML = '<div class="loading">Loading FAQs...</div>';

    let url = `/api/admin/all_faqs?page=${page}&per_page=${itemsPerPage}&search=${encodeURIComponent(searchTerm)}`;

    if (categoryFilter) {
        url += `&category=${encodeURIComponent(categoryFilter)}`;
    }

    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayFAQs(data.faqs, data.pagination);
            } else {
                document.getElementById('faqs-list').innerHTML = `<div class="error">Error: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading FAQs:', error);
            document.getElementById('faqs-list').innerHTML = '<div class="error">Failed to load FAQs. Please try again.</div>';
        });
}

// Display FAQs
function displayFAQs(faqs, pagination) {
    const faqsContainer = document.getElementById('faqs-list');
    const paginationContainer = document.getElementById('faqs-pagination');

    if (faqs.length === 0) {
        faqsContainer.innerHTML = '<div class="no-results">No FAQs found</div>';
        paginationContainer.innerHTML = '';
        return;
    }

    let html = '';

    faqs.forEach(faq => {
        html += '<div class="knowledge-item" data-id="' + faq.faq_id + '">';

        // Add category badge with dynamic color
        const normalizedCategory = faq.category.toLowerCase().replace(/[^a-z0-9]/g, '');
        const colorIndex = Math.abs(hashCode(normalizedCategory) % colors.length);
        const categoryColor = colors[colorIndex];

        html += '<div class="faq-meta">';
        html += `<span class="faq-category" style="background-color: ${categoryColor};">${faq.category}</span>`;
        html += '</div>';

        html += '<h3>' + faq.question + '</h3>';
        html += '<p>' + faq.answer + '</p>';
        html += '</div>';
    });

    faqsContainer.innerHTML = html;

    // Add click event to copy FAQ info to message input
    faqsContainer.querySelectorAll('.knowledge-item').forEach(item => {
        item.addEventListener('click', () => {
            const faqId = item.dataset.id;
            const faq = faqs.find(f => f.faq_id == faqId);

            if (faq) {
                const messageInput = document.getElementById('agent-message-input');
                messageInput.value = 'Q: ' + faq.question + '\nA: ' + faq.answer;
                messageInput.focus();
                // Trigger resize after setting value
                autoResizeTextarea(messageInput);
            }
        });
    });

    // Create pagination
    createPagination(paginationContainer, pagination, 'faqs');
}



// Load promotions
function loadPromotions(page) {
    currentPage.promotions = page;

    document.getElementById('promotions-list').innerHTML = '<div class="loading">Loading promotions...</div>';

    fetch(`/api/admin/all_promotions?page=${page}&per_page=${itemsPerPage}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayPromotions(data.promotions, data.pagination);
            } else {
                document.getElementById('promotions-list').innerHTML = `<div class="error">Error: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading promotions:', error);
            document.getElementById('promotions-list').innerHTML = '<div class="error">Failed to load promotions. Please try again.</div>';
        });
}

// Display promotions
function displayPromotions(promotions, pagination) {
    const promotionsContainer = document.getElementById('promotions-list');
    const paginationContainer = document.getElementById('promotions-pagination');

    if (promotions.length === 0) {
        promotionsContainer.innerHTML = '<div class="no-results">No promotions found</div>';
        paginationContainer.innerHTML = '';
        return;
    }

    let html = '';

    promotions.forEach(promotion => {
        const startDate = new Date(promotion.start_date);
        const endDate = new Date(promotion.end_date);
        const isActive = promotion.is_active && new Date() >= startDate && new Date() <= endDate;

        html += '<div class="knowledge-item ' + (isActive ? 'active-promotion' : '') + '" data-id="' + promotion.promotion_id + '">';
        html += '<h3>' + promotion.name + '</h3>';
        html += '<p>' + (promotion.description ? promotion.description.substring(0, 100) + (promotion.description.length > 100 ? '...' : '') : 'No description') + '</p>';
        html += '<p>';
        html += '<strong>Discount:</strong> ' + (promotion.discount_type === 'percentage' ? promotion.discount_value + '%' : 'RM' + promotion.discount_value.toFixed(2)) + ' | ';
        html += '<strong>Period:</strong> ' + formatDate(startDate) + ' - ' + formatDate(endDate) + ' | ';
        html += '<strong>Status:</strong> ' + (isActive ? '<span class="active-status">Active</span>' : '<span class="inactive-status">Inactive</span>');
        html += '</p>';
        html += '</div>';
    });

    promotionsContainer.innerHTML = html;

    // Add click event to copy promotion info to message input
    promotionsContainer.querySelectorAll('.knowledge-item').forEach(item => {
        item.addEventListener('click', () => {
            const promotionId = item.dataset.id;
            const promotion = promotions.find(p => p.promotion_id == promotionId);

            if (promotion) {
                const messageInput = document.getElementById('agent-message-input');
                const discountText = promotion.discount_type === 'percentage' ?
                    promotion.discount_value + '% off' :
                    '$' + promotion.discount_value.toFixed(2) + ' off';

                messageInput.value = 'Special Promotion: ' + promotion.name + ' - ' + discountText + '. Valid until ' + formatDate(new Date(promotion.end_date)) + '. ' + (promotion.description || '');
                messageInput.focus();
                // Trigger resize after setting value
                autoResizeTextarea(messageInput);
            }
        });
    });

    // Create pagination
    createPagination(paginationContainer, pagination, 'promotions');
}

// Create pagination controls
function createPagination(container, pagination, type) {
    if (!pagination || pagination.total_pages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = '';

    // Previous button
    html += '<button ' + (pagination.page === 1 ? 'disabled' : '') + ' onclick="load' + type.charAt(0).toUpperCase() + type.slice(1) + '(' + (pagination.page - 1) + ')">Prev</button>';

    // Page buttons
    const startPage = Math.max(1, pagination.page - 2);
    const endPage = Math.min(pagination.total_pages, pagination.page + 2);

    for (let i = startPage; i <= endPage; i++) {
        html += '<button class="' + (i === pagination.page ? 'active' : '') + '" onclick="load' + type.charAt(0).toUpperCase() + type.slice(1) + '(' + i + ')">' + i + '</button>';
    }

    // Next button
    html += '<button ' + (pagination.page === pagination.total_pages ? 'disabled' : '') + ' onclick="load' + type.charAt(0).toUpperCase() + type.slice(1) + '(' + (pagination.page + 1) + ')">Next</button>';

    container.innerHTML = html;
}

// Format date
function formatDate(date) {
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

// Fetch detailed health benefits for a product
function fetchProductBenefits(productId, callback) {
    fetch(`/api/admin/product_benefits?product_id=${productId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                callback(data.benefits);
            } else {
                console.error('Error fetching product benefits:', data.message);
                callback([]);
            }
        })
        .catch(error => {
            console.error('Error fetching product benefits:', error);
            callback([]);
        });
}

// Add a new FAQ to the database
function addNewFAQ() {
    const question = document.getElementById('faq-question').value.trim();
    const answer = document.getElementById('faq-answer').value.trim();
    const categorySelect = document.getElementById('faq-category');
    const notes = document.getElementById('faq-notes').value.trim();

    let category = categorySelect.value;

    // Check if user is adding a new category
    if (category === 'new') {
        const newCategory = document.getElementById('new-faq-category').value.trim();
        if (!newCategory) {
            alert('Please enter a name for the new category');
            return;
        }
        category = newCategory;
    }

    if (!question || !answer || !category) {
        alert('Please fill in all required fields');
        return;
    }

    // Create the data object
    const faqData = {
        question: question,
        answer: answer,
        category: category,
        notes: notes,
        language: 'en' // Default language is English
    };

    // Send the data to the server
    fetch('/api/admin/add_faq', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(faqData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Close the modal
            document.getElementById('add-faq-modal').style.display = 'none';

            // Reset the form
            document.getElementById('add-faq-form').reset();

            // Reload the FAQs
            loadFAQs(1);

            // Reload FAQ categories to include any new categories
            loadFAQCategories();

            // If this was submitted for approval (agent role)
            if (data.message.includes('submitted for manager approval')) {
                showNotification('FAQ submitted for manager approval', 'info');

                // Load pending FAQs if the tab exists
                if (document.getElementById('pending-faqs-container')) {
                    loadPendingFAQs();
                }
            } else {
                // Show success message for direct addition (manager role)
                showNotification('FAQ added successfully', 'success');
            }
        } else {
            showNotification('Error: ' + data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error adding FAQ:', error);
        showNotification('Failed to add FAQ. Please try again.', 'error');
    });
}

// Show a notification message
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    // Add to the DOM
    document.body.appendChild(notification);

    // Show the notification
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);

    // Remove after 3 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// Debounce function for search inputs
function debounce(func, wait) {
    let timeout;
    return function() {
        const context = this;
        const args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            func.apply(context, args);
        }, wait);
    };
}

// Load pending FAQs submitted by the agent
function loadPendingFAQs() {
    const pendingFaqsContainer = document.getElementById('pending-faqs-container');

    if (!pendingFaqsContainer) {
        return;
    }

    pendingFaqsContainer.innerHTML = '<div class="loading">Loading pending FAQs...</div>';

    fetch('/api/agent/pending_faqs')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayPendingFAQs(data.pending_faqs);
            } else {
                pendingFaqsContainer.innerHTML = `<div class="error">Error: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading pending FAQs:', error);
            pendingFaqsContainer.innerHTML = '<div class="error">Failed to load pending FAQs. Please try again.</div>';
        });
}

// Display pending FAQs
function displayPendingFAQs(pendingFaqs) {
    const pendingFaqsContainer = document.getElementById('pending-faqs-container');

    if (!pendingFaqsContainer) {
        return;
    }

    if (!pendingFaqs || pendingFaqs.length === 0) {
        pendingFaqsContainer.innerHTML = '<div class="no-results">No pending FAQs found</div>';
        // Update badge to show zero pending FAQs
        updatePendingFaqsBadge(0);
        return;
    }

    // Count only truly pending FAQs (not approved or rejected)
    const pendingCount = pendingFaqs.filter(faq => faq.status === 'pending').length;

    // Update the badge with the count of truly pending FAQs
    updatePendingFaqsBadge(pendingCount);

    let html = '<div class="pending-faqs-list">';

    pendingFaqs.forEach(faq => {
        const statusClass = getStatusClass(faq.status);
        const submittedDate = new Date(faq.submitted_at);

        html += `<div class="pending-faq-item ${statusClass}">`;
        html += `<div class="pending-faq-header">`;
        html += `<h3>${faq.question}</h3>`;
        html += `<span class="pending-faq-status ${statusClass}">${faq.status}</span>`;
        html += `</div>`;

        html += `<div class="pending-faq-details">`;
        html += `<p><strong>Answer:</strong> ${faq.answer}</p>`;
        html += `<p><strong>Category:</strong> ${faq.category}</p>`;
        html += `<p><strong>Submitted:</strong> ${formatDate(submittedDate)}</p>`;

        // Display agent notes if available
        if (faq.agent_notes) {
            html += `<p><strong>Your Notes:</strong> <span class="agent-notes">${faq.agent_notes}</span></p>`;
        }

        if (faq.status !== 'pending') {
            const reviewedDate = new Date(faq.reviewed_at);
            html += `<p><strong>Reviewed by:</strong> ${faq.reviewed_by_username}</p>`;
            html += `<p><strong>Reviewed on:</strong> ${formatDate(reviewedDate)}</p>`;

            if (faq.notes) {
                html += `<p><strong>Manager Notes:</strong> <span class="manager-notes">${faq.notes}</span></p>`;
            }
        }

        html += `</div>`;
        html += `</div>`;
    });

    html += '</div>';

    pendingFaqsContainer.innerHTML = html;
}

// Get CSS class for status
function getStatusClass(status) {
    switch (status) {
        case 'approved':
            return 'status-approved';
        case 'rejected':
            return 'status-rejected';
        default:
            return 'status-pending';
    }
}

/**
 * Auto-resize textarea based on content
 * @param {HTMLTextAreaElement} textarea - The textarea element to resize
 */
function autoResizeTextarea(textarea) {
    if (!textarea) return;

    // Store the current scroll position
    const scrollPos = textarea.scrollTop;

    // Reset height to auto to get the correct scrollHeight
    textarea.style.height = 'auto';

    // Create a hidden div to measure the content height more accurately
    const hiddenDiv = document.createElement('div');
    hiddenDiv.style.position = 'absolute';
    hiddenDiv.style.visibility = 'hidden';
    hiddenDiv.style.width = window.getComputedStyle(textarea).width;
    hiddenDiv.style.fontSize = window.getComputedStyle(textarea).fontSize;
    hiddenDiv.style.fontFamily = window.getComputedStyle(textarea).fontFamily;
    hiddenDiv.style.lineHeight = window.getComputedStyle(textarea).lineHeight;
    hiddenDiv.style.padding = window.getComputedStyle(textarea).padding;
    hiddenDiv.style.border = window.getComputedStyle(textarea).border;
    hiddenDiv.style.boxSizing = window.getComputedStyle(textarea).boxSizing;
    hiddenDiv.style.whiteSpace = 'pre-wrap';
    hiddenDiv.style.wordWrap = 'break-word';
    hiddenDiv.textContent = textarea.value + '\n'; // Add extra line to ensure proper height

    document.body.appendChild(hiddenDiv);
    const contentHeight = hiddenDiv.offsetHeight;
    document.body.removeChild(hiddenDiv);

    // Set the height to match the content with a minimum of 40px and maximum of 200px
    const newHeight = Math.max(40, Math.min(contentHeight, 200));
    textarea.style.height = newHeight + 'px';

    // Restore the scroll position
    textarea.scrollTop = scrollPos;
}

/**
 * Check for pending FAQs and update notification badge
 */
function checkPendingFAQs() {
    fetch('/api/agent/pending_faqs')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const pendingFaqs = data.pending_faqs || [];
                const count = pendingFaqs.length;

                // Only count FAQs with 'pending' status
                const pendingCount = pendingFaqs.filter(faq => faq.status === 'pending').length;

                // Update the badge with the count of truly pending FAQs
                updatePendingFaqsBadge(pendingCount);

                // Show notification if there are pending FAQs
                if (pendingCount > 0) {
                    showNotification(`You have ${pendingCount} pending FAQ${pendingCount > 1 ? 's' : ''}`, 'info');
                }
            }
        })
        .catch(error => {
            console.error('Error checking pending FAQs:', error);
        });
}

/**
 * Update the pending FAQs notification badge
 * @param {number} count - Number of pending FAQs
 */
function updatePendingFaqsBadge(count) {
    const badge = document.getElementById('pending-faqs-badge');
    if (badge) {
        if (count > 0) {
            badge.textContent = count;
            badge.style.display = 'inline-block';
        } else {
            badge.textContent = '0';
            badge.style.display = 'none';
        }
    }

    // Update the pendingFaqs global variable
    pendingFaqs = count;

    // Also update the tab button appearance
    const pendingFaqsButton = document.querySelector('.tab-button[data-tab="pending-faqs"]');
    if (pendingFaqsButton) {
        if (count > 0) {
            pendingFaqsButton.classList.add('has-pending');
        } else {
            pendingFaqsButton.classList.remove('has-pending');
        }
    }
}





// Load popular products based on actual purchase history
function loadPopularProducts() {
    const popularProductsContainer = document.getElementById('popular-products');

    // Use the bestselling products API which is based on actual order data
    fetch('/api/agent/bestselling_products')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayPopularProducts(data.products);
            } else {
                popularProductsContainer.innerHTML = `<div class="error">Error: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading popular products:', error);
            popularProductsContainer.innerHTML = '<div class="error">Failed to load popular products. Please try again.</div>';
        });
}

// Display popular products
function displayPopularProducts(products) {
    const popularProductsContainer = document.getElementById('popular-products');

    if (!products || products.length === 0) {
        popularProductsContainer.innerHTML = '<div class="no-results">No popular products found</div>';
        return;
    }

    let html = '';

    products.forEach(product => {
        const stockStatus = getStockStatus(product.stock_quantity);

        html += '<div class="knowledge-item" data-id="' + product.product_id + '">';
        html += '<h3>' + product.name + '</h3>';

        html += '<div class="product-details">';

        // Add product image if available
        const logoPath = '/static/images/5w2fl3vb.svg'; // Store logo path in a variable for consistency

        if (product.image_url) {
            // Check if image_url is a full URL or a local path
            const imgSrc = product.image_url.startsWith('http')
                ? product.image_url
                : `/static/images/products/${product.image_url}`;
            html += `<img src="${imgSrc}" alt="${product.name}" class="product-image" onerror="this.src='${logoPath}'">`;
        } else {
            html += `<img src="${logoPath}" alt="${product.name}" class="product-image">`;
        }

        html += '<div class="product-info">';
        html += '<p>' + (product.description ? product.description.substring(0, 100) + (product.description.length > 100 ? '...' : '') : 'No description') + '</p>';

        html += '<div class="product-meta">';
        html += '<span class="product-price">RM ' + product.price.toFixed(2) + '</span>';
        html += '<span class="product-stock ' + stockStatus.class + '">' + stockStatus.text + '</span>';
        html += '</div>';

        html += '</div>'; // End product-info
        html += '</div>'; // End product-details
        html += '</div>'; // End knowledge-item
    });

    popularProductsContainer.innerHTML = html;

    // Add click event to copy product info to message input
    popularProductsContainer.querySelectorAll('.knowledge-item').forEach(item => {
        item.addEventListener('click', () => {
            const productId = item.dataset.id;
            const product = products.find(p => p.product_id == productId);

            if (product) {
                const messageInput = document.getElementById('agent-message-input');
                let productInfo = `I'd like to recommend one of our popular products:\n\n`;
                productInfo += `Product: ${product.name}\n`;
                productInfo += `Price: RM ${product.price.toFixed(2)}\n`;

                if (product.description) {
                    productInfo += `Description: ${product.description.substring(0, 150)}${product.description.length > 150 ? '...' : ''}\n`;
                }

                const stockStatus = getStockStatus(product.stock_quantity);
                productInfo += `Availability: ${stockStatus.text}`;

                messageInput.value = productInfo;
                messageInput.focus();
            }
        });
    });
}

// Update customer recommendations when a customer is selected
function updateCustomerRecommendations(customerId) {
    if (!customerId) return;

    const recommendationsContainer = document.getElementById('customer-recommendations');
    recommendationsContainer.innerHTML = '<div class="loading">Loading recommendations...</div>';

    // For now, we'll just use a few products as recommendations
    // In a real implementation, this would be based on customer order history and preferences
    fetch('/api/admin/all_products?page=1&per_page=3')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayCustomerRecommendations(data.products);
            } else {
                recommendationsContainer.innerHTML = `<div class="error">Error: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading customer recommendations:', error);
            recommendationsContainer.innerHTML = '<div class="error">Failed to load recommendations. Please try again.</div>';
        });
}

// Display customer recommendations
function displayCustomerRecommendations(products) {
    const recommendationsContainer = document.getElementById('customer-recommendations');

    if (!products || products.length === 0) {
        recommendationsContainer.innerHTML = '<div class="no-results">No personalized recommendations found</div>';
        return;
    }

    let html = '';

    products.forEach(product => {
        const stockStatus = getStockStatus(product.stock_quantity);

        html += '<div class="knowledge-item" data-id="' + product.product_id + '">';
        html += '<h3>' + product.name + '</h3>';

        html += '<div class="product-meta">';
        html += '<span class="product-price">RM ' + product.price.toFixed(2) + '</span>';
        html += '<span class="product-stock ' + stockStatus.class + '">' + stockStatus.text + '</span>';
        html += '</div>';

        html += '</div>'; // End knowledge-item
    });

    recommendationsContainer.innerHTML = html;

    // Add click event to copy product info to message input
    recommendationsContainer.querySelectorAll('.knowledge-item').forEach(item => {
        item.addEventListener('click', () => {
            const productId = item.dataset.id;
            const product = products.find(p => p.product_id == productId);

            if (product) {
                const messageInput = document.getElementById('agent-message-input');
                let productInfo = `Based on your previous purchases, I think you might like this product:\n\n`;
                productInfo += `Product: ${product.name}\n`;
                productInfo += `Price: RM ${product.price.toFixed(2)}\n`;

                if (product.description) {
                    productInfo += `Description: ${product.description.substring(0, 150)}${product.description.length > 150 ? '...' : ''}\n`;
                }

                const stockStatus = getStockStatus(product.stock_quantity);
                productInfo += `Availability: ${stockStatus.text}`;

                messageInput.value = productInfo;
                messageInput.focus();
            }
        });
    });
}

/**
 * Initialize WebSocket connection for real-time messaging
 */
function initializeWebSocket() {
    // Initialize Socket.IO connection
    socket = io();

    // Connection event handlers
    socket.on('connect', () => {
        console.log('WebSocket connected');

        // Join agent-specific room for notifications
        if (userInfo && userInfo.userId) {
            socket.emit('join_agent_room', {
                agent_id: userInfo.userId
            });
        }
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
    });

    // Message event handlers
    socket.on('new_message', (data) => {
        if (data.session_id == currentSessionId) {
            if (data.sender_type === 'customer' || data.sender_type === 'guest') {
                displayNewCustomerMessage(data);
            }
        }
    });

    socket.on('agent_joined', (data) => {
        if (data.session_id == currentSessionId) {
            showNotification(`${data.agent_name} joined the conversation`, 'info');
        }
    });

    socket.on('agent_left', (data) => {
        if (data.session_id == currentSessionId) {
            showNotification(`${data.agent_name} left the conversation`, 'info');
        }
    });

    socket.on('customer_left', (data) => {
        if (data.session_id == currentSessionId) {
            displaySystemMessage(data.message);
            showNotification('Customer ended the chat', 'info');
            // Refresh the active chats list to remove this session
            setTimeout(() => {
                loadActiveChats();
                loadMyAssignedSessions();
                loadMyActiveSessions();
            }, 1000);
        }
    });

    socket.on('message_error', (data) => {
        console.error('Message error:', data.error);
        showNotification('Failed to send message', 'error');
    });

    // Handle chat transfer events
    socket.on('chat_transferred', (data) => {
        if (data.session_id == currentSessionId) {
            showNotification(`Chat transferred to ${data.new_agent_name}`, 'info');
            // If this chat was transferred away from current agent, clear the UI
            if (data.new_agent_id != userInfo.userId) {
                currentSessionId = null;
                currentCustomerId = null;
                chatMessages.innerHTML = '<div class="no-chat-selected">No chat selected</div>';
                customerDetails.innerHTML = '<div class="no-customer-selected">No customer selected</div>';
                chatCustomerName.textContent = 'No Customer';
                loadActiveChats(); // Refresh the chat list
            }
        }
    });

    // Handle new chat assignment
    socket.on('new_chat_assigned', (data) => {
        showNotification(data.message, 'success');
        loadActiveChats(); // Refresh the chat list to show new assignment
    });

    // Handle complete history loading
    socket.on('load_complete_history', (data) => {
        if (data.session_id == currentSessionId) {
            // Reload complete chat history to ensure nothing is missing
            loadChatMessages(data.session_id);
        }
    });
}

// Chat History Management
let currentChatHistoryPage = 1;
let chatHistoryPerPage = 10; // Default value, can be made configurable

/**
 * Load chat history for the current agent
 */
function loadChatHistory(page = 1) {
    const searchTerm = document.getElementById('chat-history-search').value.trim();
    const chatHistoryList = document.getElementById('chat-history-list');

    // Show loading
    chatHistoryList.innerHTML = '<div class="loading">Loading chat history...</div>';

    // Build query parameters
    const params = new URLSearchParams({
        page: page,
        per_page: chatHistoryPerPage
    });

    if (searchTerm) {
        params.append('search', searchTerm);
    }

    fetch(`/api/agent/chat_history?${params}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayChatHistory(data.sessions);
                displayChatHistoryPagination(data.pagination);
                currentChatHistoryPage = page;
            } else {
                chatHistoryList.innerHTML = `<div class="error">Error: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading chat history:', error);
            chatHistoryList.innerHTML = '<div class="error">Failed to load chat history. Please try again.</div>';
        });
}

/**
 * Display chat history sessions
 */
function displayChatHistory(sessions) {
    const chatHistoryList = document.getElementById('chat-history-list');

    if (!sessions || sessions.length === 0) {
        chatHistoryList.innerHTML = '<div class="no-results">No chat history found.</div>';
        return;
    }

    const historyHTML = sessions.map(session => {
        const customerName = session.customer_name || 'Guest User';
        const sessionStart = new Date(session.session_start).toLocaleString();
        const sessionEnd = session.session_end ? new Date(session.session_end).toLocaleString() : 'Ongoing';
        const messageCount = session.message_count || 0;

        // Handle feedback rating dynamically - only show if it exists
        let ratingDisplay = 'No rating';
        if (session.feedback_rating && session.feedback_rating > 0) {
            ratingDisplay = '⭐'.repeat(session.feedback_rating) + ` (${session.feedback_rating}/5)`;
        }

        // Build feedback comment section dynamically
        let feedbackSection = '';
        if (session.feedback_comment && session.feedback_comment.trim()) {
            feedbackSection = `<div class="feedback-comment"><strong>Feedback:</strong> ${session.feedback_comment}</div>`;
        }

        return `
            <div class="history-item" onclick="viewChatHistoryDetails(${session.session_id})">
                <div class="history-header">
                    <h4>Session #${session.session_id}</h4>
                    <span class="session-date">${sessionStart}</span>
                </div>
                <div class="history-details">
                    <p><strong>Customer:</strong> ${customerName}</p>
                    <p><strong>Messages:</strong> ${messageCount}</p>
                    <p><strong>Rating:</strong> ${ratingDisplay}</p>
                    <p><strong>Status:</strong> ${session.session_end ? 'Completed' : 'Ongoing'}</p>
                </div>
                ${feedbackSection}
            </div>
        `;
    }).join('');

    chatHistoryList.innerHTML = historyHTML;
}

/**
 * Display pagination for chat history
 */
function displayChatHistoryPagination(pagination) {
    const paginationContainer = document.getElementById('chat-history-pagination');

    if (pagination.total_pages <= 1) {
        paginationContainer.style.display = 'none';
        return;
    }

    let paginationHTML = '<div class="pagination">';

    // Previous button
    if (pagination.has_prev) {
        paginationHTML += `<button class="btn btn-secondary" onclick="loadChatHistory(${pagination.current_page - 1})">Previous</button>`;
    }

    // Page numbers
    const startPage = Math.max(1, pagination.current_page - 2);
    const endPage = Math.min(pagination.total_pages, pagination.current_page + 2);

    for (let i = startPage; i <= endPage; i++) {
        const activeClass = i === pagination.current_page ? 'active' : '';
        paginationHTML += `<button class="btn ${activeClass}" onclick="loadChatHistory(${i})">${i}</button>`;
    }

    // Next button
    if (pagination.has_next) {
        paginationHTML += `<button class="btn btn-secondary" onclick="loadChatHistory(${pagination.current_page + 1})">Next</button>`;
    }

    paginationHTML += '</div>';
    paginationHTML += `<div class="pagination-info">Page ${pagination.current_page} of ${pagination.total_pages} (${pagination.total_sessions} total sessions)</div>`;

    paginationContainer.innerHTML = paginationHTML;
    paginationContainer.style.display = 'block';
}

/**
 * View details of a specific chat session from history
 */
function viewChatHistoryDetails(sessionId) {
    // Load the chat messages for this session
    loadChatMessages(sessionId);

    // Update the chat header to show it's a historical session
    const chatCustomerName = document.getElementById('chat-customer-name');
    chatCustomerName.textContent = `Historical Session #${sessionId}`;

    // Disable chat input for historical sessions
    const messageInput = document.getElementById('agent-message-input');
    const sendButton = document.getElementById('send-agent-message');
    const endChatBtn = document.getElementById('end-chat-btn');
    const transferChatBtn = document.getElementById('transfer-chat-btn');

    messageInput.disabled = true;
    messageInput.placeholder = 'This is a historical chat session (read-only)';
    sendButton.disabled = true;
    endChatBtn.disabled = true;
    transferChatBtn.disabled = true;

    // Set current session ID for message loading
    currentSessionId = sessionId;
}

// Add event listeners for chat history search
document.addEventListener('DOMContentLoaded', () => {
    // Search functionality
    const searchInput = document.getElementById('chat-history-search');
    const searchButton = document.getElementById('search-chat-history');

    if (searchInput && searchButton) {
        searchButton.addEventListener('click', () => {
            loadChatHistory(1);
        });

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                loadChatHistory(1);
            }
        });
    }
});

/**
 * Join a WebSocket room for a specific session
 */
function joinSessionRoom(sessionId) {
    if (socket && sessionId) {
        socket.emit('join_session', {
            session_id: sessionId,
            user_type: 'agent'
        });
        console.log(`Joined WebSocket room for session ${sessionId}`);
    }
}

/**
 * Leave a WebSocket room for a specific session
 */
function leaveSessionRoom(sessionId) {
    if (socket && sessionId) {
        socket.emit('leave_session', {
            session_id: sessionId,
            user_type: 'agent'
        });
        console.log(`Left WebSocket room for session ${sessionId}`);
    }
}

/**
 * Display a new customer message in the agent chat interface
 */
function displayNewCustomerMessage(message) {
    if (!chatMessages) return;

    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = 'message customer-message';

    // Customer name header
    const customerHeader = document.createElement('div');
    customerHeader.className = 'customer-name';
    customerHeader.textContent = message.sender_name || 'Customer';
    customerHeader.style.fontWeight = 'bold';
    customerHeader.style.fontSize = '0.9rem';
    customerHeader.style.color = '#FF9800';
    customerHeader.style.marginBottom = '5px';

    const messageText = document.createElement('div');
    messageText.textContent = message.message_text;

    const messageTime = document.createElement('div');
    messageTime.className = 'message-time';
    // Debug timestamp for new customer messages
    console.log(`New customer message timestamp: ${message.timestamp}, parsed:`, new Date(message.timestamp));
    messageTime.textContent = new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    messageElement.appendChild(customerHeader);
    messageElement.appendChild(messageText);
    messageElement.appendChild(messageTime);

    chatMessages.appendChild(messageElement);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Show notification if page is not visible
    if (document.hidden) {
        showNotification(`New message from ${message.sender_name || 'Customer'}`, 'info');
    }
}
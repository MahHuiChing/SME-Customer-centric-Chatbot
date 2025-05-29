/**
 * Rock Chatbot - Chat Interface
 *
 * This script handles the chatbot interface for guests and customers.
 * It provides button-based interaction with the chatbot.
 */

// Global variables
let sessionId = null;
let currentLanguage = 'en';
let lastMessageId = null;
let windowId = null;
let isAgentConnected = false;
let socket = null;

// Generate unique window ID for this browser window/tab
function generateWindowId() {
    return 'window_' + Date.now() + '_' + Math.random().toString(36).substring(2, 11);
}

// Initialize window ID
windowId = generateWindowId();

// Flag to track if we're waiting for a feedback response
window.waitingForFeedbackResponse = false;

// DOM elements
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const languageSelect = document.getElementById('language-select');

// Initialize the chatbot
document.addEventListener('DOMContentLoaded', () => {
    // Initialize WebSocket connection
    initializeWebSocket();

    // Set up language selector
    languageSelect.addEventListener('change', changeLanguage);

    // Display welcome message and start button instead of automatically starting a session
    displayWelcomePrompt();
});

/**
 * Display welcome prompt with start button
 */
function displayWelcomePrompt() {
    // Create a welcome message
    const welcomeWrapper = document.createElement('div');
    welcomeWrapper.className = 'message-wrapper';

    // Create avatar
    const avatarContainer = document.createElement('div');
    avatarContainer.className = 'message-avatar';

    const avatarImg = document.createElement('img');
    avatarImg.src = '/static/images/logo.svg';
    avatarImg.alt = 'Bot Avatar';

    avatarContainer.appendChild(avatarImg);
    welcomeWrapper.appendChild(avatarContainer);

    // Create welcome message element
    const welcomeElement = document.createElement('div');
    welcomeElement.className = 'message bot-message';

    // Get welcome message based on language
    let welcomeText = 'Welcome to Rock Supplements! Click the button below to start chatting with our assistant.';
    if (languageSelect.value === 'ms') {
        welcomeText = 'Selamat datang ke Rock Supplements! Klik butang di bawah untuk mula berbual dengan pembantu kami.';
    } else if (languageSelect.value === 'zh') {
        welcomeText = '欢迎来到Rock Supplements！点击下方按钮开始与我们的助手聊天。';
    } else if (languageSelect.value === 'ta') {
        welcomeText = 'Rock Supplements க்கு வரவேற்கிறோம்! எங்கள் உதவியாளருடன் அரட்டையடிக்க தொடங்க கீழே உள்ள பொத்தானைக் கிளிக் செய்யவும்.';
    }

    const messageText = document.createElement('div');
    messageText.textContent = welcomeText;

    const messageTime = document.createElement('div');
    messageTime.className = 'message-time';
    messageTime.textContent = getCurrentTime();

    welcomeElement.appendChild(messageText);
    welcomeElement.appendChild(messageTime);

    welcomeWrapper.appendChild(welcomeElement);
    chatMessages.appendChild(welcomeWrapper);

    // Create start button
    const startButtonContainer = document.createElement('div');
    startButtonContainer.className = 'chat-buttons';

    const startButton = document.createElement('button');
    startButton.className = 'chat-button start-chat-button';

    // Get button text based on language
    let buttonText = 'Start Chat';
    if (languageSelect.value === 'ms') {
        buttonText = 'Mula Berbual';
    } else if (languageSelect.value === 'zh') {
        buttonText = '开始聊天';
    } else if (languageSelect.value === 'ta') {
        buttonText = 'அரட்டையைத் தொடங்கு';
    }

    startButton.textContent = buttonText;
    startButton.addEventListener('click', () => {
        // Remove the start button
        startButtonContainer.remove();

        // Start the chat session
        startChatSession();
    });

    startButtonContainer.appendChild(startButton);
    chatMessages.appendChild(startButtonContainer);

    // Scroll to the bottom
    scrollToBottom();
}

/**
 * Start a new chat session
 */
function startChatSession() {
    // Show loading indicator
    showTypingIndicator();

    // Get the selected language
    currentLanguage = languageSelect.value;

    // Start a new session
    fetch('/api/start_session', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            language: currentLanguage,
            customer_id: userInfo.isLoggedIn ? userInfo.userId : null,
            window_id: windowId,
            source: 'web'
        })
    })
    .then(response => response.json())
    .then(data => {
        // Hide loading indicator
        hideTypingIndicator();

        // Save the session ID
        sessionId = data.session_id;
        lastMessageId = data.message_id;

        // Display the welcome message
        displayBotMessage(data.text);

        // Display buttons if available
        if (data.buttons && data.buttons.length > 0) {
            displayButtons(data.buttons, data.message_id);
        }
    })
    .catch(error => {
        console.error('Error starting chat session:', error);
        hideTypingIndicator();
        displayBotMessage('Sorry, there was an error connecting to the chatbot. Please try again later.');
    });
}

/**
 * Change the chatbot language
 */
function changeLanguage() {
    currentLanguage = languageSelect.value;

    // Update message input texts for the new language
    updateMessageInputTexts();

    // Clear the chat
    chatMessages.innerHTML = '';

    // If we already have a session, restart it with the new language
    if (sessionId) {
        startChatSession();
    } else {
        // Otherwise, just show the welcome prompt in the new language
        displayWelcomePrompt();
    }
}

/**
 * Display a bot message
 * @param {string} message - The message text
 */
function displayBotMessage(message) {
    // Create message wrapper
    const messageWrapper = document.createElement('div');
    messageWrapper.className = 'message-wrapper';

    // Create avatar
    const avatarContainer = document.createElement('div');
    avatarContainer.className = 'message-avatar';

    const avatarImg = document.createElement('img');
    avatarImg.src = '/static/images/logo.svg';
    avatarImg.alt = 'Bot Avatar';

    avatarContainer.appendChild(avatarImg);
    messageWrapper.appendChild(avatarContainer);

    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = 'message bot-message';

    const messageText = document.createElement('div');

    // Check if the message contains markdown-style formatting or line breaks
    if (message.includes('**') || message.includes('\n')) {
        // Handle formatted messages with proper line breaks and bold text
        let formattedMessage = message
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Convert **text** to <strong>text</strong>
            .replace(/\n/g, '<br>'); // Convert \n to <br>

        messageText.innerHTML = formattedMessage;
    } else {
        // For plain text messages, just use textContent
        messageText.textContent = message;
    }

    const messageTime = document.createElement('div');
    messageTime.className = 'message-time';
    messageTime.textContent = getCurrentTime();

    messageElement.appendChild(messageText);
    messageElement.appendChild(messageTime);

    messageWrapper.appendChild(messageElement);
    chatMessages.appendChild(messageWrapper);

    // Check if this is a feedback thank you message
    if (message.includes("Thank you for your feedback!")) {
        console.log("Detected feedback thank you message");

        // We'll check if there are any buttons already in the next response
        // by setting a flag to check in the handleButtonClick response handler
        window.waitingForFeedbackResponse = true;
    }

    // Scroll to the bottom
    scrollToBottom();
}

/**
 * Display a user message
 * @param {string} message - The message text
 */
function displayUserMessage(message) {
    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = 'message user-message';

    const messageText = document.createElement('div');
    messageText.textContent = message;

    const messageTime = document.createElement('div');
    messageTime.className = 'message-time';
    messageTime.textContent = getCurrentTime();

    messageElement.appendChild(messageText);
    messageElement.appendChild(messageTime);

    chatMessages.appendChild(messageElement);

    // Scroll to the bottom
    scrollToBottom();
}

/**
 * Display buttons for user interaction
 * @param {Array} buttons - Array of button objects
 * @param {number} messageId - The ID of the message the buttons are associated with
 */
function displayButtons(buttons, messageId) {
    // Create a container for the buttons
    const buttonsContainer = document.createElement('div');
    buttonsContainer.className = 'chat-buttons';

    // Create a button for each option
    buttons.forEach(button => {
        // Check if this is a URL button
        if (button.url) {
            // Create a link instead of a button
            const linkElement = document.createElement('a');
            linkElement.className = 'chat-button chat-link-button';
            linkElement.textContent = button.text;
            linkElement.href = button.url;
            linkElement.target = '_blank'; // Open in new tab
            linkElement.dataset.value = button.value;
            linkElement.dataset.messageId = messageId;

            // Add to container
            buttonsContainer.appendChild(linkElement);
        } else {
            // Create a regular button
            const buttonElement = document.createElement('button');
            buttonElement.className = 'chat-button';
            buttonElement.textContent = button.text;
            buttonElement.dataset.value = button.value;
            buttonElement.dataset.messageId = messageId;

            // Special styling for agent button
            if (button.value === 'agent' || button.text === 'Speak to an Agent') {
                buttonElement.classList.add('request-agent-btn');
            }

            // Add click event listener
            buttonElement.addEventListener('click', handleButtonClick);

            buttonsContainer.appendChild(buttonElement);
        }
    });

    // Add the buttons to the chat
    chatMessages.appendChild(buttonsContainer);

    // Scroll to the bottom
    scrollToBottom();
}

/**
 * Display products in a card format
 * @param {Array} products - Array of product objects
 * @param {number} messageId - The ID of the message the products are associated with
 */
function displayProducts(products, messageId) {
    // Create a container for the products
    const productsContainer = document.createElement('div');
    productsContainer.className = 'product-cards';

    // Create a card for each product
    products.forEach(product => {
        const productCard = document.createElement('div');
        productCard.className = 'product-card';

        // Product image (if available)
        const productImage = document.createElement('img');
        const logoPath = '/static/images/5w2fl3vb.svg'; // Store logo path in a variable for consistency

        if (product.image_url && product.image_url.trim() !== '') {
            // Check if the image URL is a full URL or just a filename
            if (product.image_url.startsWith('http') || product.image_url.startsWith('/')) {
                productImage.src = product.image_url;
            } else {
                // Assume it's a filename and prepend the static/images path
                productImage.src = `/static/images/products/${product.image_url}`;
            }
        } else {
            // No image URL or empty string, use logo as placeholder
            productImage.src = logoPath;
        }

        productImage.alt = product.name;
        productImage.className = 'product-image';

        // Add error handler to use logo as placeholder if image fails to load
        productImage.onerror = function() {
            this.src = logoPath;
            console.log(`Image not found: ${product.image_url}, using logo as placeholder`);
        };

        productCard.appendChild(productImage);

        // Product details
        const productDetails = document.createElement('div');
        productDetails.className = 'product-details';

        // Product name
        const productName = document.createElement('h3');
        productName.textContent = product.name;
        productDetails.appendChild(productName);

        // Product price
        const productPrice = document.createElement('p');
        productPrice.className = 'product-price';
        productPrice.textContent = `RM${product.price}`;
        productDetails.appendChild(productPrice);

        // Product description (shortened)
        if (product.description) {
            const productDesc = document.createElement('p');
            productDesc.className = 'product-description';
            productDesc.textContent = product.description.length > 100 ?
                product.description.substring(0, 100) + '...' :
                product.description;
            productDetails.appendChild(productDesc);
        }

        // View product button
        const viewButton = document.createElement('button');
        viewButton.className = 'view-product-btn';

        // Translate "View Details" based on current language
        let viewDetailsText = 'View Details';
        if (currentLanguage === 'zh') {
            viewDetailsText = '查看详情';
        } else if (currentLanguage === 'ms') {
            viewDetailsText = 'Lihat Butiran';
        } else if (currentLanguage === 'ta') {
            viewDetailsText = 'விவரங்களைக் காண்க';
        }

        viewButton.textContent = viewDetailsText;
        viewButton.dataset.value = `product_${product.product_id}`;
        viewButton.dataset.messageId = messageId;
        viewButton.addEventListener('click', handleButtonClick);
        productDetails.appendChild(viewButton);

        productCard.appendChild(productDetails);
        productsContainer.appendChild(productCard);
    });

    // Add the products to the chat
    chatMessages.appendChild(productsContainer);

    // Scroll to the bottom
    scrollToBottom();
}

/**
 * Handle button click
 * @param {Event} event - The click event
 */
function handleButtonClick(event) {
    const button = event.target;
    const buttonValue = button.dataset.value;
    const messageId = button.dataset.messageId;

    // Display the selected option as a user message
    displayUserMessage(button.textContent);

    // Remove the buttons
    const buttonsContainer = button.parentElement;
    buttonsContainer.remove();

    // Show typing indicator
    showTypingIndicator();

    // Process the button click
    fetch('/api/process_button', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            session_id: sessionId,
            message_id: messageId,
            button_value: buttonValue,
            button_text: button.textContent
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        // Hide typing indicator
        hideTypingIndicator();

        // Debug: Log the response data
        console.log('Response data:', data);

        // Check if there's an error in the response
        if (data.error) {
            console.error('Error from server:', data.error);
            displayBotMessage('Sorry, there was an error processing your selection. Please try again.');
            return;
        }

        // Save the message ID
        lastMessageId = data.message_id;

        // Handle redirect response type
        if (data.type === 'redirect' && data.redirect_url) {
            // Redirect to the specified URL
            window.location.href = data.redirect_url;
            return;
        }

        // Display the response text if it's not empty
        if (data.text && data.text.trim() !== '') {
            displayBotMessage(data.text);
        }

        // Check if this was an agent request and show message input
        if (buttonValue === 'agent' || button.textContent === 'Speak to an Agent') {
            // Show the message input box for agent communication
            setTimeout(() => {
                showMessageInput();
                // Join WebSocket room for real-time communication
                joinSessionRoom();
                isAgentConnected = true;
            }, 500); // Small delay to let the bot message appear first
        }

        // Check if this was an agent ended response and hide message input
        if (data.type === 'agent_ended') {
            // Notify agent via WebSocket that customer ended the chat
            if (socket && isAgentConnected) {
                socket.emit('customer_ended_chat', {
                    session_id: sessionId,
                    message: 'Customer returned to main menu and ended the agent chat.'
                });
            }

            // Hide the message input box
            setTimeout(() => {
                hideMessageInput();
                // Leave WebSocket room
                leaveSessionRoom();
                isAgentConnected = false;
                // Update status
                updateAgentStatus('', false);
            }, 500); // Small delay to let the bot message appear first
        }

        // Display products if available
        if (data.type === 'products' && data.products && data.products.length > 0) {
            displayProducts(data.products, data.message_id);
        }

        // Handle feedback responses
        if (data.feedback_data) {
            // Store feedback data in the response for later use
            if (data.multi_select) {
                // For multi-select feedback options (like improvement areas)
                displayFeedbackButtons(data.buttons, data.message_id, data.feedback_data);
            } else {
                // For regular feedback options
                displayButtons(data.buttons, data.message_id);
            }
        } else if (data.buttons && data.buttons.length > 0) {
            console.log('Displaying buttons:', data.buttons);
            // Display regular buttons
            displayButtons(data.buttons, data.message_id);

            // If we were waiting for a feedback response, we got buttons, so clear the flag
            if (window.waitingForFeedbackResponse) {
                window.waitingForFeedbackResponse = false;
            }
        } else {
            console.log('No buttons to display');

            // If we were waiting for a feedback response and no buttons were provided,
            // add a main menu button
            if (window.waitingForFeedbackResponse) {
                console.log('Adding main menu button after feedback thank you');

                // Create a main menu button
                const mainMenuButton = {
                    text: currentLanguage === 'ms' ? 'Menu Utama' :
                          currentLanguage === 'zh' ? '主菜单' :
                          currentLanguage === 'ta' ? 'முதன்மை பட்டி' : 'Main Menu',
                    value: 'nav_main_menu'
                };

                // Display the main menu button
                displayButtons([mainMenuButton], lastMessageId);

                // Clear the flag
                window.waitingForFeedbackResponse = false;
            }
        }
    })
    .catch(error => {
        console.error('Error processing button click:', error);
        hideTypingIndicator();
        displayBotMessage('Sorry, there was an error processing your selection. Please try again.');
    });
}

/**
 * Show typing indicator
 */
function showTypingIndicator() {
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'typing-indicator';
    typingIndicator.id = 'typing-indicator';

    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('span');
        typingIndicator.appendChild(dot);
    }

    chatMessages.appendChild(typingIndicator);

    // Scroll to the bottom
    scrollToBottom();
}

/**
 * Hide typing indicator
 */
function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

/**
 * Scroll to the bottom of the chat
 */
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Get the current time in HH:MM format
 * @returns {string} The current time
 */
function getCurrentTime() {
    const now = new Date();
    const hours = now.getHours().toString().padStart(2, '0');
    const minutes = now.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
}

/**
 * Display feedback buttons for multi-select options
 * @param {Array} buttons - Array of button objects
 * @param {number} messageId - The ID of the message the buttons are associated with
 * @param {Object} feedbackData - The feedback data collected so far
 */
function displayFeedbackButtons(buttons, messageId, feedbackData) {
    // Create a container for the buttons
    const buttonsContainer = document.createElement('div');
    buttonsContainer.className = 'chat-buttons feedback-buttons';
    buttonsContainer.dataset.feedbackData = JSON.stringify(feedbackData);

    // Create a button for each option
    buttons.forEach(button => {
        const buttonElement = document.createElement('button');
        buttonElement.className = 'chat-button';

        // Check if this button is already selected (for multi-select options)
        if (button.text.startsWith('✓ ')) {
            buttonElement.classList.add('selected-feedback');
        }

        buttonElement.textContent = button.text;
        buttonElement.dataset.value = button.value;
        buttonElement.dataset.messageId = messageId;

        // Add click event listener
        buttonElement.addEventListener('click', handleButtonClick);

        buttonsContainer.appendChild(buttonElement);
    });

    // Add the buttons to the chat
    chatMessages.appendChild(buttonsContainer);

    // Scroll to the bottom
    scrollToBottom();
}

/**
 * End the chat session when the window is closed
 */
window.addEventListener('beforeunload', () => {
    if (sessionId) {
        // End the session with window ID for better tracking
        // Use sendBeacon for more reliable delivery during page unload
        navigator.sendBeacon('/api/end_session', JSON.stringify({
            session_id: sessionId,
            window_id: windowId,
            reason: 'Window closed'
        }));
    }
});

/**
 * Set up message input box functionality
 */
function setupMessageInput() {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');

    if (messageInput && sendButton) {
        // Handle Enter key press
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Handle send button click
        sendButton.addEventListener('click', sendMessage);

        // Auto-resize input and enable/disable send button
        messageInput.addEventListener('input', function() {
            const message = this.value.trim();
            sendButton.disabled = message.length === 0;
        });
    }
}

/**
 * Show the message input box for agent communication
 */
function showMessageInput() {
    const inputContainer = document.getElementById('message-input-container');
    const messageInput = document.getElementById('message-input');

    if (inputContainer) {
        inputContainer.style.display = 'block';
        isAgentConnected = true;

        // Focus on the input field
        if (messageInput) {
            setTimeout(() => {
                messageInput.focus();
            }, 300); // Wait for animation to complete
        }

        // Update status with translation
        const statusText = currentLanguage === 'ms' ? 'Disambungkan kepada ejen' :
                          currentLanguage === 'zh' ? '已连接到客服' :
                          currentLanguage === 'ta' ? 'முகவருடன் இணைக்கப்பட்டது' : 'Connected to agent';
        updateAgentStatus(statusText, true);

        // Update message input texts for current language
        updateMessageInputTexts();

        // Set up message input functionality if not already done
        setupMessageInput();
    }
}

/**
 * Hide the message input box
 */
function hideMessageInput() {
    const inputContainer = document.getElementById('message-input-container');

    if (inputContainer) {
        inputContainer.style.display = 'none';
        isAgentConnected = false;

        // Clear any typed message
        const messageInput = document.getElementById('message-input');
        if (messageInput) {
            messageInput.value = '';
        }
    }
}

/**
 * Update agent status indicator
 */
function updateAgentStatus(statusText, isConnected) {
    const statusTextElement = document.querySelector('.status-text');
    const statusIndicator = document.querySelector('.status-indicator');

    if (statusTextElement) {
        statusTextElement.textContent = statusText;
    }

    if (statusIndicator) {
        statusIndicator.style.backgroundColor = isConnected ? '#4CAF50' : '#ff9800';
    }
}

/**
 * Update message input placeholder and button text based on current language
 */
function updateMessageInputTexts() {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');

    if (messageInput) {
        const placeholder = currentLanguage === 'ms' ? 'Taip mesej anda kepada ejen...' :
                           currentLanguage === 'zh' ? '输入您给客服的消息...' :
                           currentLanguage === 'ta' ? 'முகவருக்கு உங்கள் செய்தியை தட்டச்சு செய்யுங்கள்...' : 'Type your message to the agent...';
        messageInput.placeholder = placeholder;
    }

    if (sendButton && !sendButton.disabled) {
        const sendText = currentLanguage === 'ms' ? 'Hantar' :
                        currentLanguage === 'zh' ? '发送' :
                        currentLanguage === 'ta' ? 'அனுப்பு' : 'Send';
        sendButton.textContent = sendText;
    }
}

/**
 * Send message to agent
 */
function sendMessage() {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');

    if (!messageInput || !sessionId) return;

    const message = messageInput.value.trim();
    if (message.length === 0) return;

    // Disable input while sending
    messageInput.disabled = true;
    sendButton.disabled = true;
    const sendingText = currentLanguage === 'ms' ? 'Menghantar...' :
                       currentLanguage === 'zh' ? '发送中...' :
                       currentLanguage === 'ta' ? 'அனுப்புகிறது...' : 'Sending...';
    sendButton.textContent = sendingText;

    // Add user message to chat
    displayUserMessage(message);

    // Clear input
    messageInput.value = '';

    // Send message via WebSocket
    if (socket) {
        socket.emit('send_message', {
            session_id: sessionId,
            message: message,
            sender_type: userInfo.isLoggedIn ? 'customer' : 'guest',
            sender_name: userInfo.isLoggedIn ? userInfo.username : 'Guest'
        });
        console.log('Message sent via WebSocket');
    } else {
        console.error('WebSocket not connected');
        const errorText = currentLanguage === 'ms' ? 'Ralat sambungan. Sila muat semula halaman.' :
                         currentLanguage === 'zh' ? '连接错误。请刷新页面。' :
                         currentLanguage === 'ta' ? 'இணைப்பு பிழை. பக்கத்தை புதுப்பிக்கவும்.' : 'Connection error. Please refresh the page.';
        displayBotMessage(errorText);
    }

    // Re-enable input
    messageInput.disabled = false;
    sendButton.disabled = false;
    const sendText = currentLanguage === 'ms' ? 'Hantar' :
                    currentLanguage === 'zh' ? '发送' :
                    currentLanguage === 'ta' ? 'அனுப்பு' : 'Send';
    sendButton.textContent = sendText;
    messageInput.focus();
}

/**
 * Add a generic message to the chat (used by both bot and user messages)
 */
function addMessage(message, sender) {
    if (sender === 'user') {
        displayUserMessage(message);
    } else {
        displayBotMessage(message);
    }
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
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
    });

    // Message event handlers
    socket.on('new_message', (data) => {
        if (data.session_id == sessionId) {
            if (data.sender_type === 'agent') {
                displayAgentMessage(data.message_text, data.sender_name || 'Agent');
            } else if (data.sender_type === 'system') {
                displayBotMessage(data.message_text);
            }
        }
    });

    socket.on('agent_joined', (data) => {
        if (data.session_id == sessionId) {
            displayBotMessage(data.message);
            isAgentConnected = true;
        }
    });

    socket.on('agent_left', (data) => {
        if (data.session_id == sessionId) {
            const defaultMessage = currentLanguage === 'ms' ? 'Sembang telah ditamatkan oleh ejen.' :
                                  currentLanguage === 'zh' ? '聊天已被客服结束。' :
                                  currentLanguage === 'ta' ? 'அரட்டை முகவரால் முடிக்கப்பட்டது.' : 'Chat has been ended by the agent.';
            handleChatEnded(data.message || defaultMessage);
        }
    });

    socket.on('message_error', (data) => {
        console.error('Message error:', data.error);
        const errorText = currentLanguage === 'ms' ? 'Gagal menghantar mesej. Sila cuba lagi.' :
                         currentLanguage === 'zh' ? '发送消息失败。请重试。' :
                         currentLanguage === 'ta' ? 'செய்தி அனுப்ப முடியவில்லை. மீண்டும் முயற்சிக்கவும்.' : 'Failed to send message. Please try again.';
        displayBotMessage(errorText);
    });
}

/**
 * Join a WebSocket room for the current session
 */
function joinSessionRoom() {
    if (socket && sessionId) {
        socket.emit('join_session', {
            session_id: sessionId,
            user_type: 'customer'
        });
        console.log(`Joined WebSocket room for session ${sessionId}`);
    }
}

/**
 * Leave a WebSocket room for the current session
 */
function leaveSessionRoom() {
    if (socket && sessionId) {
        socket.emit('leave_session', {
            session_id: sessionId,
            user_type: 'customer'
        });
        console.log(`Left WebSocket room for session ${sessionId}`);
    }
}

/**
 * Handle when chat is ended by agent
 */
function handleChatEnded(endMessage) {
    // Leave WebSocket room
    leaveSessionRoom();

    // Mark agent as disconnected
    isAgentConnected = false;

    // Hide message input box
    hideMessageInput();

    // Show end message
    displayBotMessage(endMessage);

    // Show main menu button after a delay
    setTimeout(() => {
        const mainMenuButton = {
            text: currentLanguage === 'ms' ? 'Menu Utama' :
                  currentLanguage === 'zh' ? '主菜单' :
                  currentLanguage === 'ta' ? 'முதன்மை பட்டி' : 'Main Menu',
            value: 'nav_main_menu'
        };

        displayButtons([mainMenuButton], Date.now());
    }, 1000);
}

// Polling functions removed - using WebSocket for real-time communication

/**
 * Display an agent message in the chat
 */
function displayAgentMessage(message, agentName) {
    // Create message wrapper
    const messageWrapper = document.createElement('div');
    messageWrapper.className = 'message-wrapper';

    // Create avatar
    const avatarContainer = document.createElement('div');
    avatarContainer.className = 'message-avatar';

    const avatarImg = document.createElement('img');
    avatarImg.src = '/static/images/logo.svg'; // Use agent avatar or default
    avatarImg.alt = 'Agent Avatar';

    avatarContainer.appendChild(avatarImg);
    messageWrapper.appendChild(avatarContainer);

    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = 'message agent-message';

    // Agent name header
    const agentHeader = document.createElement('div');
    agentHeader.className = 'agent-name';
    agentHeader.textContent = agentName;
    agentHeader.style.fontWeight = 'bold';
    agentHeader.style.fontSize = '0.9rem';
    agentHeader.style.color = '#2196F3';
    agentHeader.style.marginBottom = '5px';

    const messageText = document.createElement('div');

    // Handle formatted messages with proper line breaks
    if (message.includes('**') || message.includes('\n')) {
        let formattedMessage = message
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
        messageText.innerHTML = formattedMessage;
    } else {
        messageText.textContent = message;
    }

    const messageTime = document.createElement('div');
    messageTime.className = 'message-time';
    messageTime.textContent = getCurrentTime();

    messageElement.appendChild(agentHeader);
    messageElement.appendChild(messageText);
    messageElement.appendChild(messageTime);

    messageWrapper.appendChild(messageElement);
    chatMessages.appendChild(messageWrapper);

    // Scroll to the bottom
    scrollToBottom();
}

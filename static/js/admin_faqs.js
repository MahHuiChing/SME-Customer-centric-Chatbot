/**
 * Rock Chatbot - Admin FAQs Management
 *
 * This script handles the FAQs management functionality in the admin dashboard.
 * It provides CRUD operations for FAQs.
 */

// Global variables
let currentFaqPage = 1;
const faqsPerPage = 10;
let totalFaqPages = 1;
let faqCategories = ['General', 'Products', 'Shipping', 'Payment', 'Returns'];

// Fetch categories from the server when the page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded and parsed');

    // Fetch FAQ categories from the server
    fetch('/api/admin/all_faqs?page=1&per_page=100')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update categories from the server data
                updateFaqCategories(data.faqs || []);
                console.log('Loaded FAQ categories from server:', faqCategories);

                // Check if there are any FAQs
                if (!data.faqs || data.faqs.length === 0) {
                    console.log('No FAQs found, showing "Add New FAQ" notification');
                    showNotification('No FAQs found. Click "Add New FAQ" to create your first FAQ.', 'info');
                }
            }
        })
        .catch(error => {
            console.error('Error loading FAQ categories:', error);
            // Use default categories
            updateFaqCategories([]);
        });

    // Attach form submission handler
    const faqForm = document.getElementById('faq-form');
    if (faqForm) {
        console.log('Attaching form submission handler to FAQ form');
        faqForm.addEventListener('submit', handleFaqFormSubmit);
    } else {
        console.error('FAQ form not found in DOM');
    }

    // Attach category change handler directly
    const categorySelect = document.getElementById('faq-category');
    if (categorySelect) {
        console.log('Attaching change handler to category select');
        categorySelect.addEventListener('change', function() {
            console.log('Category changed to:', this.value);
            const newCategoryGroup = document.getElementById('new-category-group');
            if (this.value === 'new') {
                if (newCategoryGroup) {
                    newCategoryGroup.style.display = 'block';
                    const newCategoryInput = document.getElementById('new-faq-category');
                    if (newCategoryInput) {
                        newCategoryInput.focus();
                    }
                }
            } else {
                if (newCategoryGroup) {
                    newCategoryGroup.style.display = 'none';
                }
            }
        });
    } else {
        console.error('Category select not found in DOM');
    }

    // Attach modal close handler
    const closeModalBtn = document.querySelector('.close-modal');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', function() {
            const modal = document.getElementById('faq-modal');
            if (modal) {
                modal.style.display = 'none';
            }
        });
    }

    // Add event listener for FAQ tab click
    const faqTabLink = document.querySelector('.sidebar-menu a[data-tab="faqs"]');
    if (faqTabLink) {
        faqTabLink.addEventListener('click', function() {
            console.log('FAQ tab clicked, loading FAQs');
            if (typeof window.loadFaqs === 'function') {
                window.loadFaqs();
            } else {
                console.error('loadFaqs function is not defined');
            }
        });
    }

    // Make sure loadFaqs is defined in the global scope
    if (typeof window.loadFaqs !== 'function') {
        console.log('Defining loadFaqs in the global scope');
    }
});

/**
 * Load FAQs with pagination
 * @param {number} page - The page number to load
 */
window.loadFaqs = function(page = 1) {
    currentFaqPage = page;

    // Show loading indicator
    const faqsTab = document.getElementById('faqs');
    faqsTab.innerHTML = '<div class="loading">Loading FAQs...</div>';

    // Check if we have saved filter state
    const savedFilterState = sessionStorage.getItem('faqFilterState');
    if (savedFilterState) {
        try {
            const filterState = JSON.parse(savedFilterState);
            // Use the saved filter state
            loadFaqsWithFilters(
                page,
                filterState.searchTerm || '',
                filterState.category || '',
                '',
                filterState.status || ''
            );
            return; // Exit early as we're loading with filters
        } catch (e) {
            console.error('Error parsing saved filter state:', e);
            // Clear invalid filter state
            sessionStorage.removeItem('faqFilterState');
        }
    }

    // Fetch FAQs from API (no filters)
    fetch(`/api/admin/all_faqs?page=${page}&per_page=${faqsPerPage}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update pagination info
                totalFaqPages = data.pagination.total_pages;

                // Update FAQ categories
                updateFaqCategories(data.faqs);

                // Create FAQs table with search and filter
                let html = `
                    <div class="card-header">
                        <h2>Frequently Asked Questions</h2>
                        <div class="header-buttons">
                            <button class="btn" id="view-pending-faqs-btn">View Pending FAQs</button>
                            <button class="btn btn-primary" id="add-faq-btn">Add New FAQ</button>
                        </div>
                    </div>
                    <div class="search-filter-container">
                        <div class="search-box">
                            <input type="text" id="faq-search" placeholder="Search FAQs..." class="search-input">
                            <button id="faq-search-btn" class="search-btn"><i class="fas fa-search"></i></button>
                        </div>
                        <div class="filter-container">
                            <select id="category-filter" class="filter-select">
                                <option value="">All Categories</option>
                                ${faqCategories.map(cat => `<option value="${cat}">${cat}</option>`).join('')}
                            </select>
                            <select id="status-filter" class="filter-select">
                                <option value="">All Status</option>
                                <option value="active">Active</option>
                                <option value="inactive">Inactive</option>
                            </select>
                            <button id="apply-filters-btn" class="filter-btn">Apply Filters</button>
                            <button id="clear-filters-btn" class="filter-btn">Clear Filters</button>
                        </div>
                    </div>
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Question</th>
                                    <th>Category</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="faqs-table">
                `;

                // Add FAQs to table
                if (data.faqs && data.faqs.length > 0) {
                    data.faqs.forEach(faq => {
                        html += `
                            <tr>
                                <td>${faq.faq_id}</td>
                                <td>${faq.question}</td>
                                <td>${faq.category}</td>
                                <td>${faq.is_active ? 'Active' : 'Inactive'}</td>
                                <td class="action-buttons">
                                    <button class="action-btn edit-btn" onclick="editFaq(${faq.faq_id})">Edit</button>
                                    <button class="action-btn delete-btn" onclick="deleteFaq(${faq.faq_id})">Delete</button>
                                </td>
                            </tr>
                        `;
                    });
                } else {
                    html += `
                        <tr>
                            <td colspan="5" class="no-results">No FAQs found. Click "Add New FAQ" to create one.</td>
                        </tr>
                    `;
                }

                html += `
                            </tbody>
                        </table>
                    </div>
                `;

                // Add pagination
                if (totalFaqPages > 1) {
                    html += `
                        <div class="pagination">
                            <button ${page === 1 ? 'disabled' : ''} onclick="loadFaqs(1)">First</button>
                            <button ${page === 1 ? 'disabled' : ''} onclick="loadFaqs(${page - 1})">Previous</button>
                    `;

                    // Show page numbers
                    const startPage = Math.max(1, page - 2);
                    const endPage = Math.min(totalFaqPages, page + 2);

                    for (let i = startPage; i <= endPage; i++) {
                        html += `
                            <button class="${i === page ? 'active' : ''}" onclick="loadFaqs(${i})">${i}</button>
                        `;
                    }

                    html += `
                            <button ${page === totalFaqPages ? 'disabled' : ''} onclick="loadFaqs(${page + 1})">Next</button>
                            <button ${page === totalFaqPages ? 'disabled' : ''} onclick="loadFaqs(${totalFaqPages})">Last</button>
                        </div>
                    `;
                }

                // Update FAQs tab content
                faqsTab.innerHTML = html;

                // Add event listener to add FAQ button
                const addFaqBtn = document.getElementById('add-faq-btn');
                if (addFaqBtn) {
                    addFaqBtn.addEventListener('click', showAddFaqModal);
                }

                // Add event listener to view pending FAQs button
                const viewPendingFaqsBtn = document.getElementById('view-pending-faqs-btn');
                if (viewPendingFaqsBtn) {
                    viewPendingFaqsBtn.addEventListener('click', loadPendingFaqs);
                }

                // Add event listeners for search and filter
                const searchBtn = document.getElementById('faq-search-btn');
                const searchInput = document.getElementById('faq-search');
                const applyFiltersBtn = document.getElementById('apply-filters-btn');
                const clearFiltersBtn = document.getElementById('clear-filters-btn');

                if (searchBtn && searchInput) {
                    // Search on button click
                    searchBtn.addEventListener('click', () => {
                        applyFaqFilters();
                    });

                    // Search on Enter key
                    searchInput.addEventListener('keypress', (e) => {
                        if (e.key === 'Enter') {
                            applyFaqFilters();
                        }
                    });
                }

                if (applyFiltersBtn) {
                    // Remove any existing event listeners
                    applyFiltersBtn.removeEventListener('click', applyFaqFilters);
                    // Add new event listener
                    applyFiltersBtn.addEventListener('click', applyFaqFilters);

                    // Add visual feedback on hover
                    applyFiltersBtn.classList.add('active-filter-btn');
                }

                if (clearFiltersBtn) {
                    // Remove any existing event listeners
                    clearFiltersBtn.removeEventListener('click', clearFaqFilters);
                    // Add new event listener
                    clearFiltersBtn.addEventListener('click', clearFaqFilters);

                    // Add visual feedback on hover
                    clearFiltersBtn.classList.add('active-filter-btn');
                }
            } else {
                faqsTab.innerHTML = `<div class="error">Error loading FAQs: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading FAQs:', error);
            faqsTab.innerHTML = '<div class="error">Error loading FAQs. Please try again.</div>';
        });
}

/**
 * Apply FAQ filters and search
 */
window.applyFaqFilters = function() {
    // Get filter values
    const searchTerm = document.getElementById('faq-search').value.trim();
    let category = document.getElementById('category-filter').value;

    // Debug the selected category
    console.log('Selected category before normalization:', category);

    // Normalize the category if one is selected
    if (category) {
        category = normalizeCategory(category);
        console.log('Selected category after normalization:', category);
    }

    const status = document.getElementById('status-filter').value;

    // Build query parameters
    let queryParams = new URLSearchParams();

    // Add search term if provided
    if (searchTerm) {
        queryParams.append('search', searchTerm);
    }

    // Add category filter if selected
    if (category) {
        queryParams.append('category', category);
    }

    // Language filter removed

    // Add status filter if selected
    if (status) {
        queryParams.append('status', status);
    }

    // Reset to first page
    currentFaqPage = 1;
    queryParams.append('page', currentFaqPage);
    queryParams.append('per_page', faqsPerPage);

    // Show loading indicator
    const faqsTab = document.getElementById('faqs');
    faqsTab.innerHTML = '<div class="loading">Searching FAQs...</div>';

    // Save filter state to sessionStorage
    const filterState = {
        searchTerm,
        category,
        status
    };
    sessionStorage.setItem('faqFilterState', JSON.stringify(filterState));

    // Fetch filtered FAQs
    fetch(`/api/admin/all_faqs?${queryParams.toString()}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update pagination info
                totalFaqPages = data.pagination.total_pages;

                // Reload FAQs with the same filters
                loadFaqsWithFilters(currentFaqPage, searchTerm, category, '', status);

                // Show notification
                showNotification('Filters applied successfully', 'success');
            } else {
                faqsTab.innerHTML = `<div class="error">Error searching FAQs: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error searching FAQs:', error);
            faqsTab.innerHTML = '<div class="error">Error searching FAQs. Please try again.</div>';
        });
}

/**
 * Clear FAQ filters and reload all FAQs
 */
window.clearFaqFilters = function() {
    // Reset filter inputs
    document.getElementById('faq-search').value = '';
    document.getElementById('category-filter').value = '';
    document.getElementById('status-filter').value = '';

    // Clear filter state from sessionStorage
    sessionStorage.removeItem('faqFilterState');

    // Reset to first page and reload
    currentFaqPage = 1;
    loadFaqs(currentFaqPage);

    // Show notification
    showNotification('Filters cleared', 'info');
}

/**
 * Load FAQs with filters
 * @param {number} page - The page number to load
 * @param {string} searchTerm - Search term
 * @param {string} category - Category filter
 * @param {string} language - Language filter (deprecated, kept for backward compatibility)
 * @param {string} status - Status filter
 */
window.loadFaqsWithFilters = function(page = 1, searchTerm = '', category = '', language = '', status = '') {
    // Build query parameters
    let queryParams = new URLSearchParams();
    queryParams.append('page', page);
    queryParams.append('per_page', faqsPerPage);

    // Add search term if provided
    if (searchTerm) {
        queryParams.append('search', searchTerm);
    }

    // Add category filter if selected
    if (category) {
        // Ensure the category is properly normalized
        const normalizedCategory = normalizeCategory(category);
        if (normalizedCategory) {
            queryParams.append('category', normalizedCategory);
            console.log('Filtering by category:', normalizedCategory);
        }
    }

    // Language filter removed

    // Add status filter if selected
    if (status) {
        queryParams.append('status', status);
    }

    // Show loading indicator
    const faqsTab = document.getElementById('faqs');
    faqsTab.innerHTML = '<div class="loading">Loading FAQs...</div>';

    // Fetch filtered FAQs
    fetch(`/api/admin/all_faqs?${queryParams.toString()}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update pagination info
                totalFaqPages = data.pagination.total_pages;

                // Update FAQ categories
                updateFaqCategories(data.faqs);

                // Create FAQs table with search and filter
                let html = `
                    <div class="card-header">
                        <h2>Frequently Asked Questions</h2>
                        <button class="btn btn-primary" id="add-faq-btn">Add New FAQ</button>
                    </div>
                    <div class="search-filter-container">
                        <div class="search-box">
                            <input type="text" id="faq-search" placeholder="Search FAQs..." class="search-input" value="${searchTerm}">
                            <button id="faq-search-btn" class="search-btn"><i class="fas fa-search"></i></button>
                        </div>
                        <div class="filter-container">
                            <select id="category-filter" class="filter-select">
                                <option value="">All Categories</option>
                                ${faqCategories.map(cat => `<option value="${cat}" ${category === cat ? 'selected' : ''}>${cat}</option>`).join('')}
                            </select>
                            <select id="status-filter" class="filter-select">
                                <option value="">All Status</option>
                                <option value="active" ${status === 'active' ? 'selected' : ''}>Active</option>
                                <option value="inactive" ${status === 'inactive' ? 'selected' : ''}>Inactive</option>
                            </select>
                            <button id="apply-filters-btn" class="filter-btn">Apply Filters</button>
                            <button id="clear-filters-btn" class="filter-btn">Clear Filters</button>
                        </div>
                    </div>
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Question</th>
                                    <th>Category</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="faqs-table">
                `;

                // Add FAQs to table
                if (data.faqs.length === 0) {
                    html += `
                        <tr>
                            <td colspan="6" class="no-results">No FAQs found matching your criteria.</td>
                        </tr>
                    `;
                } else {
                    data.faqs.forEach(faq => {
                        html += `
                            <tr>
                                <td>${faq.faq_id}</td>
                                <td>${faq.question}</td>
                                <td>${faq.category}</td>
                                <td>${faq.is_active ? 'Active' : 'Inactive'}</td>
                                <td class="action-buttons">
                                    <button class="action-btn edit-btn" onclick="editFaq(${faq.faq_id})">Edit</button>
                                    <button class="action-btn delete-btn" onclick="deleteFaq(${faq.faq_id})">Delete</button>
                                </td>
                            </tr>
                        `;
                    });
                }

                html += `
                            </tbody>
                        </table>
                    </div>
                `;

                // Add pagination with filter parameters
                if (totalFaqPages > 1) {
                    html += `
                        <div class="pagination">
                            <button ${page === 1 ? 'disabled' : ''} onclick="loadFaqsWithFilters(1, '${searchTerm}', '${category}', '', '${status}')">First</button>
                            <button ${page === 1 ? 'disabled' : ''} onclick="loadFaqsWithFilters(${page - 1}, '${searchTerm}', '${category}', '', '${status}')">Previous</button>
                    `;

                    // Show page numbers
                    const startPage = Math.max(1, page - 2);
                    const endPage = Math.min(totalFaqPages, page + 2);

                    for (let i = startPage; i <= endPage; i++) {
                        html += `
                            <button class="${i === page ? 'active' : ''}" onclick="loadFaqsWithFilters(${i}, '${searchTerm}', '${category}', '', '${status}')">${i}</button>
                        `;
                    }

                    html += `
                            <button ${page === totalFaqPages ? 'disabled' : ''} onclick="loadFaqsWithFilters(${page + 1}, '${searchTerm}', '${category}', '', '${status}')">Next</button>
                            <button ${page === totalFaqPages ? 'disabled' : ''} onclick="loadFaqsWithFilters(${totalFaqPages}, '${searchTerm}', '${category}', '', '${status}')">Last</button>
                        </div>
                    `;
                }

                // Update FAQs tab content
                faqsTab.innerHTML = html;

                // Add event listeners
                const addFaqBtn = document.getElementById('add-faq-btn');
                if (addFaqBtn) {
                    addFaqBtn.addEventListener('click', showAddFaqModal);
                }

                // Add event listeners for search and filter
                const searchBtn = document.getElementById('faq-search-btn');
                const searchInputField = document.getElementById('faq-search');
                const applyFiltersBtn = document.getElementById('apply-filters-btn');
                const clearFiltersBtn = document.getElementById('clear-filters-btn');

                if (searchBtn && searchInputField) {
                    // Search on button click
                    searchBtn.addEventListener('click', () => {
                        applyFaqFilters();
                    });

                    // Search on Enter key
                    searchInputField.addEventListener('keypress', (e) => {
                        if (e.key === 'Enter') {
                            applyFaqFilters();
                        }
                    });
                }

                if (applyFiltersBtn) {
                    // Remove any existing event listeners
                    applyFiltersBtn.removeEventListener('click', applyFaqFilters);
                    // Add new event listener
                    applyFiltersBtn.addEventListener('click', applyFaqFilters);

                    // Add visual feedback on hover
                    applyFiltersBtn.classList.add('active-filter-btn');
                }

                if (clearFiltersBtn) {
                    // Remove any existing event listeners
                    clearFiltersBtn.removeEventListener('click', clearFaqFilters);
                    // Add new event listener
                    clearFiltersBtn.addEventListener('click', clearFaqFilters);

                    // Add visual feedback on hover
                    clearFiltersBtn.classList.add('active-filter-btn');
                }
            } else {
                faqsTab.innerHTML = `<div class="error">Error loading FAQs: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading FAQs:', error);
            faqsTab.innerHTML = '<div class="error">Error loading FAQs. Please try again.</div>';
        });
}

/**
 * Get language name by code
 * @param {string} code - The language code
 * @returns {string} The language name
 */
function getLanguageName(code) {
    const languages = {
        'en': 'English',
        'ms': 'Bahasa Melayu',
        'zh': 'Chinese',
        'ta': 'Tamil'
    };

    return languages[code] || code;
}

/**
 * Normalize category name to ensure consistency
 * @param {string} category - The category name to normalize
 * @returns {string} The normalized category name
 */
function normalizeCategory(category) {
    if (!category) return '';

    // Trim whitespace
    let normalized = category.trim();

    // If empty after trimming, return empty string
    if (normalized === '') return '';

    // Handle common variations (case insensitive)
    const categoryMap = {
        'product': 'Products',
        'products': 'Products',
        'shipping': 'Shipping',
        'payment': 'Payment',
        'payments': 'Payment',
        'return': 'Returns',
        'returns': 'Returns',
        'general': 'General'
    };

    // Check if we have a mapping for this category (case insensitive)
    const lowerCaseNormalized = normalized.toLowerCase();
    if (categoryMap[lowerCaseNormalized]) {
        return categoryMap[lowerCaseNormalized];
    }

    // If no mapping exists, capitalize the first letter
    if (normalized.length > 0) {
        normalized = normalized.charAt(0).toUpperCase() + normalized.slice(1);
    }

    return normalized;
}

/**
 * Show a notification message
 * @param {string} message - The message to display
 * @param {string} type - The type of notification (success, error, info)
 */
function showNotification(message, type = 'info') {
    // Create notification element if it doesn't exist
    let notification = document.getElementById('notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'notification';
        document.body.appendChild(notification);

        // Add styles if not already in CSS
        if (!document.getElementById('notification-styles')) {
            const style = document.createElement('style');
            style.id = 'notification-styles';
            style.textContent = `
                #notification {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    padding: 12px 20px;
                    border-radius: 4px;
                    color: white;
                    font-weight: 500;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                    z-index: 9999;
                    opacity: 0;
                    transform: translateY(-20px);
                    transition: opacity 0.3s, transform 0.3s;
                }
                #notification.show {
                    opacity: 1;
                    transform: translateY(0);
                }
                #notification.success { background-color: #4CAF50; }
                #notification.error { background-color: #F44336; }
                #notification.info { background-color: #2196F3; }
            `;
            document.head.appendChild(style);
        }
    }

    // Set notification content and type
    notification.textContent = message;
    notification.className = type;

    // Show the notification
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);

    // Hide after 3 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.style.display = 'none';
        }, 300);
    }, 3000);
}

/**
 * Update FAQ categories from the loaded FAQs
 * @param {Array} faqs - The FAQs array
 */
function updateFaqCategories(faqs) {
    // Extract unique categories from FAQs
    const uniqueCategories = new Set();

    // Default categories to ensure we always have some options
    const defaultCategories = ['General', 'Products', 'Shipping', 'Payment', 'Returns'];

    // Add default categories to ensure they're always available
    defaultCategories.forEach(category => {
        uniqueCategories.add(category);
    });

    // Check if faqs is a valid array
    if (Array.isArray(faqs) && faqs.length > 0) {
        // Add categories from FAQs with normalization
        faqs.forEach(faq => {
            if (faq.category && faq.category.trim() !== '') {
                // Normalize the category name before adding
                const normalizedCategory = normalizeCategory(faq.category);
                if (normalizedCategory) {
                    uniqueCategories.add(normalizedCategory);
                }
            }
        });
    } else {
        console.warn('No FAQs provided to updateFaqCategories, using default categories');
    }

    // Update the global categories array
    faqCategories = Array.from(uniqueCategories).sort();

    // Update the category filter dropdown if it exists
    const categoryFilter = document.getElementById('category-filter');
    if (categoryFilter) {
        // Save the currently selected value
        const selectedValue = categoryFilter.value;

        // Clear and rebuild the options
        categoryFilter.innerHTML = '<option value="">All Categories</option>';

        // Only add categories that actually have FAQs
        faqCategories.forEach(category => {
            if (category && category.trim() !== '') {
                const option = document.createElement('option');
                option.value = category;
                option.textContent = category;

                // Restore the selected value if it matches
                if (selectedValue === category) {
                    option.selected = true;
                }

                categoryFilter.appendChild(option);
            }
        });

        console.log('FAQ category filter updated with latest categories:', faqCategories);
    }
}

/**
 * Show add FAQ modal
 */
function showAddFaqModal() {
    console.log('showAddFaqModal called');

    // Reset form
    const faqForm = document.getElementById('faq-form');
    if (faqForm) {
        faqForm.reset();
    }

    // Set modal title
    const modalTitle = document.getElementById('faq-modal-title');
    if (modalTitle) {
        modalTitle.textContent = 'Add FAQ';
    }

    // Clear FAQ ID
    const faqIdInput = document.getElementById('faq-id');
    if (faqIdInput) {
        faqIdInput.value = '';
    }

    // Populate category dropdown
    populateCategoryDropdown();

    // Hide new category field initially
    const newCategoryGroup = document.getElementById('new-category-group');
    if (newCategoryGroup) {
        newCategoryGroup.style.display = 'none';
    }

    // Show modal
    const faqModal = document.getElementById('faq-modal');
    if (faqModal) {
        faqModal.style.display = 'flex';
    }

    // Set default category selection
    const categorySelect = document.getElementById('faq-category');
    if (categorySelect) {
        // Select the first actual category if available, otherwise leave as "Select Category"
        if (categorySelect.options.length > 2) {
            // If we have actual categories (beyond Select Category and Add New Category)
            if (faqCategories.length > 0) {
                // Try to select General if it exists
                let generalIndex = -1;
                for (let i = 0; i < categorySelect.options.length; i++) {
                    if (categorySelect.options[i].value.toLowerCase() === 'general') {
                        generalIndex = i;
                        break;
                    }
                }

                if (generalIndex !== -1) {
                    // Select General category
                    categorySelect.selectedIndex = generalIndex;
                } else {
                    // Select the first actual category
                    categorySelect.selectedIndex = 2;
                }
            } else {
                // No categories, select "Select Category"
                categorySelect.selectedIndex = 0;
            }
        } else {
            // No actual categories, select "Select Category"
            categorySelect.selectedIndex = 0;
        }

        console.log('Selected category index:', categorySelect.selectedIndex);
        console.log('Selected category value:', categorySelect.value);

        // Make sure the change event listener is attached
        // First remove any existing listeners to avoid duplicates
        categorySelect.removeEventListener('change', handleCategoryChange);
        // Then add the event listener
        categorySelect.addEventListener('change', handleCategoryChange);
    }

    // Show modal
    const editFaqModal = document.getElementById('faq-modal');
    if (editFaqModal) {
        editFaqModal.style.display = 'flex';
    }
}

/**
 * Fetch FAQ categories from the server
 * @returns {Promise} Promise that resolves with the categories
 */
function fetchFaqCategories() {
    return new Promise((resolve, reject) => {
        // Use default categories if fetch fails
        const defaultCategories = ['General', 'Products', 'Shipping', 'Payment', 'Returns'];

        fetch('/api/admin/all_faqs?page=1&per_page=100')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.faqs && data.faqs.length > 0) {
                    // Update categories from the server data
                    updateFaqCategories(data.faqs);
                    console.log('Fetched FAQ categories from server:', faqCategories);
                    resolve(faqCategories);
                } else {
                    console.warn('No FAQs found on server, using default categories');
                    faqCategories = defaultCategories;
                    resolve(defaultCategories);
                }
            })
            .catch(error => {
                console.error('Error fetching FAQ categories:', error);
                console.warn('Using default categories due to fetch error');
                faqCategories = defaultCategories;
                resolve(defaultCategories);
            });
    });
}

/**
 * Populate the category dropdown with available categories
 */
function populateCategoryDropdown() {
    const categorySelect = document.getElementById('faq-category');
    if (!categorySelect) return;

    // Log the current categories for debugging
    console.log('Available FAQ categories:', faqCategories);

    // If we don't have any categories, fetch them from the server
    if (!faqCategories || faqCategories.length === 0) {
        fetchFaqCategories()
            .then(() => {
                // After fetching, populate the dropdown
                populateCategoryDropdownWithData(categorySelect);
            })
            .catch(error => {
                console.error('Error fetching categories:', error);
                // Use default categories as fallback
                faqCategories = ['General', 'Products', 'Shipping', 'Payment', 'Returns'];
                populateCategoryDropdownWithData(categorySelect);
            });
    } else {
        // We already have categories, populate the dropdown
        populateCategoryDropdownWithData(categorySelect);
    }
}

/**
 * Populate the category dropdown with the available data
 * @param {HTMLElement} categorySelect - The category select element
 */
function populateCategoryDropdownWithData(categorySelect) {
    console.log('Populating category dropdown with data');

    // Clear all existing options
    categorySelect.innerHTML = '';

    // Add the default "Select Category" option
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Select Category';
    categorySelect.appendChild(defaultOption);

    // Add the "Add New Category" option
    const newCategoryOption = document.createElement('option');
    newCategoryOption.value = 'new';
    newCategoryOption.textContent = '+ Add New Category';
    categorySelect.appendChild(newCategoryOption);

    // Add existing categories
    if (faqCategories && faqCategories.length > 0) {
        faqCategories.forEach(category => {
            if (category && category.trim() !== '') {
                const option = document.createElement('option');
                option.value = category;
                option.textContent = category;
                categorySelect.appendChild(option);
            }
        });
    } else {
        console.warn('No FAQ categories available to populate dropdown');
    }

    // Add change event listener to show/hide new category field
    categorySelect.addEventListener('change', function() {
        const newCategoryGroup = document.getElementById('new-category-group');
        if (this.value === 'new') {
            if (newCategoryGroup) {
                newCategoryGroup.style.display = 'block';
                const newCategoryInput = document.getElementById('new-faq-category');
                if (newCategoryInput) {
                    newCategoryInput.focus();
                }
            }
        } else {
            if (newCategoryGroup) {
                newCategoryGroup.style.display = 'none';
            }
        }
    });
}

/**
 * Function to show/hide new category field
 * @param {string} value - The value of the category dropdown
 */
window.showHideNewCategoryField = function(value) {
    console.log('showHideNewCategoryField called with value:', value);
    const newCategoryGroup = document.getElementById('new-category-group');
    const newCategoryInput = document.getElementById('new-faq-category');

    if (value === 'new') {
        console.log('Showing new category field');
        if (newCategoryGroup) {
            // Force display with !important to override any conflicting styles
            newCategoryGroup.setAttribute('style', 'display: block !important; visibility: visible !important; background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #4361ee; margin-top: 10px;');

            // Also ensure the input field is visible
            if (newCategoryInput) {
                newCategoryInput.style.display = 'block';
                newCategoryInput.style.visibility = 'visible';
                setTimeout(() => {
                    newCategoryInput.focus();
                }, 100);
            }

            // Log the current state for debugging
            console.log('New category group display:', window.getComputedStyle(newCategoryGroup).display);
            console.log('New category group visibility:', window.getComputedStyle(newCategoryGroup).visibility);
        } else {
            console.error('New category group element not found');
        }
    } else {
        console.log('Hiding new category field');
        if (newCategoryGroup) {
            newCategoryGroup.style.display = 'none';
        }
    }
}

/**
 * Handle category dropdown change
 */
function handleCategoryChange(event) {
    console.log('handleCategoryChange called');
    const categorySelect = document.getElementById('faq-category');
    if (categorySelect) {
        showHideNewCategoryField(categorySelect.value);
    }
}

/**
 * Edit FAQ
 * @param {number} faqId - The ID of the FAQ to edit
 */
window.editFaq = function(faqId) {
    // Fetch FAQ details
    fetch(`/api/admin/faq_details?faq_id=${faqId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const faq = data.faq;

                // Set form values
                document.getElementById('faq-id').value = faq.faq_id;
                document.getElementById('faq-question').value = faq.question;
                document.getElementById('faq-answer').value = faq.answer;

                // Populate category dropdown
                populateCategoryDropdown();

                // Wait a moment for the dropdown to be populated
                setTimeout(() => {

                // Set category value or add it if it doesn't exist
                const categorySelect = document.getElementById('faq-category');
                const faqCategory = faq.category;

                console.log('Editing FAQ with category:', faqCategory);
                console.log('Available options:', Array.from(categorySelect.options).map(o => o.value));

                // Check if the category exists in the dropdown
                let categoryExists = false;
                for (let i = 0; i < categorySelect.options.length; i++) {
                    if (categorySelect.options[i].value === faqCategory) {
                        categoryExists = true;
                        categorySelect.selectedIndex = i;
                        console.log('Found category at index:', i);
                        break;
                    }
                }

                // If category doesn't exist, add it
                if (!categoryExists && faqCategory) {
                    console.log('Category not found in dropdown, adding it:', faqCategory);
                    const option = document.createElement('option');
                    option.value = faqCategory;
                    option.textContent = faqCategory;
                    categorySelect.appendChild(option);

                    // Select the newly added option
                    categorySelect.value = faqCategory;
                    console.log('After adding, selected value:', categorySelect.value);

                    // Add to categories array if not already there
                    if (!faqCategories.includes(faqCategory)) {
                        faqCategories.push(faqCategory);
                        faqCategories.sort();
                        console.log('Updated faqCategories array:', faqCategories);
                    }
                }

                // Hide new category field
                const newCategoryGroup = document.getElementById('new-category-group');
                if (newCategoryGroup) {
                    newCategoryGroup.style.display = 'none';
                }

                // Make sure the change event listener is attached
                // First remove any existing listeners to avoid duplicates
                categorySelect.removeEventListener('change', handleCategoryChange);
                // Then add the event listener
                categorySelect.addEventListener('change', handleCategoryChange);

                // Set status radio button
                if (faq.is_active) {
                    document.getElementById('faq-active').checked = true;
                } else {
                    document.getElementById('faq-inactive').checked = true;
                }

                // Set modal title
                document.getElementById('faq-modal-title').textContent = 'Edit FAQ';

                // Show modal
                document.getElementById('faq-modal').style.display = 'flex';
                }, 100); // End of setTimeout
            } else {
                console.error('Error loading FAQ details:', data.message);
                showNotification('Error loading FAQ details. Please try again.', 'error');
            }
        })
        .catch(error => {
            console.error('Error loading FAQ details:', error);
            showNotification('Error loading FAQ details. Please try again.', 'error');
        });
}

/**
 * Delete FAQ
 * @param {number} faqId - The ID of the FAQ to delete
 */
window.deleteFaq = function(faqId) {
    if (confirm('Are you sure you want to delete this FAQ?')) {
        fetch('/api/admin/delete_faq', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                faq_id: faqId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Check if a category was removed
                if (data.category_removed && data.empty_category) {
                    // Remove the empty category from the categories array
                    const emptyCategory = data.empty_category;
                    const index = faqCategories.indexOf(emptyCategory);
                    if (index !== -1) {
                        faqCategories.splice(index, 1);
                        console.log(`Removed empty category: ${emptyCategory}`);

                        // Update the category filter dropdown
                        const categoryFilter = document.getElementById('category-filter');
                        if (categoryFilter) {
                            for (let i = 0; i < categoryFilter.options.length; i++) {
                                if (categoryFilter.options[i].value === emptyCategory) {
                                    categoryFilter.remove(i);
                                    break;
                                }
                            }
                        }

                        showNotification(`FAQ deleted. Empty category "${emptyCategory}" removed.`, 'success');
                    }
                } else {
                    showNotification('FAQ deleted successfully', 'success');
                }

                // Reload FAQs
                loadFaqs(currentFaqPage);
            } else {
                console.error('Error deleting FAQ:', data.message);
                showNotification(`Error deleting FAQ: ${data.message}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error deleting FAQ:', error);
            showNotification('Error deleting FAQ. Please try again.', 'error');
        });
    }
}

/**
 * Handle FAQ form submission
 * @param {Event} event - The form submit event
 */
/**
 * Load pending FAQs that need manager approval
 */
window.loadPendingFaqs = function() {
    // Show loading indicator
    const faqsTab = document.getElementById('faqs');
    faqsTab.innerHTML = '<div class="loading">Loading pending FAQs...</div>';

    // Fetch pending FAQs from API
    fetch('/api/admin/pending_faqs?status=pending')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Create pending FAQs table
                let html = `
                    <div class="card-header">
                        <h2>Pending FAQs</h2>
                        <button class="btn" id="back-to-faqs-btn">Back to FAQs</button>
                    </div>
                    <div class="pending-faqs-info">
                        <p>These FAQs have been submitted by agents and are waiting for your approval.</p>
                    </div>
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Question</th>
                                    <th>Answer</th>
                                    <th>Category</th>
                                    <th>Submitted By</th>
                                    <th>Date</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="pending-faqs-table">
                `;

                // Add pending FAQs to table
                if (data.pending_faqs && data.pending_faqs.length > 0) {
                    data.pending_faqs.forEach(faq => {
                        const submittedDate = new Date(faq.submitted_at);
                        const formattedDate = submittedDate.toLocaleDateString() + ' ' +
                                             submittedDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

                        html += `
                            <tr>
                                <td>${faq.pending_faq_id}</td>
                                <td>${faq.question}</td>
                                <td>${faq.answer}</td>
                                <td>${faq.category}</td>
                                <td>${faq.submitted_by_username}</td>
                                <td>${formattedDate}</td>
                                <td class="action-buttons">
                                    <button class="action-btn approve-btn" onclick="approvePendingFaq(${faq.pending_faq_id})">Approve</button>
                                    <button class="action-btn reject-btn" onclick="rejectPendingFaq(${faq.pending_faq_id})">Reject</button>
                                </td>
                            </tr>
                        `;

                        // Display agent notes if available
                        if (faq.agent_notes) {
                            html += `
                            <tr class="agent-notes-row">
                                <td colspan="7">
                                    <div class="pending-faqs-info agent-notes">
                                        <strong>Agent Notes:</strong> ${faq.agent_notes}
                                    </div>
                                </td>
                            </tr>
                            `;
                        }
                    });
                } else {
                    html += `
                        <tr>
                            <td colspan="7" class="no-results">No pending FAQs found.</td>
                        </tr>
                    `;
                }

                html += `
                            </tbody>
                        </table>
                    </div>
                `;

                // Update FAQs tab content
                faqsTab.innerHTML = html;

                // Add event listener to back button
                const backToFaqsBtn = document.getElementById('back-to-faqs-btn');
                if (backToFaqsBtn) {
                    backToFaqsBtn.addEventListener('click', () => {
                        loadFaqs(1);
                    });
                }
            } else {
                faqsTab.innerHTML = `<div class="error">Error loading pending FAQs: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading pending FAQs:', error);
            faqsTab.innerHTML = '<div class="error">Error loading pending FAQs. Please try again.</div>';
        });
}

/**
 * Approve a pending FAQ
 * @param {number} pendingFaqId - The ID of the pending FAQ to approve
 */
window.approvePendingFaq = function(pendingFaqId) {
    // Show confirmation dialog
    if (!confirm('Are you sure you want to approve this FAQ?')) {
        return;
    }

    // Optional: Prompt for notes
    const notes = prompt('Add any notes (optional):');

    // Send approval request
    fetch(`/api/admin/approve_pending_faq/${pendingFaqId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ notes: notes || '' })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('FAQ approved successfully', 'success');
            // Reload pending FAQs
            loadPendingFaqs();
        } else {
            showNotification(`Error: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        console.error('Error approving FAQ:', error);
        showNotification('Failed to approve FAQ. Please try again.', 'error');
    });
}

/**
 * Reject a pending FAQ
 * @param {number} pendingFaqId - The ID of the pending FAQ to reject
 */
window.rejectPendingFaq = function(pendingFaqId) {
    // Show confirmation dialog
    if (!confirm('Are you sure you want to reject this FAQ?')) {
        return;
    }

    // Prompt for rejection reason
    const notes = prompt('Please provide a reason for rejection:');
    if (!notes) {
        showNotification('Please provide a reason for rejection', 'error');
        return;
    }

    // Send rejection request
    fetch(`/api/admin/reject_pending_faq/${pendingFaqId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ notes: notes })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('FAQ rejected successfully', 'success');
            // Reload pending FAQs
            loadPendingFaqs();
        } else {
            showNotification(`Error: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        console.error('Error rejecting FAQ:', error);
        showNotification('Failed to reject FAQ. Please try again.', 'error');
    });
}

function handleFaqFormSubmit(event) {
    event.preventDefault();

    // Get form values
    const faqId = document.getElementById('faq-id').value;
    const question = document.getElementById('faq-question').value;
    const answer = document.getElementById('faq-answer').value;

    console.log('Form values:', { faqId, question, answer });
    console.log('Category dropdown:', document.getElementById('faq-category'));

    // Get category - check if it's a new category
    let category;
    const categorySelect = document.getElementById('faq-category');
    console.log('Category select value:', categorySelect.value);

    if (categorySelect.value === 'new') {
        // Get the new category name
        const newCategoryInput = document.getElementById('new-faq-category');
        category = newCategoryInput ? newCategoryInput.value.trim() : '';
        console.log('New category name:', category);

        // Validate the new category name
        if (!category) {
            showNotification('Please enter a category name', 'error');

            // Make sure the new category field is visible
            const newCategoryGroup = document.getElementById('new-category-group');
            if (newCategoryGroup) {
                newCategoryGroup.style.display = 'block';
            }

            // Focus on the input field
            if (newCategoryInput) {
                newCategoryInput.focus();
            }

            return;
        }
    } else {
        category = categorySelect.value;

        // Validate that a category is selected
        if (!category) {
            showNotification('Please select a category', 'error');
            categorySelect.focus();
            return;
        }
    }

    console.log('Selected category:', category);

    // Normalize the category
    category = normalizeCategory(category);

    // Default language is English
    const language = 'en';
    const isActive = document.querySelector('input[name="faq-status"]:checked').value === '1';

    // Create FAQ object
    const faq = {
        question,
        answer,
        category,
        language,
        is_active: isActive
    };

    // Add FAQ ID if editing
    if (faqId) {
        faq.faq_id = parseInt(faqId);
    }

    // Send request to API
    const url = faqId ? '/api/admin/update_faq' : '/api/admin/add_faq';

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(faq)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Hide modal
            document.getElementById('faq-modal').style.display = 'none';

            // Add the new category to our list if it's not already there
            if (category && category.trim() !== '' && !faqCategories.includes(category.trim())) {
                faqCategories.push(category.trim());
                faqCategories.sort();
                console.log('Added new category to FAQ categories:', category.trim());

                // Update category filter dropdown
                const categoryFilter = document.getElementById('category-filter');
                if (categoryFilter) {
                    const option = document.createElement('option');
                    option.value = category.trim();
                    option.textContent = category.trim();
                    categoryFilter.appendChild(option);
                }
            }

            // Reload FAQs
            loadFaqs(currentFaqPage);

            // Show success message
            showNotification(faqId ? 'FAQ updated successfully.' : 'FAQ added successfully.', 'success');
        } else {
            console.error('Error saving FAQ:', data.message);
            showNotification(`Error saving FAQ: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        console.error('Error saving FAQ:', error);
        showNotification('Error saving FAQ. Please try again.', 'error');
    });
}

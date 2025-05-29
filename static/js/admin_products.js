/**
 * Rock Chatbot - Admin Products Management
 *
 * This script handles the products management functionality in the admin dashboard.
 * It provides CRUD operations for products.
 */

// Global variables
let currentProductPage = 1;
const productsPerPage = 10;
let totalProductPages = 1;
let categories = [];
let healthGoals = [];

/**
 * Load products with pagination
 * @param {number} page - The page number to load
 */
window.loadProducts = function(page = 1) {
    currentProductPage = page;

    // Show loading indicator
    const productsTab = document.getElementById('products');
    productsTab.innerHTML = '<div class="loading">Loading products and categories...</div>';

    // First load categories and health goals, then load products
    Promise.all([loadCategories(), loadHealthGoals()]).then(() => {
        // Fetch products from API
        fetch(`/api/admin/all_products?page=${page}&per_page=${productsPerPage}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update pagination info
                    totalProductPages = data.pagination.total_pages;

                    // Create products table with search and filter
                    let html = `
                        <div class="card-header">
                            <h2>Products</h2>
                            <div class="button-group">
                                <button class="btn btn-primary" id="add-product-btn">Add New Product</button>
                                <button class="btn btn-secondary" id="cleanup-categories-btn">Clean Up Empty Categories</button>
                            <button class="btn btn-info" id="setup-benefits-btn" style="background-color: #17a2b8;">Setup Health Benefits</button>
                            </div>
                        </div>
                        <div class="search-filter-container">
                            <div class="search-box">
                                <input type="text" id="product-search" placeholder="Search products..." class="search-input">
                                <button id="product-search-btn" class="search-btn"><i class="fas fa-search"></i></button>
                            </div>
                            <div class="filter-container">
                                <select id="category-filter" class="filter-select">
                                    <option value="">All Categories</option>
                                    <!-- Add categories -->
                                    <optgroup label="Product Categories">
                                        ${categories.map(cat => `<option value="${cat.category_id}">${cat.name}</option>`).join('')}
                                    </optgroup>
                                    <!-- Add health goals -->
                                    <optgroup label="Health Goals">
                                        ${healthGoals.map(goal => `<option value="goal_${goal.id}">${goal.name}</option>`).join('')}
                                    </optgroup>
                                </select>
                                <select id="price-filter" class="filter-select">
                                    <option value="">All Prices</option>
                                    <option value="0-50">RM0 - RM50</option>
                                    <option value="50-100">RM50 - RM100</option>
                                    <option value="100-200">RM100 - RM200</option>
                                    <option value="200+">RM200+</option>
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
                                        <th>Image</th>
                                        <th>Name</th>
                                        <th>Category</th>
                                        <th>Price</th>
                                        <th>Stock</th>
                                        <th>Status</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="products-table">
                    `;

                    // Add products to table
                    data.products.forEach(product => {
                        const categoryName = getCategoryName(product.category_id);
                        // Determine image source with fallback to chatbot logo
                        let imageSrc = '/static/images/5w2fl3vb.svg';
                        if (product.image_url && product.image_url.trim() !== '') {
                            // Check if the image URL is a full URL or just a filename
                            if (product.image_url.startsWith('http') || product.image_url.startsWith('/')) {
                                imageSrc = product.image_url;
                            } else {
                                // Assume it's a filename and prepend the static/images path
                                imageSrc = `/static/images/products/${product.image_url}`;
                            }
                        }

                        html += `
                            <tr>
                                <td>${product.product_id}</td>
                                <td><img src="${imageSrc}" alt="${product.name}" class="product-thumbnail" onerror="this.src='/static/images/5w2fl3vb.svg'; console.log('Image not found, using logo as placeholder');"></td>
                                <td>${product.name}</td>
                                <td>${categoryName}</td>
                                <td>RM${parseFloat(product.price).toFixed(2)}</td>
                                <td>${product.stock_quantity}</td>
                                <td>${product.is_active ? 'Active' : 'Inactive'}</td>
                                <td class="action-buttons">
                                    <button class="action-btn edit-btn" onclick="editProduct(${product.product_id})">Edit</button>
                                    <button class="action-btn delete-btn" onclick="deleteProduct(${product.product_id})">Delete</button>
                                </td>
                            </tr>
                        `;
                    });

                    html += `
                                </tbody>
                            </table>
                        </div>
                    `;

                    // Add pagination
                    if (totalProductPages > 1) {
                        html += `
                            <div class="pagination">
                                <button ${page === 1 ? 'disabled' : ''} onclick="loadProducts(1)">First</button>
                                <button ${page === 1 ? 'disabled' : ''} onclick="loadProducts(${page - 1})">Previous</button>
                        `;

                        // Show page numbers
                        const startPage = Math.max(1, page - 2);
                        const endPage = Math.min(totalProductPages, page + 2);

                        for (let i = startPage; i <= endPage; i++) {
                            html += `
                                <button class="${i === page ? 'active' : ''}" onclick="loadProducts(${i})">${i}</button>
                            `;
                        }

                        html += `
                                <button ${page === totalProductPages ? 'disabled' : ''} onclick="loadProducts(${page + 1})">Next</button>
                                <button ${page === totalProductPages ? 'disabled' : ''} onclick="loadProducts(${totalProductPages})">Last</button>
                            </div>
                        `;
                    }

                    // Preserve the health benefits section if it exists
                    const existingHealthBenefitsSection = document.getElementById('health-benefits-section');

                    // Update products tab content
                    productsTab.innerHTML = html;

                    // Re-append the health benefits section if it existed
                    if (existingHealthBenefitsSection) {
                        console.log('Preserving health benefits section after product reload');
                        productsTab.appendChild(existingHealthBenefitsSection);
                    }

                    // Add event listener to add product button
                    const addProductBtn = document.getElementById('add-product-btn');
                    if (addProductBtn) {
                        addProductBtn.addEventListener('click', showAddProductModal);
                    }

                    // Add event listener to cleanup categories button
                    const cleanupCategoriesBtn = document.getElementById('cleanup-categories-btn');
                    if (cleanupCategoriesBtn) {
                        cleanupCategoriesBtn.addEventListener('click', cleanupEmptyCategories);
                    }

                    // Add event listener to setup benefits button
                    const setupBenefitsBtn = document.getElementById('setup-benefits-btn');
                    if (setupBenefitsBtn) {
                        setupBenefitsBtn.addEventListener('click', function() {
                            console.log('Setup Benefits button clicked');
                            if (typeof window.setupHealthBenefitsManagement === 'function') {
                                window.setupHealthBenefitsManagement();
                            } else {
                                alert('Health Benefits Management function not available. Please refresh the page.');
                            }
                        });
                    }

                    // Health benefits management is now handled by the "Setup Health Benefits" button

                    // Add event listeners for search and filter
                    const searchBtn = document.getElementById('product-search-btn');
                    const searchInput = document.getElementById('product-search');
                    const applyFiltersBtn = document.getElementById('apply-filters-btn');
                    const clearFiltersBtn = document.getElementById('clear-filters-btn');

                    if (searchBtn && searchInput) {
                        // Search on button click
                        searchBtn.onclick = function() {
                            window.applyProductFilters();
                        };

                        // Search on Enter key
                        searchInput.onkeypress = function(e) {
                            if (e.key === 'Enter') {
                                window.applyProductFilters();
                            }
                        };
                    }

                    if (applyFiltersBtn) {
                        applyFiltersBtn.onclick = function() {
                            window.applyProductFilters();
                        };
                    }

                    if (clearFiltersBtn) {
                        clearFiltersBtn.onclick = function() {
                            window.clearProductFilters();
                        };
                    }

                    // Debug log to verify event listeners are attached
                    console.log('Event listeners attached to filter buttons');

                    // Health benefits management is now handled by the "Setup Health Benefits" button
                } else {
                    productsTab.innerHTML = `<div class="error">Error loading products: ${data.message}</div>`;
                }
            })
            .catch(error => {
                console.error('Error loading products:', error);
                productsTab.innerHTML = '<div class="error">Error loading products. Please try again.</div>';
            });
    }).catch(error => {
        console.error('Error loading categories:', error);
        productsTab.innerHTML = '<div class="error">Error loading categories. Please try again.</div>';
    });
}

/**
 * Apply product filters and search
 */
window.applyProductFilters = function() {
    console.log('applyProductFilters function called');

    // Get filter values
    const searchTerm = document.getElementById('product-search').value.trim();
    const filterValue = document.getElementById('category-filter').value;
    const priceRange = document.getElementById('price-filter').value;
    const status = document.getElementById('status-filter').value;

    // Build query parameters
    let queryParams = new URLSearchParams();

    // Add search term if provided
    if (searchTerm) {
        queryParams.append('search', searchTerm);
    }

    // Check if we're filtering by goal or category
    if (filterValue) {
        if (filterValue.startsWith('goal_')) {
            // We're filtering by health goal
            const goalId = filterValue.replace('goal_', '');
            queryParams.append('goal_id', goalId);
            console.log(`Filtering by health goal: ${goalId}`);
        } else {
            // We're filtering by category
            queryParams.append('category_id', filterValue);
            console.log(`Filtering by category: ${filterValue}`);
        }
    }

    // Add price range filter if selected
    if (priceRange) {
        if (priceRange === '0-50') {
            queryParams.append('min_price', 0);
            queryParams.append('max_price', 50);
        } else if (priceRange === '50-100') {
            queryParams.append('min_price', 50);
            queryParams.append('max_price', 100);
        } else if (priceRange === '100-200') {
            queryParams.append('min_price', 100);
            queryParams.append('max_price', 200);
        } else if (priceRange === '200+') {
            queryParams.append('min_price', 200);
        }
    }

    // Add status filter if selected
    if (status) {
        queryParams.append('status', status);
    }

    // Reset to first page
    currentProductPage = 1;
    queryParams.append('page', currentProductPage);
    queryParams.append('per_page', productsPerPage);

    // Show loading indicator
    const productsTab = document.getElementById('products');
    productsTab.innerHTML = '<div class="loading">Searching products...</div>';

    // Fetch filtered products
    fetch(`/api/admin/all_products?${queryParams.toString()}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update pagination info
                totalProductPages = data.pagination.total_pages;

                // Reload products with the same filters
                loadProductsWithFilters(currentProductPage, searchTerm, filterValue, priceRange, status);
            } else {
                productsTab.innerHTML = `<div class="error">Error searching products: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error searching products:', error);
            productsTab.innerHTML = '<div class="error">Error searching products. Please try again.</div>';
        });
}

/**
 * Clear product filters and reload all products
 */
window.clearProductFilters = function() {
    console.log('clearProductFilters function called');

    // Reset filter inputs
    document.getElementById('product-search').value = '';
    document.getElementById('category-filter').value = '';
    document.getElementById('price-filter').value = '';
    document.getElementById('status-filter').value = '';

    // Reset to first page and reload
    currentProductPage = 1;
    loadProducts(currentProductPage);
}

/**
 * Load products with filters
 * @param {number} page - The page number to load
 * @param {string} searchTerm - Search term
 * @param {string} filterValue - Category ID or goal_id filter
 * @param {string} priceRange - Price range filter
 * @param {string} status - Status filter
 */
function loadProductsWithFilters(page = 1, searchTerm = '', filterValue = '', priceRange = '', status = '') {
    // Build query parameters
    let queryParams = new URLSearchParams();
    queryParams.append('page', page);
    queryParams.append('per_page', productsPerPage);

    // Add search term if provided
    if (searchTerm) {
        queryParams.append('search', searchTerm);
    }

    // Check if we're filtering by goal or category
    if (filterValue) {
        if (filterValue.startsWith('goal_')) {
            // We're filtering by health goal
            const goalId = filterValue.replace('goal_', '');
            queryParams.append('goal_id', goalId);
            console.log(`loadProductsWithFilters - Filtering by health goal: ${goalId}`);
        } else {
            // We're filtering by category
            queryParams.append('category_id', filterValue);
            console.log(`loadProductsWithFilters - Filtering by category: ${filterValue}`);
        }
    }

    // Add price range filter if selected
    if (priceRange) {
        if (priceRange === '0-50') {
            queryParams.append('min_price', 0);
            queryParams.append('max_price', 50);
        } else if (priceRange === '50-100') {
            queryParams.append('min_price', 50);
            queryParams.append('max_price', 100);
        } else if (priceRange === '100-200') {
            queryParams.append('min_price', 100);
            queryParams.append('max_price', 200);
        } else if (priceRange === '200+') {
            queryParams.append('min_price', 200);
        }
    }

    // Add status filter if selected
    if (status) {
        queryParams.append('status', status);
    }

    // Show loading indicator
    const productsTab = document.getElementById('products');
    productsTab.innerHTML = '<div class="loading">Loading products...</div>';

    // Fetch filtered products
    const url = `/api/admin/all_products?${queryParams.toString()}`;
    console.log(`Fetching products with URL: ${url}`);

    fetch(url)
        .then(response => response.json())
        .then(data => {
            console.log(`Received ${data.products ? data.products.length : 0} products from API`);
            if (data.success) {
                // Update pagination info
                totalProductPages = data.pagination.total_pages;

                // Create products table with search and filter
                let html = `
                    <div class="card-header">
                        <h2>Products</h2>
                        <div class="button-group">
                            <button class="btn btn-primary" id="add-product-btn">Add New Product</button>
                            <button class="btn btn-secondary" id="cleanup-categories-btn">Clean Up Empty Categories</button>
                            <button class="btn btn-info" id="setup-benefits-btn" style="background-color: #17a2b8;">Setup Health Benefits</button>
                        </div>
                    </div>
                    <div class="search-filter-container">
                        <div class="search-box">
                            <input type="text" id="product-search" placeholder="Search products..." class="search-input" value="${searchTerm}">
                            <button id="product-search-btn" class="search-btn"><i class="fas fa-search"></i></button>
                        </div>
                        <div class="filter-container">
                            <select id="category-filter" class="filter-select">
                                <option value="">All Categories</option>
                                <!-- Add categories -->
                                <optgroup label="Product Categories">
                                    ${categories.map(cat => `<option value="${cat.category_id}" ${filterValue == cat.category_id ? 'selected' : ''}>${cat.name}</option>`).join('')}
                                </optgroup>
                                <!-- Add health goals -->
                                <optgroup label="Health Goals">
                                    ${healthGoals.map(goal => `<option value="goal_${goal.id}" ${filterValue == 'goal_' + goal.id ? 'selected' : ''}>${goal.name}</option>`).join('')}
                                </optgroup>
                            </select>
                            <select id="price-filter" class="filter-select">
                                <option value="">All Prices</option>
                                <option value="0-50" ${priceRange === '0-50' ? 'selected' : ''}>RM0 - RM50</option>
                                <option value="50-100" ${priceRange === '50-100' ? 'selected' : ''}>RM50 - RM100</option>
                                <option value="100-200" ${priceRange === '100-200' ? 'selected' : ''}>RM100 - RM200</option>
                                <option value="200+" ${priceRange === '200+' ? 'selected' : ''}>RM200+</option>
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
                                    <th>Image</th>
                                    <th>Name</th>
                                    <th>Category</th>
                                    <th>Price</th>
                                    <th>Stock</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="products-table">
                `;

                // Add products to table
                if (data.products.length === 0) {
                    html += `
                        <tr>
                            <td colspan="8" class="no-results">No products found matching your criteria.</td>
                        </tr>
                    `;
                } else {
                    data.products.forEach(product => {
                        const categoryName = getCategoryName(product.category_id);
                        // Determine image source with fallback to chatbot logo
                        let imageSrc = '/static/images/5w2fl3vb.svg';
                        if (product.image_url && product.image_url.trim() !== '') {
                            // Check if the image URL is a full URL or just a filename
                            if (product.image_url.startsWith('http') || product.image_url.startsWith('/')) {
                                imageSrc = product.image_url;
                            } else {
                                // Assume it's a filename and prepend the static/images path
                                imageSrc = `/static/images/products/${product.image_url}`;
                            }
                        }

                        html += `
                            <tr>
                                <td>${product.product_id}</td>
                                <td><img src="${imageSrc}" alt="${product.name}" class="product-thumbnail" onerror="this.src='/static/images/5w2fl3vb.svg'; console.log('Image not found, using logo as placeholder');"></td>
                                <td>${product.name}</td>
                                <td>${categoryName}</td>
                                <td>RM${parseFloat(product.price).toFixed(2)}</td>
                                <td>${product.stock_quantity}</td>
                                <td>${product.is_active ? 'Active' : 'Inactive'}</td>
                                <td class="action-buttons">
                                    <button class="action-btn edit-btn" onclick="editProduct(${product.product_id})">Edit</button>
                                    <button class="action-btn delete-btn" onclick="deleteProduct(${product.product_id})">Delete</button>
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
                if (totalProductPages > 1) {
                    html += `
                        <div class="pagination">
                            <button ${page === 1 ? 'disabled' : ''} onclick="loadProductsWithFilters(1, '${searchTerm}', '${filterValue}', '${priceRange}', '${status}')">First</button>
                            <button ${page === 1 ? 'disabled' : ''} onclick="loadProductsWithFilters(${page - 1}, '${searchTerm}', '${filterValue}', '${priceRange}', '${status}')">Previous</button>
                    `;

                    // Show page numbers
                    const startPage = Math.max(1, page - 2);
                    const endPage = Math.min(totalProductPages, page + 2);

                    for (let i = startPage; i <= endPage; i++) {
                        html += `
                            <button class="${i === page ? 'active' : ''}" onclick="loadProductsWithFilters(${i}, '${searchTerm}', '${filterValue}', '${priceRange}', '${status}')">${i}</button>
                        `;
                    }

                    html += `
                            <button ${page === totalProductPages ? 'disabled' : ''} onclick="loadProductsWithFilters(${page + 1}, '${searchTerm}', '${filterValue}', '${priceRange}', '${status}')">Next</button>
                            <button ${page === totalProductPages ? 'disabled' : ''} onclick="loadProductsWithFilters(${totalProductPages}, '${searchTerm}', '${filterValue}', '${priceRange}', '${status}')">Last</button>
                        </div>
                    `;
                }

                // Preserve the health benefits section if it exists
                const existingHealthBenefitsSection = document.getElementById('health-benefits-section');

                // Update products tab content
                productsTab.innerHTML = html;

                // Re-append the health benefits section if it existed
                if (existingHealthBenefitsSection) {
                    console.log('Preserving health benefits section after product filter');
                    productsTab.appendChild(existingHealthBenefitsSection);
                }

                // Update the category filter with categories and health goals
                updateCategoryFilter();

                // Set the selected value in the category filter
                const categoryFilter = document.getElementById('category-filter');
                if (categoryFilter && filterValue) {
                    categoryFilter.value = filterValue;
                }

                // Add event listeners
                const addProductBtn = document.getElementById('add-product-btn');
                if (addProductBtn) {
                    addProductBtn.addEventListener('click', showAddProductModal);
                }

                // Add event listener to cleanup categories button
                const cleanupCategoriesBtn = document.getElementById('cleanup-categories-btn');
                if (cleanupCategoriesBtn) {
                    cleanupCategoriesBtn.addEventListener('click', cleanupEmptyCategories);
                }

                // Add event listener to setup benefits button
                const setupBenefitsBtn = document.getElementById('setup-benefits-btn');
                if (setupBenefitsBtn) {
                    setupBenefitsBtn.addEventListener('click', function() {
                        console.log('Setup Benefits button clicked');
                        if (typeof window.setupHealthBenefitsManagement === 'function') {
                            window.setupHealthBenefitsManagement();
                        } else {
                            alert('Health Benefits Management function not available. Please refresh the page.');
                        }
                    });
                }

                // Add event listeners for search and filter
                const searchBtn = document.getElementById('product-search-btn');
                const searchInputField = document.getElementById('product-search');
                const applyFiltersBtn = document.getElementById('apply-filters-btn');
                const clearFiltersBtn = document.getElementById('clear-filters-btn');

                if (searchBtn && searchInputField) {
                    // Search on button click
                    searchBtn.onclick = function() {
                        window.applyProductFilters();
                    };

                    // Search on Enter key
                    searchInputField.onkeypress = function(e) {
                        if (e.key === 'Enter') {
                            window.applyProductFilters();
                        }
                    };
                }

                if (applyFiltersBtn) {
                    applyFiltersBtn.onclick = function() {
                        window.applyProductFilters();
                    };
                }

                if (clearFiltersBtn) {
                    clearFiltersBtn.onclick = function() {
                        window.clearProductFilters();
                    };
                }

                // Debug log to verify event listeners are attached
                console.log('Event listeners attached to filter buttons in loadProductsWithFilters');
            } else {
                productsTab.innerHTML = `<div class="error">Error loading products: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading products:', error);
            productsTab.innerHTML = '<div class="error">Error loading products. Please try again.</div>';
        });
}

/**
 * Load product categories
 * @returns {Promise} A promise that resolves when categories are loaded
 */
function loadCategories() {
    return new Promise((resolve, reject) => {
        fetch('/api/admin/all_categories?only_with_products=true&only_active=true')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Normalize category names in the loaded categories
                    categories = data.categories.map(cat => {
                        // Create a new object to avoid modifying the original
                        return {
                            ...cat,
                            name: normalizeCategory(cat.name)
                        };
                    });

                    // Update category select in product form
                    const categorySelect = document.getElementById('product-category');
                    if (categorySelect) {
                        categorySelect.innerHTML = '';

                        // Add existing categories
                        categories.forEach(category => {
                            const option = document.createElement('option');
                            option.value = category.category_id;
                            option.textContent = category.name;
                            categorySelect.appendChild(option);
                        });

                        // Add "Other/New Category" option
                        const newOption = document.createElement('option');
                        newOption.value = 'new';
                        newOption.textContent = '+ Add New Category';
                        categorySelect.appendChild(newOption);

                        // Add event listener to show/hide new category input
                        categorySelect.addEventListener('change', function() {
                            const newCategoryGroup = document.getElementById('new-category-group');
                            if (this.value === 'new') {
                                newCategoryGroup.style.display = 'block';
                                document.getElementById('new-category-name').focus();
                                document.getElementById('new-category-name').required = true;
                            } else {
                                newCategoryGroup.style.display = 'none';
                                document.getElementById('new-category-name').required = false;
                            }
                        });
                    }

                    // Also update the category filter if it exists
                    updateCategoryFilter();

                    resolve(); // Resolve the promise when categories are loaded
                } else {
                    console.error('Error loading categories:', data.message);
                    reject(new Error(data.message || 'Failed to load categories'));
                }
            })
            .catch(error => {
                console.error('Error loading categories:', error);
                reject(error);
            });
    });
}

/**
 * Load health goals
 * @returns {Promise} A promise that resolves when health goals are loaded
 */
function loadHealthGoals() {
    return new Promise((resolve, reject) => {
        fetch('/api/health_goals')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Store health goals
                    healthGoals = data.goals;
                    console.log('Health goals loaded:', healthGoals);

                    // Log the health goals to make sure they're being loaded correctly
                    if (healthGoals.length > 0) {
                        console.log(`Loaded ${healthGoals.length} health goals:`);
                        healthGoals.forEach(goal => {
                            console.log(`- ${goal.name} (ID: ${goal.id})`);
                        });
                    } else {
                        console.warn('No health goals were loaded from the API');
                    }

                    // Update the category filter with health goals
                    updateCategoryFilter();

                    resolve(); // Resolve the promise when health goals are loaded
                } else {
                    console.error('Error loading health goals:', data.message);
                    reject(new Error(data.message || 'Failed to load health goals'));
                }
            })
            .catch(error => {
                console.error('Error loading health goals:', error);
                reject(error);
            });
    });
}

/**
 * Update the category filter with both categories and health goals
 */
function updateCategoryFilter() {
    const categoryFilter = document.getElementById('category-filter');
    if (categoryFilter) {
        // Save the currently selected value
        const selectedValue = categoryFilter.value;

        // Clear and rebuild the options
        categoryFilter.innerHTML = '<option value="">All Categories</option>';

        // Add categories
        if (categories.length > 0) {
            const categoriesGroup = document.createElement('optgroup');
            categoriesGroup.label = 'Product Categories';
            categoriesGroup.style.fontWeight = 'bold';
            categoriesGroup.style.backgroundColor = '#f5f5f5';
            categoriesGroup.style.padding = '5px';

            categories.forEach(category => {
                const option = document.createElement('option');
                option.value = category.category_id;
                option.textContent = category.name;
                option.dataset.type = 'category';
                option.style.fontWeight = 'normal';
                option.style.paddingLeft = '15px';
                option.style.backgroundColor = 'white';

                // Restore the selected value if it matches
                if (selectedValue == category.category_id) {
                    option.selected = true;
                }

                categoriesGroup.appendChild(option);
            });

            categoryFilter.appendChild(categoriesGroup);
        }

        // Add health goals
        if (healthGoals.length > 0) {
            const goalsGroup = document.createElement('optgroup');
            goalsGroup.label = 'Health Goals';
            goalsGroup.style.fontWeight = 'bold';
            goalsGroup.style.backgroundColor = '#f5f5f5';
            goalsGroup.style.padding = '5px';

            healthGoals.forEach(goal => {
                const option = document.createElement('option');
                option.value = 'goal_' + goal.id;
                option.textContent = goal.name;
                option.dataset.type = 'goal';
                option.dataset.goalId = goal.id;
                option.style.fontWeight = 'normal';
                option.style.paddingLeft = '15px';
                option.style.backgroundColor = 'white';

                // Restore the selected value if it matches
                if (selectedValue == 'goal_' + goal.id) {
                    option.selected = true;
                }

                goalsGroup.appendChild(option);
            });

            categoryFilter.appendChild(goalsGroup);
        }

        console.log('Category filter updated with categories and health goals');
    }
}

/**
 * Get category name by ID
 * @param {number} categoryId - The category ID
 * @returns {string} The category name
 */
function getCategoryName(categoryId) {
    const category = categories.find(c => c.category_id === categoryId);
    return category ? category.name : 'Unknown';
}

/**
 * Clean up empty categories
 * This function calls the API to delete all categories that have no products
 */
function cleanupEmptyCategories() {
    if (!confirm('This will delete all categories that have no products. Continue?')) {
        return;
    }

    // Show loading indicator
    const cleanupBtn = document.getElementById('cleanup-categories-btn');
    const originalText = cleanupBtn.textContent;
    cleanupBtn.textContent = 'Cleaning up...';
    cleanupBtn.disabled = true;

    // Call the API to clean up empty categories
    fetch('/api/admin/cleanup_categories', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            // You can specify categories to protect from deletion
            protected_categories: [1, 2, 3, 4]  // Main parent categories
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(`Success: ${data.message}`);
            // Reload categories and products
            loadCategories().then(() => {
                loadProducts(currentProductPage);
            });
        } else {
            alert(`Error: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('Error cleaning up categories:', error);
        alert('Error cleaning up categories. Please try again.');
    })
    .finally(() => {
        // Reset button
        cleanupBtn.textContent = originalText;
        cleanupBtn.disabled = false;
    });
}

/**
 * Normalize category name to ensure consistency
 * @param {string} category - The category name to normalize
 * @returns {string} The normalized category name
 */
function normalizeCategory(category) {
    if (!category) return '';

    // Trim whitespace and convert to lowercase for comparison
    let normalized = category.trim();

    // Handle common variations
    const categoryMap = {
        'product': 'Products',
        'products': 'Products',
        'supplement': 'Supplements',
        'supplements': 'Supplements',
        'protein': 'Protein',
        'vitamin': 'Vitamins',
        'vitamins': 'Vitamins',
        'mineral': 'Minerals',
        'minerals': 'Minerals'
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
 * Show add product modal
 */
function showAddProductModal() {
    console.log('Showing add product modal');

    // First load health benefits
    if (typeof loadHealthBenefits === 'function') {
        loadHealthBenefits().then(() => {
            console.log('Health benefits loaded for add product modal');

            // Then make sure categories are loaded
            loadCategories().then(() => {
                console.log('Categories loaded for add product modal');

                // Reset form
                const productForm = document.getElementById('product-form');
                if (productForm) {
                    productForm.reset();
                }

                // Set modal title
                const modalTitle = document.getElementById('product-modal-title');
                if (modalTitle) {
                    modalTitle.textContent = 'Add Product';
                }

                // Clear product ID
                const productIdInput = document.getElementById('product-id');
                if (productIdInput) {
                    productIdInput.value = '';
                }

                // Show modal with high z-index to appear above health benefits modal
                const modal = document.getElementById('product-modal');
                if (modal) {
                    modal.style.display = 'flex';
                    modal.style.zIndex = '1300'; // Higher than health benefits modal (1100)
                }
            }).catch(error => {
                console.error('Error loading categories:', error);
                alert('Error loading categories. Please try again.');
            });
        }).catch(error => {
            console.error('Error loading health benefits:', error);

            // Continue with categories even if health benefits fail
            loadCategories().then(() => {
                // Reset form
                const productForm = document.getElementById('product-form');
                if (productForm) {
                    productForm.reset();
                }

                // Set modal title
                const modalTitle = document.getElementById('product-modal-title');
                if (modalTitle) {
                    modalTitle.textContent = 'Add Product';
                }

                // Clear product ID
                const productIdInput = document.getElementById('product-id');
                if (productIdInput) {
                    productIdInput.value = '';
                }

                // Show modal
                const modal = document.getElementById('product-modal');
                if (modal) {
                    modal.style.display = 'flex';
                }
            }).catch(error => {
                console.error('Error loading categories:', error);
                alert('Error loading categories. Please try again.');
            });
        });
    } else {
        console.error('loadHealthBenefits function not found');

        // Fallback to just loading categories
        loadCategories().then(() => {
            // Reset form
            const productForm = document.getElementById('product-form');
            if (productForm) {
                productForm.reset();
            }

            // Set modal title
            const modalTitle = document.getElementById('product-modal-title');
            if (modalTitle) {
                modalTitle.textContent = 'Add Product';
            }

            // Clear product ID
            const productIdInput = document.getElementById('product-id');
            if (productIdInput) {
                productIdInput.value = '';
            }

            // Show modal
            const modal = document.getElementById('product-modal');
            if (modal) {
                modal.style.display = 'flex';
            }
        }).catch(error => {
            console.error('Error loading categories:', error);
            alert('Error loading categories. Please try again.');
        });
    }
}

/**
 * Edit product
 * @param {number} productId - The ID of the product to edit
 */
function editProduct(productId) {
    console.log('Editing product with ID:', productId);

    // First, load health benefits
    if (typeof loadHealthBenefits === 'function') {
        loadHealthBenefits().then(() => {
            console.log('Health benefits loaded, now loading categories...');

            // Then make sure categories are loaded
            loadCategories().then(() => {
                console.log('Categories loaded, now fetching product details...');

                // Fetch product details
                fetch(`/api/admin/product_details?product_id=${productId}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            const product = data.product;
                            console.log('Product details loaded:', product);

                            // Set form values
                            document.getElementById('product-id').value = product.product_id;
                            document.getElementById('product-name').value = product.name;
                            document.getElementById('product-description').value = product.description || '';
                            document.getElementById('product-category').value = product.category_id;
                            document.getElementById('product-price').value = product.price;
                            document.getElementById('product-stock').value = product.stock_quantity;
                            document.getElementById('product-image').value = product.image_url || '';
                            document.getElementById('product-brand').value = product.brand || '';
                            document.getElementById('product-ingredients').value = product.ingredients || '';
                            document.getElementById('product-usage-instructions').value = product.usage_instructions || '';

                            // Set status radio button
                            if (product.is_active) {
                                document.getElementById('product-active').checked = true;
                            } else {
                                document.getElementById('product-inactive').checked = true;
                            }

                            // Load the product's health benefits
                            fetch(`/api/admin/product_benefits?product_id=${productId}`)
                                .then(response => response.json())
                                .then(benefitData => {
                                    console.log('Product benefits data:', benefitData);
                                    if (benefitData.success) {
                                        const benefitSelect = document.getElementById('product-health-benefits');
                                        if (benefitSelect) {
                                            const selectedBenefits = benefitData.benefits.map(b => b.benefit_id);

                                            // Select the benefits in the multi-select
                                            Array.from(benefitSelect.options).forEach(option => {
                                                option.selected = selectedBenefits.includes(parseInt(option.value));
                                            });
                                        } else {
                                            console.error('Health benefits select element not found');
                                        }
                                    }
                                })
                                .catch(error => {
                                    console.error('Error loading product benefits:', error);
                                });

                            // Set modal title
                            document.getElementById('product-modal-title').textContent = 'Edit Product';

                            // Show modal with high z-index to appear above health benefits modal
                            const productModal = document.getElementById('product-modal');
                            productModal.style.display = 'flex';
                            productModal.style.zIndex = '1300'; // Higher than health benefits modal (1100)
                        } else {
                            console.error('Error loading product details:', data.message);
                            alert('Error loading product details. Please try again.');
                        }
                    })
                    .catch(error => {
                        console.error('Error loading product details:', error);
                        alert('Error loading product details. Please try again.');
                    });
            }).catch(error => {
                console.error('Error loading categories:', error);
                alert('Error loading categories. Please try again.');
            });
        }).catch(error => {
            console.error('Error loading health benefits:', error);

            // Continue with categories even if health benefits fail
            loadCategories().then(() => {
                // Fetch product details (without health benefits)
                fetch(`/api/admin/product_details?product_id=${productId}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            const product = data.product;

                            // Set form values
                            document.getElementById('product-id').value = product.product_id;
                            document.getElementById('product-name').value = product.name;
                            document.getElementById('product-description').value = product.description || '';
                            document.getElementById('product-category').value = product.category_id;
                            document.getElementById('product-price').value = product.price;
                            document.getElementById('product-stock').value = product.stock_quantity;
                            document.getElementById('product-image').value = product.image_url || '';
                            document.getElementById('product-brand').value = product.brand || '';
                            document.getElementById('product-ingredients').value = product.ingredients || '';
                            document.getElementById('product-usage-instructions').value = product.usage_instructions || '';

                            // Set status radio button
                            if (product.is_active) {
                                document.getElementById('product-active').checked = true;
                            } else {
                                document.getElementById('product-inactive').checked = true;
                            }

                            // Set modal title
                            document.getElementById('product-modal-title').textContent = 'Edit Product';

                            // Show modal with high z-index to appear above health benefits modal
                            const productModal = document.getElementById('product-modal');
                            productModal.style.display = 'flex';
                            productModal.style.zIndex = '1300'; // Higher than health benefits modal (1100)
                        } else {
                            console.error('Error loading product details:', data.message);
                            alert('Error loading product details. Please try again.');
                        }
                    });
            });
        });
    } else {
        console.error('loadHealthBenefits function not found');

        // Fallback to just loading categories
        loadCategories().then(() => {
            // Fetch product details
            fetch(`/api/admin/product_details?product_id=${productId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const product = data.product;

                        // Set form values
                        document.getElementById('product-id').value = product.product_id;
                        document.getElementById('product-name').value = product.name;
                        document.getElementById('product-description').value = product.description || '';
                        document.getElementById('product-category').value = product.category_id;
                        document.getElementById('product-price').value = product.price;
                        document.getElementById('product-stock').value = product.stock_quantity;
                        document.getElementById('product-image').value = product.image_url || '';
                        document.getElementById('product-brand').value = product.brand || '';
                        document.getElementById('product-ingredients').value = product.ingredients || '';
                        document.getElementById('product-usage-instructions').value = product.usage_instructions || '';

                        // Set status radio button
                        if (product.is_active) {
                            document.getElementById('product-active').checked = true;
                        } else {
                            document.getElementById('product-inactive').checked = true;
                        }

                        // Set modal title
                        document.getElementById('product-modal-title').textContent = 'Edit Product';

                        // Show modal
                        document.getElementById('product-modal').style.display = 'flex';
                    } else {
                        console.error('Error loading product details:', data.message);
                        alert('Error loading product details. Please try again.');
                    }
                });
        });
    }
}

/**
 * Delete product
 * @param {number} productId - The ID of the product to delete
 */
function deleteProduct(productId) {
    if (confirm('Are you sure you want to delete this product?')) {
        fetch('/api/admin/delete_product', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                product_id: productId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Product deleted successfully.');
                loadProducts(currentProductPage);
            } else {
                console.error('Error deleting product:', data.message);
                alert(`Error deleting product: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('Error deleting product:', error);
            alert('Error deleting product. Please try again.');
        });
    }
}

/**
 * Handle product form submission
 * @param {Event} event - The form submit event
 */
function handleProductFormSubmit(event) {
    event.preventDefault();

    // Get form values
    const productId = document.getElementById('product-id').value;
    const name = document.getElementById('product-name').value;
    const description = document.getElementById('product-description').value;
    const categoryId = document.getElementById('product-category').value;
    const price = document.getElementById('product-price').value;
    const stockQuantity = document.getElementById('product-stock').value;
    const imageUrl = document.getElementById('product-image').value;
    const brand = document.getElementById('product-brand').value;
    const ingredients = document.getElementById('product-ingredients').value;
    const usageInstructions = document.getElementById('product-usage-instructions').value;
    const isActive = document.querySelector('input[name="product-status"]:checked').value === '1';

    // Get selected health benefits
    const benefits = getSelectedBenefits();

    // Check if a new category is being added
    let isNewCategory = false;
    let newCategoryName = '';

    if (categoryId === 'new') {
        isNewCategory = true;
        newCategoryName = document.getElementById('new-category-name').value.trim();

        // Validate new category name
        if (!newCategoryName) {
            alert('Please enter a name for the new category.');
            document.getElementById('new-category-name').focus();
            return;
        }

        // Normalize the category name
        newCategoryName = normalizeCategory(newCategoryName);
    }

    // If it's a new category, create it first
    if (isNewCategory) {
        // Show loading message
        const submitBtn = document.querySelector('#product-form button[type="submit"]');
        const originalBtnText = submitBtn.textContent;
        submitBtn.textContent = 'Creating category...';
        submitBtn.disabled = true;

        // Create the new category
        console.log('Creating new category:', newCategoryName);

        // Use XMLHttpRequest instead of fetch for better compatibility
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/admin/add_category', true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                console.log('XHR Status:', xhr.status);
                console.log('XHR Response:', xhr.responseText);

                if (xhr.status === 200) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        console.log('Parsed data:', data);

                        if (data.success) {
                            // Category created successfully, now create the product
                            submitBtn.textContent = 'Saving product...';

                            // Create product object with the new category ID
                            const product = {
                                name,
                                description,
                                category_id: data.category_id, // Use the new category ID
                                price: parseFloat(price),
                                stock_quantity: parseInt(stockQuantity),
                                image_url: imageUrl,
                                brand: brand,
                                ingredients: ingredients,
                                usage_instructions: usageInstructions,
                                benefits: benefits, // Use selected benefits
                                is_active: isActive
                            };

                            // Continue with product creation/update
                            saveProduct(product, productId, submitBtn, originalBtnText);
                        } else {
                            console.error('Error creating category:', data.message);

                            // Show error message using showMessage if available, otherwise fallback to alert
                            if (typeof showMessage === 'function') {
                                showMessage('error', `Error creating category: ${data.message}`);
                            } else {
                                alert(`Error creating category: ${data.message}`);
                            }

                            submitBtn.textContent = originalBtnText;
                            submitBtn.disabled = false;
                        }
                    } catch (e) {
                        console.error('Error parsing response:', e);

                        // Show error message using showMessage if available, otherwise fallback to alert
                        if (typeof showMessage === 'function') {
                            showMessage('error', 'Error creating category. Invalid response from server.');
                        } else {
                            alert('Error creating category. Invalid response from server.');
                        }

                        submitBtn.textContent = originalBtnText;
                        submitBtn.disabled = false;
                    }
                } else {
                    console.error('Error creating category. Status:', xhr.status);

                    // Show error message using showMessage if available, otherwise fallback to alert
                    if (typeof showMessage === 'function') {
                        showMessage('error', `Error creating category. Server returned status ${xhr.status}`);
                    } else {
                        alert(`Error creating category. Server returned status ${xhr.status}`);
                    }

                    submitBtn.textContent = originalBtnText;
                    submitBtn.disabled = false;
                }
            }
        };

        xhr.send(JSON.stringify({
            name: newCategoryName
        }));
    } else {
        // Create product object with existing category
        const product = {
            name,
            description,
            category_id: parseInt(categoryId),
            price: parseFloat(price),
            stock_quantity: parseInt(stockQuantity),
            image_url: imageUrl,
            brand: brand,
            ingredients: ingredients,
            usage_instructions: usageInstructions,
            benefits: benefits, // Use selected benefits
            is_active: isActive
        };

        // Save the product directly
        saveProduct(product, productId);
    }
}

/**
 * Save product to the database
 * @param {Object} product - The product object to save
 * @param {string|number} productId - The product ID if editing, empty if adding new
 * @param {HTMLElement} submitBtn - The submit button element (optional)
 * @param {string} originalBtnText - The original button text (optional)
 */
function saveProduct(product, productId, submitBtn, originalBtnText) {
    // Add product ID if editing
    if (productId) {
        product.product_id = parseInt(productId);
    }

    // Send request to API
    const url = productId ? '/api/admin/update_product' : '/api/admin/add_product';

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(product)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Hide modal
            document.getElementById('product-modal').style.display = 'none';

            // Reload categories first to ensure any new category is included
            loadCategories().then(() => {
                // Then reload products
                loadProducts(currentProductPage);
            });

            // Show success message using showMessage if available, otherwise fallback to alert
            if (typeof showMessage === 'function') {
                showMessage('success', productId ? 'Product updated successfully.' : 'Product added successfully.');
            } else {
                alert(productId ? 'Product updated successfully.' : 'Product added successfully.');
            }
        } else {
            console.error('Error saving product:', data.message);

            // Show error message using showMessage if available, otherwise fallback to alert
            if (typeof showMessage === 'function') {
                showMessage('error', `Error saving product: ${data.message}`);
            } else {
                alert(`Error saving product: ${data.message}`);
            }

            // Reset button if provided
            if (submitBtn && originalBtnText) {
                submitBtn.textContent = originalBtnText;
                submitBtn.disabled = false;
            }
        }
    })
    .catch(error => {
        console.error('Error saving product:', error);

        // Show error message using showMessage if available, otherwise fallback to alert
        if (typeof showMessage === 'function') {
            showMessage('error', 'Error saving product. Please try again.');
        } else {
            alert('Error saving product. Please try again.');
        }

        // Reset button if provided
        if (submitBtn && originalBtnText) {
            submitBtn.textContent = originalBtnText;
            submitBtn.disabled = false;
        }
    });
}

// Make functions globally accessible
window.editProduct = editProduct;
window.deleteProduct = deleteProduct;

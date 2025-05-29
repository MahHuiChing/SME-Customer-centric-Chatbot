/**
 * JavaScript for handling health benefits in the admin product form
 */

/**
 * Show a notification message
 * @param {string} type - The type of notification (success, error, info, warning)
 * @param {string} message - The message to display
 * @param {number} duration - How long to show the notification in milliseconds
 */
function showMessage(type, message, duration = 5000) {
    // Use showNotification from admin.js
    if (typeof showNotification === 'function') {
        showNotification(message, type, duration);
    } else {
        // Fallback to alert if showNotification doesn't exist
        console.log(`${type.toUpperCase()}: ${message}`);
        alert(message);
    }
}

/**
 * Load health benefits for the multi-select dropdown
 * @returns {Promise} A promise that resolves when benefits are loaded
 */
function loadHealthBenefits() {
    console.log('Loading health benefits...');
    return fetch('/api/admin/health_benefits')
        .then(response => {
            console.log('Health benefits response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Health benefits data:', data);
            if (data.success) {
                const benefitSelect = document.getElementById('product-health-benefits');
                if (!benefitSelect) {
                    console.error('Could not find product-health-benefits element');
                    return;
                }

                benefitSelect.innerHTML = ''; // Clear existing options

                // Group benefits by category
                const benefitsByCategory = {};
                data.benefits.forEach(benefit => {
                    if (!benefitsByCategory[benefit.category]) {
                        benefitsByCategory[benefit.category] = [];
                    }
                    benefitsByCategory[benefit.category].push(benefit);
                });

                console.log('Benefits by category:', benefitsByCategory);

                // Add options grouped by category
                for (const category in benefitsByCategory) {
                    const optgroup = document.createElement('optgroup');
                    optgroup.label = formatCategoryName(category);

                    benefitsByCategory[category].forEach(benefit => {
                        const option = document.createElement('option');
                        option.value = benefit.benefit_id;
                        option.textContent = benefit.name;
                        optgroup.appendChild(option);
                    });

                    benefitSelect.appendChild(optgroup);
                }

                console.log('Health benefits loaded successfully');

                // Also update the health benefits management table if it exists
                updateHealthBenefitsModalTable(data.benefits);
            } else {
                console.error('Failed to load health benefits:', data.message);
                showMessage('error', 'Failed to load health benefits: ' + (data.message || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error loading health benefits:', error);
            showMessage('error', 'Error loading health benefits: ' + error.message);
        });
}

/**
 * Load health benefits data into the modal table
 */
function loadHealthBenefitsIntoModal() {
    console.log('Loading health benefits into modal...');
    return fetch('/api/admin/health_benefits')
        .then(response => {
            console.log('Health benefits response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Health benefits data:', data);
            if (data.success) {
                updateHealthBenefitsModalTable(data.benefits);
            } else {
                console.error('Failed to load health benefits:', data.message);
                showMessage('error', 'Failed to load health benefits: ' + (data.message || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error loading health benefits:', error);
            showMessage('error', 'Error loading health benefits: ' + error.message);
        });
}

/**
 * Update the health benefits management table in modal
 * @param {Array} benefits - Array of health benefit objects
 */
function updateHealthBenefitsModalTable(benefits) {
    console.log('Updating health benefits modal table with', benefits.length, 'benefits');

    const benefitsTable = document.getElementById('health-benefits-table-modal');
    if (!benefitsTable) {
        console.error('Health benefits modal table not found, skipping update');
        return;
    }

    const tableBody = benefitsTable.querySelector('tbody');
    if (!tableBody) {
        console.error('Table body not found in health benefits modal table');
        return;
    }

    // Clear existing rows
    tableBody.innerHTML = '';

    if (benefits.length === 0) {
        // Show a message if there are no benefits
        const emptyRow = document.createElement('tr');
        const emptyCell = document.createElement('td');
        emptyCell.colSpan = 5;
        emptyCell.textContent = 'No health benefits found. Click "Add New Benefit" to create one.';
        emptyCell.style.textAlign = 'center';
        emptyCell.style.padding = '20px';
        emptyRow.appendChild(emptyCell);
        tableBody.appendChild(emptyRow);
        return;
    }

    // Group benefits by category
    const benefitsByCategory = {};
    benefits.forEach(benefit => {
        if (!benefitsByCategory[benefit.category]) {
            benefitsByCategory[benefit.category] = [];
        }
        benefitsByCategory[benefit.category].push(benefit);
    });

    // Add rows for each benefit, grouped by category
    for (const category in benefitsByCategory) {
        // Add a category header row
        const categoryRow = document.createElement('tr');
        categoryRow.className = 'category-header';

        const categoryCell = document.createElement('td');
        categoryCell.colSpan = 5;
        categoryCell.textContent = formatCategoryName(category);
        categoryCell.style.fontWeight = 'bold';
        categoryCell.style.backgroundColor = '#f0f0f0';

        categoryRow.appendChild(categoryCell);
        tableBody.appendChild(categoryRow);

        // Add rows for each benefit in this category
        benefitsByCategory[category].forEach(benefit => {
            const row = document.createElement('tr');
            row.dataset.benefitId = benefit.benefit_id;
            row.style.borderBottom = '1px solid #ddd';

            // Name cell
            const nameCell = document.createElement('td');
            nameCell.textContent = benefit.name;
            nameCell.style.padding = '10px';
            nameCell.style.fontWeight = 'bold';
            row.appendChild(nameCell);

            // Description cell
            const descCell = document.createElement('td');
            descCell.textContent = benefit.description || 'No description';
            descCell.style.padding = '10px';
            row.appendChild(descCell);

            // Category cell
            const categoryCell = document.createElement('td');
            categoryCell.textContent = formatCategoryName(benefit.category);
            categoryCell.style.padding = '10px';
            row.appendChild(categoryCell);

            // Status cell
            const statusCell = document.createElement('td');
            statusCell.textContent = benefit.is_active ? 'Active' : 'Inactive';
            statusCell.style.color = benefit.is_active ? 'green' : 'red';
            statusCell.style.padding = '10px';
            statusCell.style.fontWeight = 'bold';
            row.appendChild(statusCell);

            // Actions cell
            const actionsCell = document.createElement('td');
            actionsCell.style.whiteSpace = 'nowrap';
            actionsCell.style.padding = '10px';

            // View Products button
            const viewBtn = document.createElement('button');
            viewBtn.className = 'view-btn action-btn';
            viewBtn.textContent = 'View Products';
            viewBtn.style.marginRight = '10px';
            viewBtn.style.backgroundColor = '#4361ee';
            viewBtn.style.color = 'white';
            viewBtn.style.border = 'none';
            viewBtn.style.padding = '6px 12px';
            viewBtn.style.borderRadius = '4px';
            viewBtn.style.cursor = 'pointer';
            viewBtn.onclick = function(e) {
                e.preventDefault();
                e.stopPropagation();
                viewBenefitProducts(benefit.benefit_id, benefit.name);
            };

            // Delete button
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-btn action-btn';
            deleteBtn.textContent = 'Delete';
            deleteBtn.style.backgroundColor = '#e63946';
            deleteBtn.style.color = 'white';
            deleteBtn.style.border = 'none';
            deleteBtn.style.padding = '6px 12px';
            deleteBtn.style.borderRadius = '4px';
            deleteBtn.style.cursor = 'pointer';
            deleteBtn.onclick = function(e) {
                e.preventDefault();
                e.stopPropagation();
                deleteBenefit(benefit.benefit_id, benefit.name);
            };

            actionsCell.appendChild(viewBtn);
            actionsCell.appendChild(deleteBtn);
            row.appendChild(actionsCell);

            tableBody.appendChild(row);
        });
    }

    console.log('Health benefits table updated successfully');
}

/**
 * Format category name for display (e.g., "muscle_building" -> "Muscle Building")
 * @param {string} category - The category name to format
 * @returns {string} The formatted category name
 */
function formatCategoryName(category) {
    return category
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

/**
 * Get selected health benefits from the multi-select dropdown
 * @returns {Array} Array of selected benefit IDs
 */
function getSelectedBenefits() {
    const benefitSelect = document.getElementById('product-health-benefits');
    const selectedBenefits = [];

    Array.from(benefitSelect.options).forEach(option => {
        if (option.selected) {
            selectedBenefits.push(parseInt(option.value));
        }
    });

    return selectedBenefits;
}

/**
 * Set up the "Add New Benefit" modal
 * This function is no longer needed as the button is now handled in setupHealthBenefitsManagement
 */
function setupBenefitModal() {
    // This function is kept for backward compatibility
    // The actual setup is now done in createBenefitModal and setupHealthBenefitsManagement
    console.log('setupBenefitModal is deprecated, using createBenefitModal instead');

    // Create the benefit modal if it doesn't exist
    createBenefitModal();
}

/**
 * View products associated with a health benefit
 * @param {number} benefitId - The ID of the benefit
 * @param {string} benefitName - The name of the benefit
 */
function viewBenefitProducts(benefitId, benefitName) {
    console.log(`Viewing products for benefit ID: ${benefitId}`);

    // Show loading message
    showMessage('info', `Loading products for "${benefitName}"...`);

    fetch(`/api/admin/benefit_products?benefit_id=${benefitId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Create and show a modal with the products
                const productsModal = document.createElement('div');
                productsModal.className = 'modal';
                productsModal.id = 'benefit-products-modal';
                productsModal.style.cssText = `
                    display: flex;
                    position: fixed;
                    z-index: 1200;
                    left: 0;
                    top: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0,0,0,0.6);
                    justify-content: center;
                    align-items: center;
                    backdrop-filter: blur(3px);
                `;

                const modalContent = document.createElement('div');
                modalContent.className = 'modal-content';
                modalContent.style.cssText = `
                    background: white;
                    border-radius: 8px;
                    padding: 0;
                    max-width: 90%;
                    width: 800px;
                    max-height: 90vh;
                    overflow-y: auto;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
                    position: relative;
                `;

                // Modal header
                const modalHeader = document.createElement('div');
                modalHeader.className = 'modal-header';
                modalHeader.style.cssText = `
                    background: #f8f9fa;
                    border-bottom: 1px solid #dee2e6;
                    padding: 20px;
                    border-radius: 8px 8px 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                `;

                const modalTitle = document.createElement('h2');
                modalTitle.textContent = `Products with "${benefitName}" Health Benefit`;
                modalTitle.style.cssText = `
                    margin: 0;
                    color: #333;
                    font-size: 1.5rem;
                    font-weight: 600;
                `;
                modalHeader.appendChild(modalTitle);

                const closeBtn = document.createElement('button');
                closeBtn.className = 'close-modal';
                closeBtn.innerHTML = '&times;';
                closeBtn.style.cssText = `
                    background: none;
                    border: none;
                    font-size: 24px;
                    color: #6c757d;
                    cursor: pointer;
                    padding: 0;
                    width: 30px;
                    height: 30px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 4px;
                    transition: background-color 0.2s;
                `;
                closeBtn.onmouseover = function() { this.style.backgroundColor = '#e9ecef'; };
                closeBtn.onmouseout = function() { this.style.backgroundColor = 'transparent'; };
                closeBtn.onclick = function() {
                    document.body.removeChild(productsModal);
                };
                modalHeader.appendChild(closeBtn);

                modalContent.appendChild(modalHeader);

                // Modal body
                const modalBody = document.createElement('div');
                modalBody.className = 'modal-body';
                modalBody.style.cssText = `
                    padding: 24px;
                `;

                if (data.products.length === 0) {
                    const noProducts = document.createElement('p');
                    noProducts.textContent = 'No products are using this health benefit.';
                    modalBody.appendChild(noProducts);
                } else {
                    const productCount = document.createElement('p');
                    productCount.textContent = `${data.products.length} product(s) are using this health benefit:`;
                    modalBody.appendChild(productCount);

                    const productTable = document.createElement('table');
                    productTable.className = 'data-table';
                    productTable.style.width = '100%';

                    // Table header
                    const thead = document.createElement('thead');
                    const headerRow = document.createElement('tr');

                    const headers = ['ID', 'Name', 'Category', 'Price', 'Status', 'Actions'];
                    headers.forEach(headerText => {
                        const th = document.createElement('th');
                        th.textContent = headerText;
                        headerRow.appendChild(th);
                    });

                    thead.appendChild(headerRow);
                    productTable.appendChild(thead);

                    // Table body
                    const tbody = document.createElement('tbody');

                    data.products.forEach(product => {
                        const row = document.createElement('tr');

                        // ID cell
                        const idCell = document.createElement('td');
                        idCell.textContent = product.product_id;
                        row.appendChild(idCell);

                        // Name cell
                        const nameCell = document.createElement('td');
                        nameCell.textContent = product.name;
                        row.appendChild(nameCell);

                        // Category cell
                        const categoryCell = document.createElement('td');
                        categoryCell.textContent = product.category;
                        row.appendChild(categoryCell);

                        // Price cell
                        const priceCell = document.createElement('td');
                        priceCell.textContent = `RM ${parseFloat(product.price).toFixed(2)}`;
                        row.appendChild(priceCell);

                        // Status cell
                        const statusCell = document.createElement('td');
                        statusCell.textContent = product.is_active ? 'Active' : 'Inactive';
                        statusCell.style.color = product.is_active ? 'green' : 'red';
                        row.appendChild(statusCell);

                        // Actions cell
                        const actionsCell = document.createElement('td');

                        // View button
                        const viewBtn = document.createElement('button');
                        viewBtn.className = 'view-btn action-btn';
                        viewBtn.textContent = 'View';
                        viewBtn.style.backgroundColor = '#4361ee';
                        viewBtn.style.color = 'white';
                        viewBtn.style.border = 'none';
                        viewBtn.style.padding = '6px 12px';
                        viewBtn.style.borderRadius = '4px';
                        viewBtn.style.cursor = 'pointer';
                        viewBtn.onclick = function() {
                            console.log('View button clicked for product ID:', product.product_id);

                            // Close the current modal
                            document.body.removeChild(productsModal);

                            // Add a small delay to ensure modal is closed before opening new one
                            setTimeout(() => {
                                console.log('Checking for editProduct function...');
                                console.log('window.editProduct:', typeof window.editProduct);
                                console.log('editProduct:', typeof editProduct);

                                // Try to find the edit product function
                                if (typeof window.editProduct === 'function') {
                                    console.log('Calling window.editProduct for product ID:', product.product_id);
                                    window.editProduct(product.product_id);
                                } else if (typeof editProduct === 'function') {
                                    console.log('Calling editProduct for product ID:', product.product_id);
                                    editProduct(product.product_id);
                                } else {
                                    console.log('editProduct function not found, trying alternative method');
                                    // Otherwise, try to navigate to the product directly
                                    showMessage('info', 'Navigating to product details...');

                                    // Find the edit button for this product in the main products table
                                    const productRows = document.querySelectorAll('#products-table tr');
                                    let editButton = null;

                                    console.log('Searching for product in table, total rows:', productRows.length);
                                    for (const row of productRows) {
                                        const idCell = row.querySelector('td:first-child');
                                        if (idCell) {
                                            console.log('Checking row with ID:', idCell.textContent.trim());
                                            if (idCell.textContent.trim() === product.product_id.toString()) {
                                                editButton = row.querySelector('.edit-btn');
                                                console.log('Found matching row, edit button:', editButton);
                                                break;
                                            }
                                        }
                                    }

                                    if (editButton) {
                                        console.log('Clicking edit button');
                                        editButton.click();
                                    } else {
                                        console.log('Edit button not found in products table');
                                        showMessage('error', 'Could not find product in the table. Please try editing it directly from the products list.');
                                    }
                                }
                            }, 100);
                        };

                        actionsCell.appendChild(viewBtn);
                        row.appendChild(actionsCell);

                        tbody.appendChild(row);
                    });

                    productTable.appendChild(tbody);
                    modalBody.appendChild(productTable);
                }

                modalContent.appendChild(modalBody);

                // Modal footer with actions
                const modalFooter = document.createElement('div');
                modalFooter.className = 'modal-footer';
                modalFooter.style.marginTop = '20px';
                modalFooter.style.display = 'flex';
                modalFooter.style.justifyContent = 'space-between';

                // Close button
                const closeButton = document.createElement('button');
                closeButton.className = 'btn-secondary';
                closeButton.textContent = 'Close';
                closeButton.onclick = function() {
                    document.body.removeChild(productsModal);
                };

                // Force delete button (only show if there are products)
                const forceDeleteButton = document.createElement('button');
                forceDeleteButton.className = 'delete-btn action-btn';
                forceDeleteButton.textContent = 'Force Delete Benefit';
                forceDeleteButton.onclick = function() {
                    if (confirm(`WARNING: Are you sure you want to force delete the health benefit "${benefitName}"? This will remove the benefit from all ${data.products.length} products. This action cannot be undone.`)) {
                        forceDeleteBenefit(benefitId, benefitName);
                        document.body.removeChild(productsModal);
                    }
                };

                modalFooter.appendChild(closeButton);
                if (data.products.length > 0) {
                    modalFooter.appendChild(forceDeleteButton);
                }

                modalContent.appendChild(modalFooter);

                // Add the modal to the page
                productsModal.appendChild(modalContent);
                document.body.appendChild(productsModal);

                // Close modal when clicking outside
                productsModal.addEventListener('click', function(event) {
                    if (event.target === productsModal) {
                        document.body.removeChild(productsModal);
                    }
                });
            } else {
                showMessage('error', data.message || 'Failed to load products for this health benefit');
            }
        })
        .catch(error => {
            console.error('Error loading benefit products:', error);
            showMessage('error', 'An error occurred while loading products');
        });
}

/**
 * Delete a health benefit
 * @param {number} benefitId - The ID of the benefit to delete
 * @param {string} benefitName - The name of the benefit to delete
 */
function deleteBenefit(benefitId, benefitName) {
    if (!confirm(`Are you sure you want to delete the health benefit "${benefitName}"? This action cannot be undone.`)) {
        return;
    }

    console.log(`Deleting health benefit with ID: ${benefitId}`);

    fetch('/api/admin/delete_health_benefit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            benefit_id: benefitId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show success message
            if (data.deactivated) {
                const productCount = data.product_count || 'multiple';
                const message = `Health benefit "${benefitName}" has been deactivated because it is used by ${productCount} products.`;
                showMessage('info', message);

                // Ask if user wants to view the products
                if (confirm(`${message}\n\nDo you want to view these products?`)) {
                    viewBenefitProducts(benefitId, benefitName);
                }
            } else {
                showMessage('success', `Health benefit "${benefitName}" has been deleted successfully.`);
            }

            // Reload health benefits
            loadHealthBenefits();

            // Also reload modal table if it exists
            loadHealthBenefitsIntoModal();
        } else {
            showMessage('error', data.message || 'Failed to delete health benefit');
        }
    })
    .catch(error => {
        console.error('Error deleting health benefit:', error);
        showMessage('error', 'An error occurred while deleting health benefit');
    });
}

/**
 * Force delete a health benefit and remove it from all products
 * @param {number} benefitId - The ID of the benefit to delete
 * @param {string} benefitName - The name of the benefit to delete
 */
function forceDeleteBenefit(benefitId, benefitName) {
    console.log(`Force deleting health benefit with ID: ${benefitId}`);

    fetch('/api/admin/delete_health_benefit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            benefit_id: benefitId,
            force_delete: true
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show success message
            if (data.force_deleted) {
                showMessage('success', `Health benefit "${benefitName}" has been deleted and removed from ${data.product_count} products.`);
            } else {
                showMessage('success', `Health benefit "${benefitName}" has been deleted successfully.`);
            }

            // Reload health benefits
            loadHealthBenefits();

            // Also reload modal table if it exists
            loadHealthBenefitsIntoModal();
        } else {
            showMessage('error', data.message || 'Failed to delete health benefit');
        }
    })
    .catch(error => {
        console.error('Error force deleting health benefit:', error);
        showMessage('error', 'An error occurred while deleting health benefit');
    });
}

/**
 * Show the health benefits management modal
 */
window.setupHealthBenefitsManagement = function setupHealthBenefitsManagement() {
    console.log('Opening health benefits management modal');

    // Create the benefit modal if it doesn't exist
    createBenefitModal();

    // Create the health benefits management modal
    const managementModal = document.createElement('div');
    managementModal.id = 'health-benefits-management-modal';
    managementModal.className = 'modal';
    managementModal.style.cssText = `
        display: flex;
        position: fixed;
        z-index: 1100;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0,0,0,0.5);
        justify-content: center;
        align-items: center;
        backdrop-filter: blur(2px);
    `;

    managementModal.innerHTML = `
        <div class="modal-content" style="background: white; border-radius: 8px; padding: 0; max-width: 90%; width: 1000px; max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.15);">
            <div class="modal-header" style="background: #f8f9fa; border-bottom: 1px solid #dee2e6; padding: 20px; border-radius: 8px 8px 0 0; display: flex; justify-content: space-between; align-items: center;">
                <h2 style="margin: 0; color: #333; font-size: 1.5rem; font-weight: 600;">Health Benefits Management</h2>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <button class="btn btn-primary" id="add-benefit-btn-modal" style="background-color: #4361ee; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer;">Add New Benefit</button>
                    <button class="close-modal" style="background: none; border: none; font-size: 24px; color: #6c757d; cursor: pointer; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 4px; transition: background-color 0.2s;" onmouseover="this.style.backgroundColor='#e9ecef'" onmouseout="this.style.backgroundColor='transparent'">&times;</button>
                </div>
            </div>
            <div class="modal-body" style="padding: 24px;">
                <p style="margin-bottom: 15px; color: #666;">Manage health benefits for products. Health benefits are used to match products to health goals.</p>
                <div class="table-container" style="overflow-x: auto;">
                    <table id="health-benefits-table-modal" class="data-table" style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                        <thead>
                            <tr style="background-color: #f0f0f0;">
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd; font-weight: 600;">Name</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd; font-weight: 600;">Description</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd; font-weight: 600;">Category</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd; font-weight: 600;">Status</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd; font-weight: 600;">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td colspan="5" style="text-align: center; padding: 20px; color: #666;">Loading health benefits...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(managementModal);

    // Set up event listeners
    const closeBtn = managementModal.querySelector('.close-modal');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            document.body.removeChild(managementModal);
        });
    }

    // Close when clicking outside
    managementModal.addEventListener('click', function(event) {
        if (event.target === managementModal) {
            document.body.removeChild(managementModal);
        }
    });

    // Set up the add benefit button
    const addBenefitBtn = managementModal.querySelector('#add-benefit-btn-modal');
    if (addBenefitBtn) {
        addBenefitBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Add benefit button clicked in modal');

            const modal = document.getElementById('new-benefit-modal');
            if (modal) {
                modal.style.display = 'flex';
            } else {
                console.error('Benefit modal not found');
                showMessage('error', 'Benefit modal not found. Please refresh the page and try again.');
            }
        });
    }

    // Load health benefits data into the modal table
    loadHealthBenefitsIntoModal();
}

/**
 * Create the benefit modal if it doesn't exist
 */
function createBenefitModal() {
    // Remove any existing modal first to prevent duplicates
    const existingModal = document.getElementById('new-benefit-modal');
    if (existingModal) {
        console.log('Removing existing benefit modal');
        existingModal.remove();
    }

    console.log('Creating benefit modal');

    const modal = document.createElement('div');
    modal.id = 'new-benefit-modal';
    modal.className = 'modal';

    modal.innerHTML = `
        <div class="modal-content" style="background: white; border-radius: 8px; padding: 0; max-width: 500px; width: 90%; max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.15);">
            <div class="modal-header" style="background: #f8f9fa; border-bottom: 1px solid #dee2e6; padding: 20px; border-radius: 8px 8px 0 0; display: flex; justify-content: space-between; align-items: center;">
                <h2 style="margin: 0; color: #333; font-size: 1.5rem; font-weight: 600;">Add New Health Benefit</h2>
                <button class="close-modal" style="background: none; border: none; font-size: 24px; color: #6c757d; cursor: pointer; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 4px; transition: background-color 0.2s;" onmouseover="this.style.backgroundColor='#e9ecef'" onmouseout="this.style.backgroundColor='transparent'">&times;</button>
            </div>
            <div class="modal-body" style="padding: 24px;">
                <form id="new-benefit-form">
                    <div class="form-group" style="margin-bottom: 20px;">
                        <label for="new-benefit-name" style="display: block; margin-bottom: 8px; font-weight: 500; color: #333; font-size: 14px;">Benefit Name *</label>
                        <input type="text" id="new-benefit-name" name="name" required style="width: 100%; padding: 10px 12px; border: 1px solid #ced4da; border-radius: 4px; font-size: 14px; transition: border-color 0.2s; box-sizing: border-box;" placeholder="Enter benefit name">
                    </div>
                    <div class="form-group" style="margin-bottom: 20px;">
                        <label for="new-benefit-description" style="display: block; margin-bottom: 8px; font-weight: 500; color: #333; font-size: 14px;">Description</label>
                        <textarea id="new-benefit-description" name="description" rows="3" style="width: 100%; padding: 10px 12px; border: 1px solid #ced4da; border-radius: 4px; font-size: 14px; resize: vertical; transition: border-color 0.2s; box-sizing: border-box; font-family: inherit;" placeholder="Enter benefit description (optional)"></textarea>
                    </div>
                    <div class="form-group" style="margin-bottom: 24px;">
                        <label for="new-benefit-category" style="display: block; margin-bottom: 8px; font-weight: 500; color: #333; font-size: 14px;">Category *</label>
                        <select id="new-benefit-category" name="category" required style="width: 100%; padding: 10px 12px; border: 1px solid #ced4da; border-radius: 4px; font-size: 14px; background: white; transition: border-color 0.2s; box-sizing: border-box;">
                            <option value="">Select a category</option>
                            <option value="muscle_building">Muscle Building</option>
                            <option value="weight_management">Weight Management</option>
                            <option value="energy_performance">Energy & Performance</option>
                            <option value="general_health">General Health</option>
                            <option value="recovery">Recovery</option>
                        </select>
                    </div>
                    <div class="form-actions" style="display: flex; justify-content: flex-end; gap: 12px; padding-top: 16px; border-top: 1px solid #dee2e6;">
                        <button type="button" class="btn btn-secondary cancel-btn" style="padding: 10px 20px; border: 1px solid #6c757d; background: white; color: #6c757d; border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s;">Cancel</button>
                        <button type="submit" class="btn btn-primary" style="padding: 10px 20px; border: none; background: #4361ee; color: white; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: 500; transition: background-color 0.2s;">Save Benefit</button>
                    </div>
                </form>
            </div>
        </div>
    `;

    // Add modal styling
    modal.style.cssText = `
        display: none;
        position: fixed;
        z-index: 1000;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0,0,0,0.5);
        justify-content: center;
        align-items: center;
        backdrop-filter: blur(2px);
    `;

    document.body.appendChild(modal);

    // Set up event listeners
    const closeBtn = modal.querySelector('.close-modal');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            modal.style.display = 'none';
        });
    }

    // Set up cancel button
    const cancelBtn = modal.querySelector('.cancel-btn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            modal.style.display = 'none';
        });
    }

    // Close when clicking outside
    modal.addEventListener('click', function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });

    // Set up form submission
    const form = modal.querySelector('#new-benefit-form');
    if (form) {
        console.log('Setting up form submission event listener');
        form.addEventListener('submit', function(event) {
            console.log('Form submit event triggered');
            event.preventDefault();
            event.stopPropagation();

            const nameInput = document.getElementById('new-benefit-name');
            const descriptionInput = document.getElementById('new-benefit-description');
            const categoryInput = document.getElementById('new-benefit-category');

            if (!nameInput || !descriptionInput || !categoryInput) {
                console.error('Form inputs not found');
                showMessage('error', 'Form inputs not found');
                return;
            }

            const name = nameInput.value.trim();
            const description = descriptionInput.value.trim();
            const category = categoryInput.value;

            if (!name) {
                showMessage('error', 'Benefit name is required');
                nameInput.focus();
                return;
            }

            if (!category) {
                showMessage('error', 'Category is required');
                categoryInput.focus();
                return;
            }

            // Disable submit button
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Saving...';
            }

            // Send request to API
            fetch('/api/admin/add_health_benefit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: name,
                    description: description,
                    category: category
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Close modal and reset form
                    modal.style.display = 'none';
                    form.reset();

                    // Show success message
                    showMessage('success', 'Health benefit added successfully');

                    // Reload health benefits
                    loadHealthBenefits();

                    // Also reload modal table if it exists
                    loadHealthBenefitsIntoModal();
                } else {
                    showMessage('error', data.message || 'Failed to add health benefit');
                }

                // Re-enable submit button
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Save Benefit';
                }
            })
            .catch(error => {
                console.error('Error adding health benefit:', error);
                showMessage('error', 'An error occurred while adding health benefit');

                // Re-enable submit button
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Save Benefit';
                }
            });
        });
    } else {
        console.error('Form not found in modal');
    }

    // Also add a click event listener to the submit button as a backup
    const submitBtn = modal.querySelector('button[type="submit"]');
    if (submitBtn) {
        console.log('Setting up submit button click event listener');
        submitBtn.addEventListener('click', function(event) {
            console.log('Submit button clicked');
            event.preventDefault();
            event.stopPropagation();

            // Trigger form submission manually
            const form = modal.querySelector('#new-benefit-form');
            if (form) {
                const submitEvent = new Event('submit', { bubbles: true, cancelable: true });
                form.dispatchEvent(submitEvent);
            }
        });
    } else {
        console.error('Submit button not found in modal');
    }
}

// Initialize when the document is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, health benefits functionality ready');

    // Health benefits management is now only accessible through the "Setup Health Benefits" button
    // No automatic setup is performed

    // Add a global function to show messages
    if (typeof window.showMessage !== 'function') {
        window.showMessage = function(type, message) {
            console.log(`[${type}] ${message}`);

            // Create a message element
            const messageElement = document.createElement('div');
            messageElement.className = `message ${type}`;
            messageElement.textContent = message;

            // Add the message to the page
            const messagesContainer = document.getElementById('messages-container');
            if (messagesContainer) {
                messagesContainer.appendChild(messageElement);
            } else {
                // Create a messages container if it doesn't exist
                const container = document.createElement('div');
                container.id = 'messages-container';
                container.style.position = 'fixed';
                container.style.top = '20px';
                container.style.right = '20px';
                container.style.zIndex = '9999';
                container.appendChild(messageElement);
                document.body.appendChild(container);
            }

            // Remove the message after 5 seconds
            setTimeout(() => {
                messageElement.remove();
            }, 5000);
        };
    }
});

/**
 * Rock Chatbot - Admin Promotions Management
 *
 * This script handles the promotions management functionality in the admin dashboard.
 * It provides CRUD operations for promotions.
 */

// Global variables
let currentPromotionPage = 1;
const promotionsPerPage = 10;
let totalPromotionPages = 1;

/**
 * Load promotions with pagination
 * @param {number} page - The page number to load
 */
window.loadPromotions = function(page = 1) {
    currentPromotionPage = page;

    // Show loading indicator
    const promotionsTab = document.getElementById('promotions');
    promotionsTab.innerHTML = '<div class="loading">Loading promotions...</div>';

    // Fetch promotions from API
    fetch(`/api/admin/all_promotions?page=${page}&per_page=${promotionsPerPage}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update pagination info
                totalPromotionPages = data.pagination.total_pages;

                // Create promotions table
                let html = `
                    <div class="card-header">
                        <h2>Promotions</h2>
                        <button class="btn btn-primary" id="add-promotion-btn">Add New Promotion</button>
                    </div>
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Name</th>
                                    <th>Discount</th>
                                    <th>Start Date</th>
                                    <th>End Date</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="promotions-table">
                `;

                // Add promotions to table
                data.promotions.forEach(promotion => {
                    const discountText = promotion.discount_type === 'percentage'
                        ? `${promotion.discount_value}%`
                        : `RM${parseFloat(promotion.discount_value).toFixed(2)}`;

                    html += `
                        <tr>
                            <td>${promotion.promotion_id}</td>
                            <td>${promotion.name}</td>
                            <td>${discountText}</td>
                            <td>${new Date(promotion.start_date).toLocaleDateString()}</td>
                            <td>${new Date(promotion.end_date).toLocaleDateString()}</td>
                            <td>${promotion.is_active ? 'Active' : 'Inactive'}</td>
                            <td class="action-buttons">
                                <button class="action-btn edit-btn" onclick="editPromotion(${promotion.promotion_id})">Edit</button>
                                <button class="action-btn delete-btn" onclick="deletePromotion(${promotion.promotion_id})">Delete</button>
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
                if (totalPromotionPages > 1) {
                    html += `
                        <div class="pagination">
                            <button ${page === 1 ? 'disabled' : ''} onclick="loadPromotions(1)">First</button>
                            <button ${page === 1 ? 'disabled' : ''} onclick="loadPromotions(${page - 1})">Previous</button>
                    `;

                    // Show page numbers
                    const startPage = Math.max(1, page - 2);
                    const endPage = Math.min(totalPromotionPages, page + 2);

                    for (let i = startPage; i <= endPage; i++) {
                        html += `
                            <button class="${i === page ? 'active' : ''}" onclick="loadPromotions(${i})">${i}</button>
                        `;
                    }

                    html += `
                            <button ${page === totalPromotionPages ? 'disabled' : ''} onclick="loadPromotions(${page + 1})">Next</button>
                            <button ${page === totalPromotionPages ? 'disabled' : ''} onclick="loadPromotions(${totalPromotionPages})">Last</button>
                        </div>
                    `;
                }

                // Add promotion modal
                html += `
                    <div class="modal" id="promotion-modal">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h2 id="promotion-modal-title">Add Promotion</h2>
                                <button class="close-modal">&times;</button>
                            </div>
                            <form id="promotion-form">
                                <input type="hidden" id="promotion-id">
                                <div class="form-group">
                                    <label for="promotion-name">Name</label>
                                    <input type="text" id="promotion-name" class="form-control" required>
                                </div>
                                <div class="form-group">
                                    <label for="promotion-description">Description</label>
                                    <textarea id="promotion-description" class="form-control" rows="3"></textarea>
                                </div>
                                <div class="form-group">
                                    <label for="promotion-discount-type">Discount Type</label>
                                    <select id="promotion-discount-type" class="form-control" required>
                                        <option value="percentage">Percentage</option>
                                        <option value="fixed">Fixed Amount</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label for="promotion-discount-value">Discount Value</label>
                                    <input type="number" id="promotion-discount-value" class="form-control" step="0.01" min="0" required>
                                </div>
                                <div class="form-group">
                                    <label for="promotion-start-date">Start Date</label>
                                    <input type="date" id="promotion-start-date" class="form-control" required>
                                </div>
                                <div class="form-group">
                                    <label for="promotion-end-date">End Date</label>
                                    <input type="date" id="promotion-end-date" class="form-control" required>
                                </div>
                                <div class="form-group">
                                    <label>Status</label>
                                    <div>
                                        <input type="radio" id="promotion-active" name="promotion-status" value="1" checked>
                                        <label for="promotion-active">Active</label>
                                        <input type="radio" id="promotion-inactive" name="promotion-status" value="0">
                                        <label for="promotion-inactive">Inactive</label>
                                    </div>
                                </div>
                                <button type="submit" class="btn btn-primary">Save</button>
                            </form>
                        </div>
                    </div>
                `;

                // Update promotions tab content
                promotionsTab.innerHTML = html;

                // Add event listeners
                const addPromotionBtn = document.getElementById('add-promotion-btn');
                if (addPromotionBtn) {
                    addPromotionBtn.addEventListener('click', showAddPromotionModal);
                }

                const promotionForm = document.getElementById('promotion-form');
                if (promotionForm) {
                    promotionForm.addEventListener('submit', handlePromotionFormSubmit);
                }

                const closeModalBtn = document.querySelector('#promotion-modal .close-modal');
                if (closeModalBtn) {
                    closeModalBtn.addEventListener('click', () => {
                        document.getElementById('promotion-modal').style.display = 'none';
                    });
                }
            } else {
                promotionsTab.innerHTML = `<div class="error">Error loading promotions: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading promotions:', error);
            promotionsTab.innerHTML = '<div class="error">Error loading promotions. Please try again.</div>';
        });
}

/**
 * Show add promotion modal
 */
function showAddPromotionModal() {
    // Reset form
    const promotionForm = document.getElementById('promotion-form');
    if (promotionForm) {
        promotionForm.reset();
    }

    // Set today as the default start date
    const startDateInput = document.getElementById('promotion-start-date');
    if (startDateInput) {
        startDateInput.value = new Date().toISOString().split('T')[0];
    }

    // Set tomorrow as the default end date
    const endDateInput = document.getElementById('promotion-end-date');
    if (endDateInput) {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 30); // Default to 30 days
        endDateInput.value = tomorrow.toISOString().split('T')[0];
    }

    // Set modal title
    const modalTitle = document.getElementById('promotion-modal-title');
    if (modalTitle) {
        modalTitle.textContent = 'Add Promotion';
    }

    // Clear promotion ID
    const promotionIdInput = document.getElementById('promotion-id');
    if (promotionIdInput) {
        promotionIdInput.value = '';
    }

    // Show modal
    const modal = document.getElementById('promotion-modal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

/**
 * Edit promotion
 * @param {number} promotionId - The ID of the promotion to edit
 */
function editPromotion(promotionId) {
    // Fetch promotion details
    fetch(`/api/admin/promotion_details?promotion_id=${promotionId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const promotion = data.promotion;

                // Set form values
                document.getElementById('promotion-id').value = promotion.promotion_id;
                document.getElementById('promotion-name').value = promotion.name;
                document.getElementById('promotion-description').value = promotion.description || '';
                document.getElementById('promotion-discount-type').value = promotion.discount_type;
                document.getElementById('promotion-discount-value').value = promotion.discount_value;

                // Format dates for input fields (YYYY-MM-DD)
                const startDate = new Date(promotion.start_date);
                document.getElementById('promotion-start-date').value = startDate.toISOString().split('T')[0];

                const endDate = new Date(promotion.end_date);
                document.getElementById('promotion-end-date').value = endDate.toISOString().split('T')[0];

                // Set status radio button
                if (promotion.is_active) {
                    document.getElementById('promotion-active').checked = true;
                } else {
                    document.getElementById('promotion-inactive').checked = true;
                }

                // Set modal title
                document.getElementById('promotion-modal-title').textContent = 'Edit Promotion';

                // Show modal
                document.getElementById('promotion-modal').style.display = 'flex';
            } else {
                console.error('Error loading promotion details:', data.message);
                alert('Error loading promotion details. Please try again.');
            }
        })
        .catch(error => {
            console.error('Error loading promotion details:', error);
            alert('Error loading promotion details. Please try again.');
        });
}

/**
 * Delete promotion
 * @param {number} promotionId - The ID of the promotion to delete
 */
function deletePromotion(promotionId) {
    if (confirm('Are you sure you want to delete this promotion?')) {
        fetch('/api/admin/delete_promotion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                promotion_id: promotionId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Promotion deleted successfully.');
                loadPromotions(currentPromotionPage);
            } else {
                console.error('Error deleting promotion:', data.message);
                alert(`Error deleting promotion: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('Error deleting promotion:', error);
            alert('Error deleting promotion. Please try again.');
        });
    }
}

/**
 * Handle promotion form submission
 * @param {Event} event - The form submission event
 */
function handlePromotionFormSubmit(event) {
    event.preventDefault();

    // Get form values
    const promotionId = document.getElementById('promotion-id').value;
    const name = document.getElementById('promotion-name').value;
    const description = document.getElementById('promotion-description').value;
    const discountType = document.getElementById('promotion-discount-type').value;
    const discountValue = document.getElementById('promotion-discount-value').value;
    const startDate = document.getElementById('promotion-start-date').value;
    const endDate = document.getElementById('promotion-end-date').value;
    const isActive = document.querySelector('input[name="promotion-status"]:checked').value;

    // Validate form
    if (!name || !discountValue || !startDate || !endDate) {
        alert('Please fill in all required fields.');
        return;
    }

    // Prepare data
    const promotionData = {
        name,
        description,
        discount_type: discountType,
        discount_value: parseFloat(discountValue),
        start_date: startDate,
        end_date: endDate,
        is_active: parseInt(isActive)
    };

    // Add or update promotion
    let url, method;
    if (promotionId) {
        // Update existing promotion
        url = '/api/admin/edit_promotion';
        method = 'POST';
        promotionData.promotion_id = parseInt(promotionId);
    } else {
        // Add new promotion
        url = '/api/admin/create_promotion';
        method = 'POST';
    }

    // Send request
    fetch(url, {
        method,
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(promotionData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(promotionId ? 'Promotion updated successfully.' : 'Promotion added successfully.');

            // Hide modal
            document.getElementById('promotion-modal').style.display = 'none';

            // Reload promotions
            loadPromotions(currentPromotionPage);
        } else {
            console.error('Error saving promotion:', data.message);
            alert(`Error saving promotion: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('Error saving promotion:', error);
        alert('Error saving promotion. Please try again.');
    });
}

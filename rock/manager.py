import os
import json
import sqlite3
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from rock.database import Database
from rock.auth import Auth

class ChatbotManager:
    """
    Manager interface for Rock Chatbot.

    Provides CRUD functionality for:
    - Intents
    - Responses
    - FAQs
    - Products
    - Promotions

    Includes role-based access control:
    - Managers have full access
    - Agents have limited access
    - Authentication is required for all operations
    """

    def __init__(self, db_path: str = 'data/rock_chatbot.db'):
        """Initialize the ChatbotManager."""
        self.db = Database(db_path)
        self.auth = Auth(self.db)
        self.current_user = None

    def login(self, username_or_email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Authenticate a user and set as current user.

        Args:
            username_or_email: The username or email of the user
            password: The password of the user

        Returns:
            Tuple containing:
            - Success status (bool)
            - Message (str)
            - User information if successful (dict or None)
        """
        success, message, user_info = self.auth.login(username_or_email, password)

        if success:
            self.current_user = user_info

        return success, message, user_info

    def logout(self):
        """Log out the current user."""
        self.current_user = None

    def register_user(self, username: str, email: str, password: str,
                     first_name: str = None, last_name: str = None,
                     phone_number: str = None) -> Tuple[bool, str, Optional[int]]:
        """
        Register a new user with automatic role assignment based on email domain.

        Args:
            username: The username for the new user
            email: The email address for the new user
            password: The password for the new user
            first_name: The first name of the user (optional)
            last_name: The last name of the user (optional)
            phone_number: The phone number of the user (optional)

        Returns:
            Tuple containing:
            - Success status (bool)
            - Message (str)
            - User ID if successful (int or None)
        """
        # Check if current user has permission to register users
        if not self.current_user or not self.auth.has_permission(self.current_user, 'manager'):
            return False, "Permission denied. Only managers can register new users.", None

        return self.auth.register_user(username, email, password, first_name, last_name, phone_number)

    def check_permission(self, required_role: str) -> bool:
        """
        Check if the current user has permission for a specific role.

        Args:
            required_role: The required role for the action

        Returns:
            True if the user has permission, False otherwise
        """
        print(f"Checking permission for role: {required_role}")

        if not self.current_user:
            print("No current user set, permission denied")
            return False

        print(f"Current user: {self.current_user.get('username')}, role: {self.current_user.get('role')}")

        has_permission = self.auth.has_permission(self.current_user, required_role)
        print(f"Permission check result: {has_permission}")

        return has_permission

    # Intent Management

    def list_intents(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """List all intents."""
        return self.db.get_intents(active_only)

    def get_intent(self, intent_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific intent."""
        return self.db.get_intent(intent_id)

    def create_intent(self, intent_name: str, description: str, is_active: bool = True) -> int:
        """Create a new intent."""
        return self.db.create_intent(intent_name, description, is_active)

    def update_intent(self, intent_id: int, intent_name: str,
                     description: str, is_active: bool) -> bool:
        """Update an intent."""
        return self.db.update_intent(intent_id, intent_name, description, is_active)

    def delete_intent(self, intent_id: int) -> bool:
        """Delete an intent."""
        return self.db.delete_intent(intent_id)

    def list_intent_patterns(self, intent_id: Optional[int] = None,
                            language: Optional[str] = None) -> List[Dict[str, Any]]:
        """List intent patterns."""
        return self.db.get_intent_patterns(intent_id, language)

    def create_intent_pattern(self, intent_id: int, pattern: str, language: str = 'en') -> int:
        """Create a new intent pattern."""
        return self.db.create_intent_pattern(intent_id, pattern, language)

    def update_intent_pattern(self, pattern_id: int, pattern: str, language: str) -> bool:
        """Update an intent pattern."""
        return self.db.update_intent_pattern(pattern_id, pattern, language)

    def delete_intent_pattern(self, pattern_id: int) -> bool:
        """Delete an intent pattern."""
        return self.db.delete_intent_pattern(pattern_id)

    # Response Management

    def list_responses(self, intent_id: Optional[int] = None,
                      language: Optional[str] = None,
                      active_only: bool = True) -> List[Dict[str, Any]]:
        """List responses."""
        return self.db.get_responses(intent_id, language, active_only)

    def create_response(self, intent_id: int, response_text: str, language: str = 'en',
                       response_type: str = 'text', button_options: Optional[List[Dict]] = None,
                       is_active: bool = True) -> int:
        """Create a new response."""
        button_json = json.dumps(button_options) if button_options else None
        return self.db.create_response(intent_id, response_text, language,
                                      response_type, button_json, is_active)

    def update_response(self, response_id: int, response_text: str, language: str,
                       response_type: str, button_options: Optional[List[Dict]] = None,
                       is_active: bool = True) -> bool:
        """Update a response."""
        button_json = json.dumps(button_options) if button_options else None
        return self.db.update_response(response_id, response_text, language,
                                      response_type, button_json, is_active)

    def delete_response(self, response_id: int) -> bool:
        """Delete a response."""
        return self.db.delete_response(response_id)

    # FAQ Management

    def list_faqs(self, category: Optional[str] = None,
                 language: Optional[str] = None,
                 active_only: bool = True) -> List[Dict[str, Any]]:
        """List FAQs."""
        return self.db.get_faqs(category, language, active_only)

    def create_faq(self, question: str, answer: str, category: str,
                  language: str = 'en', is_active: bool = True) -> int:
        """Create a new FAQ."""
        return self.db.create_faq(question, answer, category, language, is_active)

    def update_faq(self, faq_id: int, question: str, answer: str,
                  category: str, language: str, is_active: bool) -> bool:
        """Update a FAQ."""
        return self.db.update_faq(faq_id, question, answer, category, language, is_active)

    def delete_faq(self, faq_id: int) -> bool:
        """Delete a FAQ."""
        return self.db.delete_faq(faq_id)

    # Pending FAQ Management

    def list_pending_faqs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List pending FAQs with optional status filter.

        Args:
            status: Optional filter for status ('pending', 'approved', 'rejected')

        Returns:
            List of pending FAQs
        """
        return self.db.get_pending_faqs(status)

    def approve_pending_faq(self, pending_faq_id: int, notes: Optional[str] = None) -> int:
        """
        Approve a pending FAQ and add it to the FAQs table.

        Args:
            pending_faq_id: ID of the pending FAQ to approve
            notes: Optional notes from the manager

        Returns:
            ID of the newly created FAQ
        """
        print(f"Manager.approve_pending_faq called: pending_faq_id={pending_faq_id}")
        print(f"Current user: {self.current_user}")

        if not self.current_user:
            print("Error: No current user set")
            return 0

        if not self.check_permission('manager'):
            print(f"Error: User {self.current_user.get('username')} does not have manager permission")
            return 0

        manager_id = self.current_user.get('staff_id')
        if not manager_id:
            print("Error: No staff_id found in current user")
            return 0

        print(f"Approving FAQ with manager_id={manager_id}")
        return self.db.approve_pending_faq(pending_faq_id, manager_id, notes)

    def reject_pending_faq(self, pending_faq_id: int, notes: Optional[str] = None) -> bool:
        """
        Reject a pending FAQ.

        Args:
            pending_faq_id: ID of the pending FAQ to reject
            notes: Optional notes from the manager

        Returns:
            True if successful, False otherwise
        """
        print(f"Manager.reject_pending_faq called: pending_faq_id={pending_faq_id}")
        print(f"Current user: {self.current_user}")

        if not self.current_user:
            print("Error: No current user set")
            return False

        if not self.check_permission('manager'):
            print(f"Error: User {self.current_user.get('username')} does not have manager permission")
            return False

        manager_id = self.current_user.get('staff_id')
        if not manager_id:
            print("Error: No staff_id found in current user")
            return False

        print(f"Rejecting FAQ with manager_id={manager_id}")
        return self.db.reject_pending_faq(pending_faq_id, manager_id, notes)

    # Product Management

    def list_products(self, category_id: Optional[int] = None,
                     active_only: bool = True,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """List products."""
        return self.db.get_products(category_id, active_only, limit)

    def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific product."""
        return self.db.get_product(product_id)

    def create_product(self, name: str, description: str, category_id: int,
                      price: float, stock_quantity: int, image_url: Optional[str] = None,
                      brand: Optional[str] = None, health_benefits: Optional[str] = None,
                      ingredients: Optional[str] = None, usage_instructions: Optional[str] = None,
                      is_active: bool = True) -> int:
        """Create a new product."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = '''
            INSERT INTO products
            (name, description, category_id, price, stock_quantity, image_url, brand,
             health_benefits, ingredients, usage_instructions, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        return self.db.execute_update(query, (
            name, description, category_id, price, stock_quantity, image_url, brand,
            health_benefits, ingredients, usage_instructions, is_active, now, now
        ))

    def update_product(self, product_id: int, name: str, description: str,
                      category_id: int, price: float, stock_quantity: int,
                      image_url: Optional[str] = None, brand: Optional[str] = None,
                      health_benefits: Optional[str] = None, ingredients: Optional[str] = None,
                      usage_instructions: Optional[str] = None, is_active: bool = True) -> bool:
        """Update a product."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = '''
            UPDATE products
            SET name = ?, description = ?, category_id = ?, price = ?, stock_quantity = ?,
                image_url = ?, brand = ?, health_benefits = ?, ingredients = ?,
                usage_instructions = ?, is_active = ?, updated_at = ?
            WHERE product_id = ?
        '''
        self.db.execute_update(query, (
            name, description, category_id, price, stock_quantity, image_url, brand,
            health_benefits, ingredients, usage_instructions, is_active, now, product_id
        ))
        return True

    def delete_product(self, product_id: int) -> bool:
        """Delete a product."""
        query = '''
            DELETE FROM products
            WHERE product_id = ?
        '''
        self.db.execute_update(query, (product_id,))
        return True

    # Promotion Management

    def list_promotions(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """List promotions."""
        query = '''
            SELECT promotion_id, name, description, discount_type, discount_value,
                   start_date, end_date, coupon_code, minimum_order_amount,
                   applicable_products, applicable_categories, is_active
            FROM promotions
        '''
        if active_only:
            query += ' WHERE is_active = 1'
        return self.db.execute_query(query)

    def get_promotion(self, promotion_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific promotion."""
        query = '''
            SELECT promotion_id, name, description, discount_type, discount_value,
                   start_date, end_date, coupon_code, minimum_order_amount,
                   applicable_products, applicable_categories, is_active
            FROM promotions
            WHERE promotion_id = ?
        '''
        results = self.db.execute_query(query, (promotion_id,))
        return results[0] if results else None

    def create_promotion(self, name: str, description: str, discount_type: str,
                        discount_value: float, start_date: str, end_date: str,
                        coupon_code: Optional[str] = None, minimum_order_amount: float = 0.0,
                        applicable_products: str = 'all', applicable_categories: str = 'all',
                        is_active: bool = True) -> int:
        """Create a new promotion."""
        query = '''
            INSERT INTO promotions
            (name, description, discount_type, discount_value, start_date, end_date,
             coupon_code, minimum_order_amount, applicable_products, applicable_categories,
             is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return self.db.execute_update(query, (
            name, description, discount_type, discount_value, start_date, end_date,
            coupon_code, minimum_order_amount, applicable_products, applicable_categories,
            is_active, now
        ))

    def update_promotion(self, promotion_id: int, name: str, description: str,
                        discount_type: str, discount_value: float, start_date: str,
                        end_date: str, coupon_code: Optional[str] = None,
                        minimum_order_amount: float = 0.0, applicable_products: str = 'all',
                        applicable_categories: str = 'all', is_active: bool = True) -> bool:
        """Update a promotion."""
        query = '''
            UPDATE promotions
            SET name = ?, description = ?, discount_type = ?, discount_value = ?,
                start_date = ?, end_date = ?, coupon_code = ?, minimum_order_amount = ?,
                applicable_products = ?, applicable_categories = ?, is_active = ?
            WHERE promotion_id = ?
        '''
        self.db.execute_update(query, (
            name, description, discount_type, discount_value, start_date, end_date,
            coupon_code, minimum_order_amount, applicable_products, applicable_categories,
            is_active, promotion_id
        ))
        return True

    def delete_promotion(self, promotion_id: int) -> bool:
        """Delete a promotion."""
        query = '''
            DELETE FROM promotions
            WHERE promotion_id = ?
        '''
        self.db.execute_update(query, (promotion_id,))
        return True

    # Customer Management

    def list_customers(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """List customers."""
        query = '''
            SELECT customer_id, username, email, phone_number, first_name, last_name,
                   date_of_birth, gender, preferred_language, created_at, last_login, is_active
            FROM customers
        '''
        if active_only:
            query += ' WHERE is_active = 1'
        return self.db.execute_query(query)

    def get_customer(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific customer."""
        return self.db.get_customer(customer_id)

    def update_customer_status(self, customer_id: int, is_active: bool) -> bool:
        """Update a customer's active status."""
        query = '''
            UPDATE customers
            SET is_active = ?
            WHERE customer_id = ?
        '''
        self.db.execute_update(query, (is_active, customer_id))
        return True

    # Chat Session Management

    def list_chat_sessions(self, customer_id: Optional[int] = None,
                          agent_id: Optional[int] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """List chat sessions."""
        query = '''
            SELECT session_id, customer_id, session_start, session_end, agent_id, language, source
            FROM chat_sessions
        '''
        params = []
        where_clauses = []

        if customer_id is not None:
            where_clauses.append('customer_id = ?')
            params.append(customer_id)

        if agent_id is not None:
            where_clauses.append('agent_id = ?')
            params.append(agent_id)

        if where_clauses:
            query += ' WHERE ' + ' AND '.join(where_clauses)

        query += ' ORDER BY session_start DESC LIMIT ?'
        params.append(limit)

        return self.db.execute_query(query, tuple(params))

    def get_session_messages(self, session_id: int) -> List[Dict[str, Any]]:
        """Get all messages for a session."""
        return self.db.get_session_messages(session_id)

    def close(self):
        """Close the database connection."""
        if self.db:
            self.db.close()

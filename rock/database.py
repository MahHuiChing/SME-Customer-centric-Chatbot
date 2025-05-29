import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union

class Database:
    """Database interaction layer for Rock Chatbot."""

    def __init__(self, db_path: str = 'data/rock_chatbot.db'):
        """Initialize the database connection."""
        self.db_path = db_path

        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Initialize connection
        self.conn = self._get_connection()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a fresh database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute a SELECT query and return results as a list of dictionaries."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT, UPDATE, or DELETE query and return the last row ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        last_id = cursor.lastrowid
        conn.close()
        return last_id

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    # Session Management

    def create_session(self, customer_id: Optional[int] = None,
                      language: str = 'en', source: str = 'cli') -> int:
        """Create a new chat session."""
        query = '''
            INSERT INTO chat_sessions (customer_id, language, session_start, source)
            VALUES (?, ?, ?, ?)
        '''
        return self.execute_update(query, (customer_id, language,
                                          datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                          source))

    def end_session(self, session_id: int) -> bool:
        """End a chat session."""
        query = '''
            UPDATE chat_sessions
            SET session_end = ?
            WHERE session_id = ?
        '''
        self.execute_update(query, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session_id))
        return True

    def assign_agent(self, session_id: int, agent_id: int) -> bool:
        """Assign an agent to a session."""
        query = '''
            UPDATE chat_sessions
            SET agent_id = ?
            WHERE session_id = ?
        '''
        self.execute_update(query, (agent_id, session_id))
        return True

    # Message Management

    def save_message(self, session_id: int, sender_type: str,
                    sender_id: Optional[int], message_text: str,
                    intent_id: Optional[int] = None,
                    original_language: Optional[str] = None) -> int:
        """Save a chat message."""
        query = '''
            INSERT INTO chat_messages
            (session_id, sender_type, sender_id, message_text, intent_id, original_language, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        return self.execute_update(query, (
            session_id, sender_type, sender_id, message_text, intent_id,
            original_language, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

    def save_button_interaction(self, message_id: int, button_text: str, button_value: str) -> int:
        """Save a button interaction."""
        query = '''
            INSERT INTO button_interactions
            (message_id, button_text, button_value, timestamp)
            VALUES (?, ?, ?, ?)
        '''
        return self.execute_update(query, (
            message_id, button_text, button_value,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

    def get_session_messages(self, session_id: int) -> List[Dict]:
        """Get all messages for a session."""
        query = '''
            SELECT message_id, sender_type, sender_id, message_text, intent_id, timestamp
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY timestamp
        '''
        return self.execute_query(query, (session_id,))

    # Intent Management

    def get_intents(self, active_only: bool = True) -> List[Dict]:
        """Get all intents."""
        query = '''
            SELECT intent_id, intent_name, description, is_active
            FROM intents
        '''
        if active_only:
            query += ' WHERE is_active = 1'
        return self.execute_query(query)

    def get_intent(self, intent_id: int) -> Optional[Dict]:
        """Get a specific intent."""
        query = '''
            SELECT intent_id, intent_name, description, is_active
            FROM intents
            WHERE intent_id = ?
        '''
        results = self.execute_query(query, (intent_id,))
        return results[0] if results else None

    def create_intent(self, intent_name: str, description: str, is_active: bool = True) -> int:
        """Create a new intent."""
        query = '''
            INSERT INTO intents (intent_name, description, is_active)
            VALUES (?, ?, ?)
        '''
        return self.execute_update(query, (intent_name, description, is_active))

    def update_intent(self, intent_id: int, intent_name: str,
                     description: str, is_active: bool) -> bool:
        """Update an intent."""
        query = '''
            UPDATE intents
            SET intent_name = ?, description = ?, is_active = ?
            WHERE intent_id = ?
        '''
        self.execute_update(query, (intent_name, description, is_active, intent_id))
        return True

    def delete_intent(self, intent_id: int) -> bool:
        """Delete an intent."""
        query = '''
            DELETE FROM intents
            WHERE intent_id = ?
        '''
        self.execute_update(query, (intent_id,))
        return True

    def get_intent_patterns(self, intent_id: Optional[int] = None,
                           language: Optional[str] = None) -> List[Dict]:
        """Get intent patterns."""
        query = '''
            SELECT pattern_id, intent_id, pattern, language
            FROM intent_patterns
        '''
        params = []
        where_clauses = []

        if intent_id is not None:
            where_clauses.append('intent_id = ?')
            params.append(intent_id)

        if language is not None:
            where_clauses.append('language = ?')
            params.append(language)

        if where_clauses:
            query += ' WHERE ' + ' AND '.join(where_clauses)

        return self.execute_query(query, tuple(params))

    def create_intent_pattern(self, intent_id: int, pattern: str, language: str = 'en') -> int:
        """Create a new intent pattern."""
        query = '''
            INSERT INTO intent_patterns (intent_id, pattern, language)
            VALUES (?, ?, ?)
        '''
        return self.execute_update(query, (intent_id, pattern, language))

    def update_intent_pattern(self, pattern_id: int, pattern: str, language: str) -> bool:
        """Update an intent pattern."""
        query = '''
            UPDATE intent_patterns
            SET pattern = ?, language = ?
            WHERE pattern_id = ?
        '''
        self.execute_update(query, (pattern, language, pattern_id))
        return True

    def delete_intent_pattern(self, pattern_id: int) -> bool:
        """Delete an intent pattern."""
        query = '''
            DELETE FROM intent_patterns
            WHERE pattern_id = ?
        '''
        self.execute_update(query, (pattern_id,))
        return True

    # Response Management

    def get_responses(self, intent_id: Optional[int] = None,
                     language: Optional[str] = None,
                     active_only: bool = True) -> List[Dict]:
        """Get responses."""
        query = '''
            SELECT response_id, intent_id, response_text, language, response_type, button_options, is_active
            FROM responses
        '''
        params = []
        where_clauses = []

        if intent_id is not None:
            where_clauses.append('intent_id = ?')
            params.append(intent_id)

        if language is not None:
            where_clauses.append('language = ?')
            params.append(language)

        if active_only:
            where_clauses.append('is_active = 1')

        if where_clauses:
            query += ' WHERE ' + ' AND '.join(where_clauses)

        return self.execute_query(query, tuple(params))

    def create_response(self, intent_id: int, response_text: str, language: str = 'en',
                       response_type: str = 'text', button_options: Optional[str] = None,
                       is_active: bool = True) -> int:
        """Create a new response."""
        query = '''
            INSERT INTO responses (intent_id, response_text, language, response_type, button_options, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        '''
        return self.execute_update(query, (
            intent_id, response_text, language, response_type, button_options, is_active
        ))

    def update_response(self, response_id: int, response_text: str, language: str,
                       response_type: str, button_options: Optional[str], is_active: bool) -> bool:
        """Update a response."""
        query = '''
            UPDATE responses
            SET response_text = ?, language = ?, response_type = ?, button_options = ?, is_active = ?
            WHERE response_id = ?
        '''
        self.execute_update(query, (
            response_text, language, response_type, button_options, is_active, response_id
        ))
        return True

    def delete_response(self, response_id: int) -> bool:
        """Delete a response."""
        query = '''
            DELETE FROM responses
            WHERE response_id = ?
        '''
        self.execute_update(query, (response_id,))
        return True

    # FAQ Management

    def get_faqs(self, category: Optional[str] = None,
                language: Optional[str] = None,
                active_only: bool = True) -> List[Dict]:
        """Get FAQs."""
        query = '''
            SELECT faq_id, question, answer, category, language, is_active
            FROM faqs
        '''
        params = []
        where_clauses = []

        if category is not None:
            where_clauses.append('category = ?')
            params.append(category)

        if language is not None:
            where_clauses.append('language = ?')
            params.append(language)

        if active_only:
            where_clauses.append('is_active = 1')

        if where_clauses:
            query += ' WHERE ' + ' AND '.join(where_clauses)

        return self.execute_query(query, tuple(params))

    def create_faq(self, question: str, answer: str, category: str,
                  language: str = 'en', is_active: bool = True) -> int:
        """Create a new FAQ."""
        query = '''
            INSERT INTO faqs (question, answer, category, language, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return self.execute_update(query, (
            question, answer, category, language, is_active, now, now
        ))

    def update_faq(self, faq_id: int, question: str, answer: str,
                  category: str, language: str, is_active: bool) -> bool:
        """Update a FAQ."""
        query = '''
            UPDATE faqs
            SET question = ?, answer = ?, category = ?, language = ?, is_active = ?, updated_at = ?
            WHERE faq_id = ?
        '''
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.execute_update(query, (
            question, answer, category, language, is_active, now, faq_id
        ))
        return True

    def delete_faq(self, faq_id: int) -> bool:
        """Delete a FAQ."""
        query = '''
            DELETE FROM faqs
            WHERE faq_id = ?
        '''
        self.execute_update(query, (faq_id,))
        return True

    # Pending FAQ Management

    def get_pending_faqs(self, status: Optional[str] = None) -> List[Dict]:
        """Get pending FAQs with optional status filter."""
        query = '''
            SELECT p.pending_faq_id, p.question, p.answer, p.category, p.language,
                   p.submitted_by, p.submitted_at, p.status, p.reviewed_by, p.reviewed_at,
                   p.notes, p.agent_notes,
                   s1.username as submitted_by_username, s2.username as reviewed_by_username
            FROM pending_faqs p
            LEFT JOIN staff s1 ON p.submitted_by = s1.staff_id
            LEFT JOIN staff s2 ON p.reviewed_by = s2.staff_id
        '''
        params = []

        if status is not None:
            query += ' WHERE p.status = ?'
            params.append(status)

        query += ' ORDER BY p.submitted_at DESC'

        return self.execute_query(query, tuple(params))

    def create_pending_faq(self, question: str, answer: str, category: str,
                          language: str, submitted_by: int, agent_notes: str = None) -> int:
        """Create a new pending FAQ."""
        query = '''
            INSERT INTO pending_faqs (question, answer, category, language, submitted_by,
                                     agent_notes, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        '''
        return self.execute_update(query, (
            question, answer, category, language, submitted_by, agent_notes
        ))

    def approve_pending_faq(self, pending_faq_id: int, reviewed_by: int, notes: Optional[str] = None) -> int:
        """
        Approve a pending FAQ and add it to the FAQs table.

        Returns the ID of the newly created FAQ.
        """
        # First, get the pending FAQ
        query = '''
            SELECT question, answer, category, language
            FROM pending_faqs
            WHERE pending_faq_id = ?
        '''
        pending_faq = self.execute_query(query, (pending_faq_id,))

        if not pending_faq:
            return 0

        # Update the pending FAQ status
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        update_query = '''
            UPDATE pending_faqs
            SET status = 'approved', reviewed_by = ?, reviewed_at = ?, notes = ?
            WHERE pending_faq_id = ?
        '''
        self.execute_update(update_query, (reviewed_by, now, notes, pending_faq_id))

        # Add to the FAQs table
        faq = pending_faq[0]
        return self.create_faq(
            faq['question'],
            faq['answer'],
            faq['category'],
            faq['language'],
            True
        )

    def reject_pending_faq(self, pending_faq_id: int, reviewed_by: int, notes: Optional[str] = None) -> bool:
        """Reject a pending FAQ."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = '''
            UPDATE pending_faqs
            SET status = 'rejected', reviewed_by = ?, reviewed_at = ?, notes = ?
            WHERE pending_faq_id = ?
        '''
        self.execute_update(query, (reviewed_by, now, notes, pending_faq_id))
        return True

    # Customer Management

    def get_customer(self, customer_id: int) -> Optional[Dict]:
        """Get a customer by ID."""
        query = '''
            SELECT customer_id, username, email, phone_number, first_name, last_name,
                   date_of_birth, gender, preferred_language, created_at, last_login, is_active
            FROM customers
            WHERE customer_id = ?
        '''
        results = self.execute_query(query, (customer_id,))
        return results[0] if results else None

    def get_staff_by_id(self, staff_id: int) -> Optional[Dict]:
        """Get a staff member by ID."""
        try:
            # Try to get all fields including online_status and last_activity
            query = '''
                SELECT staff_id, username, email, first_name, last_name, role,
                       is_active, created_at, last_login, online_status, last_activity
                FROM staff
                WHERE staff_id = ?
            '''
            results = self.execute_query(query, (staff_id,))
        except sqlite3.OperationalError:
            # Fallback if online_status or last_activity columns don't exist
            query = '''
                SELECT staff_id, username, email, first_name, last_name, role,
                       is_active, created_at, last_login
                FROM staff
                WHERE staff_id = ?
            '''
            results = self.execute_query(query, (staff_id,))

        return results[0] if results else None

    def get_customer_preferences(self, customer_id: int) -> Optional[Dict]:
        """Get customer preferences."""
        query = '''
            SELECT preference_id, customer_id, health_goal, preferred_categories
            FROM customer_preferences
            WHERE customer_id = ?
        '''
        results = self.execute_query(query, (customer_id,))
        return results[0] if results else None

    # Product Management

    def get_products(self, category_id: Optional[int] = None,
                    active_only: bool = True,
                    limit: int = 100) -> List[Dict]:
        """Get products."""
        query = '''
            SELECT product_id, name, description, category_id, price, stock_quantity,
                   image_url, brand, health_benefits, ingredients, usage_instructions, is_active
            FROM products
        '''
        params = []
        where_clauses = []

        if category_id is not None:
            where_clauses.append('(category_id = ? OR category_id IN (SELECT category_id FROM categories WHERE parent_category_id = ?))')
            params.extend([category_id, category_id])

        if active_only:
            where_clauses.append('is_active = 1')

        if where_clauses:
            query += ' WHERE ' + ' AND '.join(where_clauses)

        query += f' LIMIT {limit}'

        return self.execute_query(query, tuple(params))

    def get_product(self, product_id: int) -> Optional[Dict]:
        """Get a product by ID."""
        query = '''
            SELECT product_id, name, description, category_id, price, stock_quantity,
                   image_url, brand, health_benefits, ingredients, usage_instructions, is_active
            FROM products
            WHERE product_id = ?
        '''
        results = self.execute_query(query, (product_id,))
        return results[0] if results else None

    # Order Management

    def get_order(self, order_id: int) -> Optional[Dict]:
        """Get an order by ID."""
        query = '''
            SELECT o.order_id, o.customer_id, o.order_date, o.total_amount, o.status,
                   o.payment_method, o.payment_status, o.shipping_address, o.tracking_number, o.notes,
                   (SELECT status FROM delivery_status WHERE order_id = o.order_id ORDER BY status_date DESC LIMIT 1) as delivery_status
            FROM orders o
            WHERE o.order_id = ?
        '''
        results = self.execute_query(query, (order_id,))
        if not results:
            return None

        order = results[0]

        # Get order items
        query = '''
            SELECT oi.order_item_id, oi.product_id, p.name as product_name,
                   oi.quantity, oi.unit_price, oi.subtotal
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            WHERE oi.order_id = ?
        '''
        order['items'] = self.execute_query(query, (order_id,))

        return order

    def get_customer_orders(self, customer_id: int, limit: int = 5) -> List[Dict]:
        """Get orders for a customer."""
        query = '''
            SELECT order_id, order_date, total_amount, status, payment_status
            FROM orders
            WHERE customer_id = ?
            ORDER BY order_date DESC
            LIMIT ?
        '''
        return self.execute_query(query, (customer_id, limit))

    # Promotion Management

    def get_active_promotions(self) -> List[Dict]:
        """Get active promotions."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = '''
            SELECT promotion_id, name, description, discount_type, discount_value,
                   start_date, end_date, coupon_code, minimum_order_amount,
                   applicable_products, applicable_categories
            FROM promotions
            WHERE is_active = 1
            AND start_date <= ?
            AND end_date >= ?
        '''
        return self.execute_query(query, (now, now))

    def request_agent(self, session_id: int) -> bool:
        """Mark a session as needing agent assistance."""
        print(f"Requesting agent for session {session_id}")
        query = '''
            UPDATE chat_sessions
            SET needs_agent = 1, agent_requested_at = ?
            WHERE session_id = ?
        '''
        self.execute_update(query, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session_id))
        return True

    def get_bestselling_products(self, limit: int = 5) -> List[Dict]:
        """
        Get popular products based on order history.

        Args:
            limit: Maximum number of products to return

        Returns:
            List of popular products
        """
        query = '''
            SELECT p.product_id, p.name, p.description, p.category_id, p.price,
                   p.stock_quantity, p.image_url, p.brand, p.health_benefits,
                   p.ingredients, p.usage_instructions, p.is_active,
                   SUM(oi.quantity) as total_sold
            FROM products p
            JOIN order_items oi ON p.product_id = oi.product_id
            JOIN orders o ON oi.order_id = o.order_id
            WHERE p.is_active = 1
            GROUP BY p.product_id
            ORDER BY total_sold DESC
            LIMIT ?
        '''
        return self.execute_query(query, (limit,))

    def get_sessions_needing_agent(self, limit: int = 20) -> List[Dict]:
        """
        Get sessions that have specifically requested agent assistance.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of sessions that need agent assistance
        """
        query = '''
            SELECT cs.session_id, cs.customer_id, cs.session_start, cs.language,
                   cs.needs_agent, cs.agent_requested_at,
                   c.username, c.first_name, c.last_name, c.email,
                   (SELECT COUNT(*) FROM chat_messages WHERE session_id = cs.session_id) as message_count,
                   (SELECT MAX(timestamp) FROM chat_messages WHERE session_id = cs.session_id) as last_activity
            FROM chat_sessions cs
            LEFT JOIN customers c ON cs.customer_id = c.customer_id
            WHERE cs.session_end IS NULL AND cs.agent_id IS NULL AND cs.needs_agent = 1
            ORDER BY cs.agent_requested_at ASC, last_activity DESC
            LIMIT ?
        '''
        return self.execute_query(query, (limit,))

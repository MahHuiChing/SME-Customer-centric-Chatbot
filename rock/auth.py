"""
Authentication and role management for Rock Chatbot.

This module provides authentication and role management functionality for the Rock chatbot.
It includes:
- Email domain-based role assignment
- Role-based access control
- Authentication functions
"""

import re
import hashlib
from typing import Dict, Optional, List, Tuple, Any
from rock.database import Database

# Define roles and their hierarchy
ROLES = {
    'customer': 0,  # Regular customer
    'agent': 1,     # Customer service agent
    'manager': 2    # Manager with administrative privileges
}

# Define domain-based role mapping
DOMAIN_ROLES = {
    'agent.rock.com': 'agent',
    'manager.rock.com': 'manager'
}

class Auth:
    """Authentication and role management for Rock Chatbot."""

    def __init__(self, db: Database):
        """Initialize the Auth module with a database connection."""
        self.db = db

    def hash_password(self, password: str) -> str:
        """Hash a password using SHA-256."""
        return hashlib.sha256(password.encode()).hexdigest()

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
        # Validate email format
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return False, "Invalid email format", None

        # Check if username or email already exists
        existing_customer = self.db.execute_query(
            "SELECT customer_id FROM customers WHERE username = ? OR email = ?",
            (username, email)
        )

        existing_staff = self.db.execute_query(
            "SELECT staff_id FROM staff WHERE username = ? OR email = ?",
            (username, email)
        )

        if existing_customer or existing_staff:
            return False, "Username or email already exists", None

        # Determine role based on email domain
        domain = email.split('@')[-1].lower()
        role = self._get_role_from_domain(domain)

        # Hash the password
        password_hash = self.hash_password(password)

        # Register based on role
        if role in ['agent', 'manager']:
            # Register as staff
            staff_id = self.db.execute_update(
                """
                INSERT INTO staff
                (username, email, password_hash, first_name, last_name, role, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (username, email, password_hash, first_name, last_name, role, True)
            )
            return True, f"Registered successfully as {role}", staff_id
        else:
            # Register as customer
            customer_id = self.db.execute_update(
                """
                INSERT INTO customers
                (username, email, phone_number, password_hash, first_name, last_name, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (username, email, phone_number, password_hash, first_name, last_name, True)
            )
            return True, "Registered successfully as customer", customer_id

    def login(self, username_or_email: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Authenticate a user and return their information.

        Args:
            username_or_email: The username or email of the user
            password: The password of the user

        Returns:
            Tuple containing:
            - Success status (bool)
            - Message (str)
            - User information if successful (dict or None)
        """
        # Hash the password
        password_hash = self.hash_password(password)

        # Try to find the user in customers table
        customer = self.db.execute_query(
            """
            SELECT customer_id, username, email, first_name, last_name,
                   preferred_language, is_active
            FROM customers
            WHERE (username = ? OR email = ?) AND password_hash = ?
            """,
            (username_or_email, username_or_email, password_hash)
        )

        if customer and customer[0]['is_active']:
            # Update last login
            self.db.execute_update(
                "UPDATE customers SET last_login = CURRENT_TIMESTAMP WHERE customer_id = ?",
                (customer[0]['customer_id'],)
            )

            user_info = dict(customer[0])
            user_info['role'] = 'customer'
            return True, "Login successful", user_info

        # Try to find the user in staff table
        staff = self.db.execute_query(
            """
            SELECT staff_id, username, email, first_name, last_name, role, is_active
            FROM staff
            WHERE (username = ? OR email = ?) AND password_hash = ?
            """,
            (username_or_email, username_or_email, password_hash)
        )

        if staff and staff[0]['is_active']:
            # Update last login
            self.db.execute_update(
                "UPDATE staff SET last_login = CURRENT_TIMESTAMP WHERE staff_id = ?",
                (staff[0]['staff_id'],)
            )

            user_info = dict(staff[0])
            return True, "Login successful", user_info

        return False, "Invalid credentials or account is inactive", None

    def _get_role_from_domain(self, domain: str) -> str:
        """
        Determine the role based on email domain.

        Args:
            domain: The email domain

        Returns:
            The role name (customer, agent, or manager)
        """
        return DOMAIN_ROLES.get(domain, 'customer')

    def has_permission(self, user_info: Dict[str, Any], required_role: str) -> bool:
        """
        Check if a user has permission for a specific role.

        Args:
            user_info: The user information dictionary
            required_role: The required role for the action

        Returns:
            True if the user has permission, False otherwise
        """
        print(f"Auth.has_permission called: required_role={required_role}")
        print(f"User info: {user_info}")

        if not user_info or 'role' not in user_info:
            print("No user info or role not found in user info")
            return False

        user_role = user_info['role']
        print(f"User role: {user_role}")

        # Check if the user's role level is sufficient
        user_role_level = ROLES.get(user_role, -1)
        required_role_level = ROLES.get(required_role, 999)

        has_permission = user_role_level >= required_role_level
        print(f"User role level: {user_role_level}, Required role level: {required_role_level}, Has permission: {has_permission}")

        return has_permission

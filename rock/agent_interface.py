"""
Agent interface for Rock Chatbot.

This module provides functionality for agents to:
1. View active chat sessions
2. Take over a chat session
3. Send messages to customers
4. View chat history
5. End a chat session
6. Manage agent online status
7. Handle multiple customer chats simultaneously
"""

import os
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

from rock.database import Database
from rock.chatbot import RockChatbot
from rock.auth import Auth

class AgentInterface:
    """Interface for agents to interact with the Rock Chatbot."""

    def __init__(self, db_path: str = 'data/rock_chatbot.db'):
        """Initialize the AgentInterface."""
        self.db = Database(db_path)
        self.chatbot = RockChatbot(db_path)
        self.auth = Auth(self.db)
        self.current_user = None
        self.current_session = None
        self.active_sessions = []  # List of session IDs the agent is handling

    def login(self, username_or_email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Authenticate an agent and set as current user.

        Args:
            username_or_email: The username or email of the agent
            password: The password of the agent

        Returns:
            Tuple containing:
            - Success status (bool)
            - Message (str)
            - User information if successful (dict or None)
        """
        success, message, user_info = self.auth.login(username_or_email, password)

        if success:
            if user_info['role'] in ['agent', 'manager']:
                self.current_user = user_info
                # Set agent as online
                self.set_agent_status(user_info['staff_id'], True)
                return True, f"Welcome, {user_info['first_name']} {user_info['last_name']}", user_info
            else:
                return False, "Access denied. You must be an agent or manager to use this interface.", None

        return False, message, None

    def logout(self):
        """Log out the current agent."""
        if self.current_user:
            # Set agent as offline
            self.set_agent_status(self.current_user['staff_id'], False)
        self.current_user = None
        self.current_session = None
        self.active_sessions = []

    def set_agent_status(self, agent_id: int, is_online: bool) -> bool:
        """
        Set the online status of an agent.

        Args:
            agent_id: The ID of the agent
            is_online: True if agent is online, False otherwise

        Returns:
            True if successful, False otherwise
        """
        try:
            # Update the agent's online status and last activity time
            query = """
                UPDATE staff
                SET online_status = ?, last_activity = ?
                WHERE staff_id = ?
            """
            self.db.execute_update(query, (is_online, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), agent_id))
            return True
        except Exception as e:
            print(f"Error setting agent status: {e}")
            return False

    def update_agent_activity(self, agent_id: int) -> bool:
        """
        Update the last activity time for an agent.

        Args:
            agent_id: The ID of the agent

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
                UPDATE staff
                SET last_activity = ?
                WHERE staff_id = ?
            """
            self.db.execute_update(query, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), agent_id))
            return True
        except Exception as e:
            print(f"Error updating agent activity: {e}")
            return False

    def get_online_agents(self) -> List[Dict[str, Any]]:
        """
        Get a list of all online agents.

        Returns:
            List of online agents
        """
        query = """
            SELECT staff_id, username, first_name, last_name, email, last_activity
            FROM staff
            WHERE role = 'agent' AND is_active = 1 AND online_status = 1
            ORDER BY first_name, last_name
        """
        return self.db.execute_query(query)

    def list_active_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List active chat sessions that need agent attention.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of active chat sessions
        """
        # Get sessions that are active (no end time) and have no agent assigned
        # Prioritize sessions that have requested agent assistance
        query = """
            SELECT cs.session_id, cs.customer_id, cs.session_start, cs.language,
                   cs.needs_agent, cs.agent_requested_at,
                   c.username, c.first_name, c.last_name, c.email,
                   (SELECT COUNT(*) FROM chat_messages WHERE session_id = cs.session_id) as message_count,
                   (SELECT MAX(timestamp) FROM chat_messages WHERE session_id = cs.session_id) as last_activity
            FROM chat_sessions cs
            LEFT JOIN customers c ON cs.customer_id = c.customer_id
            WHERE cs.session_end IS NULL AND cs.agent_id IS NULL
            ORDER BY cs.needs_agent DESC, cs.agent_requested_at ASC, last_activity DESC
            LIMIT ?
        """
        return self.db.execute_query(query, (limit,))

    def list_sessions_needing_agent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List sessions that have specifically requested agent assistance.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of sessions that need agent assistance
        """
        return self.db.get_sessions_needing_agent(limit)

    def list_my_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List chat sessions assigned to the current agent.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of sessions assigned to the current agent
        """
        if not self.current_user:
            return []

        agent_id = self.current_user.get('staff_id')
        if not agent_id:
            return []

        query = """
            SELECT cs.session_id, cs.customer_id, cs.session_start, cs.language,
                   c.username, c.first_name, c.last_name, c.email,
                   (SELECT COUNT(*) FROM chat_messages WHERE session_id = cs.session_id) as message_count,
                   (SELECT MAX(timestamp) FROM chat_messages WHERE session_id = cs.session_id) as last_activity
            FROM chat_sessions cs
            LEFT JOIN customers c ON cs.customer_id = c.customer_id
            WHERE cs.session_end IS NULL AND cs.agent_id = ?
            ORDER BY cs.session_start DESC
            LIMIT ?
        """
        return self.db.execute_query(query, (agent_id, limit))

    def submit_faq_for_approval(self, question: str, answer: str, category: str,
                               language: str = 'en', agent_notes: str = None) -> int:
        """
        Submit a new FAQ for manager approval.

        Args:
            question: The FAQ question
            answer: The FAQ answer
            category: The FAQ category
            language: The FAQ language (default: 'en')
            agent_notes: Optional notes from the agent

        Returns:
            ID of the newly created pending FAQ, or 0 if failed
        """
        if not self.current_user:
            return 0

        agent_id = self.current_user.get('staff_id')
        if not agent_id:
            return 0

        return self.db.create_pending_faq(question, answer, category, language, agent_id, agent_notes)

    def list_my_pending_faqs(self) -> List[Dict[str, Any]]:
        """
        List pending FAQs submitted by the current agent.

        Returns:
            List of pending FAQs submitted by the current agent
        """
        if not self.current_user:
            return []

        agent_id = self.current_user.get('staff_id')
        if not agent_id:
            return []

        # Get all pending FAQs
        all_pending = self.db.get_pending_faqs()

        # Filter to only those submitted by this agent
        return [faq for faq in all_pending if faq['submitted_by'] == agent_id]

    def take_over_session(self, session_id: int) -> bool:
        """
        Take over a chat session.

        Args:
            session_id: The ID of the session to take over

        Returns:
            True if successful, False otherwise
        """
        if not self.current_user:
            return False

        agent_id = self.current_user.get('staff_id')
        if not agent_id:
            return False

        # Check if the session exists and is not already assigned
        session = self.db.execute_query(
            "SELECT * FROM chat_sessions WHERE session_id = ? AND session_end IS NULL",
            (session_id,)
        )

        if not session:
            return False

        # If already assigned to another agent, check if it's inactive
        if session[0]['agent_id'] is not None and session[0]['agent_id'] != agent_id:
            # Check if there's been activity in the last 5 minutes
            last_message = self.db.execute_query(
                "SELECT MAX(timestamp) as last_activity FROM chat_messages WHERE session_id = ?",
                (session_id,)
            )

            if last_message and last_message[0]['last_activity']:
                last_activity = datetime.strptime(last_message[0]['last_activity'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() - last_activity < timedelta(minutes=5):
                    return False  # Session is active with another agent

        # Assign the session to this agent
        result = self.chatbot.assign_agent(session_id, agent_id)

        if result:
            # Set as current session if no current session is set
            if not self.current_session:
                self.current_session = session_id

            # Add to active sessions list if not already there
            if session_id not in self.active_sessions:
                self.active_sessions.append(session_id)

            # Update agent activity timestamp
            self.update_agent_activity(agent_id)

            # Send a notification message to the customer
            agent_name = f"{self.current_user['first_name']} {self.current_user['last_name']}"
            notification = f"Agent {agent_name} has joined the conversation."

            self.db.save_message(session_id, 'system', None, notification)

            return True

        return False

    def release_session(self, session_id: int) -> bool:
        """
        Release a chat session (unassign from the current agent).

        Args:
            session_id: The ID of the session to release

        Returns:
            True if successful, False otherwise
        """
        if not self.current_user:
            return False

        agent_id = self.current_user.get('staff_id')
        if not agent_id:
            return False

        # Check if the session is assigned to this agent
        session = self.db.execute_query(
            "SELECT * FROM chat_sessions WHERE session_id = ? AND agent_id = ?",
            (session_id, agent_id)
        )

        if not session:
            return False

        # Unassign the session
        result = self.db.execute_update(
            "UPDATE chat_sessions SET agent_id = NULL WHERE session_id = ?",
            (session_id,)
        )

        if result:
            # Update agent activity timestamp
            self.update_agent_activity(agent_id)

            # Remove from active sessions list
            if session_id in self.active_sessions:
                self.active_sessions.remove(session_id)

            # If this was the current session, set to another active session or None
            if self.current_session == session_id:
                self.current_session = self.active_sessions[0] if self.active_sessions else None

            # Send a notification message to the customer
            agent_name = f"{self.current_user['first_name']} {self.current_user['last_name']}"
            notification = f"Agent {agent_name} has left the conversation. You are now chatting with the bot."

            self.db.save_message(session_id, 'system', None, notification)

            return True

        return False

    def get_session_messages(self, session_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get messages for a chat session.

        Args:
            session_id: The ID of the session
            limit: Maximum number of messages to return

        Returns:
            List of messages for the session
        """
        query = """
            SELECT m.message_id, m.sender_type, m.sender_id, m.message_text, m.timestamp,
                   c.username, c.first_name, c.last_name
            FROM chat_messages m
            LEFT JOIN customers c ON (m.sender_type = 'customer' AND m.sender_id = c.customer_id)
            WHERE m.session_id = ?
            ORDER BY m.timestamp DESC
            LIMIT ?
        """
        return self.db.execute_query(query, (session_id, limit))

    def send_message(self, session_id: int, message: str) -> bool:
        """
        Send a message to a chat session.

        Args:
            session_id: The ID of the session
            message: The message to send

        Returns:
            True if successful, False otherwise
        """
        if not self.current_user:
            return False

        agent_id = self.current_user.get('staff_id')
        if not agent_id:
            return False

        # Check if the session is assigned to this agent
        session = self.db.execute_query(
            "SELECT * FROM chat_sessions WHERE session_id = ? AND agent_id = ?",
            (session_id, agent_id)
        )

        if not session:
            return False

        # Update agent activity timestamp
        self.update_agent_activity(agent_id)

        # Save the message
        agent_name = f"{self.current_user['first_name']} {self.current_user['last_name']}"
        message_with_name = f"[Agent {agent_name}]: {message}"

        message_id = self.db.save_message(session_id, 'agent', agent_id, message_with_name)

        return message_id is not None

    def end_session(self, session_id: int) -> bool:
        """
        End a chat session.

        Args:
            session_id: The ID of the session to end

        Returns:
            True if successful, False otherwise
        """
        if not self.current_user:
            return False

        agent_id = self.current_user.get('staff_id')
        if not agent_id:
            return False

        # Check if the session is assigned to this agent
        session = self.db.execute_query(
            "SELECT * FROM chat_sessions WHERE session_id = ? AND agent_id = ?",
            (session_id, agent_id)
        )

        if not session:
            return False

        # Update agent activity timestamp
        self.update_agent_activity(agent_id)

        # Send a closing message
        agent_name = f"{self.current_user['first_name']} {self.current_user['last_name']}"
        closing_message = f"Agent {agent_name} has ended the conversation. Thank you for chatting with us!"

        self.db.save_message(session_id, 'system', None, closing_message)

        # End the session
        result = self.chatbot.end_session(session_id)

        if result:
            # Remove from active sessions list
            if session_id in self.active_sessions:
                self.active_sessions.remove(session_id)

            # If this was the current session, set to another active session or None
            if self.current_session == session_id:
                self.current_session = self.active_sessions[0] if self.active_sessions else None

        return result

    def transfer_session(self, session_id: int, new_agent_id: int) -> bool:
        """
        Transfer a chat session to another agent.

        Args:
            session_id: The ID of the session to transfer
            new_agent_id: The ID of the agent to transfer to

        Returns:
            True if successful, False otherwise
        """
        if not self.current_user:
            return False

        agent_id = self.current_user.get('staff_id')
        if not agent_id:
            return False

        # Check if the session is assigned to this agent
        session = self.db.execute_query(
            "SELECT * FROM chat_sessions WHERE session_id = ? AND agent_id = ?",
            (session_id, agent_id)
        )

        if not session:
            return False

        # Check if the new agent exists and is online
        new_agent = self.db.execute_query(
            "SELECT * FROM staff WHERE staff_id = ? AND is_active = 1 AND online_status = 1",
            (new_agent_id,)
        )

        if not new_agent:
            return False

        # Update agent activity timestamp
        self.update_agent_activity(agent_id)

        # Transfer the session
        try:
            self.db.execute_update(
                "UPDATE chat_sessions SET agent_id = ? WHERE session_id = ?",
                (new_agent_id, session_id)
            )

            # Verify the transfer was successful
            verify_query = "SELECT agent_id FROM chat_sessions WHERE session_id = ?"
            verify_result = self.db.execute_query(verify_query, (session_id,))

            if verify_result and verify_result[0]['agent_id'] == new_agent_id:
                # Remove from active sessions list
                if session_id in self.active_sessions:
                    self.active_sessions.remove(session_id)

                # If this was the current session, set to another active session or None
                if self.current_session == session_id:
                    self.current_session = self.active_sessions[0] if self.active_sessions else None

                # Send notification messages
                current_agent_name = f"{self.current_user['first_name']} {self.current_user['last_name']}"
                new_agent_name = f"{new_agent[0]['first_name']} {new_agent[0]['last_name']}"

                transfer_message = f"Agent {current_agent_name} has transferred you to Agent {new_agent_name}."
                self.db.save_message(session_id, 'system', None, transfer_message)

                return True
            else:
                return False

        except Exception as e:
            print(f"Error transferring session: {e}")
            return False

    def get_agent_sessions_count(self, agent_id: int) -> int:
        """
        Get the number of active sessions assigned to an agent.

        Args:
            agent_id: The ID of the agent

        Returns:
            Number of active sessions
        """
        query = """
            SELECT COUNT(*) as session_count
            FROM chat_sessions
            WHERE agent_id = ? AND session_end IS NULL
        """
        result = self.db.execute_query(query, (agent_id,))

        if result and 'session_count' in result[0]:
            return result[0]['session_count']

        return 0

    def close(self):
        """Close the database connection."""
        if self.current_user:
            # Set agent as offline
            self.set_agent_status(self.current_user['staff_id'], False)

        if self.db:
            self.db.close()
        if self.chatbot:
            self.chatbot.close()

import sqlite3
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Set up logging
import os

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/scheduled_tasks.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scheduled_tasks")

class ScheduledTasks:
    """
    Class to handle scheduled maintenance tasks for the Rock Chatbot database.
    """

    def __init__(self, db_path: str = 'data/rock_chatbot.db'):
        """Initialize with database path."""
        self.db_path = db_path

        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a fresh database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def find_empty_categories(self) -> List[Dict[str, Any]]:
        """
        Find categories that have no associated products.

        Returns:
            List of dictionaries containing empty category information
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT c.category_id, c.name, c.description, c.parent_category_id, c.is_active
            FROM categories c
            LEFT JOIN products p ON c.category_id = p.category_id
            WHERE p.product_id IS NULL
        """

        cursor.execute(query)
        empty_categories = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return empty_categories

    def delete_empty_categories(self, exclude_ids: List[int] = None) -> int:
        """
        Delete categories that have no associated products.

        Args:
            exclude_ids: List of category IDs to exclude from deletion

        Returns:
            Number of categories deleted
        """
        if exclude_ids is None:
            exclude_ids = []

        empty_categories = self.find_empty_categories()

        if not empty_categories:
            logger.info("No empty categories found.")
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()

        deleted_count = 0

        for category in empty_categories:
            category_id = category['category_id']

            # Skip excluded categories
            if category_id in exclude_ids:
                logger.info(f"Skipping excluded category: {category['name']} (ID: {category_id})")
                continue

            # Check if this category is a parent category
            cursor.execute("SELECT COUNT(*) FROM categories WHERE parent_category_id = ?", (category_id,))
            child_count = cursor.fetchone()[0]

            if child_count > 0:
                logger.info(f"Skipping category with child categories: {category['name']} (ID: {category_id})")
                continue

            try:
                cursor.execute("DELETE FROM categories WHERE category_id = ?", (category_id,))
                logger.info(f"Deleted empty category: {category['name']} (ID: {category_id})")
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting category {category_id}: {str(e)}")

        conn.commit()
        conn.close()

        logger.info(f"Deleted {deleted_count} empty categories")
        return deleted_count

    def cleanup_inactive_agents(self):
        """Set agents offline if they haven't been active for a while."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Set agents offline if no activity for more than 15 minutes
            cutoff_time = datetime.now() - timedelta(minutes=15)

            # Find agents that are marked online but haven't been active
            cursor.execute('''
                SELECT staff_id, first_name, last_name, last_activity
                FROM staff
                WHERE role = 'agent'
                AND online_status = 1
                AND (last_activity IS NULL OR last_activity < ?)
            ''', (cutoff_time.strftime('%Y-%m-%d %H:%M:%S'),))

            inactive_agents = cursor.fetchall()

            if inactive_agents:
                # Set them offline
                agent_ids = [agent[0] for agent in inactive_agents]
                placeholders = ','.join(['?' for _ in agent_ids])

                cursor.execute(f'''
                    UPDATE staff
                    SET online_status = 0
                    WHERE staff_id IN ({placeholders})
                ''', agent_ids)

                conn.commit()

                for agent in inactive_agents:
                    agent_id, first_name, last_name, last_activity = agent
                    logger.info(f"Set agent {first_name} {last_name} (ID: {agent_id}) offline due to inactivity. Last activity: {last_activity}")

                logger.info(f"Set {len(inactive_agents)} inactive agents offline")
            else:
                logger.debug("No inactive agents found")

            conn.close()
            return len(inactive_agents)

        except Exception as e:
            logger.error(f"Error cleaning up inactive agents: {str(e)}")
            return 0

    def cleanup_inactive_sessions(self):
        """End chat sessions that have been inactive for more than 5 minutes."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Find sessions that are still active but haven't had any activity for 5+ minutes
            cutoff_time = datetime.now() - timedelta(minutes=5)

            # Get sessions that are active (no session_end) and have no recent activity
            cursor.execute('''
                SELECT cs.session_id, cs.customer_id, cs.session_start,
                       MAX(cm.timestamp) as last_message_time
                FROM chat_sessions cs
                LEFT JOIN chat_messages cm ON cs.session_id = cm.session_id
                WHERE cs.session_end IS NULL
                GROUP BY cs.session_id, cs.customer_id, cs.session_start
                HAVING (last_message_time IS NULL AND cs.session_start < ?)
                    OR (last_message_time IS NOT NULL AND last_message_time < ?)
            ''', (cutoff_time.strftime('%Y-%m-%d %H:%M:%S'), cutoff_time.strftime('%Y-%m-%d %H:%M:%S')))

            inactive_sessions = cursor.fetchall()

            if inactive_sessions:
                for session in inactive_sessions:
                    session_id = session[0]

                    # End the session
                    cursor.execute('''
                        UPDATE chat_sessions
                        SET session_end = ?
                        WHERE session_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session_id))

                    # Add a system message indicating the session was ended due to inactivity
                    cursor.execute('''
                        INSERT INTO chat_messages (session_id, sender_type, sender_id, message_text, timestamp)
                        VALUES (?, 'system', NULL, ?, ?)
                    ''', (session_id, 'Session ended due to inactivity (5 minutes)', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                    logger.info(f"Ended inactive session {session_id} due to 5 minutes of inactivity")

                conn.commit()
                logger.info(f"Ended {len(inactive_sessions)} inactive sessions")
            else:
                logger.debug("No inactive sessions found")

            conn.close()
            return len(inactive_sessions)

        except Exception as e:
            logger.error(f"Error cleaning up inactive sessions: {str(e)}")
            return 0

    def run_maintenance(self):
        """Run all maintenance tasks."""
        logger.info("Starting scheduled maintenance tasks")

        # List of category IDs to never delete (e.g., default categories)
        protected_categories = [1, 2, 3, 4]  # Main parent categories

        # Delete empty categories
        self.delete_empty_categories(exclude_ids=protected_categories)

        # Cleanup inactive agents
        self.cleanup_inactive_agents()

        # Cleanup inactive sessions
        self.cleanup_inactive_sessions()

        logger.info("Completed scheduled maintenance tasks")


# Function to run as a standalone script
def run_tasks():
    """Run scheduled tasks."""
    tasks = ScheduledTasks()
    tasks.run_maintenance()


if __name__ == "__main__":
    run_tasks()

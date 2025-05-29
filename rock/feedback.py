"""
Feedback collection and processing for Rock Chatbot.

This module provides functionality for:
1. Collecting customer feedback after chat sessions
2. Processing feedback for future training
3. Extracting training data from chat sessions
4. Generating reports on chatbot performance
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from rock.database import Database

class FeedbackManager:
    """Manager for collecting and processing feedback."""
    
    def __init__(self, db_path: str = 'data/rock_chatbot.db'):
        """Initialize the FeedbackManager."""
        self.db = Database(db_path)
    
    def save_feedback(self, session_id: int, customer_id: Optional[int], 
                     rating: int, feedback_text: Optional[str] = None,
                     improvement_areas: Optional[List[str]] = None,
                     was_helpful: Optional[bool] = None) -> int:
        """
        Save feedback for a chat session.
        
        Args:
            session_id: The ID of the chat session
            customer_id: The ID of the customer (optional)
            rating: Rating from 1-5
            feedback_text: Optional text feedback
            improvement_areas: List of areas for improvement
            was_helpful: Whether the chatbot was helpful
            
        Returns:
            The ID of the saved feedback
        """
        # Validate rating
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")
        
        # Convert improvement areas to comma-separated string
        improvement_areas_str = None
        if improvement_areas:
            improvement_areas_str = ','.join(improvement_areas)
        
        query = """
            INSERT INTO chat_feedback 
            (session_id, customer_id, rating, feedback_text, improvement_areas, was_helpful, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        feedback_id = self.db.execute_update(query, (
            session_id, customer_id, rating, feedback_text, improvement_areas_str, 
            was_helpful, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        # After saving feedback, extract training data from the session
        self._extract_training_data(session_id, customer_id, feedback_id)
        
        return feedback_id
    
    def get_feedback_categories(self) -> List[Dict[str, Any]]:
        """
        Get all feedback categories.
        
        Returns:
            List of feedback categories
        """
        query = """
            SELECT category_id, category_name, description
            FROM feedback_categories
            WHERE is_active = 1
            ORDER BY category_name
        """
        
        return self.db.execute_query(query)
    
    def get_session_feedback(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Get feedback for a specific session.
        
        Args:
            session_id: The ID of the chat session
            
        Returns:
            Feedback data or None if no feedback exists
        """
        query = """
            SELECT feedback_id, session_id, customer_id, rating, feedback_text, 
                   improvement_areas, was_helpful, created_at
            FROM chat_feedback
            WHERE session_id = ?
        """
        
        results = self.db.execute_query(query, (session_id,))
        
        if not results:
            return None
        
        feedback = dict(results[0])
        
        # Convert improvement areas back to a list
        if feedback['improvement_areas']:
            feedback['improvement_areas'] = feedback['improvement_areas'].split(',')
        else:
            feedback['improvement_areas'] = []
        
        return feedback
    
    def get_customer_feedback(self, customer_id: int) -> List[Dict[str, Any]]:
        """
        Get all feedback from a specific customer.
        
        Args:
            customer_id: The ID of the customer
            
        Returns:
            List of feedback data
        """
        query = """
            SELECT f.feedback_id, f.session_id, f.customer_id, f.rating, f.feedback_text, 
                   f.improvement_areas, f.was_helpful, f.created_at,
                   s.session_start, s.session_end
            FROM chat_feedback f
            JOIN chat_sessions s ON f.session_id = s.session_id
            WHERE f.customer_id = ?
            ORDER BY f.created_at DESC
        """
        
        results = self.db.execute_query(query, (customer_id,))
        
        # Convert improvement areas back to a list for each feedback
        for i, feedback in enumerate(results):
            feedback_dict = dict(feedback)
            if feedback_dict['improvement_areas']:
                feedback_dict['improvement_areas'] = feedback_dict['improvement_areas'].split(',')
            else:
                feedback_dict['improvement_areas'] = []
            results[i] = feedback_dict
        
        return results
    
    def get_feedback_stats(self, start_date: Optional[str] = None, 
                          end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics on feedback.
        
        Args:
            start_date: Optional start date for filtering (format: YYYY-MM-DD)
            end_date: Optional end date for filtering (format: YYYY-MM-DD)
            
        Returns:
            Dictionary of feedback statistics
        """
        params = []
        date_filter = ""
        
        if start_date:
            date_filter += " AND created_at >= ?"
            params.append(f"{start_date} 00:00:00")
        
        if end_date:
            date_filter += " AND created_at <= ?"
            params.append(f"{end_date} 23:59:59")
        
        # Get average rating
        avg_query = f"""
            SELECT AVG(rating) as avg_rating, COUNT(*) as total_feedback
            FROM chat_feedback
            WHERE 1=1 {date_filter}
        """
        
        avg_result = self.db.execute_query(avg_query, tuple(params))
        
        # Get rating distribution
        dist_query = f"""
            SELECT rating, COUNT(*) as count
            FROM chat_feedback
            WHERE 1=1 {date_filter}
            GROUP BY rating
            ORDER BY rating
        """
        
        dist_result = self.db.execute_query(dist_query, tuple(params))
        
        # Get improvement areas distribution
        areas_query = f"""
            SELECT category_name, COUNT(*) as count
            FROM (
                SELECT cf.feedback_id, fc.category_name
                FROM chat_feedback cf
                CROSS JOIN feedback_categories fc
                WHERE cf.improvement_areas LIKE '%' || fc.category_name || '%'
                {date_filter}
            )
            GROUP BY category_name
            ORDER BY count DESC
        """
        
        areas_result = self.db.execute_query(areas_query, tuple(params))
        
        # Get helpfulness stats
        helpful_query = f"""
            SELECT was_helpful, COUNT(*) as count
            FROM chat_feedback
            WHERE was_helpful IS NOT NULL {date_filter}
            GROUP BY was_helpful
        """
        
        helpful_result = self.db.execute_query(helpful_query, tuple(params))
        
        # Compile stats
        stats = {
            'average_rating': avg_result[0]['avg_rating'] if avg_result else 0,
            'total_feedback': avg_result[0]['total_feedback'] if avg_result else 0,
            'rating_distribution': {r['rating']: r['count'] for r in dist_result},
            'improvement_areas': {a['category_name']: a['count'] for a in areas_result},
            'helpfulness': {
                'helpful': next((r['count'] for r in helpful_result if r['was_helpful'] == 1), 0),
                'not_helpful': next((r['count'] for r in helpful_result if r['was_helpful'] == 0), 0)
            }
        }
        
        return stats
    
    def _extract_training_data(self, session_id: int, customer_id: Optional[int], 
                              feedback_id: Optional[int] = None) -> None:
        """
        Extract training data from a chat session.
        
        Args:
            session_id: The ID of the chat session
            customer_id: The ID of the customer
            feedback_id: The ID of the associated feedback (optional)
        """
        # Get all messages from the session
        query = """
            SELECT message_id, sender_type, message_text, intent_id, timestamp
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY timestamp
        """
        
        messages = self.db.execute_query(query, (session_id,))
        
        # Process messages to extract user-bot interaction pairs
        for i in range(len(messages) - 1):
            if messages[i]['sender_type'] == 'customer' and messages[i+1]['sender_type'] == 'bot':
                user_input = messages[i]['message_text']
                bot_response = messages[i+1]['message_text']
                intent_id = messages[i+1]['intent_id']
                
                # Save as training data
                self._save_training_data(
                    session_id, customer_id, user_input, bot_response, 
                    intent_id, None, None, feedback_id
                )
    
    def _save_training_data(self, session_id: int, customer_id: Optional[int],
                           user_input: str, bot_response: str, intent_id: Optional[int],
                           was_correct: Optional[bool] = None, 
                           corrected_intent_id: Optional[int] = None,
                           feedback_id: Optional[int] = None) -> int:
        """
        Save training data.
        
        Args:
            session_id: The ID of the chat session
            customer_id: The ID of the customer
            user_input: The user's input message
            bot_response: The bot's response
            intent_id: The identified intent ID
            was_correct: Whether the intent identification was correct
            corrected_intent_id: The correct intent ID if was_correct is False
            feedback_id: The ID of the associated feedback
            
        Returns:
            The ID of the saved training data
        """
        query = """
            INSERT INTO training_data
            (session_id, customer_id, user_input, bot_response, intent_id, 
             was_correct, corrected_intent_id, feedback_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        return self.db.execute_update(query, (
            session_id, customer_id, user_input, bot_response, intent_id,
            was_correct, corrected_intent_id, feedback_id,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
    
    def mark_training_data(self, data_id: int, was_correct: bool, 
                          corrected_intent_id: Optional[int] = None) -> bool:
        """
        Mark training data as correct or incorrect.
        
        Args:
            data_id: The ID of the training data
            was_correct: Whether the intent identification was correct
            corrected_intent_id: The correct intent ID if was_correct is False
            
        Returns:
            True if successful, False otherwise
        """
        query = """
            UPDATE training_data
            SET was_correct = ?, corrected_intent_id = ?
            WHERE data_id = ?
        """
        
        self.db.execute_update(query, (was_correct, corrected_intent_id, data_id))
        return True
    
    def get_training_data(self, was_correct: Optional[bool] = None, 
                         limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get training data for review.
        
        Args:
            was_correct: Filter by correctness (optional)
            limit: Maximum number of records to return
            
        Returns:
            List of training data records
        """
        query = """
            SELECT td.data_id, td.session_id, td.customer_id, td.user_input, td.bot_response,
                   td.intent_id, i1.intent_name as intent_name, td.was_correct, 
                   td.corrected_intent_id, i2.intent_name as corrected_intent_name,
                   td.created_at
            FROM training_data td
            LEFT JOIN intents i1 ON td.intent_id = i1.intent_id
            LEFT JOIN intents i2 ON td.corrected_intent_id = i2.intent_id
        """
        
        params = []
        
        if was_correct is not None:
            query += " WHERE was_correct = ?"
            params.append(was_correct)
        
        query += " ORDER BY td.created_at DESC LIMIT ?"
        params.append(limit)
        
        return self.db.execute_query(query, tuple(params))
    
    def close(self):
        """Close the database connection."""
        if self.db:
            self.db.close()

import re
import json
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime
import random

from rock.database import Database
from rock.translation import TranslationService
from rock.feedback import FeedbackManager
from rock.health_goals import get_all_standard_goals, match_health_benefits_to_standard_goals, match_user_goal_to_products

class RockChatbot:
    """
    Rock Chatbot - A rule-based multilingual chatbot for supplements e-commerce.

    Features:
    - Rule-based intent recognition
    - Multilingual support
    - Personalized recommendations
    - FAQ automation
    - Button-based interface
    """

    def __init__(self, db_path: str = 'data/rock_chatbot.db'):
        """Initialize the Rock Chatbot."""
        self.db = Database(db_path)
        self.feedback_manager = FeedbackManager(db_path)
        self.current_session = None
        self.current_customer = None
        self.current_language = 'en'  # Default language
        # Dictionary to store session languages
        self.session_languages = {}
        # Navigation history for each session
        self.navigation_history = {}  # {session_id: [previous_states]}
        # Current context for each session
        self.session_context = {}  # {session_id: {'location': 'main_menu', 'data': {}}}
        # Special button values for navigation
        self.BACK_BUTTON = "nav_back"
        self.MAIN_MENU_BUTTON = "nav_main_menu"
        # Special button values for feedback
        self.FEEDBACK_BUTTON = "feedback"
        self.RATING_PREFIX = "rating_"  # e.g., rating_1, rating_2, etc.
        self.HELPFUL_PREFIX = "helpful_"  # e.g., helpful_yes, helpful_no
        self.FEEDBACK_CATEGORY_PREFIX = "feedback_category_"  # e.g., feedback_category_Understanding

    def start_session(self, customer_id: Optional[int] = None,
                     language: str = 'en', source: str = 'cli') -> int:
        """Start a new chat session."""
        self.current_language = language
        self.current_customer = customer_id

        # Store language in database (always as 'en' for client-side translation)
        # In a real implementation, we would store the user's preferred language
        # but process everything in English on the server side
        session_id = self.db.create_session(customer_id, 'en', source)
        self.current_session = session_id

        # Store the actual language preference for this session
        self.session_languages[session_id] = language

        # Initialize navigation history and context for this session
        self.navigation_history[session_id] = []
        self.session_context[session_id] = {
            'location': 'main_menu',
            'data': {}
        }

        return session_id

    def get_welcome_message(self, session_id: int, customer_id: Optional[int] = None, language: str = 'en') -> Dict[str, Any]:
        """
        Get the welcome message for a new chat session without processing a fake user message.

        Args:
            session_id: The session ID
            customer_id: The customer ID (if logged in)
            language: The language for the response

        Returns:
            Welcome message response
        """
        # Set the current customer for this session
        self.current_customer = customer_id

        # Get the greeting response (intent ID 1 is the greeting)
        response = self.get_response(1, language)

        # Customize the main menu based on whether the user is logged in
        if 'buttons' in response and customer_id:
            # Modify the recommendation button text for registered customers
            for button in response['buttons']:
                if button.get('value') == 'recommendation':
                    # Change the button text to indicate personalized recommendations
                    if language == 'en':
                        button['text'] = 'Your Personalized Recommendations'
                    elif language == 'ms':
                        button['text'] = 'Cadangan Peribadi Anda'
                    elif language == 'zh':
                        button['text'] = '您的个性化推荐'
                    elif language == 'ta':
                        button['text'] = 'உங்கள் தனிப்பயனாக்கப்பட்ட பரிந்துரைகள்'
                    # Keep the same button value for compatibility

        # Save the bot response (welcome message)
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response.get('text', 'Welcome to Rock Supplements!')
        )

        # Add session and message IDs to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def end_session(self, session_id: int, request_feedback: bool = True) -> Union[bool, Dict[str, Any]]:
        """
        End a chat session.

        Args:
            session_id: The ID of the session to end
            request_feedback: Whether to request feedback before ending

        Returns:
            If request_feedback is True, returns a feedback request response
            If request_feedback is False, returns True if successful
        """
        # Check if feedback already exists for this session
        existing_feedback = self.feedback_manager.get_session_feedback(session_id)

        if request_feedback and not existing_feedback:
            # Get the language for this session
            language = self.session_languages.get(session_id, 'en')

            # Request feedback before ending
            return self.request_feedback(session_id, language)

        # End the session
        result = self.db.end_session(session_id)

        if self.current_session == session_id:
            self.current_session = None

        # Clean up session data
        if session_id in self.session_languages:
            del self.session_languages[session_id]

        if session_id in self.navigation_history:
            del self.navigation_history[session_id]

        if session_id in self.session_context:
            del self.session_context[session_id]

        return result

    def assign_agent(self, session_id: int, agent_id: int) -> bool:
        """Assign a human agent to a chat session."""
        return self.db.assign_agent(session_id, agent_id)

    def _push_navigation_state(self, session_id: int, location: str, data: Dict = None) -> None:
        """
        Push the current state to the navigation history stack.

        Args:
            session_id: The current session ID
            location: The current location (e.g., 'main_menu', 'product_details', etc.)
            data: Additional data for the current location (e.g., product_id)
        """
        if session_id not in self.navigation_history:
            self.navigation_history[session_id] = []

        if session_id not in self.session_context:
            self.session_context[session_id] = {'location': 'main_menu', 'data': {}}

        # Push current state to history before updating
        current_state = self.session_context[session_id].copy()
        self.navigation_history[session_id].append(current_state)

        # Update current state
        self.session_context[session_id] = {
            'location': location,
            'data': data or {}
        }

        # Limit history size to prevent memory issues
        if len(self.navigation_history[session_id]) > 10:
            self.navigation_history[session_id].pop(0)

    def _pop_navigation_state(self, session_id: int) -> Dict:
        """
        Pop the previous state from the navigation history stack.

        Args:
            session_id: The current session ID

        Returns:
            The previous state or the main menu state if history is empty
        """
        if session_id not in self.navigation_history or not self.navigation_history[session_id]:
            # If no history, return to main menu
            return {'location': 'main_menu', 'data': {}}

        # Pop the last state from history
        previous_state = self.navigation_history[session_id].pop()

        # Check if the previous state is valid
        location = previous_state.get('location', 'main_menu')
        data = previous_state.get('data', {})

        # If we're in product_details and trying to go back to a category
        # but don't have a category_id, go to the products menu
        if location == 'product_category' and 'category_id' not in data:
            # Fallback to products menu
            previous_state = {'location': 'products_menu', 'data': {}}

        # Update current context
        self.session_context[session_id] = previous_state

        return previous_state

    def _get_main_menu_state(self) -> Dict:
        """Get the main menu state."""
        return {'location': 'main_menu', 'data': {}}

    def _handle_navigation(self, session_id: int, state: Dict) -> Dict[str, Any]:
        """
        Handle navigation to a specific state.

        Args:
            session_id: The current session ID
            state: The state to navigate to

        Returns:
            Response for the new state
        """
        location = state.get('location', 'main_menu')
        data = state.get('data', {})
        language = self.session_languages.get(session_id, 'en')

        # Handle different locations
        if location == 'main_menu':
            # Return the main menu response (greeting)
            greeting_response = self.get_response(1, language)  # 1 is the greeting intent ID

            # Customize the main menu based on whether the user is logged in
            if 'buttons' in greeting_response and self.current_customer:
                # Modify the recommendation button text for registered customers
                for button in greeting_response['buttons']:
                    if button.get('value') == 'recommendation':
                        # Change the button text to indicate personalized recommendations
                        if language == 'en':
                            button['text'] = 'Your Personalized Recommendations'
                        elif language == 'ms':
                            button['text'] = 'Cadangan Peribadi Anda'
                        elif language == 'zh':
                            button['text'] = '您的个性化推荐'
                        elif language == 'ta':
                            button['text'] = 'உங்கள் தனிப்பயனாக்கப்பட்ட பரிந்துரைகள்'
                        # Keep the same button value for compatibility

            # Save the bot response
            bot_message_id = self.db.save_message(
                session_id, 'bot', None, greeting_response.get('text', 'Welcome back to the main menu!')
            )

            # Add message_id to the response
            greeting_response['session_id'] = session_id
            greeting_response['message_id'] = bot_message_id

            return greeting_response

        elif location == 'product_category':
            # Return products in the category
            category_id = data.get('category_id')
            if category_id:
                return self._handle_category_selection(session_id, f"category_{category_id}")
            else:
                return self._handle_navigation(session_id, self._get_main_menu_state())

        elif location == 'product_details':
            # Return product details
            product_id = data.get('product_id')
            if product_id:
                return self._handle_product_selection(session_id, f"product_{product_id}")
            else:
                return self._handle_navigation(session_id, self._get_main_menu_state())

        elif location == 'recommendations':
            # Return recommendations
            health_goal = data.get('health_goal')
            if health_goal:
                return self._handle_recommendation_request(session_id, health_goal)
            else:
                return self._handle_navigation(session_id, self._get_main_menu_state())

        elif location == 'personalized_recommendations':
            # Return personalized recommendations for registered customers
            if self.current_customer:
                return self._handle_personalized_recommendations(session_id)
            else:
                # Fallback to regular recommendations for guests
                return self._handle_navigation(session_id, {'location': 'recommendations', 'data': {}})

        elif location == 'products_menu':
            # Show the products menu (categories)
            return self.process_button_click(session_id, 0, 'products')

        elif location == 'order_status':
            # Return order status
            order_id = data.get('order_id')
            if order_id:
                return self._handle_order_status(session_id, f"order_{order_id}")
            else:
                return self._handle_orders_menu(session_id)

        elif location == 'delivery_status':
            # Return delivery status
            order_id = data.get('order_id')
            if order_id:
                return self._handle_delivery_status(session_id, f"delivery_{order_id}")
            else:
                return self._handle_delivery_status_menu(session_id)

        else:
            # Unknown location, return to main menu
            return self._handle_navigation(session_id, self._get_main_menu_state())

    def _handle_category_selection(self, session_id: int, button_value: str) -> Dict[str, Any]:
        """Handle selection of a product category."""
        # Check if the button value is a category selection
        if not button_value.startswith('category_'):
            error_text = 'Invalid category selection'
            language = self.session_languages.get(session_id, 'en')
            if language != 'en':
                error_text = TranslationService.translate(error_text, language)
            return {'error': error_text}

        # Extract category ID from button value
        try:
            category_id = int(button_value.split('_')[1])
        except (IndexError, ValueError):
            error_text = 'Invalid category ID'
            language = self.session_languages.get(session_id, 'en')
            if language != 'en':
                error_text = TranslationService.translate(error_text, language)
            return {'error': error_text}

        # Update navigation state
        self._push_navigation_state(session_id, 'product_category', {'category_id': category_id})

        # Get products in the selected category
        language = self.session_languages.get(session_id, 'en')
        products = self.db.get_products(category_id=category_id, limit=10)

        # Create response text
        category = self.db.execute_query(
            "SELECT name FROM categories WHERE category_id = ?",
            (category_id,)
        )
        category_name = category[0]['name'] if category else "Selected Category"

        if products:
            # Use product cards instead of buttons
            response_text = f"Here are products in the {category_name} category:"
        else:
            # No products found
            response_text = f"Sorry, no products found in the {category_name} category at the moment."

        # Add navigation buttons
        back_text = "Back"
        main_menu_text = "Main Menu"

        if language != 'en':
            back_text = TranslationService.translate(back_text, language)
            main_menu_text = TranslationService.translate(main_menu_text, language)
            response_text = TranslationService.translate(response_text, language)

        buttons = [
            {'text': back_text, 'value': self.BACK_BUTTON},
            {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
        ]

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response_text
        )

        # Create response with product cards
        response = {
            'text': response_text,
            'type': 'products',  # New type for product cards
            'buttons': buttons,
            'products': products,  # Include full product data
            'session_id': session_id,
            'message_id': bot_message_id
        }

        return response

    def _handle_product_selection(self, session_id: int, button_value: str) -> Dict[str, Any]:
        """Handle selection of a product."""
        # Extract product ID from button value
        product_id = int(button_value.split('_')[1])

        # Update navigation state
        self._push_navigation_state(session_id, 'product_details', {'product_id': product_id})

        # Get product details
        language = self.session_languages.get(session_id, 'en')
        product = self.db.get_product(product_id)

        if product:
            # Create product text in English
            product_text = f"**{product['name']}**\n\n"
            product_text += f"**Price:** RM{product['price']}\n"
            product_text += f"**Brand:** {product['brand']}\n\n"
            product_text += f"**Description:** {product['description']}\n\n"
            product_text += f"**Health Benefits:** {product['health_benefits']}\n\n"
            product_text += f"**Ingredients:** {product['ingredients']}\n\n"
            product_text += f"**Usage Instructions:** {product['usage_instructions']}\n\n"

            # Add navigation options
            back_text = "Back to Category"
            main_menu_text = "Main Menu"
            add_to_cart_text = "Add to Cart"

            if language != 'en':
                back_text = TranslationService.translate(back_text, language)
                main_menu_text = TranslationService.translate(main_menu_text, language)
                add_to_cart_text = TranslationService.translate(add_to_cart_text, language)

            # No longer adding navigation text to product description

            # Translate if needed
            if language != 'en':
                # Translate field labels
                price_label = TranslationService.translate("Price", language)
                brand_label = TranslationService.translate("Brand", language)
                description_label = TranslationService.translate("Description", language)
                benefits_label = TranslationService.translate("Health Benefits", language)
                ingredients_label = TranslationService.translate("Ingredients", language)
                usage_label = TranslationService.translate("Usage Instructions", language)

                # Translate product details
                # Note: We're not translating the product name, brand, or price as these are proper nouns
                description = TranslationService.translate(product['description'], language)
                benefits = TranslationService.translate(product['health_benefits'], language)
                ingredients = TranslationService.translate(product['ingredients'], language)
                usage = TranslationService.translate(product['usage_instructions'], language)

                # Create translated product text
                product_text = f"**{product['name']}**\n\n"
                product_text += f"**{price_label}:** RM{product['price']}\n"
                product_text += f"**{brand_label}:** {product['brand']}\n\n"
                product_text += f"**{description_label}:** {description}\n\n"
                product_text += f"**{benefits_label}:** {benefits}\n\n"
                product_text += f"**{ingredients_label}:** {ingredients}\n\n"
                product_text += f"**{usage_label}:** {usage}\n\n"
                # No longer adding navigation text to product description

            # Create buttons for navigation and actions
            buttons = [
                {'text': back_text, 'value': self.BACK_BUTTON},
                {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
            ]

            # Only show Add to Cart button for logged-in users
            if self.current_customer:
                buttons.append({'text': add_to_cart_text, 'value': f"add_to_cart_{product_id}"})
            else:
                # For guests, show a login prompt button
                login_text = "Login to Add to Cart"
                if language != 'en':
                    login_text = TranslationService.translate(login_text, language)
                buttons.append({'text': login_text, 'value': f"login_for_cart_{product_id}"})

            response = {
                'text': product_text,
                'type': 'buttons',
                'buttons': buttons,
                'original_language': 'en'
            }
        else:
            error_text = 'Sorry, I could not find that product.'
            if language != 'en':
                error_text = TranslationService.translate(error_text, language)

            response = {
                'text': error_text,
                'type': 'text',
                'original_language': 'en'
            }

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response['text']
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def _handle_recommendation_request(self, session_id: int, goal_id: str) -> Dict[str, Any]:
        """Handle a recommendation request based on a standard goal ID."""
        # Update navigation state
        self._push_navigation_state(session_id, 'recommendations', {'goal_id': goal_id})

        # Get the standard goal details
        standard_goals = get_all_standard_goals()
        goal_obj = next((goal for goal in standard_goals if goal['id'] == goal_id), None)
        goal_name = goal_obj['name'] if goal_obj else goal_id

        # Get personalized recommendations - use a higher limit to show more products
        language = self.session_languages.get(session_id, 'en')
        recommendations = self.get_product_recommendations(
            customer_id=self.current_customer,
            goal_id=goal_id,
            session_id=session_id,
            limit=10  # Increased from 3 to show more products
        )

        if recommendations:
            # Create response with recommended products
            if self.current_customer:
                # Get order history to check if this is a new customer
                order_history = self._get_order_history_products(self.current_customer)

                if order_history:
                    # Personalized message for customers with order history
                    response_text = f"Based on your previous purchases and {goal_name} goal, here are some personalized recommendations:"
                else:
                    # Check if we have preferences
                    prefs = self.db.get_customer_preferences(self.current_customer)
                    if prefs and prefs['preferred_categories']:
                        # Message for customers with preferences but no order history
                        response_text = f"Based on your profile and {goal_name} goal, here are some personalized recommendations:"
                    else:
                        # Message for new customers with minimal profile information
                        response_text = f"Here are our top recommendations for your {goal_name} goal:"
            else:
                # Generic message for guests
                response_text = f"Here are some recommendations for your {goal_name} goal:"

            if language != 'en':
                response_text = TranslationService.translate(response_text, language)

            # Add navigation buttons
            back_text = "Back"
            main_menu_text = "Main Menu"

            if language != 'en':
                back_text = TranslationService.translate(back_text, language)
                main_menu_text = TranslationService.translate(main_menu_text, language)

            buttons = [
                {'text': back_text, 'value': self.BACK_BUTTON},
                {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
            ]

            response = {
                'text': response_text,
                'type': 'products',  # Use product cards
                'buttons': buttons,
                'products': recommendations  # Include full product data
            }
        else:
            response_text = f"I couldn't find any products matching your {goal_name} goal. Would you like to browse our categories instead?"
            if language != 'en':
                response_text = TranslationService.translate(response_text, language)

            response = {
                'text': response_text,
                'type': 'buttons',
                'buttons': [
                    {'text': 'Browse Categories', 'value': 'products'},
                    {'text': TranslationService.translate('Main Menu', language) if language != 'en' else 'Main Menu',
                     'value': self.MAIN_MENU_BUTTON}
                ]
            }

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response['text']
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def _handle_personalized_recommendations(self, session_id: int) -> Dict[str, Any]:
        """
        Handle personalized recommendations for registered customers.
        This provides a more personalized experience without requiring health goal selection.
        """
        # Update navigation state
        self._push_navigation_state(session_id, 'personalized_recommendations', {})

        language = self.session_languages.get(session_id, 'en')

        # Get customer preferences and order history
        prefs = self.db.get_customer_preferences(self.current_customer)
        order_history = self._get_order_history_products(self.current_customer)

        # Determine health goal from preferences if available
        health_goal = None
        if prefs and prefs['health_goal']:
            health_goal = prefs['health_goal']

        # Get personalized recommendations
        recommendations = self.get_product_recommendations(
            customer_id=self.current_customer,
            health_goal=health_goal,
            session_id=session_id,
            limit=5  # Show more recommendations for registered customers
        )

        if recommendations:
            # Create personalized response based on customer data
            if order_history:
                # Customer with order history gets the most personalized experience
                response_text = "Here are your personalized recommendations based on your previous purchases:"
            elif prefs and prefs['preferred_categories']:
                # Customer with preferences but no order history
                response_text = "Based on your profile preferences, here are some products you might like:"
            else:
                # New customer with minimal profile information
                response_text = "Welcome! Here are some popular products we think you might enjoy:"

            if language != 'en':
                response_text = TranslationService.translate(response_text, language)

            # Add navigation buttons
            main_menu_text = "Main Menu"
            explore_more_text = "Explore More Options"

            if language != 'en':
                main_menu_text = TranslationService.translate(main_menu_text, language)
                explore_more_text = TranslationService.translate(explore_more_text, language)

            # Different button value for registered customers vs guests
            explore_button_value = 'explore_more_registered' if self.current_customer else 'recommendation'

            buttons = [
                {'text': explore_more_text, 'value': explore_button_value},
                {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
            ]

            response = {
                'text': response_text,
                'type': 'products',  # Use product cards
                'buttons': buttons,
                'products': recommendations  # Include full product data
            }
        else:
            # Fallback if no recommendations could be generated
            response_text = "I'd like to recommend products tailored to your preferences. What are you looking for?"
            if language != 'en':
                response_text = TranslationService.translate(response_text, language)

            # Get standard health goals from our module
            standard_goals = get_all_standard_goals()

            # Create buttons for each standard goal
            goal_buttons = []
            for goal in standard_goals:
                button_text = goal['name']
                if language != 'en':
                    button_text = TranslationService.translate(button_text, language)
                goal_buttons.append({'text': button_text, 'value': goal['id']})

            # Add main menu button
            goal_buttons.append({
                'text': TranslationService.translate('Main Menu', language) if language != 'en' else 'Main Menu',
                'value': self.MAIN_MENU_BUTTON
            })

            response = {
                'text': response_text,
                'type': 'buttons',
                'buttons': goal_buttons
            }

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response['text']
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def _handle_orders_menu(self, session_id: int) -> Dict[str, Any]:
        """Handle the orders menu."""
        # Update navigation state
        self._push_navigation_state(session_id, 'order_status', {})

        language = self.session_languages.get(session_id, 'en')

        # Check if user is logged in
        if not self.current_customer:
            # User is not logged in, prompt to login or register
            return self._handle_login_register_prompt(session_id, 'order_status')

        # User is logged in, get their recent orders
        orders = self.db.get_customer_orders(self.current_customer)

        if orders:
            buttons = []
            for order in orders:
                buttons.append({
                    'text': f"Order #{order['order_id']} ({order['status']})",
                    'value': f"order_{order['order_id']}"
                })

            # Add navigation buttons
            back_text = "Back"
            main_menu_text = "Main Menu"

            if language != 'en':
                back_text = TranslationService.translate(back_text, language)
                main_menu_text = TranslationService.translate(main_menu_text, language)

            buttons.append({'text': back_text, 'value': self.BACK_BUTTON})
            buttons.append({'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON})

            response_text = "Here are your recent orders:"
            if language != 'en':
                response_text = TranslationService.translate(response_text, language)

            response = {
                'text': response_text,
                'type': 'buttons',
                'buttons': buttons
            }
        else:
            response_text = "You don't have any recent orders. Would you like to browse our products?"
            if language != 'en':
                response_text = TranslationService.translate(response_text, language)

            response = {
                'text': response_text,
                'type': 'buttons',
                'buttons': [
                    {'text': TranslationService.translate('Browse Products', language) if language != 'en' else 'Browse Products',
                     'value': 'products'},
                    {'text': TranslationService.translate('Main Menu', language) if language != 'en' else 'Main Menu',
                     'value': self.MAIN_MENU_BUTTON}
                ]
            }

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response['text']
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def _handle_delivery_status_menu(self, session_id: int) -> Dict[str, Any]:
        """Handle the delivery status menu."""
        # Update navigation state
        self._push_navigation_state(session_id, 'delivery_status', {})

        language = self.session_languages.get(session_id, 'en')

        # Check if user is logged in
        if not self.current_customer:
            # User is not logged in, prompt to login or register
            return self._handle_login_register_prompt(session_id, 'order_status')

        # User is logged in, get their recent orders
        orders = self.db.get_customer_orders(self.current_customer)

        if orders:
            buttons = []
            for order in orders:
                # Get order details including both order status and delivery status
                order_details = self.db.get_order(order['order_id'])
                order_status = order_details.get('status', 'pending')
                delivery_status = order_details.get('delivery_status', 'not_shipped')

                # Make sure we display "not_shipped" if there's no delivery status
                if not delivery_status:
                    delivery_status = 'not_shipped'

                # Get courier company if available
                courier_company = None
                if delivery_status.lower() in ['picked_up', 'in_transit', 'out_for_delivery', 'delivered']:
                    # Query for courier company
                    courier_result = self.db.execute_query('''
                        SELECT courier_company
                        FROM delivery_status
                        WHERE order_id = ? AND courier_company IS NOT NULL
                        ORDER BY status_date DESC
                        LIMIT 1
                    ''', (order['order_id'],))

                    if courier_result and courier_result[0]['courier_company']:
                        courier_company = courier_result[0]['courier_company']

                # Create status emoji based on delivery status
                status_emoji = self._get_delivery_status_emoji(delivery_status)

                # Create display text for delivery status
                delivery_display = self._format_delivery_status(delivery_status)

                # Simplified button text - include courier for shipped orders
                button_text = f"{status_emoji} Order #{order['order_id']} - {delivery_display}"
                if courier_company and delivery_status.lower() in ['picked_up', 'in_transit', 'out_for_delivery', 'delivered']:
                    button_text = f"{status_emoji} Order #{order['order_id']} - {delivery_display} ({courier_company})"

                buttons.append({
                    'text': button_text,
                    'value': f"delivery_{order['order_id']}"
                })

            # Add navigation buttons
            back_text = "Back"
            main_menu_text = "Main Menu"

            if language != 'en':
                back_text = TranslationService.translate(back_text, language)
                main_menu_text = TranslationService.translate(main_menu_text, language)

            buttons.append({'text': back_text, 'value': self.BACK_BUTTON})
            buttons.append({'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON})

            response_text = "🚚 **Your Delivery Status**\n\nHere are the delivery statuses for your recent orders. Select an order to view shipping details:"
            if language != 'en':
                base_text = "Here are the delivery statuses for your recent orders. Select an order to view shipping details:"
                translated_text = TranslationService.translate(base_text, language)
                response_text = f"🚚 **{TranslationService.translate('Your Delivery Status', language)}**\n\n{translated_text}"

            response = {
                'text': response_text,
                'type': 'buttons',
                'buttons': buttons
            }
        else:
            response_text = "📦 **Order Status**\n\nYou don't have any recent orders to check delivery status. Would you like to browse our products?"
            if language != 'en':
                base_text = "You don't have any recent orders to check delivery status. Would you like to browse our products?"
                translated_text = TranslationService.translate(base_text, language)
                response_text = f"📦 **{TranslationService.translate('Order Status', language)}**\n\n{translated_text}"

            response = {
                'text': response_text,
                'type': 'buttons',
                'buttons': [
                    {'text': TranslationService.translate('Browse Products', language) if language != 'en' else 'Browse Products',
                     'value': 'products'},
                    {'text': TranslationService.translate('Main Menu', language) if language != 'en' else 'Main Menu',
                     'value': self.MAIN_MENU_BUTTON}
                ]
            }

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response['text']
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def _get_delivery_status_emoji(self, delivery_status: str) -> str:
        """Get emoji for delivery status."""
        status_emojis = {
            'not_shipped': '📦',
            'picked_up': '📋',
            'in_transit': '🚚',
            'out_for_delivery': '🚛',
            'delivered': '✅',
            'failed_delivery': '❌',
            'returned': '↩️'
        }
        return status_emojis.get(delivery_status.lower(), '📦')

    def _format_delivery_status(self, delivery_status: str) -> str:
        """Format delivery status for display."""
        status_display = {
            'not_shipped': 'Not Shipped',
            'picked_up': 'Picked Up',
            'in_transit': 'In Transit',
            'out_for_delivery': 'Out for Delivery',
            'delivered': 'Delivered',
            'failed_delivery': 'Failed Delivery',
            'returned': 'Returned'
        }
        return status_display.get(delivery_status.lower(), delivery_status.title())

    def _get_order_status_emoji(self, order_status: str) -> str:
        """Get emoji for order status."""
        status_emojis = {
            'pending': '⏳',
            'confirmed': '✅',
            'preparing': '👨‍🍳',
            'ready_to_ship': '📦',
            'completed': '🎉',
            'cancelled': '❌',
            'refunded': '💰'
        }
        return status_emojis.get(order_status.lower(), '📋')

    def _format_order_status(self, order_status: str) -> str:
        """Format order status for display."""
        status_display = {
            'pending': 'Pending Payment',
            'confirmed': 'Confirmed',
            'preparing': 'Preparing Order',
            'ready_to_ship': 'Ready to Ship',
            'completed': 'Completed',
            'cancelled': 'Cancelled',
            'refunded': 'Refunded'
        }
        return status_display.get(order_status.lower(), order_status.title())

    def _handle_login_register_prompt(self, session_id: int, feature: str, product_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Handle prompting the user to login or register to access a feature.

        Args:
            session_id: The ID of the chat session
            feature: The feature the user is trying to access (for context)
            product_id: Optional product ID (for cart-related features)

        Returns:
            Response with login/register buttons
        """
        language = self.session_languages.get(session_id, 'en')

        # Create the prompt message
        if feature == 'order_status':
            response_text = "You need to be logged in to check your order status. Please login or register first."
        elif feature == 'agent':
            response_text = "You need to be logged in to speak with an agent. Please login or register first."
        elif feature == 'cart':
            response_text = "You need to be logged in to add products to your cart. Please login or register first."
        else:
            response_text = "You need to be logged in to access this feature. Please login or register first."

        if language != 'en':
            response_text = TranslationService.translate(response_text, language)

        # Create login/register buttons
        login_text = "Login"
        register_text = "Register"
        main_menu_text = "Main Menu"

        if language != 'en':
            login_text = TranslationService.translate(login_text, language)
            register_text = TranslationService.translate(register_text, language)
            main_menu_text = TranslationService.translate(main_menu_text, language)

        buttons = [
            {'text': login_text, 'value': 'login_redirect'},
            {'text': register_text, 'value': 'register_redirect'},
            {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
        ]

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response_text
        )

        # Create the response
        response = {
            'text': response_text,
            'type': 'buttons',
            'buttons': buttons,
            'session_id': session_id,
            'message_id': bot_message_id
        }

        return response

    def _handle_delivery_status(self, session_id: int, button_value: str) -> Dict[str, Any]:
        """Handle delivery status request - shows only shipping/logistics information."""
        # Extract order ID from button value
        order_id = int(button_value.split('_')[1])

        # Update navigation state
        self._push_navigation_state(session_id, 'delivery_status', {'order_id': order_id})

        language = self.session_languages.get(session_id, 'en')
        order = self.db.get_order(order_id)

        if order:
            # Get delivery status
            delivery_status = order.get('delivery_status', 'not_shipped')

            # Create delivery-focused display
            delivery_emoji = self._get_delivery_status_emoji(delivery_status)
            delivery_text = f"{delivery_emoji} **Delivery Status - Order #{order['order_id']}**\n\n"

            # Delivery Status Section (Logistics Only)
            delivery_status_display = self._format_delivery_status(delivery_status)
            delivery_text += f"🚚 **Current Status:** {delivery_status_display}\n"

            # Add tracking number if available
            if order['tracking_number']:
                delivery_text += f"📍 **Tracking Number:** {order['tracking_number']}\n"

            # Get the latest delivery status details
            latest_status = self.db.execute_query('''
                SELECT status, status_date, location, courier_company
                FROM delivery_status
                WHERE order_id = ?
                ORDER BY status_date DESC
                LIMIT 1
            ''', (order_id,))

            # Get courier company and detailed info
            if latest_status:
                latest_status_info = latest_status[0]

                if latest_status_info['courier_company']:
                    delivery_text += f"📦 **Courier:** {latest_status_info['courier_company']}\n"

                # Format the date for better readability
                date_parts = latest_status_info['status_date'].split(' ')
                if len(date_parts) == 2:
                    date = date_parts[0]
                else:
                    date = latest_status_info['status_date']

                delivery_text += f"📅 **Last Updated:** {date}\n"

                # Include location if available
                if latest_status_info['location']:
                    delivery_text += f"📍 **Current Location:** {latest_status_info['location']}\n"

            # Add helpful delivery information based on status
            if delivery_status.lower() == 'not_shipped':
                delivery_text += "\n💡 Your order is being prepared for shipment."
            elif delivery_status.lower() == 'picked_up':
                delivery_text += "\n💡 Your order has been picked up by the courier."
            elif delivery_status.lower() == 'in_transit':
                delivery_text += "\n💡 Your order is on its way to you."
            elif delivery_status.lower() == 'out_for_delivery':
                delivery_text += "\n💡 Your order is out for delivery today."
            elif delivery_status.lower() == 'delivered':
                delivery_text += "\n✅ Your order has been successfully delivered!"

            # Translate if needed
            if language != 'en':
                # Translate the delivery text
                delivery_text = TranslationService.translate(delivery_text, language)

            # Create buttons for navigation
            back_text = "Back to Delivery List"
            main_menu_text = "Main Menu"

            if language != 'en':
                back_text = TranslationService.translate(back_text, language)
                main_menu_text = TranslationService.translate(main_menu_text, language)

            buttons = [
                {'text': back_text, 'value': self.BACK_BUTTON},
                {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
            ]

            response = {
                'text': delivery_text,
                'type': 'buttons',
                'buttons': buttons
            }
        else:
            error_text = 'Sorry, I could not find that order.'
            if language != 'en':
                error_text = TranslationService.translate(error_text, language)

            response = {
                'text': error_text,
                'type': 'buttons',
                'buttons': [
                    {'text': TranslationService.translate('Main Menu', language) if language != 'en' else 'Main Menu',
                     'value': self.MAIN_MENU_BUTTON}
                ]
            }

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response['text']
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def _handle_order_status(self, session_id: int, button_value: str) -> Dict[str, Any]:
        """Handle order status request."""
        # Extract order ID from button value
        order_id = int(button_value.split('_')[1])

        # Update navigation state
        self._push_navigation_state(session_id, 'order_status', {'order_id': order_id})

        language = self.session_languages.get(session_id, 'en')
        order = self.db.get_order(order_id)

        if order:
            # Create a cleaner, more structured order display with better spacing
            order_text = f"📦 **Order #{order['order_id']}**\n\n"

            # Get order status only
            order_status = order.get('status', 'pending')

            # Order Status Section (Business Only)
            order_status_emoji = self._get_order_status_emoji(order_status)
            order_status_display = self._format_order_status(order_status)

            order_text += f"{order_status_emoji} **Order Status:** {order_status_display}\n"
            order_text += f"📅 **Order Date:** {order['order_date']}\n"
            order_text += f"💳 **Payment Status:** {order['payment_status'].capitalize()}\n"

            # Add shipping address if available
            if order['shipping_address']:
                order_text += f"\n📍 **Shipping Address:**\n{order['shipping_address']}\n"

            # Add order notes if available
            if order['notes']:
                order_text += f"\n📝 **Notes:** {order['notes']}\n"

            # Items section - with better spacing
            order_text += "\n🛒 **Order Items**\n"
            for item in order['items']:
                order_text += f"• {item['product_name']}\n  x{item['quantity']} - RM{item['subtotal']}\n"

            # Total section
            order_text += f"\n💰 **Total Amount: RM{order['total_amount']}**"

            # Add navigation options
            back_text = "Back to Orders"
            main_menu_text = "Main Menu"

            if language != 'en':
                # Translate field labels
                date_label = TranslationService.translate("Date", language)
                status_label = TranslationService.translate("Status", language)
                payment_label = TranslationService.translate("Payment Status", language)
                delivery_label = TranslationService.translate("Delivery Status", language)
                tracking_label = TranslationService.translate("Tracking Number", language)
                items_label = TranslationService.translate("Items", language)
                total_label = TranslationService.translate("Total", language)

                # Translate status values
                status = TranslationService.translate(order['status'], language)
                payment_status = TranslationService.translate(order['payment_status'], language)
                delivery_status = TranslationService.translate(order['delivery_status'], language) if order['delivery_status'] else None

                # Translate section headers
                order_details_label = TranslationService.translate("Order Details", language)
                delivery_info_label = TranslationService.translate("Delivery Information", language)
                order_items_label = TranslationService.translate("Order Items", language)
                total_amount_label = TranslationService.translate("Total Amount", language)
                current_status_label = TranslationService.translate("Current Status", language)

                # Create translated order text with improved formatting and better spacing
                order_text = f"📦 **Order #{order['order_id']}**\n\n"

                # Order details section - simplified with line breaks
                order_text += f"📅 **{order_details_label}**\n"
                order_text += f"{date_label}: {order['order_date']}\n"
                order_text += f"{status_label}: {status}\n"
                order_text += f"{payment_label}: {payment_status}\n"

                # Delivery section - simplified
                order_text += f"\n🚚 **{delivery_info_label}**\n"
                if delivery_status:
                    order_text += f"{current_status_label}: {delivery_status}\n"
                if order['tracking_number']:
                    order_text += f"{tracking_label}: {order['tracking_number']}\n"

                # Get the latest delivery status
                latest_status = self.db.execute_query('''
                    SELECT status, status_date, location, courier_company
                    FROM delivery_status
                    WHERE order_id = ?
                    ORDER BY status_date DESC
                    LIMIT 1
                ''', (order_id,))

                # Get courier company from the latest status
                courier_company = None
                latest_status_info = None
                if latest_status:
                    latest_status_info = latest_status[0]
                    if latest_status_info['courier_company']:
                        courier_company = latest_status_info['courier_company']

                # Add shipping status information
                if latest_status_info:
                    # Translate labels
                    shipping_status_label = TranslationService.translate("Shipping Status", language)
                    courier_label = TranslationService.translate("Courier", language)
                    status_label = TranslationService.translate("Status", language)
                    date_label = TranslationService.translate("Date", language)
                    location_label = TranslationService.translate("Location", language)

                    order_text += f"\n📋 **{shipping_status_label}**\n"
                    if courier_company:
                        order_text += f"{courier_label}: {courier_company}\n"

                    # Translate status
                    status_translated = TranslationService.translate(latest_status_info['status'], language)

                    # Format the date for better readability
                    date_parts = latest_status_info['status_date'].split(' ')
                    if len(date_parts) == 2:
                        date = date_parts[0]
                    else:
                        date = latest_status_info['status_date']

                    # Add status information
                    order_text += f"{status_label}: {status_translated.capitalize()}\n"
                    order_text += f"{date_label}: {date}\n"

                    # Include location if available
                    if latest_status_info['location']:
                        location_translated = TranslationService.translate(latest_status_info['location'], language)
                        order_text += f"{location_label}: {location_translated}\n"

                # Items section - with better spacing
                order_text += f"\n🛒 **{order_items_label}**\n"
                for item in order['items']:
                    product_name = TranslationService.translate(item['product_name'], language)
                    order_text += f"• {product_name}\n  x{item['quantity']} - RM{item['subtotal']}\n"

                # Total section
                order_text += f"\n💰 **{total_amount_label}: RM{order['total_amount']}**"

                back_text = TranslationService.translate(back_text, language)
                main_menu_text = TranslationService.translate(main_menu_text, language)

            # Create buttons for navigation
            buttons = [
                {'text': back_text, 'value': self.BACK_BUTTON},
                {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
            ]

            response = {
                'text': order_text,
                'type': 'buttons',
                'buttons': buttons
            }
        else:
            error_text = 'Sorry, I could not find that order.'
            if language != 'en':
                error_text = TranslationService.translate(error_text, language)

            response = {
                'text': error_text,
                'type': 'buttons',
                'buttons': [
                    {'text': TranslationService.translate('Main Menu', language) if language != 'en' else 'Main Menu',
                     'value': self.MAIN_MENU_BUTTON}
                ]
            }

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response['text']
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def _handle_explore_more_registered(self, session_id: int) -> Dict[str, Any]:
        """
        Handle 'Explore More Options' for registered customers.
        Provides different recommendation categories and browsing options.
        """
        # Update navigation state
        self._push_navigation_state(session_id, 'explore_more_registered', {})

        language = self.session_languages.get(session_id, 'en')

        # Create response text
        response_text = "🔍 **Explore More Options**\n\nWhat would you like to discover today?"

        if language != 'en':
            response_text = TranslationService.translate(response_text, language)

        # Create exploration options for registered customers
        buttons = []

        # Health goal-based recommendations
        health_goals = [
            {'text': '💪 Muscle Building', 'value': 'muscle_building'},
            {'text': '⚖️ Weight Management', 'value': 'weight_management'},
            {'text': '⚡ Energy & Performance', 'value': 'energy_performance'},
            {'text': '🌿 General Health', 'value': 'general_health'},
            {'text': '🔄 Recovery', 'value': 'recovery'}
        ]

        for goal in health_goals:
            if language != 'en':
                goal_text = TranslationService.translate(goal['text'], language)
            else:
                goal_text = goal['text']
            buttons.append({'text': goal_text, 'value': goal['value']})

        # Add other exploration options
        other_options = [
            {'text': '🏆 Bestsellers', 'value': 'bestsellers'},
            {'text': '📦 Browse All Products', 'value': 'products'},
            {'text': '🎯 Your Personalized Picks', 'value': 'recommendation'}
        ]

        for option in other_options:
            if language != 'en':
                option_text = TranslationService.translate(option['text'], language)
            else:
                option_text = option['text']
            buttons.append({'text': option_text, 'value': option['value']})

        # Add navigation buttons
        back_text = "Back"
        main_menu_text = "Main Menu"

        if language != 'en':
            back_text = TranslationService.translate(back_text, language)
            main_menu_text = TranslationService.translate(main_menu_text, language)

        buttons.extend([
            {'text': back_text, 'value': self.BACK_BUTTON},
            {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
        ])

        response = {
            'text': response_text,
            'type': 'buttons',
            'buttons': buttons
        }

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response['text']
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def identify_intent(self, user_input: str, language: str = 'en') -> Tuple[Optional[int], float]:
        """
        Identify the intent from user input.

        Returns:
        - intent_id: The identified intent ID or None if no intent was identified
        - confidence: A confidence score between 0 and 1
        """
        # Get all intent patterns for the specified language
        patterns = self.db.get_intent_patterns(language=language)

        # Find the best match
        best_match = None
        best_score = 0.0

        for pattern in patterns:
            # Simple exact match (case insensitive)
            if pattern['pattern'].lower() in user_input.lower():
                # Score based on the length of the pattern relative to the input
                score = len(pattern['pattern']) / len(user_input)
                if score > best_score:
                    best_score = score
                    best_match = pattern

        # If no match in the specified language, try English as fallback
        if not best_match and language != 'en':
            patterns = self.db.get_intent_patterns(language='en')

            for pattern in patterns:
                if pattern['pattern'].lower() in user_input.lower():
                    score = len(pattern['pattern']) / len(user_input)
                    if score > best_score:
                        best_score = score
                        best_match = pattern

        if best_match:
            return best_match['intent_id'], best_score
        else:
            return None, 0.0

    def get_response(self, intent_id: int, language: str = 'en') -> Dict[str, Any]:
        """
        Get a response for the identified intent.

        Returns a dictionary with:
        - response_id: The ID of the response
        - text: The response text
        - type: The response type (text, buttons, etc.)
        - buttons: Optional list of buttons if type is 'buttons'
        - original_language: The language of the original response
        """
        # Always get responses in English (client-side translation approach)
        responses = self.db.get_responses(intent_id=intent_id, language='en')

        if responses:
            # Randomly select one of the available responses for variety
            response = random.choice(responses)

            # Get the response text and translate it if needed
            response_text = response['response_text']
            if language != 'en':
                response_text = TranslationService.translate(response_text, language)

            result = {
                'response_id': response['response_id'],
                'text': response_text,
                'type': response['response_type'],
                'original_language': 'en'
            }

            # Handle button options
            if response['button_options']:
                buttons = json.loads(response['button_options'])

                # Customize buttons for registered customers
                if self.current_customer and intent_id == 1:  # Main menu intent
                    for button in buttons:
                        if button.get('value') == 'recommendation':
                            # Change the button text to indicate personalized recommendations
                            if language == 'en':
                                button['text'] = 'Your Personalized Recommendations'
                            elif language == 'ms':
                                button['text'] = 'Cadangan Peribadi Anda'
                            elif language == 'zh':
                                button['text'] = '您的个性化推荐'
                            elif language == 'ta':
                                button['text'] = 'உங்கள் தனிப்பயனாக்கப்பட்ட பரிந்துரைகள்'

                if language != 'en':
                    # Translate button text but keep the values
                    buttons = TranslationService.translate_button_options(buttons, language)
                result['buttons'] = buttons

            return result
        else:
            # Default fallback response
            fallback_response = "I'm sorry, I don't understand. Could you please rephrase or select an option?"

            # Translate the fallback response
            if language != 'en':
                fallback_response = TranslationService.translate(fallback_response, language)

            return {
                'response_id': None,
                'text': fallback_response,
                'type': 'text',
                'original_language': 'en'
            }

    def get_faq_answer(self, question: str, language: str = 'en') -> Optional[str]:
        """
        Get an answer to a FAQ.

        Uses a simple keyword matching algorithm to find the most relevant FAQ.
        With client-side translation, we only search English FAQs and translate the result.
        """
        # Always get FAQs in English (client-side translation approach)
        faqs = self.db.get_faqs(language='en')

        # Debug output
        print(f"Found {len(faqs)} FAQs in the database")

        # If no FAQs in database, return None
        if not faqs:
            print("No FAQs found in database")
            return None

        # Find the best match
        best_match = None
        best_score = 0.0

        # If the question is not in English, we need to handle it differently
        # In a real implementation, we would translate the question to English first
        # For this demo, we'll just do our best with the original question

        for faq in faqs:
            # Simple word matching score
            question_words = set(re.findall(r'\w+', question.lower()))
            faq_words = set(re.findall(r'\w+', faq['question'].lower()))

            print(f"Comparing: '{question}' with FAQ: '{faq['question']}'")
            print(f"Question words: {question_words}")
            print(f"FAQ words: {faq_words}")

            common_words = question_words.intersection(faq_words)
            if common_words:
                score = len(common_words) / len(faq_words)
                print(f"Common words: {common_words}, Score: {score}")
                if score > best_score:
                    best_score = score
                    best_match = faq

        print(f"Best match: {best_match['question'] if best_match else None}, Score: {best_score}")

        if best_match and best_score > 0.3:  # Lower threshold for considering it a match
            answer = best_match['answer']
            print(f"Returning answer: {answer}")

            # Translate the answer if needed
            if language != 'en':
                answer = TranslationService.translate(answer, language)

            return answer
        else:
            print("No good match found")
            return None

    def get_product_recommendations(self, customer_id: Optional[int] = None,
                                   goal_id: Optional[str] = None,
                                   health_goal: Optional[str] = None,  # For backward compatibility
                                   category_id: Optional[int] = None,
                                   session_id: Optional[int] = None,
                                   limit: int = 3) -> List[Dict[str, Any]]:
        """
        Get personalized product recommendations.

        For registered customers:
        - Uses stored customer preferences
        - Considers purchase history
        - Provides highly personalized recommendations

        For guests:
        - Uses current session context
        - Considers browsing behavior
        - Provides more generic recommendations
        - Offers bestsellers for undecided customers

        Parameters:
        - customer_id: ID of the registered customer (None for guests)
        - health_goal: Health goal mentioned in the conversation
        - category_id: Category being browsed
        - session_id: Current chat session ID (for tracking guest preferences)
        - limit: Maximum number of recommendations to return
        """
        # Start with empty products list
        products = []
        recommendation_source = "generic"  # Track the source of recommendations for logging

        # If we have a goal_id, use it to find matching products
        if goal_id:
            # Get all products - use a higher limit to ensure we get all relevant products
            all_products = self.db.get_products(limit=100)  # Increased from limit*3 to get more products
            # Use our health goals matching system
            products = match_user_goal_to_products(goal_id, all_products)
            if products:
                recommendation_source = "standard_goal_match"
                # Don't limit the products yet - we want to show all matching products

        # REGISTERED CUSTOMER RECOMMENDATIONS
        if customer_id:
            # Get customer preferences from database
            prefs = self.db.get_customer_preferences(customer_id)

            # First, check order history for this customer
            order_history_products = self._get_order_history_products(customer_id)
            if order_history_products:
                recommendation_source = "order_history"

                # Get products similar to previously purchased ones
                for product_id in order_history_products:
                    product = self.db.get_product(product_id)
                    if product and product['category_id']:
                        # Get similar products in the same category
                        similar_products = self.db.get_products(category_id=product['category_id'], limit=2)
                        # Only add products that haven't been purchased before
                        for p in similar_products:
                            if p['product_id'] not in order_history_products and p not in products:
                                products.append(p)

                        if len(products) >= limit:
                            break

            # If we don't have enough from order history, use preferences
            if len(products) < limit and prefs:
                recommendation_source = "customer_preferences"

                # Use stored health goal if none provided in current conversation
                if health_goal is None and prefs['health_goal']:
                    health_goal = prefs['health_goal']

                # Get products matching the customer's preferred categories
                if prefs['preferred_categories']:
                    # Get products from preferred categories
                    category_products = self.db.get_products(limit=limit*2)  # Get more for better filtering

                    # Filter by health goal if available
                    if health_goal:
                        health_matches = [p for p in category_products
                                        if p['health_benefits'] and
                                        health_goal.lower() in p['health_benefits'].lower() and
                                        prefs['preferred_categories'].lower() in p['description'].lower() and
                                        p not in products]
                        products.extend(health_matches[:limit-len(products)])

                    # Add category matches if we don't have enough
                    if len(products) < limit:
                        category_matches = [p for p in category_products
                                          if prefs['preferred_categories'].lower() in p['description'].lower() and
                                          p not in products]
                        products.extend(category_matches[:limit-len(products)])

            # For new customers with no order history and limited preferences
            # Add popular products for their health goal
            if len(products) < limit and health_goal:
                recommendation_source = "new_customer_recommendations"

                # Get popular products
                popular_products = self.db.get_bestselling_products(limit=limit*2)

                # Filter popular products by health goal if available
                if popular_products:
                    goal_popular_products = [p for p in popular_products
                                          if p['health_benefits'] and
                                          health_goal.lower() in p['health_benefits'].lower() and
                                          p not in products]
                    products.extend(goal_popular_products[:limit-len(products)])

        # GUEST RECOMMENDATIONS
        else:
            # If we already have products from the standard goal matching, skip this section
            if not products:
                recommendation_source = "guest_session"

                # For guests, we rely more on the current context

                # If we have a health goal from the current conversation, use it (backward compatibility)
                if health_goal:
                    goal_products = self.db.get_products(limit=limit*2)
                    health_matches = [p for p in goal_products
                                    if p['health_benefits'] and
                                    health_goal.lower() in p['health_benefits'].lower()]
                    products.extend(health_matches[:limit])

            # If we have a category from current browsing, use it
            if category_id and len(products) < limit:
                category_products = self.db.get_products(category_id=category_id, limit=limit*2)
                products.extend([p for p in category_products if p not in products][:limit-len(products)])

            # If we have a session, check for previous interactions to infer preferences
            if session_id and len(products) < limit:
                # Get previous product interactions in this session
                previous_interactions = self._get_session_product_interactions(session_id)

                if previous_interactions:
                    # Get products similar to previously viewed ones
                    for product_id in previous_interactions:
                        product = self.db.get_product(product_id)
                        if product and product['category_id']:
                            similar_products = self.db.get_products(category_id=product['category_id'], limit=3)
                            products.extend([p for p in similar_products if p not in products][:limit-len(products)])

                            if len(products) >= limit:
                                break

        # COMMON FALLBACK RECOMMENDATIONS

        # If we still don't have enough recommendations based on health goal
        if len(products) < limit:
            if goal_id:
                # Try again with the standard goal system as a fallback
                recommendation_source = "standard_goal_fallback"
                all_products = self.db.get_products(limit=limit*3)
                goal_matches = match_user_goal_to_products(goal_id, all_products)
                # Filter out products we already have
                goal_matches = [p for p in goal_matches if p not in products]
                products.extend(goal_matches[:limit-len(products)])
            elif health_goal:  # Backward compatibility
                recommendation_source = "health_goal_fallback"
                goal_products = self.db.get_products(limit=limit*2)
                goal_matches = [p for p in goal_products
                              if p['health_benefits'] and
                              health_goal.lower() in p['health_benefits'].lower() and
                              p not in products]
                products.extend(goal_matches[:limit-len(products)])

        # If we still don't have enough, add products from the specified category
        if len(products) < limit and category_id:
            recommendation_source = "category_fallback"
            category_products = self.db.get_products(category_id=category_id, limit=limit*2)
            products.extend([p for p in category_products if p not in products][:limit-len(products)])

        # If we still don't have enough, add popular products based on order history
        if len(products) < limit:
            recommendation_source = "popular_products_fallback"
            # Get popular products based on order data
            popular_products = self.db.get_bestselling_products(limit=limit*2)

            # If we have popular products from order history, use them
            if popular_products:
                products.extend([p for p in popular_products if p not in products][:limit-len(products)])
            else:
                # Fallback to products marked as popular products in their health benefits
                static_popular_products = self.db.get_products(limit=limit*3)
                popular_products_list = [p for p in static_popular_products
                                      if p['health_benefits'] and 'popular product' in p['health_benefits'].lower()
                                      and p not in products]
                products.extend(popular_products_list[:limit-len(products)])

        # If we still don't have enough, add popular products
        if len(products) < limit:
            recommendation_source = "popular_fallback"
            # In a real system, this would query popular products based on sales data
            # For this demo, we'll just get random products
            popular_products = self.db.get_products(limit=limit*2)
            products.extend([p for p in popular_products if p not in products][:limit-len(products)])

        # Only limit if we have more than the requested number and not using goal_id
        # For goal-based recommendations, we want to show all matching products
        if not goal_id and len(products) > limit:
            products = products[:limit]

        # Log the recommendation source and product count for analytics
        print(f"Recommendation source: {recommendation_source} for {'customer' if customer_id else 'guest'}")
        print(f"Returning {len(products)} products for goal_id: {goal_id}")

        # Format the results
        result = []
        for product in products:
            result.append({
                'product_id': product['product_id'],
                'name': product['name'],
                'description': product['description'],
                'price': product['price'],
                'brand': product['brand'],
                'health_benefits': product['health_benefits'],
                'ingredients': product.get('ingredients', ''),
                'usage_instructions': product.get('usage_instructions', ''),
                'image_url': product.get('image_url', '')  # Include image URL
            })

        return result

    # Methods for dietary restrictions and allergies have been removed

    def _get_session_product_interactions(self, session_id: int) -> List[int]:
        """Get product IDs that the user interacted with in this session."""
        # Get button interactions for this session
        interactions = self.db.execute_query('''
            SELECT bi.button_value
            FROM button_interactions bi
            JOIN chat_messages cm ON bi.message_id = cm.message_id
            WHERE cm.session_id = ? AND bi.button_value LIKE 'product_%'
            ORDER BY bi.timestamp DESC
        ''', (session_id,))

        # Extract product IDs
        product_ids = []
        for interaction in interactions:
            try:
                product_id = int(interaction['button_value'].split('_')[1])
                if product_id not in product_ids:
                    product_ids.append(product_id)
            except (IndexError, ValueError):
                continue

        return product_ids

    def _get_order_history_products(self, customer_id: int) -> List[int]:
        """Get product IDs that the customer has purchased in the past."""
        # Get order items for this customer
        order_items = self.db.execute_query('''
            SELECT oi.product_id
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE o.customer_id = ? AND o.status = 'delivered'
            ORDER BY o.order_date DESC
        ''', (customer_id,))

        # Extract product IDs
        product_ids = []
        for item in order_items:
            product_id = item['product_id']
            if product_id not in product_ids:
                product_ids.append(product_id)

        return product_ids

    def _handle_bestsellers(self, session_id: int) -> Dict[str, Any]:
        """Handle popular products request."""
        # Update navigation state
        self._push_navigation_state(session_id, 'bestsellers', {})

        # Get popular products
        language = self.session_languages.get(session_id, 'en')
        popular_products = self.db.get_bestselling_products(limit=5)

        products = []
        if popular_products:
            products = popular_products
            response_text = "Here are our popular products:"
        else:
            # No popular products found, get some products as fallback
            products = self.db.get_products(limit=5)
            response_text = "Here are some of our products:"

        # Add navigation buttons
        back_text = "Back"
        main_menu_text = "Main Menu"

        if language != 'en':
            back_text = TranslationService.translate(back_text, language)
            main_menu_text = TranslationService.translate(main_menu_text, language)
            response_text = TranslationService.translate(response_text, language)

        buttons = [
            {'text': back_text, 'value': self.BACK_BUTTON},
            {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
        ]

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response_text
        )

        # Create response with product cards
        response = {
            'text': response_text,
            'type': 'products',  # Use product cards
            'buttons': buttons,
            'products': products,  # Include full product data
            'session_id': session_id,
            'message_id': bot_message_id
        }

        return response

    def process_message(self, user_input: str, session_id: Optional[int] = None,
                       customer_id: Optional[int] = None, language: str = 'en') -> Dict[str, Any]:
        """
        Process a user message and generate a response.

        This is the main entry point for the chatbot.
        With client-side translation, we process everything in English and translate the response.
        """
        # Start a new session if needed
        if session_id is None:
            session_id = self.start_session(customer_id, language)

        # Set the current customer for this session
        self.current_customer = customer_id

        # Save the user message
        # In a real implementation, we would translate non-English input to English first
        user_message_id = self.db.save_message(session_id, 'customer', customer_id, user_input)

        # Identify the intent
        intent_id, confidence = self.identify_intent(user_input, language)

        # Check for next_faq pattern first (before FAQ category patterns)
        if user_input.lower() in ['next_faq', 'next faq', 'next']:
            return self._handle_next_faq(session_id)

        # Check for FAQ category patterns
        if user_input.lower().endswith('_faq') and user_input.lower() != 'next_faq':
            # Extract category from the input
            category = user_input.lower().replace('_faq', '')
            return self._handle_faq_category(session_id, category)

        # Check for specific FAQ category inputs
        if user_input.lower() in ['product_faq', 'shipping_faq', 'payment_faq', 'returns_faq']:
            category = user_input.lower().replace('_faq', '')
            return self._handle_faq_category(session_id, category)

        # If no intent was identified with high confidence, check if it's a FAQ
        if intent_id is None or confidence < 0.5:
            faq_answer = self.get_faq_answer(user_input, language)
            if faq_answer:
                # Save the bot response (in English for database consistency)
                # In a real implementation, we would store both the English and translated versions
                original_answer = faq_answer
                if language != 'en':
                    # Get the English version for database storage
                    # This is a simplification - in a real system we'd have a way to get the original
                    original_answer = "FAQ answer stored in English"

                # Add navigation buttons
                main_menu_text = "Main Menu"
                if language != 'en':
                    main_menu_text = TranslationService.translate(main_menu_text, language)

                bot_message_id = self.db.save_message(session_id, 'bot', None, original_answer)
                return {
                    'session_id': session_id,
                    'message_id': bot_message_id,
                    'text': faq_answer,
                    'type': 'buttons',
                    'buttons': [
                        {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
                    ],
                    'original_language': 'en'
                }

        # Get the response for the identified intent
        # Default to help intent (10) if none identified
        response = self.get_response(intent_id if intent_id else 10, language)

        # Save the bot response (in English for database consistency)
        original_text = response.get('text', '')
        if language != 'en' and 'original_language' in response and response['original_language'] == 'en':
            # Get the English version for database storage
            # In a real implementation, we would have a way to get the original English text
            # For this demo, we'll just use a placeholder
            original_text = "Response stored in English"

        bot_message_id = self.db.save_message(
            session_id, 'bot', None, original_text, intent_id
        )

        # Prepare the result
        result = {
            'session_id': session_id,
            'message_id': bot_message_id,
            'text': response['text'],
            'type': response['type']
        }

        if 'buttons' in response:
            # Add navigation buttons if not already present
            has_main_menu = any(button.get('value') == self.MAIN_MENU_BUTTON for button in response['buttons'])

            if not has_main_menu:
                # Add Main Menu button
                main_menu_text = "Main Menu"
                if language != 'en':
                    main_menu_text = TranslationService.translate(main_menu_text, language)

                response['buttons'].append({'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON})

            result['buttons'] = response['buttons']
        else:
            # If no buttons, add navigation buttons
            main_menu_text = "Main Menu"
            if language != 'en':
                main_menu_text = TranslationService.translate(main_menu_text, language)

            result['type'] = 'buttons'
            result['buttons'] = [
                {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
            ]

        if 'original_language' in response:
            result['original_language'] = response['original_language']

        return result

    def process_button_click(self, session_id: int, message_id: int, button_value: str, button_text: str = None) -> Dict[str, Any]:
        """
        Process a button click and generate a response.

        Handles various button actions like product browsing, order status, etc.
        With client-side translation, we process everything in English and translate the response.
        Also handles navigation buttons (back, main menu).

        Args:
            session_id: The ID of the chat session
            message_id: The ID of the message containing the button
            button_value: The value of the button clicked
            button_text: The text of the button clicked

        Returns:
            Response based on the button clicked
        """
        # Get the session language
        language = self.session_languages.get(session_id, 'en')
        self.current_language = language

        # Handle feedback buttons
        if button_value == self.FEEDBACK_BUTTON:
            # Request feedback
            return self.request_feedback(session_id, language)
        elif button_value.startswith(self.RATING_PREFIX) or \
             button_value.startswith(self.HELPFUL_PREFIX) or \
             button_value.startswith(self.FEEDBACK_CATEGORY_PREFIX) or \
             button_value == 'feedback_done':
            # Process feedback
            return self.process_feedback(session_id, button_value, self.current_customer, language)

        # Handle navigation buttons
        if button_value == self.BACK_BUTTON or button_value == "Back":
            # Go back to previous state
            print(f"Processing BACK button: session_id={session_id}")
            previous_state = self._pop_navigation_state(session_id)
            print(f"Previous state: {previous_state}")
            return self._handle_navigation(session_id, previous_state)

        elif button_value == self.MAIN_MENU_BUTTON:
            # Check if this session has an agent assigned or is waiting for an agent
            session_info = self.db.execute_query(
                "SELECT agent_id, needs_agent FROM chat_sessions WHERE session_id = ?",
                (session_id,)
            )

            if session_info and (session_info[0]['agent_id'] is not None or session_info[0]['needs_agent'] == 1):
                agent_id = session_info[0]['agent_id']
                needs_agent = session_info[0]['needs_agent']

                if agent_id is not None:
                    # Session has an agent assigned - end the agent session
                    # Get agent info for the closing message
                    agent_info = self.db.execute_query(
                        "SELECT first_name, last_name FROM staff WHERE staff_id = ?",
                        (agent_id,)
                    )

                    if agent_info:
                        agent_name = f"{agent_info[0]['first_name']} {agent_info[0]['last_name']}"
                        closing_message = f"Agent {agent_name} has ended the conversation. Thank you for chatting with us!"
                        original_closing_message = closing_message  # Store original for database
                    else:
                        closing_message = "The agent has ended the conversation. Thank you for chatting with us!"
                        original_closing_message = closing_message  # Store original for database

                    # Translate the closing message if needed
                    if language != 'en':
                        if agent_info:
                            # For agent-specific message, translate the template but keep agent name
                            message_template = "Agent {agent_name} has ended the conversation. Thank you for chatting with us!"
                            translated_template = TranslationService.translate(message_template, language)
                            closing_message = translated_template.replace("{agent_name}", agent_name)
                        else:
                            closing_message = TranslationService.translate(closing_message, language)

                    # Unassign the agent from the session
                    self.db.execute_update(
                        "UPDATE chat_sessions SET agent_id = NULL WHERE session_id = ?",
                        (session_id,)
                    )
                else:
                    # Session is waiting for an agent - cancel the agent request
                    closing_message = "Agent request cancelled. Returning to main menu."

                    # Translate the closing message if needed
                    if language != 'en':
                        closing_message = TranslationService.translate(closing_message, language)

                # Reset the needs_agent flag
                self.db.execute_update(
                    "UPDATE chat_sessions SET needs_agent = 0 WHERE session_id = ?",
                    (session_id,)
                )

                # Save the closing message (store original English version in database)
                if 'original_closing_message' not in locals():
                    original_closing_message = "Agent request cancelled. Returning to main menu."
                self.db.save_message(session_id, 'system', None, original_closing_message)

                # Return a response that will trigger hiding the input field and showing main menu
                main_menu_text = 'Main Menu'
                if language != 'en':
                    main_menu_text = TranslationService.translate(main_menu_text, language)

                response = {
                    'text': closing_message,
                    'type': 'agent_ended',  # Special type to trigger input field hiding
                    'buttons': [
                        {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
                    ],
                    'original_language': 'en'
                }

                # Save the bot response
                bot_message_id = self.db.save_message(
                    session_id, 'bot', None, response['text']
                )

                # Add message_id to the response
                response['session_id'] = session_id
                response['message_id'] = bot_message_id

                return response

            # No agent assigned - proceed with normal main menu navigation
            main_menu_state = self._get_main_menu_state()
            # Clear navigation history
            if session_id in self.navigation_history:
                self.navigation_history[session_id] = []
            # Update current context
            self.session_context[session_id] = main_menu_state
            return self._handle_navigation(session_id, main_menu_state)

        # For debugging
        print(f"Processing button click: session_id={session_id}, message_id={message_id}, button_value={button_value}, button_text={button_text}")

        # Use button_text if provided, otherwise use button_value
        if button_text is None:
            button_text = button_value

        # Log the button interaction directly
        try:
            self.db.save_button_interaction(message_id, button_text, button_value)
        except Exception as e:
            print(f"Error saving button interaction: {str(e)}")
            # Continue anyway

        # Button interaction already saved above

        # Generate a response based on the button value
        response = None

        # Handle different button actions
        if button_value == 'products':
            # Get only categories that have products
            categories = self.db.execute_query('''
                SELECT DISTINCT c.category_id, c.name
                FROM categories c
                JOIN products p ON c.category_id = p.category_id
                WHERE c.is_active = 1 AND p.is_active = 1
            ''')

            buttons = []
            for category in categories:
                # Translate category name if language is not English
                category_name = category['name']
                if language != 'en':
                    category_name = TranslationService.translate(category_name, language)

                buttons.append({
                    'text': category_name,
                    'value': f"category_{category['category_id']}"
                })

            response_text = 'Please select a product category:'
            if language != 'en':
                response_text = TranslationService.translate(response_text, language)

            response = {
                'text': response_text,
                'type': 'buttons',
                'buttons': buttons
            }

        elif button_value.startswith('category_'):
            # Use the product category selection handler
            return self._handle_category_selection(session_id, button_value)

        elif button_value.startswith('product_'):
            # Check if it's a product FAQ or a product selection
            if button_value == 'product_faq':
                # Handle product FAQ
                return self._handle_faq_category(session_id, 'product')
            else:
                # Use the product selection handler
                return self._handle_product_selection(session_id, button_value)

        elif button_value.startswith('login_for_cart_'):
            # Handle login prompt for adding to cart
            try:
                product_id = int(button_value.split('_')[-1])
                # Store the product ID in the redirect context for potential future use
                return self._handle_login_register_prompt(session_id, 'cart', product_id)
            except (IndexError, ValueError):
                # Invalid product ID
                language = self.session_languages.get(session_id, 'en')
                error_text = "Sorry, there was an error processing your request."
                if language != 'en':
                    error_text = TranslationService.translate(error_text, language)

                # Save the bot response
                bot_message_id = self.db.save_message(
                    session_id, 'bot', None, error_text
                )

                # Create error response
                response = {
                    'text': error_text,
                    'type': 'buttons',
                    'buttons': [
                        {'text': TranslationService.translate('Main Menu', language) if language != 'en' else 'Main Menu',
                         'value': self.MAIN_MENU_BUTTON}
                    ],
                    'session_id': session_id,
                    'message_id': bot_message_id
                }

                return response

        elif button_value.startswith('add_to_cart_'):
            # Handle add to cart action
            # Check if user is logged in
            if not self.current_customer:
                # User is not logged in, prompt to login or register
                try:
                    product_id = int(button_value.split('_')[-1])
                    return self._handle_login_register_prompt(session_id, 'cart', product_id)
                except (IndexError, ValueError):
                    return self._handle_login_register_prompt(session_id, 'cart')

            try:
                product_id = int(button_value.split('_')[-1])
                # In a real implementation, we would add the product to the cart in the database
                # For this demo, we'll just show a success message

                # Get product details for the success message
                product = self.db.get_product(product_id)

                if product:
                    # Create success message
                    language = self.session_languages.get(session_id, 'en')
                    success_text = f"**{product['name']}** has been added to your cart!"

                    if language != 'en':
                        # Translate success message
                        product_name = product['name']  # Don't translate product name
                        message_template = "{product_name} has been added to your cart!"
                        translated_template = TranslationService.translate(message_template, language)
                        success_text = translated_template.replace("{product_name}", f"**{product_name}**")

                    # Add navigation buttons
                    continue_shopping_text = "Continue Shopping"
                    main_menu_text = "Main Menu"

                    if language != 'en':
                        continue_shopping_text = TranslationService.translate(continue_shopping_text, language)
                        main_menu_text = TranslationService.translate(main_menu_text, language)

                    buttons = [
                        {'text': continue_shopping_text, 'value': 'products'},
                        {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
                    ]

                    # Save the bot response
                    bot_message_id = self.db.save_message(
                        session_id, 'bot', None, success_text
                    )

                    # Create response
                    response = {
                        'text': success_text,
                        'type': 'buttons',
                        'buttons': buttons,
                        'session_id': session_id,
                        'message_id': bot_message_id
                    }

                    return response
                else:
                    # Product not found
                    error_text = "Sorry, I couldn't find that product."
                    if language != 'en':
                        error_text = TranslationService.translate(error_text, language)

                    # Save the bot response
                    bot_message_id = self.db.save_message(
                        session_id, 'bot', None, error_text
                    )

                    # Create error response
                    response = {
                        'text': error_text,
                        'type': 'buttons',
                        'buttons': [
                            {'text': TranslationService.translate('Main Menu', language) if language != 'en' else 'Main Menu',
                             'value': self.MAIN_MENU_BUTTON}
                        ],
                        'session_id': session_id,
                        'message_id': bot_message_id
                    }

                    return response
            except (IndexError, ValueError):
                # Invalid product ID
                language = self.session_languages.get(session_id, 'en')
                error_text = "Sorry, there was an error adding the product to your cart."
                if language != 'en':
                    error_text = TranslationService.translate(error_text, language)

                # Save the bot response
                bot_message_id = self.db.save_message(
                    session_id, 'bot', None, error_text
                )

                # Create error response
                response = {
                    'text': error_text,
                    'type': 'buttons',
                    'buttons': [
                        {'text': TranslationService.translate('Main Menu', language) if language != 'en' else 'Main Menu',
                         'value': self.MAIN_MENU_BUTTON}
                    ],
                    'session_id': session_id,
                    'message_id': bot_message_id
                }

                return response

        elif button_value == 'recommendation' or button_value == 'Get Recommendations':
            # Check if this is a registered customer or a guest
            if self.current_customer:
                # For registered customers, provide personalized recommendations directly
                return self._handle_personalized_recommendations(session_id)
            else:
                # For guests, show the health goal selection options
                # Update navigation state
                self._push_navigation_state(session_id, 'recommendations', {})

                # Add navigation buttons
                back_text = "Back"
                main_menu_text = "Main Menu"

                if language != 'en':
                    back_text = TranslationService.translate(back_text, language)
                    main_menu_text = TranslationService.translate(main_menu_text, language)

                # Get standard health goals from our module
                standard_goals = get_all_standard_goals()

                # Create buttons for each standard goal
                goal_buttons = []
                for goal in standard_goals:
                    button_text = goal['name']
                    if language != 'en':
                        button_text = TranslationService.translate(button_text, language)
                    goal_buttons.append({'text': button_text, 'value': goal['id']})

                # Add navigation buttons
                goal_buttons.append({'text': back_text, 'value': self.BACK_BUTTON})
                goal_buttons.append({'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON})

                response_text = 'I can recommend products based on your fitness goals. What are you looking for?'
                if language != 'en':
                    response_text = TranslationService.translate(response_text, language)

                response = {
                    'text': response_text,
                    'type': 'buttons',
                    'buttons': goal_buttons
                }

        elif button_value == 'promotions':
            # Update navigation state
            self._push_navigation_state(session_id, 'promotions', {})

            # Get active promotions
            promotions = self.db.get_active_promotions()

            # Add navigation buttons
            main_menu_text = "Main Menu"
            if language != 'en':
                main_menu_text = TranslationService.translate(main_menu_text, language)

            if promotions:
                # Show introduction message first
                intro_text = "Here are our current promotions:"
                if language != 'en':
                    intro_text = TranslationService.translate(intro_text, language)

                # Create buttons for each promotion and to navigate back
                buttons = []
                for i, promo in enumerate(promotions):
                    buttons.append({
                        'text': promo['name'],
                        'value': f"promo_{promo['promotion_id']}"
                    })

                buttons.append({'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON})

                response = {
                    'text': intro_text,
                    'type': 'buttons',
                    'buttons': buttons
                }

                # Store promotions in session context for later use
                if session_id in self.session_context:
                    self.session_context[session_id]['data']['promotions'] = promotions
            else:
                response_text = 'There are no active promotions at the moment. Check back soon!'
                if language != 'en':
                    response_text = TranslationService.translate(response_text, language)

                response = {
                    'text': response_text,
                    'type': 'buttons',
                    'buttons': [
                        {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
                    ]
                }

        elif button_value == 'order_status':
            # Use the orders menu handler
            return self._handle_orders_menu(session_id)

        elif button_value == 'delivery_status':
            # Use the delivery status menu handler
            return self._handle_delivery_status_menu(session_id)

        elif button_value.startswith('order_'):
            # Use the order status handler
            return self._handle_order_status(session_id, button_value)

        elif button_value.startswith('delivery_'):
            # Use the delivery status handler
            return self._handle_delivery_status(session_id, button_value)

        elif button_value == 'explore_more_registered':
            # Handle explore more options for registered customers
            return self._handle_explore_more_registered(session_id)

        elif button_value.startswith('promo_'):
            # Handle promotion details
            try:
                promo_id = int(button_value.split('_')[1])
                return self._handle_promotion_details(session_id, promo_id)
            except (IndexError, ValueError):
                error_text = "Invalid promotion selection"
                if language != 'en':
                    error_text = TranslationService.translate(error_text, language)
                return {'error': error_text}

        elif button_value in ['muscle_building', 'weight_management', 'energy_performance', 'general_health', 'recovery']:
            # Handle recommendation buttons using standard goal IDs
            # Use the recommendation handler with the standard goal ID
            return self._handle_recommendation_request(session_id, button_value)

        elif button_value == 'bestsellers':
            # Use the bestsellers handler
            return self._handle_bestsellers(session_id)

        elif button_value == 'faq':
            # Show FAQ categories
            return self._handle_faq_menu(session_id)

        elif button_value == 'next_faq':
            # Show the next FAQ in the current category
            return self._handle_next_faq(session_id)

        elif button_value.endswith('_faq'):
            # Extract the category from the button value
            parts = button_value.split('_')
            if len(parts) < 2:
                error_text = f'Invalid FAQ button value: {button_value}'
                if language != 'en':
                    error_text = TranslationService.translate(error_text, language)
                return {'error': error_text}

            # Get the category (everything before _faq)
            category = '_'.join(parts[:-1]) if len(parts) > 2 else parts[0]

            # Handle special cases
            if category == 'return' or category == 'returns':
                category = 'returns'

            # Use the FAQ category handler
            return self._handle_faq_category(session_id, category)

        elif button_value == 'agent' or button_text == 'Speak to an Agent':
            # Allow both logged-in users and guests to request agents
            # Update navigation state
            self._push_navigation_state(session_id, 'agent', {})

            # Mark the session as needing agent assistance
            print(f"Requesting agent for session {session_id} (customer_id: {self.current_customer})")
            self.db.request_agent(session_id)

            # Request for human agent
            if self.current_customer:
                # Logged-in user
                response_text = 'I\'ll connect you with a human agent shortly. Please wait a moment.'
            else:
                # Guest user
                response_text = 'I\'ll connect you with a human agent shortly. As a guest user, the agent will be able to assist you with general inquiries. Please wait a moment.'

            if language != 'en':
                response_text = TranslationService.translate(response_text, language)

            # Add navigation buttons
            main_menu_text = "Main Menu"
            if language != 'en':
                main_menu_text = TranslationService.translate(main_menu_text, language)

            # Save only the bot response (no need for separate system message)
            bot_message_id = self.db.save_message(
                session_id, 'bot', None, response_text
            )

            response = {
                'text': response_text,
                'type': 'buttons',
                'buttons': [
                    {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
                ],
                'session_id': session_id,
                'message_id': bot_message_id,
                'sender_type': 'system',
                'already_saved': True  # Flag to prevent duplicate saving
            }

        # Handle login/register redirects
        elif button_value == 'login_redirect':
            # Create a direct login link without additional message
            login_text = "Login"
            if language != 'en':
                login_text = TranslationService.translate(login_text, language)

            # Create response with a login link
            response = {
                'text': '',  # Empty text to avoid showing a message
                'type': 'redirect',
                'redirect_url': '/login',
                'session_id': session_id
            }

        elif button_value == 'register_redirect':
            # Create a direct register link without additional message
            register_text = "Register"
            if language != 'en':
                register_text = TranslationService.translate(register_text, language)

            # Create response with a registration link
            response = {
                'text': '',  # Empty text to avoid showing a message
                'type': 'redirect',
                'redirect_url': '/register',
                'session_id': session_id
            }

        # If no specific handling, use a default response
        if not response:
            # Add navigation buttons
            main_menu_text = "Main Menu"
            if language != 'en':
                main_menu_text = TranslationService.translate(main_menu_text, language)

            response_text = f'You selected: {button_text}. How can I help you with this?'
            if language != 'en':
                response_text = TranslationService.translate(response_text, language)

            response = {
                'text': response_text,
                'type': 'buttons',
                'buttons': [
                    {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
                ]
            }

        # Save the bot response (in English for database consistency) only if not already saved
        if not response.get('already_saved', False):
            original_text = response.get('text', '')
            if language != 'en' and not 'original_language' in response:
                # In a real implementation, we would have a way to get the original English text
                # For this demo, we'll just use a placeholder
                original_text = "Response stored in English"

            bot_message_id = self.db.save_message(
                session_id, 'bot', None, original_text
            )

            # Add message_id to the response
            response['session_id'] = session_id
            response['message_id'] = bot_message_id

        # Add original language if not present
        if 'original_language' not in response:
            response['original_language'] = 'en'

        return response

    def request_feedback(self, session_id: int, language: str = 'en') -> Dict[str, Any]:
        """
        Request feedback from the user.

        Args:
            session_id: The ID of the chat session
            language: The language for the response

        Returns:
            Response with feedback request
        """
        # Get the feedback categories
        try:
            categories = self.feedback_manager.get_feedback_categories()
        except Exception as e:
            print(f"Error getting feedback categories: {str(e)}")
            categories = []

        # Create buttons for rating
        rating_buttons = []
        for i in range(1, 6):
            rating_buttons.append({
                'text': '⭐' * i,
                'value': f"{self.RATING_PREFIX}{i}"
            })

        # Create the response
        text = "Thank you for chatting with Rock Supplements! Please rate your experience:"
        if language != 'en':
            text = TranslationService.translate(text, language)

        response = {
            'text': text,
            'type': 'buttons',
            'buttons': rating_buttons,
            'original_language': 'en'
        }

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, text
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def process_feedback(self, session_id: int, button_value: str,
                        customer_id: Optional[int] = None,
                        language: str = 'en') -> Dict[str, Any]:
        """
        Process feedback from the user.

        Args:
            session_id: The ID of the chat session
            button_value: The value of the button clicked
            customer_id: The ID of the customer
            language: The language for the response

        Returns:
            Response with next feedback step or thank you message
        """
        if button_value.startswith(self.RATING_PREFIX):
            # Process rating
            rating = int(button_value.split('_')[1])

            # Ask if the chatbot was helpful
            text = "Was the chatbot helpful in addressing your needs?"
            if language != 'en':
                text = TranslationService.translate(text, language)

            helpful_buttons = [
                {'text': 'Yes', 'value': f"{self.HELPFUL_PREFIX}yes"},
                {'text': 'No', 'value': f"{self.HELPFUL_PREFIX}no"}
            ]

            response = {
                'text': text,
                'type': 'buttons',
                'buttons': helpful_buttons,
                'original_language': 'en',
                'feedback_data': {'rating': rating}
            }

        elif button_value.startswith(self.HELPFUL_PREFIX):
            # Process helpfulness
            was_helpful = button_value.endswith('yes')

            # Get feedback data from previous step
            feedback_data = self._get_feedback_data(session_id)
            if not feedback_data:
                feedback_data = {'rating': 3}  # Default if no previous data

            feedback_data['was_helpful'] = was_helpful

            # If not helpful, ask for improvement areas
            if not was_helpful:
                # Get categories
                categories = self.feedback_manager.get_feedback_categories()

                # Create buttons for categories
                category_buttons = []
                for category in categories:
                    category_buttons.append({
                        'text': category['category_name'],
                        'value': f"{self.FEEDBACK_CATEGORY_PREFIX}{category['category_name']}"
                    })

                text = "Which areas could we improve? (Select all that apply)"
                if language != 'en':
                    text = TranslationService.translate(text, language)

                # Add a "Done" button
                category_buttons.append({
                    'text': 'Done',
                    'value': 'feedback_done'
                })

                response = {
                    'text': text,
                    'type': 'buttons',
                    'buttons': category_buttons,
                    'original_language': 'en',
                    'feedback_data': feedback_data,
                    'multi_select': True  # Allow multiple selections
                }
            else:
                # Save feedback
                self.feedback_manager.save_feedback(
                    session_id, customer_id, feedback_data['rating'],
                    None, None, was_helpful
                )

                # Thank the user
                text = "Thank you for your feedback! It helps us improve our service."
                if language != 'en':
                    text = TranslationService.translate(text, language)

                response = {
                    'text': text,
                    'type': 'text',
                    'original_language': 'en'
                }

        elif button_value.startswith(self.FEEDBACK_CATEGORY_PREFIX):
            # Process feedback category selection
            category = button_value.split('_')[2]

            # Get feedback data from previous steps
            feedback_data = self._get_feedback_data(session_id)
            if not feedback_data:
                feedback_data = {'rating': 3, 'was_helpful': False}

            # Add category to the list
            if 'improvement_areas' not in feedback_data:
                feedback_data['improvement_areas'] = []

            if category not in feedback_data['improvement_areas']:
                feedback_data['improvement_areas'].append(category)

            # Return the same categories menu with updated selection
            categories = self.feedback_manager.get_feedback_categories()

            # Create buttons for categories
            category_buttons = []
            for cat in categories:
                # Mark selected categories
                prefix = "✓ " if cat['category_name'] in feedback_data['improvement_areas'] else ""
                category_buttons.append({
                    'text': f"{prefix}{cat['category_name']}",
                    'value': f"{self.FEEDBACK_CATEGORY_PREFIX}{cat['category_name']}"
                })

            text = "Which areas could we improve? (Select all that apply)"
            if language != 'en':
                text = TranslationService.translate(text, language)

            # Add a "Done" button
            category_buttons.append({
                'text': 'Done',
                'value': 'feedback_done'
            })

            response = {
                'text': text,
                'type': 'buttons',
                'buttons': category_buttons,
                'original_language': 'en',
                'feedback_data': feedback_data,
                'multi_select': True
            }

        elif button_value == 'feedback_done':
            # Process final feedback submission
            feedback_data = self._get_feedback_data(session_id)
            if not feedback_data:
                feedback_data = {'rating': 3, 'was_helpful': False}

            # Save feedback
            self.feedback_manager.save_feedback(
                session_id, customer_id, feedback_data['rating'],
                None, feedback_data.get('improvement_areas'),
                feedback_data.get('was_helpful')
            )

            # Thank the user
            text = "Thank you for your feedback! It helps us improve our service."
            if language != 'en':
                text = TranslationService.translate(text, language)

            # Add main menu button
            main_menu_text = "Main Menu"
            if language != 'en':
                main_menu_text = TranslationService.translate(main_menu_text, language)

            # First, save the thank you message
            bot_message_id = self.db.save_message(
                session_id, 'bot', None, text
            )

            # Then, create a separate message with the main menu button
            main_menu_response = {
                'text': "What would you like to do next?",
                'type': 'buttons',
                'buttons': [
                    {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
                ],
                'original_language': 'en'
            }

            # Save the main menu message
            main_menu_message_id = self.db.save_message(
                session_id, 'bot', None, main_menu_response['text']
            )

            # Return the combined response
            response = {
                'text': text,
                'type': 'buttons',
                'buttons': [
                    {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
                ],
                'original_language': 'en',
                'session_id': session_id,
                'message_id': main_menu_message_id
            }

        else:
            # Invalid button value
            text = "I'm sorry, I didn't understand your feedback. Let's try again."
            if language != 'en':
                text = TranslationService.translate(text, language)

            response = self.request_feedback(session_id, language)
            return response

        # For all cases except 'feedback_done' and invalid button value
        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response['text']
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def _get_feedback_data(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Get feedback data from previous messages.

        Args:
            session_id: The ID of the chat session

        Returns:
            Dictionary of feedback data or None if not found
        """
        # Get recent messages
        messages = self.db.get_session_messages(session_id)

        # Look for feedback data in recent bot messages
        for message in messages:
            if message['sender_type'] == 'bot' and 'feedback_data' in message:
                return message['feedback_data']

        return None

    def _handle_faq_menu(self, session_id: int) -> Dict[str, Any]:
        """
        Handle the FAQ menu.

        Shows FAQ categories that users can browse.
        """
        # Update navigation state
        self._push_navigation_state(session_id, 'faq', {})

        language = self.session_languages.get(session_id, 'en')

        # Create buttons for FAQ categories
        response_text = "Here are some frequently asked questions categories:"
        if language != 'en':
            response_text = TranslationService.translate(response_text, language)

        # Add navigation buttons
        back_text = "Back"
        main_menu_text = "Main Menu"

        if language != 'en':
            back_text = TranslationService.translate(back_text, language)
            main_menu_text = TranslationService.translate(main_menu_text, language)

        # Get unique FAQ categories from the database
        categories = self.db.execute_query('''
            SELECT DISTINCT category
            FROM faqs
            WHERE language = 'en' AND is_active = 1
        ''')

        buttons = []
        for category in categories:
            # Create a display name for the category (capitalize first letter)
            display_name = category['category'].capitalize()
            if language != 'en':
                display_name = TranslationService.translate(display_name, language)

            # Use consistent button values
            button_value = f"{category['category']}_faq"

            # Special case for returns category
            if category['category'] == 'returns':
                button_value = 'returns_faq'

            buttons.append({
                'text': display_name,
                'value': button_value
            })

        # Add navigation buttons
        buttons.append({'text': back_text, 'value': self.BACK_BUTTON})
        buttons.append({'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON})

        response = {
            'text': response_text,
            'type': 'buttons',
            'buttons': buttons
        }

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response['text']
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def _handle_promotion_details(self, session_id: int, promo_id: int) -> Dict[str, Any]:
        """
        Handle displaying details for a specific promotion.

        Args:
            session_id: The current session ID
            promo_id: The promotion ID to display

        Returns:
            Response with promotion details
        """
        # Get the session language
        language = self.session_languages.get(session_id, 'en')

        # Get the promotion details from session context
        promotions = []
        if session_id in self.session_context and 'promotions' in self.session_context[session_id]['data']:
            promotions = self.session_context[session_id]['data']['promotions']

        # If not in session context, get from database
        if not promotions:
            promotions = self.db.get_active_promotions()

        # Find the specific promotion
        promo = next((p for p in promotions if p['promotion_id'] == promo_id), None)

        if not promo:
            error_text = "Sorry, I couldn't find that promotion."
            if language != 'en':
                error_text = TranslationService.translate(error_text, language)

            return {
                'text': error_text,
                'type': 'buttons',
                'buttons': [
                    {'text': 'Back', 'value': self.BACK_BUTTON},
                    {'text': 'Main Menu', 'value': self.MAIN_MENU_BUTTON}
                ]
            }

        # Format the promotion details
        if promo['discount_type'] == 'percentage':
            discount = f"{promo['discount_value']}%"
        else:
            discount = f"RM{promo['discount_value']}"

        promo_text = f"**{promo['name']}**\n\n"
        promo_text += f"{promo['description']}\n\n"
        promo_text += f"**Discount:** {discount} off\n"
        promo_text += f"**Use code:** **{promo['coupon_code']}**\n\n"

        if promo['minimum_order_amount']:
            promo_text += f"**Minimum order:** RM{promo['minimum_order_amount']}\n"

        if promo['start_date'] and promo['end_date']:
            promo_text += f"**Valid from:** {promo['start_date']} to {promo['end_date']}\n"

        # Translate if needed
        if language != 'en':
            promo_text = TranslationService.translate(promo_text, language)

        # Add navigation buttons
        back_text = "Back to Promotions"
        main_menu_text = "Main Menu"

        if language != 'en':
            back_text = TranslationService.translate(back_text, language)
            main_menu_text = TranslationService.translate(main_menu_text, language)

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, promo_text
        )

        # Create response
        response = {
            'text': promo_text,
            'type': 'buttons',
            'buttons': [
                {'text': back_text, 'value': self.BACK_BUTTON},
                {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
            ],
            'session_id': session_id,
            'message_id': bot_message_id
        }

        return response

    def _handle_faq_category(self, session_id: int, category: str) -> Dict[str, Any]:
        """
        Handle a FAQ category selection.

        Shows the first FAQ in the selected category and provides navigation buttons.
        """
        print(f"DEBUG: _handle_faq_category called with category: '{category}'")

        # Update navigation state
        self._push_navigation_state(session_id, 'faq_category', {'category': category})

        language = self.session_languages.get(session_id, 'en')

        # Get FAQs for this category
        faqs = self.db.get_faqs(category=category, language='en')

        if faqs:
            # Create a formatted response with the first FAQ in this category
            category_display = category.capitalize()
            if language != 'en':
                category_display = TranslationService.translate(category_display, language)

            # Store FAQs in session context for navigation
            if session_id not in self.session_context:
                self.session_context[session_id] = {'location': 'faq_category', 'data': {}}

            if 'data' not in self.session_context[session_id]:
                self.session_context[session_id]['data'] = {}

            self.session_context[session_id]['data']['faqs'] = faqs
            self.session_context[session_id]['data']['current_faq_index'] = 0
            self.session_context[session_id]['data']['category'] = category

            # Get the first FAQ
            faq = faqs[0]

            question = faq['question']
            answer = faq['answer']

            if language != 'en':
                question = TranslationService.translate(question, language)
                answer = TranslationService.translate(answer, language)

            response_text = f"**{category_display} FAQ:**\n\n"
            response_text += f"**Q: {question}**\n"
            response_text += f"A: {answer}"

            # Add navigation buttons
            back_text = "Back to FAQ Categories"
            main_menu_text = "Main Menu"

            if language != 'en':
                back_text = TranslationService.translate(back_text, language)
                main_menu_text = TranslationService.translate(main_menu_text, language)

            buttons = [
                {'text': back_text, 'value': 'faq'},
                {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
            ]

            # Add Next FAQ button if there are more FAQs
            if len(faqs) > 1:
                next_text = "Next FAQ"
                if language != 'en':
                    next_text = TranslationService.translate(next_text, language)

                buttons.insert(0, {'text': next_text, 'value': 'next_faq'})
        else:
            # No FAQs found for this category
            response_text = f"Sorry, no FAQs found for {category}."
            if language != 'en':
                response_text = TranslationService.translate(response_text, language)

            # Add navigation buttons
            back_text = "Back to FAQ Categories"
            main_menu_text = "Main Menu"

            if language != 'en':
                back_text = TranslationService.translate(back_text, language)
                main_menu_text = TranslationService.translate(main_menu_text, language)

            buttons = [
                {'text': back_text, 'value': 'faq'},
                {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
            ]

        response = {
            'text': response_text,
            'type': 'buttons',
            'buttons': buttons
        }

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response['text']
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def _handle_next_faq(self, session_id: int) -> Dict[str, Any]:
        """
        Handle navigation to the next FAQ in the current category.

        Shows the next FAQ in the current category and provides navigation buttons.
        """
        language = self.session_languages.get(session_id, 'en')

        # Get FAQs and current index from session context
        faqs = []
        current_index = 0

        if session_id in self.session_context:
            if 'data' in self.session_context[session_id]:
                data = self.session_context[session_id]['data']
                faqs = data.get('faqs', [])
                current_index = data.get('current_faq_index', 0)

        # If no FAQs in session context, return to FAQ menu
        if not faqs:
            return self._handle_faq_menu(session_id)

        # Increment the index
        current_index += 1

        # Check if we've reached the end of the FAQs
        if current_index >= len(faqs):
            # Loop back to the first FAQ
            current_index = 0

        # Update the current index in session context
        if session_id in self.session_context:
            self.session_context[session_id]['data']['current_faq_index'] = current_index

        # Get the current FAQ
        faq = faqs[current_index]

        # Get category display name
        category_display = faq['category'].capitalize()
        if language != 'en':
            category_display = TranslationService.translate(category_display, language)

        # Translate question and answer if needed
        question = faq['question']
        answer = faq['answer']

        if language != 'en':
            question = TranslationService.translate(question, language)
            answer = TranslationService.translate(answer, language)

        # Create response text
        response_text = f"**{category_display} FAQ:**\n\n"
        response_text += f"**Q: {question}**\n"
        response_text += f"A: {answer}"

        # Add navigation buttons
        back_text = "Back to FAQ Categories"
        main_menu_text = "Main Menu"
        next_text = "Next FAQ"

        if language != 'en':
            back_text = TranslationService.translate(back_text, language)
            main_menu_text = TranslationService.translate(main_menu_text, language)
            next_text = TranslationService.translate(next_text, language)

        buttons = [
            {'text': next_text, 'value': 'next_faq'},
            {'text': back_text, 'value': 'faq'},
            {'text': main_menu_text, 'value': self.MAIN_MENU_BUTTON}
        ]

        response = {
            'text': response_text,
            'type': 'buttons',
            'buttons': buttons
        }

        # Save the bot response
        bot_message_id = self.db.save_message(
            session_id, 'bot', None, response['text']
        )

        # Add message_id to the response
        response['session_id'] = session_id
        response['message_id'] = bot_message_id

        return response

    def close(self):
        """Close the database connection."""
        if self.db:
            self.db.close()
        if self.feedback_manager:
            self.feedback_manager.close()

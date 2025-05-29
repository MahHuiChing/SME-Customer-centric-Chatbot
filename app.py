import os
import json
import threading
import time
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
import sys
from datetime import datetime

# Add the current directory to the path so we can import the rock package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import Rock chatbot components
from rock.chatbot import RockChatbot
from rock.database import Database
from rock.auth import Auth
from rock.manager import ChatbotManager
from rock.scheduled_tasks import ScheduledTasks
from rock.agent_interface import AgentInterface
from rock.health_goals import get_all_standard_goals

app = Flask(__name__)
app.secret_key = 'rock_supplements_chatbot_secret_key'  # Change this in production

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Initialize the chatbot and other components
DB_PATH = 'data/rock_chatbot.db'

chatbot = RockChatbot(DB_PATH)
auth = Auth(Database(DB_PATH))
manager = ChatbotManager(DB_PATH)

# Initialize scheduled tasks
scheduled_tasks = ScheduledTasks(DB_PATH)

# Background task for cleanup
def cleanup_task():
    """Background task to cleanup inactive agents and sessions every 5 minutes."""
    while True:
        try:
            time.sleep(300)  # Wait 5 minutes
            scheduled_tasks.cleanup_inactive_agents()
            scheduled_tasks.cleanup_inactive_sessions()
        except Exception as e:
            print(f"Error in cleanup task: {e}")

# Start background task
cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
cleanup_thread.start()

def check_empty_category(category):
    """Check if a category is empty and remove it if it is."""
    if not category:
        return

    db = Database(DB_PATH)

    # Check if there are any FAQs with this category
    query = "SELECT COUNT(*) as count FROM faqs WHERE category = ?"
    result = db.execute_query(query, (category,))

    # If no FAQs with this category, return that it's empty
    if result and result[0]['count'] == 0:
        print(f"Category '{category}' is now empty")
        return True

    return False

# Routes
@app.route('/')
def index():
    """Home page with chatbot interface."""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login route."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        success, message, user_info = auth.login(username, password)

        if success:
            # Set session variables
            session['user_id'] = user_info.get('customer_id') or user_info.get('staff_id')
            session['username'] = user_info.get('username')
            session['role'] = user_info.get('role')
            session['name'] = f"{user_info.get('first_name')} {user_info.get('last_name')}"

            flash('Login successful!', 'success')

            # Redirect based on role
            if user_info.get('role') == 'manager':
                return redirect(url_for('admin'))
            elif user_info.get('role') == 'agent':
                return redirect(url_for('agent'))  # Now points to the modern interface
            else:
                return redirect(url_for('index'))
        else:
            flash(message, 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register route."""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone_number = request.form.get('phone_number', '')

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')

        # Use Auth directly to bypass the manager permission check
        success, message, user_id = auth.register_user(
            username, email, password, first_name, last_name, phone_number
        )

        if success:
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'error')

    return render_template('register.html')

@app.route('/admin')
def admin():
    """Admin dashboard route."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        flash('You must be logged in as a manager or agent to access the admin area.', 'error')
        return redirect(url_for('login'))

    # Redirect agents to the agent interface
    if session.get('role') == 'agent':
        return redirect(url_for('agent'))

    return render_template('admin.html')

@app.route('/agent')
def agent():
    """Agent interface route."""
    # Check if user is logged in and has agent role
    if not session.get('user_id') or session.get('role') != 'agent':
        flash('You must be logged in as an agent to access the agent interface.', 'error')
        return redirect(url_for('login'))

    return render_template('agent.html')

@app.route('/logout')
def logout():
    """Logout route."""
    session.clear()
    return redirect(url_for('index'))

# API Endpoints
@app.route('/api/get_languages', methods=['GET'])
def get_languages():
    """Get available languages."""
    # This would normally come from the database
    languages = [
        {'code': 'en', 'name': 'English'},
        {'code': 'ms', 'name': 'Bahasa Melayu'},
        {'code': 'zh', 'name': 'Chinese'},
        {'code': 'ta', 'name': 'Tamil'}
    ]
    return jsonify(languages)

@app.route('/api/start_session', methods=['POST'])
def start_session():
    """Start a new chat session."""
    data = request.json
    language = data.get('language', 'en')
    customer_id = data.get('customer_id')
    window_id = data.get('window_id', f'window_{datetime.now().timestamp()}')
    source = data.get('source', 'web')

    # Validate customer_id - only use it if it's a valid customer
    # If the user is logged in as staff (agent/manager), don't use their ID as customer_id
    if customer_id:
        db = Database(DB_PATH)
        customer_check = db.execute_query("SELECT customer_id FROM customers WHERE customer_id = ?", (customer_id,))
        if not customer_check:
            # Invalid customer_id, treat as guest
            customer_id = None

    # Start a new session
    session_id = chatbot.start_session(customer_id, language, source)

    # Store window ID in session for tracking multiple windows
    if 'chat_sessions' not in session:
        session['chat_sessions'] = {}
    session['chat_sessions'][window_id] = {
        'session_id': session_id,
        'customer_id': customer_id,
        'language': language,
        'created_at': datetime.now().isoformat()
    }

    # Get welcome message without processing a fake "hello" message
    welcome_response = chatbot.get_welcome_message(session_id, customer_id, language)

    # Add window_id to response
    welcome_response['window_id'] = window_id

    return jsonify(welcome_response)

@app.route('/api/process_message', methods=['POST'])
def process_message():
    """Process a user message."""
    data = request.json
    user_input = data.get('message')
    session_id = data.get('session_id')
    customer_id = data.get('customer_id')
    language = data.get('language', 'en')

    # Process the message
    response = chatbot.process_message(user_input, session_id, customer_id, language)

    return jsonify(response)

@app.route('/api/process_button', methods=['POST'])
def process_button():
    """Process a button click."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400

        session_id = data.get('session_id')
        message_id = data.get('message_id')
        button_value = data.get('button_value')
        button_text = data.get('button_text')

        if not session_id or not message_id or not button_value:
            return jsonify({'error': 'Missing required parameters'}), 400

        # If button_value is not recognized but we have button_text, use that instead
        if button_text and not button_value:
            button_value = button_text

        # Process the button click
        response = chatbot.process_button_click(session_id, message_id, button_value, button_text)

        # Ensure response is JSON serializable
        if not isinstance(response, dict):
            return jsonify({'error': 'Invalid response from chatbot'}), 500

        return jsonify(response)
    except Exception as e:
        print(f"Error processing button click: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/end_session', methods=['POST'])
def end_session():
    """End a chat session."""
    try:
        # Handle different types of request data (JSON, form data, or sendBeacon)
        data = {}

        if request.is_json and request.json:
            data = request.json
        elif request.form:
            data = request.form.to_dict()
        elif request.data:
            # Handle sendBeacon data
            try:
                import json
                data = json.loads(request.data.decode('utf-8'))
            except:
                data = {}

        session_id = data.get('session_id')

        if not session_id:
            return jsonify({'success': False, 'message': 'Session ID is required'}), 400

        # End the session
        response = chatbot.end_session(session_id)

        # Ensure response is properly formatted
        if isinstance(response, bool):
            if response:
                return jsonify({'success': True, 'message': 'Session ended successfully'})
            else:
                return jsonify({'success': False, 'message': 'Failed to end session'}), 500
        elif isinstance(response, dict):
            return jsonify(response)
        else:
            return jsonify({'success': True, 'message': 'Session ended successfully'})

    except Exception as e:
        print(f"Error ending session: {e}")
        return jsonify({'success': False, 'message': f'Error ending session: {str(e)}'}), 500

@app.route('/api/send_agent_message', methods=['POST'])
def send_agent_message():
    """Send a message from customer to agent."""
    data = request.json
    session_id = data.get('session_id')
    message = data.get('message')
    language = data.get('language', 'en')

    if not session_id or not message:
        return jsonify({'success': False, 'message': 'Session ID and message are required'})

    try:
        # Store the message in the database
        db = Database(DB_PATH)

        # Get session info
        session_query = """
            SELECT customer_id, agent_id FROM chat_sessions
            WHERE session_id = ? AND session_end IS NULL
        """
        session_info = db.execute_query(session_query, (session_id,))

        if not session_info:
            return jsonify({'success': False, 'message': 'Session not found or ended'})

        customer_id = session_info[0]['customer_id']
        agent_id = session_info[0]['agent_id']

        # Store the message
        message_query = """
            INSERT INTO chat_messages (session_id, sender_type, sender_id, message_text, timestamp, original_language)
            VALUES (?, ?, ?, ?, datetime('now'), ?)
        """

        # Determine sender type and ID
        if customer_id:
            sender_type = 'customer'
            sender_id = customer_id
        else:
            sender_type = 'guest'
            sender_id = None

        db.execute_update(message_query, (session_id, sender_type, sender_id, message, language))

        # Note: Session activity tracking removed as columns don't exist in schema

        return jsonify({'success': True, 'message': 'Message sent to agent'})

    except Exception as e:
        print(f"Error sending agent message: {e}")
        return jsonify({'success': False, 'message': 'Error sending message'})

@app.route('/api/check_chat_status', methods=['GET'])
def check_chat_status():
    """Check if a chat session has been ended."""
    session_id = request.args.get('session_id')

    if not session_id:
        return jsonify({'success': False, 'message': 'Session ID required'})

    try:
        db = Database(DB_PATH)

        # Check if session is ended
        session_query = """
            SELECT session_end FROM chat_sessions
            WHERE session_id = ?
        """
        session_info = db.execute_query(session_query, (session_id,))

        if not session_info:
            return jsonify({'success': False, 'message': 'Session not found'})

        session_end = session_info[0]['session_end']
        chat_ended = session_end is not None

        # Get the last system message if chat was ended
        end_message = None
        if chat_ended:
            message_query = """
                SELECT message_text FROM chat_messages
                WHERE session_id = ? AND sender_type = 'system'
                ORDER BY timestamp DESC LIMIT 1
            """
            message_result = db.execute_query(message_query, (session_id,))
            if message_result:
                end_message = message_result[0]['message_text']

        return jsonify({
            'success': True,
            'chat_ended': chat_ended,
            'end_message': end_message,
            'session_end': str(session_end) if session_end else None
        })

    except Exception as e:
        print(f"Error checking chat status: {e}")
        return jsonify({'success': False, 'message': 'Error checking chat status'})

@app.route('/api/get_new_messages', methods=['GET'])
def get_new_messages():
    """Get new messages for a chat session since a specific timestamp."""
    session_id = request.args.get('session_id')
    since_timestamp = request.args.get('since_timestamp')

    if not session_id:
        return jsonify({'success': False, 'message': 'Session ID required'})

    try:
        db = Database(DB_PATH)

        # Build query based on whether we have a timestamp
        if since_timestamp:
            messages_query = """
                SELECT message_id, sender_type, sender_id, message_text, timestamp, original_language
                FROM chat_messages
                WHERE session_id = ? AND timestamp > ?
                ORDER BY timestamp ASC
            """
            messages = db.execute_query(messages_query, (session_id, since_timestamp))
        else:
            # Get all messages if no timestamp provided
            messages_query = """
                SELECT message_id, sender_type, sender_id, message_text, timestamp, original_language
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """
            messages = db.execute_query(messages_query, (session_id,))

        # Convert timestamps to strings for JSON serialization
        for message in messages:
            if message['timestamp']:
                message['timestamp'] = str(message['timestamp'])

        # Get sender names for agent messages
        for message in messages:
            if message['sender_type'] == 'agent' and message['sender_id']:
                agent_query = """
                    SELECT first_name, last_name FROM staff
                    WHERE staff_id = ?
                """
                agent_info = db.execute_query(agent_query, (message['sender_id'],))
                if agent_info:
                    agent_name = f"{agent_info[0]['first_name']} {agent_info[0]['last_name']}".strip()
                    message['sender_name'] = agent_name or 'Agent'
                else:
                    message['sender_name'] = 'Agent'
            elif message['sender_type'] == 'customer' and message['sender_id']:
                customer_query = """
                    SELECT first_name, last_name, username FROM customers
                    WHERE customer_id = ?
                """
                customer_info = db.execute_query(customer_query, (message['sender_id'],))
                if customer_info:
                    customer_name = f"{customer_info[0]['first_name'] or ''} {customer_info[0]['last_name'] or ''}".strip()
                    message['sender_name'] = customer_name or customer_info[0]['username'] or 'Customer'
                else:
                    message['sender_name'] = 'Customer'
            elif message['sender_type'] == 'guest':
                message['sender_name'] = 'Guest User'
            else:
                message['sender_name'] = message['sender_type'].title()

        return jsonify({
            'success': True,
            'messages': messages,
            'count': len(messages)
        })

    except Exception as e:
        print(f"Error getting new messages: {e}")
        return jsonify({'success': False, 'message': 'Error getting messages'})

# Admin API Endpoints
@app.route('/api/admin/dashboard_stats', methods=['GET'])
def dashboard_stats():
    """Get dashboard statistics."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    db = Database(DB_PATH)

    # Get active sessions count
    active_sessions_query = """
        SELECT COUNT(*) as count
        FROM chat_sessions
        WHERE session_end IS NULL
    """
    active_sessions_result = db.execute_query(active_sessions_query)
    active_sessions = active_sessions_result[0]['count'] if active_sessions_result else 0

    # Get total users count (customers + staff)
    total_users_query = """
        SELECT
            (SELECT COUNT(*) FROM customers) +
            (SELECT COUNT(*) FROM staff)
        as count
    """
    total_users_result = db.execute_query(total_users_query)
    total_users = total_users_result[0]['count'] if total_users_result else 0

    # Get products count
    products_query = """
        SELECT COUNT(*) as count
        FROM products
        WHERE is_active = 1
    """
    products_result = db.execute_query(products_query)
    products = products_result[0]['count'] if products_result else 0

    # Get FAQs count
    faqs_query = """
        SELECT COUNT(*) as count
        FROM faqs
        WHERE is_active = 1
    """
    faqs_result = db.execute_query(faqs_query)
    faqs = faqs_result[0]['count'] if faqs_result else 0

    return jsonify({
        'success': True,
        'active_sessions': active_sessions,
        'total_users': total_users,
        'products': products,
        'faqs': faqs
    })

@app.route('/api/admin/recent_sessions', methods=['GET'])
def recent_sessions():
    """Get recent chat sessions."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        print("Unauthorized access to recent_sessions API")
        return jsonify({'success': False, 'message': 'Unauthorized'})

    limit = request.args.get('limit', 10, type=int)
    print(f"Recent sessions API: Requested {limit} sessions")

    db = Database(DB_PATH)

    query = """
        SELECT cs.session_id, cs.customer_id, cs.session_start, cs.session_end,
               cs.language, c.username, c.first_name, c.last_name
        FROM chat_sessions cs
        LEFT JOIN customers c ON cs.customer_id = c.customer_id
        ORDER BY cs.session_start DESC
        LIMIT ?
    """

    sessions = db.execute_query(query, (limit,))
    print(f"Recent sessions API: Found {len(sessions)} sessions")

    # Convert datetime objects to strings for JSON serialization
    for s in sessions:
        if 'session_start' in s and s['session_start']:
            s['session_start'] = str(s['session_start'])
        if 'session_end' in s and s['session_end']:
            s['session_end'] = str(s['session_end'])

    return jsonify({
        'success': True,
        'sessions': sessions
    })

@app.route('/api/admin/recent_users', methods=['GET'])
def recent_users():
    """Get recent users."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    limit = request.args.get('limit', 10, type=int)

    db = Database(DB_PATH)

    # Get recent customers
    customers_query = """
        SELECT customer_id as id, username, first_name, last_name, email,
               'customer' as role, created_at
        FROM customers
        ORDER BY created_at DESC
        LIMIT ?
    """

    customers = db.execute_query(customers_query, (limit,))

    # Get recent staff
    staff_query = """
        SELECT staff_id as id, username, first_name, last_name, email,
               role, created_at
        FROM staff
        ORDER BY created_at DESC
        LIMIT ?
    """

    staff = db.execute_query(staff_query, (limit,))

    # Combine and sort
    users = sorted(customers + staff, key=lambda x: x['created_at'], reverse=True)[:limit]

    return jsonify({
        'success': True,
        'users': users
    })

@app.route('/api/admin/all_sessions', methods=['GET'])
def all_sessions():
    """Get all chat sessions."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        print("Unauthorized access to all_sessions API")
        return jsonify({'success': False, 'message': 'Unauthorized'})

    db = Database(DB_PATH)

    query = """
        SELECT cs.session_id, cs.customer_id, cs.session_start, cs.session_end,
               cs.language, c.username, c.first_name, c.last_name
        FROM chat_sessions cs
        LEFT JOIN customers c ON cs.customer_id = c.customer_id
        ORDER BY cs.session_start DESC
    """

    sessions = db.execute_query(query)
    print(f"All sessions API: Found {len(sessions)} sessions")

    # Convert datetime objects to strings for JSON serialization
    for s in sessions:
        if 'session_start' in s and s['session_start']:
            s['session_start'] = str(s['session_start'])
        if 'session_end' in s and s['session_end']:
            s['session_end'] = str(s['session_end'])

    return jsonify({
        'success': True,
        'sessions': sessions
    })

@app.route('/api/admin/all_users', methods=['GET'])
def all_users():
    """Get all users with search and filter support."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Get search and filter parameters
    search_term = request.args.get('search', '').strip()
    role_filter = request.args.get('role')  # 'customer', 'agent', 'manager', or None for all
    status = request.args.get('status')  # 'active', 'inactive', or None for all

    # Validate pagination parameters
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 10

    db = Database(DB_PATH)

    # Build customer query with filters
    customer_where_clauses = []
    customer_params = []

    if search_term:
        customer_where_clauses.append("(username LIKE ? OR email LIKE ? OR first_name LIKE ? OR last_name LIKE ?)")
        search_pattern = f"%{search_term}%"
        customer_params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

    if status == 'inactive':
        customer_where_clauses.append("is_active = 0")
    elif status == 'active':
        customer_where_clauses.append("is_active = 1")

    customer_where_clause = " WHERE " + " AND ".join(customer_where_clauses) if customer_where_clauses else ""

    # Build staff query with filters
    staff_where_clauses = []
    staff_params = []

    if search_term:
        staff_where_clauses.append("(username LIKE ? OR email LIKE ? OR first_name LIKE ? OR last_name LIKE ?)")
        search_pattern = f"%{search_term}%"
        staff_params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

    if role_filter == 'agent':
        staff_where_clauses.append("role = 'agent'")
    elif role_filter == 'manager':
        staff_where_clauses.append("role = 'manager'")

    if status == 'inactive':
        staff_where_clauses.append("is_active = 0")
    elif status == 'active':
        staff_where_clauses.append("is_active = 1")

    staff_where_clause = " WHERE " + " AND ".join(staff_where_clauses) if staff_where_clauses else ""

    # Get all customers if not filtering by role or if role is 'customer'
    customers = []
    if not role_filter or role_filter == 'customer':
        customers_query = f"""
            SELECT customer_id as id, username, first_name, last_name, email,
                   'customer' as role, created_at, last_login, 1 as is_active
            FROM customers
            {customer_where_clause}
        """
        customers = db.execute_query(customers_query, tuple(customer_params))

    # Get all staff if not filtering by role or if role is 'agent' or 'manager'
    staff = []
    if not role_filter or role_filter in ['agent', 'manager']:
        staff_query = f"""
            SELECT staff_id as id, username, first_name, last_name, email,
                   role, created_at, last_login, is_active
            FROM staff
            {staff_where_clause}
        """
        staff = db.execute_query(staff_query, tuple(staff_params))

    # Combine and sort
    all_users = sorted(customers + staff, key=lambda x: x['created_at'], reverse=True)

    # Calculate total count
    total_users = len(all_users)

    # Calculate total pages
    total_pages = (total_users + per_page - 1) // per_page

    # Apply pagination manually
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_users)
    users = all_users[start_idx:end_idx]

    return jsonify({
        'success': True,
        'users': users,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_items': total_users,
            'total_pages': total_pages
        }
    })

@app.route('/api/admin/all_products', methods=['GET'])
def all_products():
    """Get all products with pagination, search and filter support."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Get search and filter parameters
    search_term = request.args.get('search', '').strip()
    category_id = request.args.get('category_id', type=int)
    goal_id = request.args.get('goal_id')  # Health goal ID
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    status = request.args.get('status')  # 'active', 'inactive', or None for all

    # Debug log
    print(f"API Request - all_products: goal_id={goal_id}, category_id={category_id}, search={search_term}")

    # Validate pagination parameters
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 10

    # Calculate offset
    offset = (page - 1) * per_page

    db = Database(DB_PATH)

    # Check if we're filtering by health goal
    if goal_id:
        print(f"Filtering by health goal: {goal_id}")

        # Get all products with health benefits - COMPLETE INFORMATION
        query = """
            SELECT p.product_id, p.name, p.description, p.price, p.stock_quantity,
                   p.image_url, p.brand, p.health_benefits, p.ingredients,
                   p.usage_instructions, p.is_active, p.category_id
            FROM products p
            WHERE p.health_benefits IS NOT NULL AND p.health_benefits != ''
        """
        all_products = db.execute_query(query)
        print(f"Found {len(all_products)} products with health benefits")

        # Import the health goals module
        from rock.health_goals import match_user_goal_to_products

        # Filter products by health goal
        matching_products = match_user_goal_to_products(goal_id, all_products)
        print(f"Found {len(matching_products)} products matching goal '{goal_id}'")

        # Extract product IDs
        product_ids = [p['product_id'] for p in matching_products]

        # If no products match this goal, return empty result
        if not product_ids:
            print(f"No products match goal '{goal_id}'")
            return jsonify({
                'success': True,
                'products': [],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_items': 0,
                    'total_pages': 0
                }
            })

        # Build the query with health goal filter and other filters
        where_clauses = ["p.product_id IN (" + ",".join("?" for _ in product_ids) + ")"]
        params = product_ids.copy()
    else:
        # Build the query with regular filters
        where_clauses = []
        params = []

    # Add other filters
    if search_term:
        where_clauses.append("(p.name LIKE ? OR p.description LIKE ? OR p.brand LIKE ?)")
        search_pattern = f"%{search_term}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    if category_id:
        where_clauses.append("p.category_id = ?")
        params.append(category_id)

    if min_price is not None:
        where_clauses.append("p.price >= ?")
        params.append(min_price)

    if max_price is not None:
        where_clauses.append("p.price <= ?")
        params.append(max_price)

    if status == 'active':
        where_clauses.append("p.is_active = 1")
    elif status == 'inactive':
        where_clauses.append("p.is_active = 0")

    # Construct the WHERE clause
    where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Get total count with filters
    count_query = f"""
        SELECT COUNT(*) as total
        FROM products p
        {where_clause}
    """
    count_result = db.execute_query(count_query, tuple(params))
    total_products = count_result[0]['total'] if count_result else 0

    # Calculate total pages
    total_pages = (total_products + per_page - 1) // per_page

    # Get products for current page with filters - COMPLETE INFORMATION
    query = f"""
        SELECT p.product_id, p.name, p.description, p.price, p.stock_quantity,
               p.image_url, p.brand, p.health_benefits, p.ingredients,
               p.usage_instructions, p.is_active, p.category_id
        FROM products p
        {where_clause}
        ORDER BY p.name
        LIMIT ? OFFSET ?
    """

    # Add pagination parameters
    query_params = params + [per_page, offset]
    products = db.execute_query(query, tuple(query_params))

    print(f"Returning {len(products)} products after filtering")

    return jsonify({
        'success': True,
        'products': products,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_items': total_products,
            'total_pages': total_pages
        }
    })

@app.route('/api/admin/all_faqs', methods=['GET'])
def all_faqs():
    """Get all FAQs with pagination, search and filter support."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Get search and filter parameters
    search_term = request.args.get('search', '').strip()
    category = request.args.get('category')
    status = request.args.get('status')  # 'active', 'inactive', or None for all

    # Validate pagination parameters
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 10

    # Calculate offset
    offset = (page - 1) * per_page

    db = Database(DB_PATH)

    # Build the query with filters
    where_clauses = []
    params = []

    if search_term:
        where_clauses.append("(question LIKE ? OR answer LIKE ?)")
        search_pattern = f"%{search_term}%"
        params.extend([search_pattern, search_pattern])

    if category:
        # Make the category filter case-insensitive
        where_clauses.append("LOWER(category) = LOWER(?)")
        params.append(category)

    # Language filter removed as the application will auto-translate

    if status == 'active':
        where_clauses.append("is_active = 1")
    elif status == 'inactive':
        where_clauses.append("is_active = 0")

    # Construct the WHERE clause
    where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Get total count with filters
    count_query = f"""
        SELECT COUNT(*) as total
        FROM faqs
        {where_clause}
    """
    count_result = db.execute_query(count_query, tuple(params))
    total_faqs = count_result[0]['total'] if count_result else 0

    # Calculate total pages
    total_pages = (total_faqs + per_page - 1) // per_page

    # Get FAQs for current page with filters
    query = f"""
        SELECT faq_id, question, answer, category, language, is_active
        FROM faqs
        {where_clause}
        ORDER BY category, question
        LIMIT ? OFFSET ?
    """

    # Add pagination parameters
    query_params = params + [per_page, offset]
    faqs = db.execute_query(query, tuple(query_params))

    return jsonify({
        'success': True,
        'faqs': faqs,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_items': total_faqs,
            'total_pages': total_pages
        }
    })

@app.route('/api/admin/customer_details', methods=['GET'])
def admin_customer_details():
    """Get customer details including order history."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    customer_id = request.args.get('customer_id', type=int)
    if not customer_id:
        return jsonify({'success': False, 'message': 'Missing customer ID'})

    db = Database(DB_PATH)

    # Get customer details
    customer_query = """
        SELECT customer_id, username, email, phone_number, first_name, last_name,
               date_of_birth, gender, preferred_language, created_at, last_login, is_active
        FROM customers
        WHERE customer_id = ?
    """
    customer_result = db.execute_query(customer_query, (customer_id,))

    if not customer_result:
        return jsonify({'success': False, 'message': 'Customer not found'})

    customer = customer_result[0]

    # Get customer orders
    orders_query = """
        SELECT o.order_id, o.order_date, o.total_amount, o.status,
               o.payment_method, o.payment_status, o.shipping_address, o.tracking_number
        FROM orders o
        WHERE o.customer_id = ?
        ORDER BY o.order_date DESC
    """
    orders = db.execute_query(orders_query, (customer_id,))

    # Convert datetime objects to strings for JSON serialization
    if 'created_at' in customer and customer['created_at']:
        customer['created_at'] = str(customer['created_at'])
    if 'last_login' in customer and customer['last_login']:
        customer['last_login'] = str(customer['last_login'])

    for order in orders:
        if 'order_date' in order and order['order_date']:
            order['order_date'] = str(order['order_date'])

    return jsonify({
        'success': True,
        'customer': customer,
        'orders': orders
    })

@app.route('/api/admin/order_details', methods=['GET'])
def admin_order_details():
    """Get order details including order items."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    order_id = request.args.get('order_id', type=int)
    if not order_id:
        return jsonify({'success': False, 'message': 'Missing order ID'})

    db = Database(DB_PATH)

    # Get order details
    order_query = """
        SELECT o.order_id, o.customer_id, o.order_date, o.total_amount, o.status,
               o.payment_method, o.payment_status, o.shipping_address, o.tracking_number,
               c.first_name || ' ' || c.last_name as customer_name
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_id = ?
    """
    order_result = db.execute_query(order_query, (order_id,))

    if not order_result:
        return jsonify({'success': False, 'message': 'Order not found'})

    order = order_result[0]

    # Get order items
    items_query = """
        SELECT oi.order_item_id, oi.product_id, oi.quantity, oi.unit_price, oi.subtotal,
               p.name as product_name
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = ?
    """
    items = db.execute_query(items_query, (order_id,))

    # Convert datetime objects to strings for JSON serialization
    if 'order_date' in order and order['order_date']:
        order['order_date'] = str(order['order_date'])

    return jsonify({
        'success': True,
        'order': order,
        'items': items
    })

# Agent API Endpoints
@app.route('/api/agent/active_chats', methods=['GET'])
def agent_active_chats():
    """Get active chat sessions for agent interface."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    db = Database(DB_PATH)

    # Get active sessions that need agent assistance (unassigned sessions that requested agents)
    # Order by most recent agent requests first
    query = """
        SELECT cs.session_id, cs.customer_id, cs.session_start, cs.language,
               c.username, c.first_name, c.last_name, cs.agent_id,
               cs.needs_agent, cs.agent_requested_at,
               (SELECT COUNT(*) FROM chat_messages WHERE session_id = cs.session_id) as message_count
        FROM chat_sessions cs
        LEFT JOIN customers c ON cs.customer_id = c.customer_id
        WHERE cs.session_end IS NULL AND cs.agent_id IS NULL AND cs.needs_agent = 1
        ORDER BY cs.agent_requested_at DESC, cs.session_start DESC
    """

    chats = db.execute_query(query)

    # Enhance chat data to better handle guest users
    for chat in chats:
        # Convert datetime objects to strings for JSON serialization
        if 'session_start' in chat and chat['session_start']:
            chat['session_start'] = str(chat['session_start'])

        # Handle guest vs registered users
        if not chat.get('customer_id'):
            # This is a guest user
            chat['customer_name'] = f"Guest User (Session: {str(chat['session_id'])[-8:]})"
            chat['is_guest'] = True
            chat['display_name'] = chat['customer_name']
        else:
            # This is a registered user
            first_name = (chat.get('first_name') or '').strip()
            last_name = (chat.get('last_name') or '').strip()
            username = (chat.get('username') or '').strip()

            if first_name or last_name:
                chat['customer_name'] = f"{first_name} {last_name}".strip()
            elif username:
                chat['customer_name'] = username
            else:
                chat['customer_name'] = f"User {chat['customer_id']}"

            chat['is_guest'] = False
            chat['display_name'] = chat['customer_name']

    return jsonify({
        'success': True,
        'chats': chats
    })

@app.route('/api/agent/chat_messages', methods=['GET'])
def agent_chat_messages():
    """Get messages for a specific chat session."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    session_id = request.args.get('session_id', type=int)
    if not session_id:
        return jsonify({'success': False, 'message': 'Missing session ID'})

    db = Database(DB_PATH)

    # Get session details
    session_query = """
        SELECT cs.session_id, cs.customer_id, cs.language,
               c.username, c.first_name, c.last_name
        FROM chat_sessions cs
        LEFT JOIN customers c ON cs.customer_id = c.customer_id
        WHERE cs.session_id = ?
    """
    session_result = db.execute_query(session_query, (session_id,))

    if not session_result:
        return jsonify({'success': False, 'message': 'Chat session not found'})

    session_data = session_result[0]
    customer_name = None

    if session_data['customer_id']:
        customer_name = f"{session_data['first_name'] or ''} {session_data['last_name'] or ''}".strip() or session_data['username']

    # Get messages
    messages_query = """
        SELECT cm.message_id, cm.sender_type, cm.sender_id, cm.message_text, cm.intent_id, cm.timestamp,
               CASE
                   WHEN cm.sender_type = 'agent' THEN (
                       SELECT s.first_name FROM staff s WHERE s.staff_id = cm.sender_id
                   )
                   ELSE NULL
               END as sender_name
        FROM chat_messages cm
        WHERE cm.session_id = ?
        ORDER BY cm.timestamp
    """
    messages = db.execute_query(messages_query, (session_id,))

    # Convert datetime objects to strings for JSON serialization
    for message in messages:
        if 'timestamp' in message and message['timestamp']:
            # Ensure timestamp is in ISO format for proper JavaScript parsing
            if isinstance(message['timestamp'], str):
                # If it's already a string, try to parse and reformat
                try:
                    dt = datetime.strptime(message['timestamp'], '%Y-%m-%d %H:%M:%S')
                    message['timestamp'] = dt.isoformat()
                except ValueError:
                    # If parsing fails, keep the original string
                    pass
            else:
                # If it's a datetime object, convert to ISO format
                message['timestamp'] = message['timestamp'].isoformat()

    return jsonify({
        'success': True,
        'messages': messages,
        'customer_name': customer_name
    })

@app.route('/api/agent/customer_details', methods=['GET'])
def agent_customer_details():
    """Get customer details including order history for agent interface."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    customer_id = request.args.get('customer_id', type=int)
    if not customer_id:
        return jsonify({'success': False, 'message': 'Missing customer ID'})

    db = Database(DB_PATH)

    # Get customer details
    customer_query = """
        SELECT customer_id, username, email, phone_number, first_name, last_name,
               date_of_birth, gender, preferred_language, created_at, last_login, is_active
        FROM customers
        WHERE customer_id = ?
    """
    customer_result = db.execute_query(customer_query, (customer_id,))

    if not customer_result:
        return jsonify({'success': False, 'message': 'Customer not found'})

    customer = customer_result[0]

    # Get customer orders
    orders_query = """
        SELECT o.order_id, o.order_date, o.total_amount, o.status,
               o.payment_method, o.payment_status
        FROM orders o
        WHERE o.customer_id = ?
        ORDER BY o.order_date DESC
    """
    orders = db.execute_query(orders_query, (customer_id,))

    # Convert datetime objects to strings for JSON serialization
    if 'created_at' in customer and customer['created_at']:
        customer['created_at'] = str(customer['created_at'])
    if 'last_login' in customer and customer['last_login']:
        customer['last_login'] = str(customer['last_login'])

    for order in orders:
        if 'order_date' in order and order['order_date']:
            order['order_date'] = str(order['order_date'])

    return jsonify({
        'success': True,
        'customer': customer,
        'orders': orders
    })

@app.route('/api/agent/customer_orders', methods=['GET'])
def agent_customer_orders():
    """Get all orders for a specific customer."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    customer_id = request.args.get('customer_id', type=int)
    if not customer_id:
        return jsonify({'success': False, 'message': 'Missing customer ID'})

    db = Database(DB_PATH)

    # Get customer orders
    orders_query = """
        SELECT o.order_id, o.order_date, o.total_amount, o.status,
               o.payment_method, o.payment_status, o.shipping_address, o.tracking_number
        FROM orders o
        WHERE o.customer_id = ?
        ORDER BY o.order_date DESC
    """
    orders = db.execute_query(orders_query, (customer_id,))

    # Convert datetime objects to strings for JSON serialization
    for order in orders:
        if 'order_date' in order and order['order_date']:
            order['order_date'] = str(order['order_date'])

    return jsonify({
        'success': True,
        'orders': orders
    })

@app.route('/api/agent/send_message', methods=['POST'])
def agent_send_message():
    """Send a message as an agent."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    session_id = data.get('session_id')
    message = data.get('message')
    agent_id = data.get('agent_id') or session.get('user_id')

    if not all([session_id, message, agent_id]):
        return jsonify({'success': False, 'message': 'Missing required parameters'})

    db = Database(DB_PATH)

    # Check if the session exists and is not already ended
    check_query = """
        SELECT session_id FROM chat_sessions
        WHERE session_id = ? AND session_end IS NULL
    """

    session_exists = db.execute_query(check_query, (session_id,))

    if not session_exists:
        return jsonify({'success': False, 'message': 'Chat session not found or already ended'})

    # Get current timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Insert the message
    query = """
        INSERT INTO chat_messages (session_id, sender_type, sender_id, message_text, timestamp)
        VALUES (?, 'agent', ?, ?, ?)
    """

    try:
        message_id = db.execute_update(
            query,
            (session_id, agent_id, message, timestamp)
        )

        return jsonify({
            'success': True,
            'message_id': message_id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/agent/end_chat', methods=['POST'])
def agent_end_chat():
    """End a chat session."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({'success': False, 'message': 'Missing session ID'})

    db = Database(DB_PATH)

    # First check if the session exists and is not already ended
    check_query = """
        SELECT session_id FROM chat_sessions
        WHERE session_id = ? AND session_end IS NULL
    """

    session_exists = db.execute_query(check_query, (session_id,))

    if not session_exists:
        return jsonify({'success': False, 'message': 'Chat session not found or already ended'})

    # Update the session end time
    query = """
        UPDATE chat_sessions
        SET session_end = datetime('now')
        WHERE session_id = ? AND session_end IS NULL
    """

    try:
        db.execute_update(query, (session_id,))

        # Add a system message indicating the chat was ended by an agent
        agent_name = session.get('name', 'An agent')
        system_message = f"Chat ended by {agent_name}."

        message_query = """
            INSERT INTO chat_messages (session_id, sender_type, sender_id, message_text, timestamp)
            VALUES (?, 'system', NULL, ?, datetime('now'))
        """

        db.execute_update(message_query, (session_id, system_message))

        return jsonify({
            'success': True,
            'message': 'Chat ended successfully',
            'chat_ended': True,
            'end_message': system_message
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/agent/transfer_chat', methods=['POST'])
def agent_transfer_chat():
    """Transfer a chat to another agent."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    session_id = data.get('session_id')
    agent_id = data.get('agent_id')

    if not all([session_id, agent_id]):
        return jsonify({'success': False, 'message': 'Missing required parameters'})

    db = Database(DB_PATH)

    # Check if the session exists and is not already ended
    check_query = """
        SELECT session_id FROM chat_sessions
        WHERE session_id = ? AND session_end IS NULL
    """

    session_exists = db.execute_query(check_query, (session_id,))

    if not session_exists:
        return jsonify({'success': False, 'message': 'Chat session not found or already ended'})

    # Check if the target agent exists and is active
    agent_query = """
        SELECT staff_id, first_name, last_name
        FROM staff
        WHERE staff_id = ? AND is_active = 1
    """

    agent_result = db.execute_query(agent_query, (agent_id,))

    if not agent_result:
        return jsonify({'success': False, 'message': 'Target agent not found or inactive'})

    agent = agent_result[0]

    # Update the session with the new agent
    update_query = """
        UPDATE chat_sessions
        SET agent_id = ?
        WHERE session_id = ? AND session_end IS NULL
    """

    try:
        db.execute_update(update_query, (agent_id, session_id))

        # Add a system message indicating the chat was transferred
        current_agent_name = session.get('name', 'An agent')
        target_agent_name = f"{agent['first_name']} {agent['last_name']}".strip()
        system_message = f"Chat transferred from {current_agent_name} to {target_agent_name}."

        message_query = """
            INSERT INTO chat_messages (session_id, sender_type, sender_id, message_text, timestamp)
            VALUES (?, 'system', NULL, ?, datetime('now'))
        """

        db.execute_update(message_query, (session_id, system_message))

        # Emit WebSocket event to notify all users about the transfer
        room = f"session_{session_id}"
        socketio.emit('chat_transferred', {
            'session_id': session_id,
            'new_agent_id': agent_id,
            'new_agent_name': target_agent_name,
            'message': system_message
        }, room=room)

        # Also emit to the new agent specifically to notify them of the new assignment
        socketio.emit('new_chat_assigned', {
            'session_id': session_id,
            'message': f'You have been assigned a new chat from {current_agent_name}.'
        }, room=f"agent_{agent_id}")

        # Emit a specific event to ensure the new agent loads complete chat history
        socketio.emit('load_complete_history', {
            'session_id': session_id
        }, room=f"agent_{agent_id}")

        return jsonify({'success': True, 'message': 'Chat transferred successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/agent/available_agents', methods=['GET'])
def agent_available_agents():
    """Get a list of available agents for chat transfer."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    db = Database(DB_PATH)

    # Get all active and online agents
    query = """
        SELECT s.staff_id, s.username, s.first_name, s.last_name, s.email, s.online_status, s.last_activity,
               (SELECT COUNT(*) FROM chat_sessions WHERE agent_id = s.staff_id AND session_end IS NULL) as active_chats
        FROM staff s
        WHERE s.role = 'agent' AND s.is_active = 1
        ORDER BY s.online_status DESC, s.first_name, s.last_name
    """

    agents = db.execute_query(query)

    # Convert datetime objects to strings for JSON serialization
    for agent in agents:
        if 'last_activity' in agent and agent['last_activity']:
            agent['last_activity'] = str(agent['last_activity'])

    return jsonify({
        'success': True,
        'agents': agents
    })

@app.route('/api/agent/set_status', methods=['POST'])
def agent_set_status():
    """Set the online status of an agent."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    is_online = data.get('is_online')
    reason = data.get('reason', '')
    agent_id = data.get('agent_id') or session.get('user_id')

    if is_online is None or not agent_id:
        return jsonify({'success': False, 'message': 'Missing required parameters'})

    try:
        # Create an agent interface to use its methods
        agent_interface = AgentInterface(DB_PATH)
        result = agent_interface.set_agent_status(agent_id, is_online)

        if result:
            # Log the status change with reason
            if reason:
                app.logger.info(f"Agent {agent_id} status changed to {'online' if is_online else 'offline'}: {reason}")

            return jsonify({
                'success': True,
                'message': f'Agent status set to {"online" if is_online else "offline"}',
                'reason': reason
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to update agent status'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/agent/my_sessions', methods=['GET'])
def agent_my_sessions():
    """Get chat sessions assigned to the current agent."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    agent_id = session.get('user_id')

    # Debug logging to track which agent is making the request
    app.logger.info(f"Agent {agent_id} requesting their sessions")

    db = Database(DB_PATH)

    # Get sessions assigned to this agent
    query = """
        SELECT cs.session_id, cs.customer_id, cs.session_start, cs.language,
               c.username, c.first_name, c.last_name, c.email,
               (SELECT COUNT(*) FROM chat_messages WHERE session_id = cs.session_id) as message_count,
               (SELECT MAX(timestamp) FROM chat_messages WHERE session_id = cs.session_id) as last_activity
        FROM chat_sessions cs
        LEFT JOIN customers c ON cs.customer_id = c.customer_id
        WHERE cs.session_end IS NULL AND cs.agent_id = ?
        ORDER BY cs.session_start DESC
    """

    sessions = db.execute_query(query, (agent_id,))

    # Debug logging to show which sessions are returned
    session_ids = [s['session_id'] for s in sessions]
    app.logger.info(f"Agent {agent_id} has {len(sessions)} sessions: {session_ids}")

    # Convert datetime objects to strings for JSON serialization
    for s in sessions:
        if 'session_start' in s and s['session_start']:
            s['session_start'] = str(s['session_start'])
        if 'last_activity' in s and s['last_activity']:
            s['last_activity'] = str(s['last_activity'])

    return jsonify({
        'success': True,
        'sessions': sessions
    })

@app.route('/api/agent/update_activity', methods=['POST'])
def agent_update_activity():
    """Update the last activity time for an agent."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    agent_id = session.get('user_id')
    data = request.json or {}
    timestamp = data.get('timestamp', datetime.now().timestamp() * 1000)

    try:
        # Create an agent interface to use its methods
        agent_interface = AgentInterface(DB_PATH)
        result = agent_interface.update_agent_activity(agent_id)

        if result:
            return jsonify({
                'success': True,
                'message': 'Agent activity updated',
                'timestamp': timestamp
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to update agent activity'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/agent/heartbeat', methods=['POST'])
def agent_heartbeat():
    """Receive heartbeat from agent to confirm they are still online."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    agent_id = session.get('user_id')
    data = request.json or {}
    client_timestamp = data.get('timestamp', datetime.now().timestamp() * 1000)

    try:
        # Update agent activity
        agent_interface = AgentInterface(DB_PATH)
        result = agent_interface.update_agent_activity(agent_id)

        if result:
            return jsonify({
                'success': True,
                'message': 'Heartbeat received',
                'server_timestamp': datetime.now().timestamp() * 1000,
                'client_timestamp': client_timestamp
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to process heartbeat'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/agent/ping', methods=['GET'])
def agent_ping():
    """Simple ping endpoint to check connection."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    return jsonify({
        'success': True,
        'message': 'Pong',
        'timestamp': datetime.now().timestamp() * 1000,
        'agent_id': session.get('user_id')
    })

@app.route('/api/agent/set_offline', methods=['POST'])
def agent_set_offline():
    """Set agent offline immediately (used by beacon on page unload)."""
    # This endpoint is called by navigator.sendBeacon, so we need to handle it differently
    try:
        # Get the raw data
        data = request.get_data()
        if data:
            try:
                data = json.loads(data)
            except:
                data = {}
        else:
            data = {}

        # Try to get agent ID from session or data
        agent_id = session.get('user_id')
        reason = data.get('reason', 'Browser closed')

        if agent_id:
            # Create an agent interface to use its methods
            agent_interface = AgentInterface(DB_PATH)
            result = agent_interface.set_agent_status(agent_id, False)

            if result:
                app.logger.info(f"Agent {agent_id} set offline via beacon: {reason}")
                return jsonify({
                    'success': True,
                    'message': 'Agent set offline',
                    'reason': reason
                })

        return jsonify({'success': False, 'message': 'Failed to set agent offline'})
    except Exception as e:
        app.logger.error(f"Error in set_offline endpoint: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/agent/take_over_chat', methods=['POST'])
def agent_take_over_chat():
    """Take over a chat session."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({'success': False, 'message': 'Missing session ID'})

    try:
        # Create an agent interface to use its methods
        agent_interface = AgentInterface(DB_PATH)

        # Set current user
        agent_id = session.get('user_id')
        agent_info = agent_interface.db.execute_query(
            "SELECT * FROM staff WHERE staff_id = ?",
            (agent_id,)
        )

        if not agent_info:
            return jsonify({'success': False, 'message': 'Agent not found'})

        agent_interface.current_user = agent_info[0]

        # Take over the session
        result = agent_interface.take_over_session(session_id)

        if result:
            return jsonify({'success': True, 'message': 'Chat taken over successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to take over chat'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Additional API Endpoints for Admin Dashboard

@app.route('/api/admin/session_messages', methods=['GET'])
def session_messages():
    """Get messages for a specific chat session."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    session_id = request.args.get('session_id', type=int)
    if not session_id:
        return jsonify({'success': False, 'message': 'Missing session ID'})

    db = Database(DB_PATH)

    # Get messages for this session
    query = """
        SELECT message_id, sender_type, sender_id, message_text, intent_id, timestamp,
               CASE
                   WHEN sender_type = 'agent' THEN (
                       SELECT s.first_name FROM staff s WHERE s.staff_id = sender_id
                   )
                   ELSE NULL
               END as sender_name
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY timestamp
    """

    messages = db.execute_query(query, (session_id,))

    # Convert datetime objects to strings for JSON serialization
    for message in messages:
        if 'timestamp' in message and message['timestamp']:
            # Ensure timestamp is in ISO format for proper JavaScript parsing
            if isinstance(message['timestamp'], str):
                # If it's already a string, try to parse and reformat
                try:
                    dt = datetime.strptime(message['timestamp'], '%Y-%m-%d %H:%M:%S')
                    message['timestamp'] = dt.isoformat()
                except ValueError:
                    # If parsing fails, keep the original string
                    pass
            else:
                # If it's a datetime object, convert to ISO format
                message['timestamp'] = message['timestamp'].isoformat()

    return jsonify({
        'success': True,
        'messages': messages
    })

@app.route('/api/admin/all_categories', methods=['GET'])
def all_categories():
    """Get all product categories."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    # Check if we should filter out empty categories
    only_with_products = request.args.get('only_with_products', 'false').lower() == 'true'
    # Check if we should only return active categories
    only_active = request.args.get('only_active', 'true').lower() == 'true'

    db = Database(DB_PATH)

    # Build the query based on parameters
    if only_with_products and only_active:
        # Get only active categories that have products
        query = """
            SELECT c.category_id, c.name, c.description, c.parent_category_id, c.is_active
            FROM categories c
            WHERE c.is_active = 1
            AND EXISTS (
                SELECT 1 FROM products p WHERE p.category_id = c.category_id
            )
            ORDER BY c.name
        """
    elif only_with_products:
        # Get only categories that have products
        query = """
            SELECT c.category_id, c.name, c.description, c.parent_category_id, c.is_active
            FROM categories c
            WHERE EXISTS (
                SELECT 1 FROM products p WHERE p.category_id = c.category_id
            )
            ORDER BY c.name
        """
    elif only_active:
        # Get only active categories
        query = """
            SELECT category_id, name, description, parent_category_id, is_active
            FROM categories
            WHERE is_active = 1
            ORDER BY name
        """
    else:
        # Get all categories
        query = """
            SELECT category_id, name, description, parent_category_id, is_active
            FROM categories
            ORDER BY name
        """

    categories = db.execute_query(query)

    return jsonify({
        'success': True,
        'categories': categories
    })

@app.route('/api/admin/health_benefits', methods=['GET'])
def get_health_benefits():
    """Get all health benefits."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id'):
        app.logger.warning(f"Unauthorized access attempt to health_benefits API. Session: {session}")
        return jsonify({'success': False, 'message': 'Unauthorized - Not logged in'})

    if session.get('role') not in ['manager', 'agent']:
        app.logger.warning(f"Unauthorized role accessing health_benefits API. Role: {session.get('role')}")
        return jsonify({'success': False, 'message': 'Unauthorized - Invalid role'})

    # Check if we should filter by category
    category = request.args.get('category', None)
    only_active = request.args.get('only_active', 'true').lower() == 'true'

    db = Database(DB_PATH)

    try:
        # Build the query based on parameters
        query = """
            SELECT benefit_id, name, description, category, is_active
            FROM health_benefits
            WHERE 1=1
        """

        params = []

        if category:
            query += " AND category = ?"
            params.append(category)

        if only_active:
            query += " AND is_active = 1"

        query += " ORDER BY category, name"

        app.logger.info(f"Executing health benefits query: {query} with params: {params}")
        benefits = db.execute_query(query, tuple(params) if params else ())
        app.logger.info(f"Found {len(benefits)} health benefits")

        return jsonify({
            'success': True,
            'benefits': benefits
        })
    except Exception as e:
        app.logger.error(f"Error retrieving health benefits: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error retrieving health benefits: {str(e)}'
        })

@app.route('/api/admin/benefit_products', methods=['GET'])
def get_benefit_products():
    """Get products associated with a specific health benefit."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    benefit_id = request.args.get('benefit_id', type=int)
    if not benefit_id:
        return jsonify({'success': False, 'message': 'Missing benefit ID'})

    db = Database(DB_PATH)

    try:
        # Get the benefit details
        benefit_query = """
            SELECT benefit_id, name, description, category, is_active
            FROM health_benefits
            WHERE benefit_id = ?
        """
        benefit = db.execute_query(benefit_query, (benefit_id,))

        if not benefit:
            return jsonify({'success': False, 'message': 'Health benefit not found'})

        # Get products associated with this benefit - COMPLETE INFORMATION
        products_query = """
            SELECT p.product_id, p.name, p.description, p.price, p.stock_quantity,
                   p.image_url, p.brand, p.health_benefits, p.ingredients,
                   p.usage_instructions, p.is_active, c.name as category
            FROM products p
            JOIN product_benefits pb ON p.product_id = pb.product_id
            JOIN categories c ON p.category_id = c.category_id
            WHERE pb.benefit_id = ?
            ORDER BY p.name
        """
        products = db.execute_query(products_query, (benefit_id,))

        return jsonify({
            'success': True,
            'benefit': benefit[0],
            'products': products
        })
    except Exception as e:
        app.logger.error(f"Error getting benefit products: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting benefit products: {str(e)}'
        })

@app.route('/api/admin/delete_health_benefit', methods=['POST'])
def delete_health_benefit():
    """Delete a health benefit."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'manager':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    benefit_id = data.get('benefit_id')
    force_delete = data.get('force_delete', False)

    if not benefit_id:
        return jsonify({'success': False, 'message': 'Missing benefit ID'})

    db = Database(DB_PATH)

    try:
        # First check if this benefit is associated with any products
        check_query = """
            SELECT COUNT(*) as count
            FROM product_benefits
            WHERE benefit_id = ?
        """
        result = db.execute_query(check_query, (benefit_id,))
        product_count = result[0]['count'] if result else 0

        # Get the benefit name for the response message
        name_query = "SELECT name FROM health_benefits WHERE benefit_id = ?"
        name_result = db.execute_query(name_query, (benefit_id,))
        benefit_name = name_result[0]['name'] if name_result else "Unknown"

        if product_count > 0 and not force_delete:
            # This benefit is used by products, so we should just mark it as inactive
            update_query = """
                UPDATE health_benefits
                SET is_active = 0
                WHERE benefit_id = ?
            """
            db.execute_update(update_query, (benefit_id,))

            # Get the products that use this benefit
            products_query = """
                SELECT p.product_id, p.name
                FROM products p
                JOIN product_benefits pb ON p.product_id = pb.product_id
                WHERE pb.benefit_id = ?
                ORDER BY p.name
            """
            products = db.execute_query(products_query, (benefit_id,))

            return jsonify({
                'success': True,
                'message': f'Health benefit "{benefit_name}" marked as inactive because it is used by {product_count} products',
                'deactivated': True,
                'product_count': product_count,
                'products': products
            })
        else:
            # If force_delete is true, remove all product associations first
            if force_delete and product_count > 0:
                # Remove all product associations
                remove_assoc_query = """
                    DELETE FROM product_benefits
                    WHERE benefit_id = ?
                """
                db.execute_update(remove_assoc_query, (benefit_id,))

                # Update the health_benefits field in products table
                products_query = """
                    SELECT product_id, health_benefits
                    FROM products
                    WHERE health_benefits LIKE ?
                """
                products = db.execute_query(products_query, (f'%{benefit_name}%',))

                for product in products:
                    product_id = product['product_id']
                    health_benefits = product['health_benefits']

                    if health_benefits:
                        # Remove the benefit from the comma-separated list
                        benefits_list = [b.strip() for b in health_benefits.split(',')]
                        if benefit_name in benefits_list:
                            benefits_list.remove(benefit_name)

                        # Update the product
                        new_benefits = ', '.join(benefits_list)
                        update_product_query = """
                            UPDATE products
                            SET health_benefits = ?
                            WHERE product_id = ?
                        """
                        db.execute_update(update_product_query, (new_benefits, product_id))

            # Delete the health benefit
            delete_query = """
                DELETE FROM health_benefits
                WHERE benefit_id = ?
            """
            db.execute_update(delete_query, (benefit_id,))

            return jsonify({
                'success': True,
                'message': f'Health benefit "{benefit_name}" deleted successfully',
                'deactivated': False,
                'force_deleted': force_delete and product_count > 0,
                'product_count': product_count
            })
    except Exception as e:
        app.logger.error(f"Error deleting health benefit: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error deleting health benefit: {str(e)}'
        })

@app.route('/api/health_goals', methods=['GET'])
def get_health_goals():
    """Get all standard health goals."""
    try:
        # Import the health goals module
        from rock.health_goals import get_all_standard_goals

        # Get all standard health goals
        goals = get_all_standard_goals()

        # Debug: Check products with health benefits
        db = Database(DB_PATH)
        products_with_benefits = db.execute_query(
            "SELECT product_id, name, health_benefits FROM products WHERE health_benefits IS NOT NULL AND health_benefits != ''"
        )

        print(f"Found {len(products_with_benefits)} products with health benefits:")
        for product in products_with_benefits:
            print(f"Product {product['product_id']} ({product['name']}): '{product['health_benefits']}'")

            # Check which goals this product matches
            from rock.health_goals import match_health_benefits_to_standard_goals
            matching_goals = match_health_benefits_to_standard_goals(product['health_benefits'])
            print(f"  - Matching goals: {matching_goals}")

        return jsonify({
            'success': True,
            'goals': goals
        })
    except Exception as e:
        app.logger.error(f"Error retrieving health goals: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error retrieving health goals: {str(e)}'
        })

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Get product recommendations based on health goal."""
    try:
        goal_id = request.args.get('goal_id')

        if not goal_id:
            return jsonify({
                'success': False,
                'message': 'Missing goal_id parameter'
            })

        # Create a RockChatbot instance to use its recommendation function
        chatbot = RockChatbot(DB_PATH)

        # Get recommendations for the goal
        recommendations = chatbot.get_product_recommendations(
            customer_id=None,  # No customer ID for agent interface
            goal_id=goal_id,
            session_id=None,   # No session ID for agent interface
            limit=100          # Get all matching products
        )

        return jsonify({
            'success': True,
            'products': recommendations
        })
    except Exception as e:
        app.logger.error(f"Error getting recommendations: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting recommendations: {str(e)}'
        })

@app.route('/api/admin/add_health_benefit', methods=['POST'])
def add_health_benefit():
    """Add a new health benefit."""
    # Check if user is logged in and has appropriate role
    print(f"Add health benefit request from user ID: {session.get('user_id')}, role: {session.get('role')}")

    # Allow both managers and agents to add health benefits
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        print(f"Unauthorized access to add_health_benefit: {session.get('role')}")
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    name = data.get('name')
    description = data.get('description', '')
    category = data.get('category')

    # Validate required fields
    if not all([name, category]):
        return jsonify({'success': False, 'message': 'Missing required fields'})

    db = Database(DB_PATH)

    # Check if benefit already exists
    check_query = "SELECT benefit_id FROM health_benefits WHERE name = ?"
    existing = db.execute_query(check_query, (name,))

    if existing:
        return jsonify({'success': False, 'message': 'A benefit with this name already exists'})

    # Add the benefit
    query = """
        INSERT INTO health_benefits (name, description, category, is_active)
        VALUES (?, ?, ?, 1)
    """

    try:
        benefit_id = db.execute_update(query, (name, description, category))
        return jsonify({
            'success': True,
            'message': 'Health benefit added successfully',
            'benefit_id': benefit_id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/product_benefits', methods=['GET'])
def get_product_benefits():
    """Get benefits for a specific product."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    product_id = request.args.get('product_id', type=int)
    if not product_id:
        return jsonify({'success': False, 'message': 'Missing product ID'})

    db = Database(DB_PATH)

    query = """
        SELECT hb.benefit_id, hb.name, hb.description, hb.category
        FROM health_benefits hb
        JOIN product_benefits pb ON hb.benefit_id = pb.benefit_id
        WHERE pb.product_id = ? AND hb.is_active = 1
        ORDER BY hb.category, hb.name
    """

    benefits = db.execute_query(query, (product_id,))

    return jsonify({
        'success': True,
        'benefits': benefits
    })

@app.route('/api/admin/health_benefit_details', methods=['GET'])
def get_health_benefit_details():
    """Get details for a specific health benefit."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    benefit_id = request.args.get('benefit_id', type=int)
    if not benefit_id:
        return jsonify({'success': False, 'message': 'Missing benefit ID'})

    db = Database(DB_PATH)

    query = """
        SELECT benefit_id, name, description, category, is_active
        FROM health_benefits
        WHERE benefit_id = ?
    """

    benefit = db.execute_query(query, (benefit_id,))

    if not benefit:
        return jsonify({'success': False, 'message': 'Health benefit not found'})

    return jsonify({
        'success': True,
        'benefit': benefit[0]
    })

@app.route('/api/admin/faq_categories', methods=['GET'])
def faq_categories():
    """Get all FAQ categories."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    db = Database(DB_PATH)

    # Get distinct categories from FAQs
    query = """
        SELECT DISTINCT category
        FROM faqs
        WHERE is_active = 1
        ORDER BY category
    """

    categories_result = db.execute_query(query)

    # Extract category names from the result
    categories = [item['category'] for item in categories_result]

    return jsonify({
        'success': True,
        'categories': categories
    })

@app.route('/api/test', methods=['GET'])
def test_api():
    """Test endpoint to verify API is working."""
    return jsonify({'success': True, 'message': 'API is working!'})



@app.route('/api/admin/add_category', methods=['POST'])
def add_category():
    """Add a new product category."""
    print("Add category endpoint called!")

    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        print("Unauthorized access to add_category")
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    print(f"Received data: {data}")
    name = data.get('name')
    description = data.get('description', '')
    parent_category_id = data.get('parent_category_id')
    is_active = data.get('is_active', True)

    # Validate required fields
    if not name:
        return jsonify({'success': False, 'message': 'Category name is required'})

    db = Database(DB_PATH)

    # Check if category with this name already exists
    check_query = """
        SELECT category_id FROM categories WHERE LOWER(name) = LOWER(?)
    """
    existing = db.execute_query(check_query, (name,))

    if existing:
        return jsonify({
            'success': True,
            'message': 'Category already exists',
            'category_id': existing[0]['category_id']
        })

    # Insert new category
    query = """
        INSERT INTO categories (name, description, parent_category_id, is_active)
        VALUES (?, ?, ?, ?)
    """

    try:
        category_id = db.execute_update(query, (
            name, description, parent_category_id, is_active
        ))

        return jsonify({
            'success': True,
            'message': 'Category added successfully',
            'category_id': category_id
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/product_details', methods=['GET'])
def product_details():
    """Get details for a specific product."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    product_id = request.args.get('product_id', type=int)
    if not product_id:
        return jsonify({'success': False, 'message': 'Missing product ID'})

    db = Database(DB_PATH)

    query = """
        SELECT product_id, name, description, category_id, price, stock_quantity,
               image_url, brand, health_benefits, ingredients, usage_instructions, is_active
        FROM products
        WHERE product_id = ?
    """

    product = db.execute_query(query, (product_id,))

    if not product:
        return jsonify({'success': False, 'message': 'Product not found'})

    return jsonify({
        'success': True,
        'product': product[0]
    })



@app.route('/api/admin/update_product', methods=['POST'])
def update_product():
    """Update an existing product."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'manager':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json

    # Validate required fields
    required_fields = ['product_id', 'name', 'category_id', 'price', 'stock_quantity']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'message': f'Missing required field: {field}'})

    db = Database(DB_PATH)

    # Get the product ID
    product_id = data['product_id']
    benefits = data.get('benefits', [])

    query = """
        UPDATE products
        SET name = ?, description = ?, category_id = ?, price = ?,
            stock_quantity = ?, image_url = ?, brand = ?, ingredients = ?,
            usage_instructions = ?, is_active = ?
        WHERE product_id = ?
    """

    try:
        db.execute_update(
            query,
            (
                data['name'],
                data.get('description', ''),
                data['category_id'],
                data['price'],
                data['stock_quantity'],
                data.get('image_url', ''),
                data.get('brand', ''),
                data.get('ingredients', ''),
                data.get('usage_instructions', ''),
                data.get('is_active', True),
                product_id
            )
        )

        # Handle health benefits (if provided)
        if 'benefits' in data:
            print(f"Updating health benefits for product {product_id}")

            # First, delete existing benefits for this product
            db.execute_update(
                "DELETE FROM product_benefits WHERE product_id = ?",
                (product_id,)
            )

            # Get the health benefit names and categories for these IDs
            benefit_names = []
            benefit_details = []
            for benefit_id in benefits:
                query = "SELECT name, category FROM health_benefits WHERE benefit_id = ?"
                result = db.execute_query(query, (benefit_id,))
                if result:
                    benefit_names.append(result[0]['name'])
                    benefit_details.append(result[0])

            # Join the benefit names into a comma-separated string
            health_benefits_str = ', '.join(benefit_names)
            print(f"Health benefits string: '{health_benefits_str}'")

            # Update the product with the health benefits string
            update_query = """
                UPDATE products
                SET health_benefits = ?
                WHERE product_id = ?
            """
            db.execute_update(update_query, (health_benefits_str, product_id))

            # Then add the new benefits to the junction table
            for benefit_id in benefits:
                db.execute_update(
                    "INSERT INTO product_benefits (product_id, benefit_id) VALUES (?, ?)",
                    (product_id, benefit_id)
                )

            # Log the benefit details for debugging
            print(f"Benefit details for product {product_id}:")
            for benefit in benefit_details:
                print(f"  - Name: '{benefit['name']}', Category: '{benefit['category']}'")

            # Check which goals this product matches
            from rock.health_goals import match_health_benefits_to_standard_goals

            # Create a dictionary mapping benefit names to their categories
            benefit_categories = {}
            for benefit in benefit_details:
                benefit_categories[benefit['name'].lower()] = benefit['category']

            matching_goals = match_health_benefits_to_standard_goals(health_benefits_str, benefit_categories)
            print(f"Product {product_id} matches goals: {matching_goals}")

        return jsonify({'success': True, 'message': 'Product updated successfully'})
    except Exception as e:
        print(f"Error updating product: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})



@app.route('/api/admin/faq_details', methods=['GET'])
def faq_details():
    """Get details for a specific FAQ."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    faq_id = request.args.get('faq_id', type=int)
    if not faq_id:
        return jsonify({'success': False, 'message': 'Missing FAQ ID'})

    db = Database(DB_PATH)

    query = """
        SELECT faq_id, question, answer, category, language, is_active
        FROM faqs
        WHERE faq_id = ?
    """

    faq = db.execute_query(query, (faq_id,))

    if not faq:
        return jsonify({'success': False, 'message': 'FAQ not found'})

    return jsonify({
        'success': True,
        'faq': faq[0]
    })







@app.route('/api/admin/analytics_data', methods=['GET'])
def analytics_data():
    """Get analytics data for the dashboard."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        db = Database(DB_PATH)

        # Get total sessions count
        total_sessions_query = """
            SELECT COUNT(*) as count
            FROM chat_sessions
        """
        total_sessions_result = db.execute_query(total_sessions_query)
        total_sessions = total_sessions_result[0]['count'] if total_sessions_result else 0

        # Get active users count (users with sessions in the last 30 days)
        active_users_query = """
            SELECT COUNT(DISTINCT customer_id) as count
            FROM chat_sessions
            WHERE customer_id IS NOT NULL
            AND session_start >= datetime('now', '-30 days')
        """
        active_users_result = db.execute_query(active_users_query)
        active_users = active_users_result[0]['count'] if active_users_result else 0

        # Get total messages count
        total_messages_query = """
            SELECT COUNT(*) as count
            FROM chat_messages
        """
        total_messages_result = db.execute_query(total_messages_query)
        total_messages = total_messages_result[0]['count'] if total_messages_result else 0

        # Get average session duration
        avg_duration_query = """
            SELECT AVG(
                CASE
                    WHEN session_end IS NOT NULL THEN
                        (julianday(session_end) - julianday(session_start)) * 86400
                    ELSE
                        (julianday('now') - julianday(session_start)) * 86400
                END
            ) as avg_duration
            FROM chat_sessions
        """
        avg_duration_result = db.execute_query(avg_duration_query)
        avg_session_duration = avg_duration_result[0]['avg_duration'] if avg_duration_result and avg_duration_result[0]['avg_duration'] is not None else 0

        # Get sessions by day for the last 30 days
        sessions_by_day_query = """
            SELECT date(session_start) as date, COUNT(*) as count
            FROM chat_sessions
            WHERE session_start >= datetime('now', '-30 days')
            GROUP BY date(session_start)
            ORDER BY date(session_start)
        """
        sessions_by_day = db.execute_query(sessions_by_day_query)

        # If no sessions in the last 30 days, provide empty data for chart
        if not sessions_by_day:
            today = datetime.now().strftime('%Y-%m-%d')
            sessions_by_day = [{'date': today, 'count': 0}]

        # Get top intents - handle case where intents table might be empty
        try:
            top_intents_query = """
                SELECT i.intent_id, i.intent_name, COUNT(cm.message_id) as count
                FROM intents i
                JOIN chat_messages cm ON i.intent_id = cm.intent_id
                WHERE cm.intent_id IS NOT NULL
                GROUP BY i.intent_id
                ORDER BY count DESC
                LIMIT 10
            """
            top_intents = db.execute_query(top_intents_query)

            # If no intents, provide placeholder data
            if not top_intents:
                top_intents = [
                    {'intent_id': 0, 'intent_name': 'No Data', 'count': 0}
                ]
        except Exception:
            # Fallback if intents table doesn't exist or has issues
            top_intents = [
                {'intent_id': 0, 'intent_name': 'No Data', 'count': 0}
            ]

        # Language distribution section removed as requested

        # Get satisfaction ratings
        try:
            satisfaction_ratings_query = """
                SELECT rating, feedback_text, created_at
                FROM chat_feedback
                ORDER BY created_at DESC
                LIMIT 100
            """
            satisfaction_ratings = db.execute_query(satisfaction_ratings_query)

            # If no ratings, provide placeholder data
            if not satisfaction_ratings:
                satisfaction_ratings = [
                    {'rating': 5, 'feedback_text': 'No feedback yet', 'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                ]
        except Exception:
            # Fallback if chat_feedback table doesn't exist
            satisfaction_ratings = [
                {'rating': 5, 'feedback_text': 'No feedback yet', 'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            ]

        # Get top products
        try:
            top_products_query = """
                SELECT p.product_id, p.name,
                    COUNT(DISTINCT cm.session_id) as views,
                    COUNT(DISTINCT oi.order_id) as orders,
                    COALESCE(SUM(oi.subtotal), 0) as revenue
                FROM products p
                LEFT JOIN chat_messages cm ON cm.message_text LIKE '%' || p.name || '%'
                LEFT JOIN order_items oi ON p.product_id = oi.product_id
                GROUP BY p.product_id
                ORDER BY revenue DESC
                LIMIT 10
            """
            top_products = db.execute_query(top_products_query)

            # Ensure revenue is never null
            for product in top_products:
                if product['revenue'] is None:
                    product['revenue'] = 0
                if product['views'] is None:
                    product['views'] = 0
                if product['orders'] is None:
                    product['orders'] = 0

            # If no products, provide placeholder
            if not top_products:
                top_products = [
                    {'product_id': 0, 'name': 'No products', 'views': 0, 'orders': 0, 'revenue': 0}
                ]
        except Exception as e:
            # Fallback if tables don't exist
            top_products = [
                {'product_id': 0, 'name': 'No products', 'views': 0, 'orders': 0, 'revenue': 0}
            ]

        # Convert datetime objects to strings for JSON serialization
        for session_day in sessions_by_day:
            if 'date' in session_day and session_day['date']:
                session_day['date'] = str(session_day['date'])

        for rating in satisfaction_ratings:
            if 'created_at' in rating and rating['created_at']:
                rating['created_at'] = str(rating['created_at'])

        return jsonify({
            'success': True,
            'total_sessions': total_sessions,
            'active_users': active_users,
            'total_messages': total_messages,
            'avg_session_duration': avg_session_duration,
            'sessions_by_day': sessions_by_day,
            'top_intents': top_intents,
            'satisfaction_ratings': satisfaction_ratings,
            'top_products': top_products
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error loading analytics data: {str(e)}'
        })

@app.route('/api/admin/all_promotions', methods=['GET'])
def all_promotions():
    """Get all promotions with pagination, search and filter support."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Get search and filter parameters
    search_term = request.args.get('search', '').strip()
    discount_type = request.args.get('discount_type')  # 'percentage', 'fixed', or None for all
    status = request.args.get('status')  # 'active', 'inactive', 'current', 'upcoming', 'expired', or None for all

    # Validate pagination parameters
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 10

    # Calculate offset
    offset = (page - 1) * per_page

    db = Database(DB_PATH)

    # Build the query with filters
    where_clauses = []
    params = []

    if search_term:
        where_clauses.append("(name LIKE ? OR description LIKE ?)")
        search_pattern = f"%{search_term}%"
        params.extend([search_pattern, search_pattern])

    if discount_type:
        where_clauses.append("discount_type = ?")
        params.append(discount_type)

    current_date = datetime.now().strftime('%Y-%m-%d')

    if status == 'active':
        where_clauses.append("is_active = 1")
    elif status == 'inactive':
        where_clauses.append("is_active = 0")
    elif status == 'current':
        where_clauses.append("start_date <= ? AND end_date >= ? AND is_active = 1")
        params.extend([current_date, current_date])
    elif status == 'upcoming':
        where_clauses.append("start_date > ? AND is_active = 1")
        params.append(current_date)
    elif status == 'expired':
        where_clauses.append("end_date < ? OR is_active = 0")
        params.append(current_date)

    # Construct the WHERE clause
    where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Get total count with filters
    count_query = f"""
        SELECT COUNT(*) as total
        FROM promotions
        {where_clause}
    """
    count_result = db.execute_query(count_query, tuple(params))
    total_promotions = count_result[0]['total'] if count_result else 0

    # Calculate total pages
    total_pages = (total_promotions + per_page - 1) // per_page

    # Get promotions for current page with filters
    query = f"""
        SELECT promotion_id, name, description, discount_type, discount_value,
               start_date, end_date, is_active
        FROM promotions
        {where_clause}
        ORDER BY start_date DESC
        LIMIT ? OFFSET ?
    """

    # Add pagination parameters
    query_params = params + [per_page, offset]
    promotions = db.execute_query(query, tuple(query_params))

    # Convert datetime objects to strings for JSON serialization
    for promotion in promotions:
        if 'start_date' in promotion and promotion['start_date']:
            promotion['start_date'] = str(promotion['start_date'])
        if 'end_date' in promotion and promotion['end_date']:
            promotion['end_date'] = str(promotion['end_date'])

    return jsonify({
        'success': True,
        'promotions': promotions,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_items': total_promotions,
            'total_pages': total_pages
        }
    })

@app.route('/api/admin/promotion_details', methods=['GET'])
def promotion_details():
    """Get details for a specific promotion."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    promotion_id = request.args.get('promotion_id', type=int)
    if not promotion_id:
        return jsonify({'success': False, 'message': 'Missing promotion ID'})

    db = Database(DB_PATH)

    query = """
        SELECT promotion_id, name, description, discount_type, discount_value,
               start_date, end_date, is_active
        FROM promotions
        WHERE promotion_id = ?
    """

    promotion = db.execute_query(query, (promotion_id,))

    if not promotion:
        return jsonify({'success': False, 'message': 'Promotion not found'})

    # Convert datetime objects to strings for JSON serialization
    if 'start_date' in promotion[0] and promotion[0]['start_date']:
        promotion[0]['start_date'] = str(promotion[0]['start_date'])
    if 'end_date' in promotion[0] and promotion[0]['end_date']:
        promotion[0]['end_date'] = str(promotion[0]['end_date'])

    return jsonify({
        'success': True,
        'promotion': promotion[0]
    })

@app.route('/api/admin/create_promotion', methods=['POST'])
def create_promotion():
    """Add a new promotion."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'manager':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json

    # Validate required fields
    required_fields = ['name', 'discount_type', 'discount_value', 'start_date', 'end_date']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'message': f'Missing required field: {field}'})

    db = Database(DB_PATH)

    query = """
        INSERT INTO promotions (name, description, discount_type, discount_value, start_date, end_date, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """

    try:
        db.execute_update(
            query,
            (
                data['name'],
                data.get('description', ''),
                data['discount_type'],
                data['discount_value'],
                data['start_date'],
                data['end_date'],
                data.get('is_active', True)
            )
        )

        return jsonify({'success': True, 'message': 'Promotion added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/admin/edit_promotion', methods=['POST'])
def edit_promotion():
    """Update an existing promotion."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'manager':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json

    # Validate required fields
    required_fields = ['promotion_id', 'name', 'discount_type', 'discount_value', 'start_date', 'end_date']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'message': f'Missing required field: {field}'})

    db = Database(DB_PATH)

    query = """
        UPDATE promotions
        SET name = ?, description = ?, discount_type = ?, discount_value = ?,
            start_date = ?, end_date = ?, is_active = ?
        WHERE promotion_id = ?
    """

    try:
        db.execute_update(
            query,
            (
                data['name'],
                data.get('description', ''),
                data['discount_type'],
                data['discount_value'],
                data['start_date'],
                data['end_date'],
                data.get('is_active', True),
                data['promotion_id']
            )
        )

        return jsonify({'success': True, 'message': 'Promotion updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/admin/delete_promotion', methods=['POST'])
def delete_promotion():
    """Delete a promotion."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'manager':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json

    if 'promotion_id' not in data:
        return jsonify({'success': False, 'message': 'Missing promotion ID'})

    db = Database(DB_PATH)

    query = """
        DELETE FROM promotions
        WHERE promotion_id = ?
    """

    try:
        db.execute_update(query, (data['promotion_id'],))
        return jsonify({'success': True, 'message': 'Promotion deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/admin/add_product', methods=['POST'])
def add_product():
    """Add a new product."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    name = data.get('name')
    description = data.get('description', '')
    category_id = data.get('category_id')
    price = data.get('price')
    stock_quantity = data.get('stock_quantity')
    image_url = data.get('image_url', '')
    brand = data.get('brand', '')
    ingredients = data.get('ingredients', '')
    usage_instructions = data.get('usage_instructions', '')
    is_active = data.get('is_active', 1)
    benefits = data.get('benefits', [])

    # Validate required fields
    if not all([name, category_id, price, stock_quantity]):
        return jsonify({'success': False, 'message': 'Missing required fields'})

    try:
        # Convert types
        category_id = int(category_id)
        price = float(price)
        stock_quantity = int(stock_quantity)
        is_active = int(is_active)

        # Create a database connection
        db = Database(DB_PATH)

        # First, create the product (health_benefits will be updated later)
        product_id = manager.create_product(
            name, description, category_id, price, stock_quantity,
            image_url, brand, '', ingredients, usage_instructions, bool(is_active)
        )

        if not product_id:
            return jsonify({'success': False, 'message': 'Failed to add product'})

        # Handle health benefits if provided
        if benefits:
            print(f"Adding {len(benefits)} health benefits to product {product_id}")

            # First, get the health benefit names and categories for these IDs
            benefit_names = []
            benefit_details = []
            for benefit_id in benefits:
                query = "SELECT name, category FROM health_benefits WHERE benefit_id = ?"
                result = db.execute_query(query, (benefit_id,))
                if result:
                    benefit_names.append(result[0]['name'])
                    benefit_details.append(result[0])

            # Join the benefit names into a comma-separated string
            health_benefits_str = ', '.join(benefit_names)
            print(f"Health benefits string: '{health_benefits_str}'")

            # Update the product with the health benefits string
            update_query = """
                UPDATE products
                SET health_benefits = ?
                WHERE product_id = ?
            """
            db.execute_update(update_query, (health_benefits_str, product_id))

            # Also add entries to the product_benefits junction table
            for benefit_id in benefits:
                db.execute_update(
                    "INSERT INTO product_benefits (product_id, benefit_id) VALUES (?, ?)",
                    (product_id, benefit_id)
                )

            # Log the benefit details for debugging
            print(f"Benefit details for product {product_id}:")
            for benefit in benefit_details:
                print(f"  - Name: '{benefit['name']}', Category: '{benefit['category']}'")

            # Check which goals this product matches
            from rock.health_goals import match_health_benefits_to_standard_goals

            # Create a dictionary mapping benefit names to their categories
            benefit_categories = {}
            for benefit in benefit_details:
                benefit_categories[benefit['name'].lower()] = benefit['category']

            matching_goals = match_health_benefits_to_standard_goals(health_benefits_str, benefit_categories)
            print(f"Product {product_id} matches goals: {matching_goals}")

        return jsonify({
            'success': True,
            'message': 'Product added successfully',
            'product_id': product_id
        })
    except Exception as e:
        print(f"Error adding product: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/delete_product', methods=['POST'])
def delete_product():
    """Delete a product."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    product_id = data.get('product_id')
    auto_delete_category = data.get('auto_delete_category', True)  # Default to True

    # Validate required fields
    if not product_id:
        return jsonify({'success': False, 'message': 'Missing product ID'})

    try:
        # Convert types
        product_id = int(product_id)

        # Get the product's category before deleting
        db = Database(DB_PATH)
        query = "SELECT category_id FROM products WHERE product_id = ?"
        product_info = db.execute_query(query, (product_id,))

        if not product_info:
            return jsonify({'success': False, 'message': 'Product not found'})

        category_id = product_info[0]['category_id']

        # Delete product
        success = manager.delete_product(product_id)

        if success:
            # Check if the category is now empty and delete it if requested
            if auto_delete_category and category_id:
                # Check if there are any other products in this category
                check_query = """
                    SELECT COUNT(*) as count
                    FROM products
                    WHERE category_id = ?
                """
                result = db.execute_query(check_query, (category_id,))

                if result and result[0]['count'] == 0:
                    # Check if this is a parent category with child categories
                    child_check_query = """
                        SELECT COUNT(*) as count
                        FROM categories
                        WHERE parent_category_id = ?
                    """
                    child_result = db.execute_query(child_check_query, (category_id,))

                    # Only delete if it's not a parent category
                    if child_result and child_result[0]['count'] == 0:
                        # Get category name for the message
                        name_query = "SELECT name FROM categories WHERE category_id = ?"
                        name_result = db.execute_query(name_query, (category_id,))
                        category_name = name_result[0]['name'] if name_result else "Unknown"

                        # Delete the empty category
                        delete_query = "DELETE FROM categories WHERE category_id = ?"
                        db.execute_update(delete_query, (category_id,))

                        return jsonify({
                            'success': True,
                            'message': f'Product deleted successfully. Empty category "{category_name}" was also removed.'
                        })

            return jsonify({'success': True, 'message': 'Product deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to delete product'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/update_faq', methods=['POST'])
def update_faq():
    """Update a FAQ."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    faq_id = data.get('faq_id')
    question = data.get('question')
    answer = data.get('answer')
    category = data.get('category', 'General')
    language = data.get('language', 'en')
    is_active = data.get('is_active', 1)

    # Validate required fields
    if not all([faq_id, question, answer]):
        return jsonify({'success': False, 'message': 'Missing required fields'})

    try:
        # Convert types
        faq_id = int(faq_id)
        is_active = bool(int(is_active))

        # Update FAQ
        success = manager.update_faq(faq_id, question, answer, category, language, is_active)

        if success:
            return jsonify({'success': True, 'message': 'FAQ updated successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to update FAQ'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/add_faq', methods=['POST'])
def add_faq():
    """Add a new FAQ."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    question = data.get('question')
    answer = data.get('answer')
    category = data.get('category', 'General')
    language = data.get('language', 'en')
    notes = data.get('notes', '')
    is_active = data.get('is_active', 1)

    # Validate required fields
    if not all([question, answer]):
        return jsonify({'success': False, 'message': 'Missing required fields'})

    try:
        # If user is a manager, add directly to FAQs
        if session.get('role') == 'manager':
            # Convert types
            is_active = bool(int(is_active))

            # Add FAQ
            faq_id = manager.create_faq(question, answer, category, language, is_active)

            if faq_id:
                return jsonify({'success': True, 'message': 'FAQ added successfully', 'faq_id': faq_id})
            else:
                return jsonify({'success': False, 'message': 'Failed to add FAQ'})
        # If user is an agent, submit for approval
        else:
            # Initialize agent interface
            agent_interface = AgentInterface(DB_PATH)

            # Login the agent
            user_id = session.get('user_id')
            db = Database(DB_PATH)
            user = db.get_staff_by_id(user_id)
            if user:
                agent_interface.current_user = user

                # Submit FAQ for approval
                pending_faq_id = agent_interface.submit_faq_for_approval(
                    question, answer, category, language, notes
                )

                if pending_faq_id:
                    return jsonify({
                        'success': True,
                        'message': 'FAQ submitted for manager approval',
                        'pending_faq_id': pending_faq_id
                    })
                else:
                    return jsonify({'success': False, 'message': 'Failed to submit FAQ for approval'})
            else:
                return jsonify({'success': False, 'message': 'User not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/pending_faqs', methods=['GET'])
def get_pending_faqs():
    """Get pending FAQs for manager approval."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id'):
        return jsonify({'success': False, 'message': 'Unauthorized'})

    # Get status filter
    status = request.args.get('status', 'pending')

    try:
        if session.get('role') == 'manager':
            # Get the current user
            user_id = session.get('user_id')
            db = Database(DB_PATH)
            user = db.get_staff_by_id(user_id)

            if not user:
                return jsonify({'success': False, 'message': 'User not found'})

            # Set the current user for the manager
            manager.current_user = user

            # Managers can see all pending FAQs
            pending_faqs = manager.list_pending_faqs(status)
            return jsonify({'success': True, 'pending_faqs': pending_faqs})
        elif session.get('role') == 'agent':
            # Agents can only see their own pending FAQs
            agent_interface = AgentInterface(DB_PATH)

            # Login the agent
            user_id = session.get('user_id')
            db = Database(DB_PATH)
            user = db.get_staff_by_id(user_id)

            if user:
                agent_interface.current_user = user
                pending_faqs = agent_interface.list_my_pending_faqs()
                return jsonify({'success': True, 'pending_faqs': pending_faqs})
            else:
                return jsonify({'success': False, 'message': 'User not found'})
        else:
            return jsonify({'success': False, 'message': 'Unauthorized'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/approve_pending_faq/<int:pending_faq_id>', methods=['POST'])
def approve_pending_faq(pending_faq_id):
    """Approve a pending FAQ."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'manager':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json or {}
    notes = data.get('notes', '')

    try:
        # Get the current user
        user_id = session.get('user_id')
        db = Database(DB_PATH)
        user = db.get_staff_by_id(user_id)

        if not user:
            return jsonify({'success': False, 'message': 'User not found'})

        # Set the current user for the manager
        manager.current_user = user

        # Log for debugging
        print(f"Manager approving FAQ: user_id={user_id}, role={user.get('role')}, pending_faq_id={pending_faq_id}")

        # Approve the pending FAQ
        faq_id = manager.approve_pending_faq(pending_faq_id, notes)

        if faq_id:
            return jsonify({
                'success': True,
                'message': 'FAQ approved and added to database',
                'faq_id': faq_id
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to approve FAQ'})
    except Exception as e:
        print(f"Error approving FAQ: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/reject_pending_faq/<int:pending_faq_id>', methods=['POST'])
def reject_pending_faq(pending_faq_id):
    """Reject a pending FAQ."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'manager':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json or {}
    notes = data.get('notes', '')

    try:
        # Get the current user
        user_id = session.get('user_id')
        db = Database(DB_PATH)
        user = db.get_staff_by_id(user_id)

        if not user:
            return jsonify({'success': False, 'message': 'User not found'})

        # Set the current user for the manager
        manager.current_user = user

        # Log for debugging
        print(f"Manager rejecting FAQ: user_id={user_id}, role={user.get('role')}, pending_faq_id={pending_faq_id}")

        # Reject the pending FAQ
        success = manager.reject_pending_faq(pending_faq_id, notes)

        if success:
            return jsonify({
                'success': True,
                'message': 'FAQ rejected'
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to reject FAQ'})
    except Exception as e:
        print(f"Error rejecting FAQ: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/response_templates', methods=['GET'])
def get_response_templates():
    """Get response templates for agent panel."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    db = Database(DB_PATH)

    try:
        # Check if response_templates table exists
        query = """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='response_templates'
        """
        table_exists = len(db.execute_query(query)) > 0

        if not table_exists:
            # Create the table if it doesn't exist
            create_table_query = """
                CREATE TABLE response_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            db.execute_query(create_table_query)

            # Insert default templates
            default_templates = [
                ('Greetings', 'Hello! Thank you for contacting Rock Supplements. How can I assist you today?'),
                ('Greetings', 'Hi there! My name is [Agent Name] and I\'ll be helping you today. What can I do for you?'),
                ('Product Information', 'This product is one of our bestsellers. It\'s known for its high quality and effectiveness.'),
                ('Product Information', 'Based on your goals, I would recommend this product because it contains ingredients that support [benefit].'),
                ('Product Information', 'This product is suitable for [specific goal/need]. Many of our customers have reported positive results.'),
                ('Order Status', 'Your order #[Order ID] is currently [status]. The estimated delivery date is [date].'),
                ('Order Status', 'I can see that your order has been shipped on [date] via [courier]. The tracking number is [tracking number].'),
                ('Order Status', 'Your order is being processed and should be shipped within the next 24-48 hours.'),
                ('Troubleshooting', 'I understand you\'re experiencing an issue with your order. Let me help resolve this for you.'),
                ('Troubleshooting', 'I apologize for the inconvenience. Let me look into this issue and find a solution for you.'),
                ('Troubleshooting', 'Thank you for bringing this to our attention. We\'ll make sure to address this issue promptly.'),
                ('Closing', 'Thank you for chatting with Rock Supplements today. Is there anything else I can help you with?'),
                ('Closing', 'I\'m glad I could assist you today. If you have any other questions, feel free to ask!')
            ]

            insert_query = """
                INSERT INTO response_templates (category, text)
                VALUES (?, ?)
            """
            for template in default_templates:
                db.execute_query(insert_query, template)

        # Get all templates
        templates_query = """
            SELECT template_id, category, text
            FROM response_templates
            ORDER BY category, template_id
        """
        templates = db.execute_query(templates_query)

        return jsonify({
            'success': True,
            'templates': templates
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/api/admin/delete_faq', methods=['POST'])
def delete_faq():
    """Delete a FAQ."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    faq_id = data.get('faq_id')

    # Validate required fields
    if not faq_id:
        return jsonify({'success': False, 'message': 'Missing FAQ ID'})

    try:
        # Convert types
        faq_id = int(faq_id)

        # Get the category of the FAQ before deleting it
        db = Database(DB_PATH)
        query = "SELECT category FROM faqs WHERE faq_id = ?"
        result = db.execute_query(query, (faq_id,))

        category = None
        if result and len(result) > 0:
            category = result[0]['category']

        # Delete FAQ
        success = manager.delete_faq(faq_id)

        if success:
            # Check if the category is now empty
            is_empty = False
            if category:
                is_empty = check_empty_category(category)

            if is_empty:
                return jsonify({
                    'success': True,
                    'message': 'FAQ deleted successfully',
                    'empty_category': category,
                    'category_removed': True
                })
            else:
                return jsonify({'success': True, 'message': 'FAQ deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to delete FAQ'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/get_promotions', methods=['GET'])
def get_promotions():
    """Get all promotions with pagination support."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Validate pagination parameters
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 10

    try:
        # Get all promotions first
        all_promotions = manager.list_promotions(active_only=False)

        # Calculate pagination
        total_promotions = len(all_promotions)
        total_pages = (total_promotions + per_page - 1) // per_page

        # Apply pagination manually
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_promotions = all_promotions[start_idx:end_idx] if start_idx < total_promotions else []

        return jsonify({
            'success': True,
            'promotions': paginated_promotions,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_promotions,
                'total_pages': total_pages
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/new_promotion', methods=['POST'])
def new_promotion():
    """Add a new promotion."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    name = data.get('name')
    description = data.get('description', '')
    discount_type = data.get('discount_type', 'percentage')
    discount_value = data.get('discount')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    coupon_code = data.get('code')
    minimum_order_amount = data.get('minimum_order_amount', 0)
    applicable_products = data.get('applicable_products', '')
    applicable_categories = data.get('applicable_categories', '')
    is_active = data.get('is_active', 1)

    # Validate required fields
    if not all([name, discount_value, start_date, end_date, coupon_code]):
        return jsonify({'success': False, 'message': 'Missing required fields'})

    try:
        # Convert types
        discount_value = float(discount_value)
        minimum_order_amount = float(minimum_order_amount)
        is_active = bool(int(is_active))

        # Add promotion
        promotion_id = manager.create_promotion(
            name, description, discount_type, discount_value,
            start_date, end_date, coupon_code, minimum_order_amount,
            applicable_products, applicable_categories, is_active
        )

        if promotion_id:
            return jsonify({'success': True, 'message': 'Promotion added successfully', 'promotion_id': promotion_id})
        else:
            return jsonify({'success': False, 'message': 'Failed to add promotion'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/modify_promotion', methods=['POST'])
def modify_promotion():
    """Update a promotion."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    promotion_id = data.get('promotion_id')
    name = data.get('name')
    description = data.get('description', '')
    discount_type = data.get('discount_type', 'percentage')
    discount_value = data.get('discount')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    coupon_code = data.get('code')
    minimum_order_amount = data.get('minimum_order_amount', 0)
    applicable_products = data.get('applicable_products', '')
    applicable_categories = data.get('applicable_categories', '')
    is_active = data.get('is_active', 1)

    # Validate required fields
    if not all([promotion_id, name, discount_value, start_date, end_date, coupon_code]):
        return jsonify({'success': False, 'message': 'Missing required fields'})

    try:
        # Convert types
        promotion_id = int(promotion_id)
        discount_value = float(discount_value)
        minimum_order_amount = float(minimum_order_amount)
        is_active = bool(int(is_active))

        # Update promotion
        success = manager.update_promotion(
            promotion_id, name, description, discount_type, discount_value,
            start_date, end_date, coupon_code, minimum_order_amount,
            applicable_products, applicable_categories, is_active
        )

        if success:
            return jsonify({'success': True, 'message': 'Promotion updated successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to update promotion'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/remove_promotion', methods=['POST'])
def remove_promotion():
    """Delete a promotion."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    data = request.json
    promotion_id = data.get('promotion_id')

    # Validate required fields
    if not promotion_id:
        return jsonify({'success': False, 'message': 'Missing promotion ID'})

    try:
        # Convert types
        promotion_id = int(promotion_id)

        # Delete promotion
        success = manager.delete_promotion(promotion_id)

        if success:
            return jsonify({'success': True, 'message': 'Promotion deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to delete promotion'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})



@app.route('/api/admin/cleanup_categories', methods=['POST'])
def cleanup_categories():
    """Delete all empty categories that have no products."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'manager':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        # Initialize the scheduled tasks
        tasks = ScheduledTasks(DB_PATH)

        # Get protected categories from request or use defaults
        data = request.json or {}
        protected_ids = data.get('protected_categories', [1, 2, 3, 4])  # Default to main parent categories

        # Delete empty categories
        deleted_count = tasks.delete_empty_categories(exclude_ids=protected_ids)

        return jsonify({
            'success': True,
            'message': f'Successfully deleted {deleted_count} empty categories',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/admin/cleanup_sessions', methods=['POST'])
def cleanup_sessions():
    """Cleanup inactive sessions."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'manager':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        # Initialize the scheduled tasks
        tasks = ScheduledTasks(DB_PATH)

        # Cleanup inactive sessions
        ended_count = tasks.cleanup_inactive_sessions()

        return jsonify({
            'success': True,
            'message': f'Successfully ended {ended_count} inactive sessions',
            'ended_count': ended_count
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/agent/faqs', methods=['GET'])
def agent_faqs():
    """Get FAQs for agent panel."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'agent':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        # Get the current user
        user_id = session.get('user_id')
        db = Database(DB_PATH)
        user = db.get_staff_by_id(user_id)

        if not user:
            return jsonify({'success': False, 'message': 'User not found'})

        # Get all FAQs
        faqs = db.get_faqs()
        return jsonify({'success': True, 'faqs': faqs})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/agent/faq_categories', methods=['GET'])
def agent_faq_categories():
    """Get all FAQ categories for agent panel."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'agent':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        # Get the current user
        user_id = session.get('user_id')
        db = Database(DB_PATH)
        user = db.get_staff_by_id(user_id)

        if not user:
            return jsonify({'success': False, 'message': 'User not found'})

        # Get all FAQs
        faqs = db.get_faqs()

        # Extract unique categories
        categories = set()
        for faq in faqs:
            if faq.get('category'):
                categories.add(faq.get('category'))

        # Convert to sorted list
        categories_list = sorted(list(categories))

        return jsonify({'success': True, 'categories': categories_list})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/agent/pending_faqs', methods=['GET'])
def agent_pending_faqs():
    """Get pending FAQs submitted by the current agent."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'agent':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        # Get the current user
        user_id = session.get('user_id')
        db = Database(DB_PATH)

        # Get pending FAQs submitted by this agent
        query = '''
            SELECT p.pending_faq_id, p.question, p.answer, p.category, p.language,
                   p.submitted_by, p.submitted_at, p.status, p.reviewed_by, p.reviewed_at,
                   p.notes, p.agent_notes,
                   s1.username as submitted_by_username, s2.username as reviewed_by_username
            FROM pending_faqs p
            LEFT JOIN staff s1 ON p.submitted_by = s1.staff_id
            LEFT JOIN staff s2 ON p.reviewed_by = s2.staff_id
            WHERE p.submitted_by = ?
            ORDER BY p.submitted_at DESC
        '''

        pending_faqs = db.execute_query(query, (user_id,))

        # Convert datetime objects to strings for JSON serialization
        for faq in pending_faqs:
            if 'submitted_at' in faq and faq['submitted_at']:
                faq['submitted_at'] = str(faq['submitted_at'])
            if 'reviewed_at' in faq and faq['reviewed_at']:
                faq['reviewed_at'] = str(faq['reviewed_at'])

        return jsonify({'success': True, 'pending_faqs': pending_faqs})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/agent/products', methods=['GET'])
def agent_products():
    """Get products for agent panel."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'agent':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        # Get the current user
        user_id = session.get('user_id')
        db = Database(DB_PATH)
        user = db.get_staff_by_id(user_id)

        if not user:
            return jsonify({'success': False, 'message': 'User not found'})

        # Get all products with complete information for agents
        query = """
            SELECT p.product_id, p.name, p.description, p.category_id, p.price,
                   p.stock_quantity, p.image_url, p.brand, p.health_benefits,
                   p.ingredients, p.usage_instructions, p.is_active,
                   c.name as category
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.category_id
            WHERE p.is_active = 1
            ORDER BY p.name
        """
        products = db.execute_query(query)

        return jsonify({'success': True, 'products': products})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/agent/bestselling_products', methods=['GET'])
def agent_bestselling_products():
    """Get bestselling products based on purchase history for agent panel."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'agent':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        # Get the current user
        user_id = session.get('user_id')
        db = Database(DB_PATH)
        user = db.get_staff_by_id(user_id)

        if not user:
            return jsonify({'success': False, 'message': 'User not found'})

        # Get bestselling products based on actual order data
        products = db.get_bestselling_products(limit=10)

        return jsonify({'success': True, 'products': products})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/agent/chat_history', methods=['GET'])
def get_agent_chat_history():
    """Get chat history for the current agent"""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') not in ['manager', 'agent']:
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        agent_id = session.get('user_id')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        search = request.args.get('search', '').strip()

        # Calculate offset
        offset = (page - 1) * per_page

        db = Database(DB_PATH)

        # Base query for agent's chat sessions with feedback data
        base_query = '''
            SELECT cs.session_id, cs.session_start, cs.session_end, cs.customer_id,
                   c.username as customer_name, c.email as customer_email,
                   COUNT(cm.message_id) as message_count,
                   MAX(cm.timestamp) as last_message_time,
                   cf.rating as feedback_rating,
                   cf.feedback_text as feedback_comment
            FROM chat_sessions cs
            LEFT JOIN customers c ON cs.customer_id = c.customer_id
            LEFT JOIN chat_messages cm ON cs.session_id = cm.session_id
            LEFT JOIN chat_feedback cf ON cs.session_id = cf.session_id
            WHERE cs.agent_id = ?
        '''

        # Add search filter if provided
        search_params = [agent_id]
        if search:
            base_query += ' AND (c.username LIKE ? OR c.email LIKE ? OR cs.session_id LIKE ?)'
            search_term = f'%{search}%'
            search_params.extend([search_term, search_term, search_term])

        # Complete query with grouping and ordering
        query = base_query + '''
            GROUP BY cs.session_id, cs.session_start, cs.session_end, cs.customer_id,
                     c.username, c.email, cf.rating, cf.feedback_text
            ORDER BY cs.session_start DESC
            LIMIT ? OFFSET ?
        '''

        search_params.extend([per_page, offset])

        # Get chat sessions
        sessions = db.execute_query(query, search_params)

        # Get total count for pagination
        count_query = '''
            SELECT COUNT(DISTINCT cs.session_id) as total
            FROM chat_sessions cs
            LEFT JOIN customers c ON cs.customer_id = c.customer_id
            LEFT JOIN chat_feedback cf ON cs.session_id = cf.session_id
            WHERE cs.agent_id = ?
        '''

        count_params = [agent_id]
        if search:
            count_query += ' AND (c.username LIKE ? OR c.email LIKE ? OR cs.session_id LIKE ?)'
            count_params.extend([search_term, search_term, search_term])

        total_result = db.execute_query(count_query, count_params)
        total_sessions = total_result[0]['total'] if total_result else 0

        # Calculate pagination info
        total_pages = (total_sessions + per_page - 1) // per_page

        # Convert datetime objects to strings for JSON serialization
        for session_data in sessions:
            if 'session_start' in session_data and session_data['session_start']:
                session_data['session_start'] = str(session_data['session_start'])
            if 'session_end' in session_data and session_data['session_end']:
                session_data['session_end'] = str(session_data['session_end'])
            if 'last_message_time' in session_data and session_data['last_message_time']:
                session_data['last_message_time'] = str(session_data['last_message_time'])

        return jsonify({
            'success': True,
            'sessions': sessions,
            'pagination': {
                'current_page': page,
                'per_page': per_page,
                'total_sessions': total_sessions,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        })

    except Exception as e:
        print(f"Error getting agent chat history: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to load chat history'
        }), 500

@app.route('/api/agent/promotions', methods=['GET'])
def agent_promotions():
    """Get promotions for agent panel."""
    # Check if user is logged in and has appropriate role
    if not session.get('user_id') or session.get('role') != 'agent':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        # Get the current user
        user_id = session.get('user_id')
        db = Database(DB_PATH)
        user = db.get_staff_by_id(user_id)

        if not user:
            return jsonify({'success': False, 'message': 'User not found'})

        # Get all active promotions
        query = """
            SELECT promotion_id, name, description, discount_type, discount_value,
                   code, start_date, end_date, is_active
            FROM promotions
            WHERE is_active = 1
            ORDER BY start_date DESC
        """
        promotions = db.execute_query(query)

        # Convert datetime objects to strings for JSON serialization
        for promotion in promotions:
            if 'start_date' in promotion and promotion['start_date']:
                promotion['start_date'] = str(promotion['start_date'])
            if 'end_date' in promotion and promotion['end_date']:
                promotion['end_date'] = str(promotion['end_date'])

        return jsonify({'success': True, 'promotions': promotions})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})



# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")

@socketio.on('join_session')
def handle_join_session(data):
    """Join a chat session room"""
    session_id = data.get('session_id')
    user_type = data.get('user_type', 'customer')  # 'customer' or 'agent'

    if session_id:
        room = f"session_{session_id}"
        join_room(room)
        print(f"{user_type} joined session {session_id}")
        emit('joined_session', {'session_id': session_id, 'user_type': user_type})

@socketio.on('join_agent_room')
def handle_join_agent_room(data):
    """Join an agent-specific room for notifications"""
    agent_id = data.get('agent_id')

    if agent_id:
        room = f"agent_{agent_id}"
        join_room(room)
        print(f"Agent {agent_id} joined their notification room")
        emit('joined_agent_room', {'agent_id': agent_id})

@socketio.on('leave_session')
def handle_leave_session(data):
    """Leave a chat session room"""
    session_id = data.get('session_id')
    user_type = data.get('user_type', 'customer')

    if session_id:
        room = f"session_{session_id}"
        leave_room(room)
        print(f"{user_type} left session {session_id}")

@socketio.on('send_message')
def handle_send_message(data):
    """Handle real-time message sending"""
    session_id = data.get('session_id')
    message = data.get('message')
    sender_type = data.get('sender_type', 'customer')
    sender_name = data.get('sender_name', '')

    if session_id and message:
        # Store message in database
        timestamp = datetime.now()
        timestamp_iso = timestamp.isoformat()

        try:
            # For WebSocket messages, we'll store sender_id as None for now
            # and rely on sender_name in the broadcast for display purposes
            # This maintains compatibility with the existing database schema
            sender_id = None

            # Store the message using the correct database schema
            # Use the datetime object for database storage (SQLite will handle it properly)
            message_query = """
                INSERT INTO chat_messages (session_id, sender_type, sender_id, message_text, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """
            db_instance = Database(DB_PATH)
            # Use execute_update for INSERT statements, not execute_query
            db_instance.execute_update(message_query, (session_id, sender_type, sender_id, message, timestamp.strftime('%Y-%m-%d %H:%M:%S')))

            # Broadcast message to all users in the session room
            room = f"session_{session_id}"
            socketio.emit('new_message', {
                'session_id': session_id,
                'sender_type': sender_type,
                'sender_name': sender_name,
                'message_text': message,
                'timestamp': timestamp_iso
            }, room=room)

            print(f"Message sent in session {session_id}: {sender_type} - {message[:50]}...")

        except Exception as e:
            print(f"Error storing/broadcasting message: {e}")
            emit('message_error', {'error': 'Failed to send message'})

@socketio.on('agent_takeover')
def handle_agent_takeover(data):
    """Handle agent taking over a chat"""
    session_id = data.get('session_id')
    agent_name = data.get('agent_name', '')

    if session_id:
        room = f"session_{session_id}"
        socketio.emit('agent_joined', {
            'session_id': session_id,
            'agent_name': agent_name,
            'message': f"Agent {agent_name} has joined the conversation."
        }, room=room)

        # Also emit a specific event to ensure the new agent loads complete chat history
        socketio.emit('load_complete_history', {
            'session_id': session_id
        }, room=room)

@socketio.on('agent_end_chat')
def handle_agent_end_chat(data):
    """Handle agent ending a chat"""
    session_id = data.get('session_id')
    agent_name = data.get('agent_name', '')

    if session_id:
        room = f"session_{session_id}"
        socketio.emit('agent_left', {
            'session_id': session_id,
            'agent_name': agent_name,
            'message': f"Agent {agent_name} has ended the conversation."
        }, room=room)

@socketio.on('customer_ended_chat')
def handle_customer_ended_chat(data):
    """Handle customer ending a chat by clicking main menu"""
    session_id = data.get('session_id')
    message = data.get('message', 'Customer ended the chat.')

    if session_id:
        room = f"session_{session_id}"
        # Notify agents that the customer ended the chat
        socketio.emit('customer_left', {
            'session_id': session_id,
            'message': message
        }, room=room)

if __name__ == '__main__':
    # Check if the database exists
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Please initialize the database first.")
        sys.exit(1)

    socketio.run(app, debug=True, host='127.0.0.1', port=5000)

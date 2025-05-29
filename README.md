# Rock Supplements Chatbot

A rule-based multilingual chatbot for supplements e-commerce in Malaysia with real-time WebSocket communication, agent interface, and comprehensive admin dashboard.

## Features

- **Rule-Based Logic**: Uses conditional statements and pattern matching to identify user intents and generate appropriate responses
- **Multilingual Support**: Supports English, Bahasa Melayu, Chinese, and Tamil with automatic translation
- **Personalized Recommendations**: Provides product recommendations based on customer profiles, purchase history, and health goals
- **FAQ Automation**: Automatically answers frequently asked questions with agent-modifiable responses
- **Real-time Communication**: WebSocket-based real-time messaging between customers and agents
- **Agent Interface**: Comprehensive agent dashboard for managing multiple customer chats simultaneously
- **Manager Dashboard**: Full CRUD interface for products, FAQs, promotions, users, and analytics
- **Health Goals Integration**: Product recommendations based on specific health and wellness goals
- **Order Status Tracking**: Real-time order and delivery status checking
- **Guest User Support**: Allows guest users to chat and request agent assistance without registration

## Project Structure

```
chatbot4/
├── app.py                     # Main Flask application with WebSocket support
├── requirements.txt           # Python dependencies
├── data/                      # Database directory
│   └── rock_chatbot.db        # SQLite database
├── rock/                      # Main package
│   ├── __init__.py            # Package initialization
│   ├── chatbot.py             # Core chatbot engine
│   ├── database.py            # Database interaction layer
│   ├── auth.py                # Authentication and role management
│   ├── manager.py             # Manager interface and CRUD operations
│   ├── agent_interface.py     # Agent interface functionality
│   ├── health_goals.py        # Health goals and product matching
│   ├── translation.py         # Translation service
│   ├── feedback.py            # Feedback collection system
│   └── scheduled_tasks.py     # Background maintenance tasks
├── config/                    # Configuration files
│   └── role_config.py         # Role-based access configuration
├── static/                    # Static web assets
│   ├── css/                   # Stylesheets
│   ├── js/                    # JavaScript files
│   └── images/                # Images and icons
├── templates/                 # HTML templates
├── logs/                      # Application logs
└── README.md                  # This file
```

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/rock-chatbot.git
   cd chatbot4
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Run the Complete Application

To start the Rock chatbot web application with all features:

```bash
python app.py
```

The application will be available at `http://localhost:5000` with:
- **Customer Interface**: Main chatbot interface for customers and guests
- **Agent Interface**: Real-time chat management for customer service agents
- **Manager Dashboard**: Administrative interface for managing all chatbot data

### Default Access

- **Customers**: Can register and use the chatbot, or use as guest
- **Agents**: Use email with domain `@agent.rock.com` or `@support.rock.com`
- **Managers**: Use email with domain `@manager.rock.com`

## Manager Interface

The manager dashboard provides comprehensive control over:

1. **Dashboard Analytics**: Real-time statistics and performance metrics
2. **User Management**: View and manage customers, agents, and staff
3. **Product Management**: Full CRUD operations for products, categories, and health benefits
4. **FAQ Management**: Create, update, and approve FAQ entries with category organization
5. **Promotion Management**: Create and manage promotional campaigns and discounts
6. **Session Monitoring**: View all chat sessions and customer interactions
7. **Health Goals**: Manage health goals and product benefit mappings

## Agent Interface

The agent interface enables customer service representatives to:

1. **Real-time Chat Management**: Handle multiple customer conversations simultaneously
2. **Customer Information**: Access customer profiles and order history
3. **Product Knowledge Base**: Search and reference product information
4. **FAQ Management**: Add new FAQs and modify quick responses
5. **Session Transfer**: Take over conversations from the chatbot
6. **Online Status**: Manage availability and online presence

## Customer Interface

The customer chatbot interface allows users to:

1. **Product Discovery**: Browse products by category and health goals
2. **Personalized Recommendations**: Get product suggestions based on health objectives
3. **Order Tracking**: Check order status and delivery information
4. **FAQ Support**: Get instant answers to common questions
5. **Agent Assistance**: Request human agent support for complex queries
6. **Guest Access**: Use the chatbot without registration requirement
7. **Multilingual Support**: Communicate in English, Bahasa Melayu, Chinese, or Tamil

## Database Schema

The database includes comprehensive tables for:

- **User Management**: Customers, staff, roles, and authentication
- **Product Catalog**: Products, categories, health benefits, and goals
- **Order Management**: Orders, order items, and delivery tracking
- **Chat System**: Sessions, messages, agent assignments, and real-time status
- **Content Management**: FAQs, promotions, and quick responses
- **Analytics**: Feedback, training data, and performance metrics

## Key Features

### Real-time Communication
- WebSocket-based messaging for instant customer-agent communication
- Automatic session management with 5-minute inactivity timeout
- Multi-window support for agents handling multiple customers

### Health Goals Integration
- Dynamic product recommendations based on health objectives
- Structured health benefit categorization
- Goal-to-product matching algorithm

### Multilingual Support
- Automatic translation using Google Translate API
- Support for English, Bahasa Melayu, Chinese, and Tamil
- Language preference storage for registered users

### Role-based Access Control
- Domain-based automatic role assignment
- Hierarchical permissions (Customer < Agent < Manager)
- Secure authentication with password hashing

## Technical Stack

- **Backend**: Python Flask with SocketIO for real-time communication
- **Database**: SQLite with comprehensive relational schema
- **Frontend**: HTML5, CSS3, JavaScript with WebSocket integration
- **Translation**: Google Translate API via googletrans library
- **Authentication**: Custom role-based system with domain mapping

## Copyright

© 2025 Rock Supplements Chatbot. All rights reserved.

## Acknowledgments

This project demonstrates a comprehensive rule-based chatbot system for e-commerce with real-time agent support, multilingual capabilities, and advanced product recommendation features.

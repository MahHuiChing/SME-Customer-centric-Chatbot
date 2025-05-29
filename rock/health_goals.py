"""
Health Goals Module for Rock Chatbot

This module defines standard health goal categories and provides mapping functionality
to connect user-selected goals with product health benefits.
"""

# Standard health goal categories that will be shown to users
STANDARD_HEALTH_GOALS = [
    {
        "id": "muscle_building",
        "name": "Muscle Building",
        "description": "Build muscle mass and strength",
        "keywords": ["muscle gain", "muscle building", "strength", "muscle mass", "bodybuilding", "lean muscle"]
    },
    {
        "id": "weight_management",
        "name": "Weight Management",
        "description": "Support weight loss and metabolism",
        "keywords": ["weight loss", "fat loss", "metabolism", "fat burning", "appetite control", "weight management"]
    },
    {
        "id": "energy_performance",
        "name": "Energy & Performance",
        "description": "Boost energy and athletic performance",
        "keywords": ["energy", "performance", "endurance", "stamina", "pre-workout", "workout", "training", "focus"]
    },
    {
        "id": "general_health",
        "name": "General Health & Wellness",
        "description": "Support overall health and wellbeing",
        "keywords": ["general health", "wellness", "health", "wellbeing", "immunity", "immune support"]
    },
    {
        "id": "recovery",
        "name": "Recovery & Repair",
        "description": "Support muscle recovery and joint health",
        "keywords": ["recovery", "muscle recovery", "joint health", "repair", "post-workout", "soreness"]
    }
]

def get_all_standard_goals():
    """Return all standard health goal categories."""
    return STANDARD_HEALTH_GOALS

def get_standard_goal_by_id(goal_id):
    """Get a standard health goal by its ID."""
    for goal in STANDARD_HEALTH_GOALS:
        if goal["id"] == goal_id:
            return goal
    return None

def get_standard_goal_by_name(goal_name):
    """Get a standard health goal by its name."""
    for goal in STANDARD_HEALTH_GOALS:
        if goal["name"].lower() == goal_name.lower():
            return goal
    return None

def match_health_benefits_to_standard_goals(health_benefits, benefit_categories=None):
    """
    Match product health benefits to standard goal categories.

    Args:
        health_benefits (str): Comma-separated health benefits from a product
        benefit_categories (dict, optional): Dictionary mapping benefit names to their categories

    Returns:
        list: List of matching standard goal IDs
    """
    if not health_benefits:
        print(f"No health benefits provided")
        return []

    print(f"Matching health benefits: '{health_benefits}'")

    # Convert to lowercase and split by commas
    benefits = [b.strip().lower() for b in health_benefits.split(',')]
    print(f"Parsed benefits: {benefits}")

    matching_goals = set()

    # Check each benefit against all goal keywords
    for benefit in benefits:
        benefit_matched = False

        # First try to match by keyword
        for goal in STANDARD_HEALTH_GOALS:
            for keyword in goal["keywords"]:
                if keyword in benefit or benefit in keyword:
                    matching_goals.add(goal["id"])
                    print(f"Match found: benefit '{benefit}' matches keyword '{keyword}' for goal '{goal['id']}'")
                    benefit_matched = True
                    break
            if benefit_matched:
                break

        # If no match by keyword and we have category information, try to match by category
        if not benefit_matched and benefit_categories and benefit in benefit_categories:
            category = benefit_categories[benefit]
            print(f"No keyword match for '{benefit}', trying to match by category: '{category}'")

            # Map benefit category to standard goal ID
            category_to_goal = {
                'muscle_building': 'muscle_building',
                'weight_management': 'weight_management',
                'energy_performance': 'energy_performance',
                'general_health': 'general_health',
                'recovery': 'recovery'
            }

            if category in category_to_goal:
                goal_id = category_to_goal[category]
                matching_goals.add(goal_id)
                print(f"Category match found: benefit '{benefit}' in category '{category}' matches goal '{goal_id}'")

    print(f"Matching goals: {list(matching_goals)}")
    return list(matching_goals)

def match_user_goal_to_products(user_goal_id, products):
    """
    Filter products that match a user's selected health goal.

    Args:
        user_goal_id (str): The standard goal ID selected by the user
        products (list): List of product dictionaries with health_benefits field

    Returns:
        list: Filtered list of products that match the goal
    """
    print(f"Matching products for goal: '{user_goal_id}'")
    print(f"Total products to check: {len(products)}")

    if not user_goal_id or not products:
        print("No goal ID or products provided")
        return []

    goal = get_standard_goal_by_id(user_goal_id)
    if not goal:
        print(f"Goal with ID '{user_goal_id}' not found")
        return []

    print(f"Found goal: {goal['name']}")

    # Get benefit categories from the database
    from rock.database import Database
    import os
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'rock_chatbot.db')
    db = Database(db_path)

    # Get all health benefits with their categories
    benefit_query = "SELECT name, category FROM health_benefits WHERE is_active = 1"
    benefit_results = db.execute_query(benefit_query)

    # Create a dictionary mapping benefit names to their categories
    benefit_categories = {}
    for benefit in benefit_results:
        benefit_categories[benefit['name'].lower()] = benefit['category']

    print(f"Loaded {len(benefit_categories)} benefit categories from database")

    matching_products = []

    for product in products:
        print(f"Checking product: {product.get('name')} (ID: {product.get('product_id')})")

        # Skip products without health benefits
        if not product.get('health_benefits'):
            print(f"  - No health benefits for product {product.get('product_id')}")
            continue

        print(f"  - Health benefits: '{product['health_benefits']}'")

        # Get all standard goals this product matches
        product_goals = match_health_benefits_to_standard_goals(
            product['health_benefits'],
            benefit_categories
        )

        # If the user's goal is in the product's matching goals, include it
        if user_goal_id in product_goals:
            print(f"  - MATCH: Product {product.get('product_id')} matches goal '{user_goal_id}'")
            matching_products.append(product)
        else:
            print(f"  - NO MATCH: Product {product.get('product_id')} does not match goal '{user_goal_id}'")

    print(f"Total matching products: {len(matching_products)}")
    return matching_products

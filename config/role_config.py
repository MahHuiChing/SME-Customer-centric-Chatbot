"""
Role configuration for Rock Chatbot.

This module defines the mapping between email domains and user roles.
"""

# Domain-to-role mapping
DOMAIN_ROLE_MAPPING = {
    # Manager domains
    'manager.rock.com': 'manager',

    # Agent domains
    'agent.rock.com': 'agent',
    'support.rock.com': 'agent',
    'helpdesk.rock.com': 'agent',

    # Default domain (for testing/development)
    'rock.com': 'agent'  # Default to agent for general company emails
}

# Default role if no domain match is found
DEFAULT_ROLE = 'agent'

# Valid roles
VALID_ROLES = ['manager', 'agent']

def get_role_from_email(email: str) -> str:
    """
    Determine the role based on the email domain.

    Args:
        email: The email address to check

    Returns:
        The role associated with the email domain or the default role
    """
    if not email or '@' not in email:
        return DEFAULT_ROLE

    # Extract domain from email
    domain = email.split('@')[-1].lower()

    # Check for exact domain match
    if domain in DOMAIN_ROLE_MAPPING:
        return DOMAIN_ROLE_MAPPING[domain]

    # Check for subdomain match (e.g., team.agent.rock.com should match agent.rock.com)
    domain_parts = domain.split('.')
    for i in range(1, len(domain_parts)):
        potential_domain = '.'.join(domain_parts[i:])
        if potential_domain in DOMAIN_ROLE_MAPPING:
            return DOMAIN_ROLE_MAPPING[potential_domain]

    return DEFAULT_ROLE

def is_valid_role(role: str) -> bool:
    """
    Check if a role is valid.

    Args:
        role: The role to check

    Returns:
        True if the role is valid, False otherwise
    """
    return role in VALID_ROLES

from db_credits import check_user_has_sufficient_credits, deduct_user_credits
from db_credits_deduction import get_credit_deduction_by_action
from db_user import get_user_by_wp_number

def can_user_perform_action(whatsapp, action):
    try:
        credit_deduction = get_credit_deduction_by_action(action)
    except Exception as e:
        print(f"Error retrieving credit deduction for action '{action}': {e}")
        return False
    try:
        if credit_deduction is None:
            print(f"No credit deduction found for action '{action}'. Assuming no credits required.")
            return True
    except Exception as e:
        print(f"Error checking credit deduction for action '{action}': {e}")
        return False
    
    required_credits = credit_deduction.credits_deduction_value

    try:
        wp_number = whatsapp.replace(" ", "").strip() if isinstance(whatsapp, str) else whatsapp
        user = get_user_by_wp_number(wp_number)
        if user is None:
            print(f"No user found for WhatsApp number '{wp_number}'. Cannot perform action '{action}'.")
            return False
    except Exception as e:
        print(f"Error retrieving user for WhatsApp number '{wp_number}': {e}")
        return False
    
    result = check_user_has_sufficient_credits(user.id, required_credits)
    if not result:
        print(f"User with WhatsApp number '{wp_number}' does not have enough credits to perform action '{action}'. Required: {required_credits}.")
        return False
    return True


def deduct_credits_for_action(whatsapp, action):
    try:
        credit_deduction = get_credit_deduction_by_action(action)
    except Exception as e:
        print(f"Error retrieving credit deduction for action '{action}': {e}")
        return False, "exception"
    try:
        if credit_deduction is None:
            print(f"No credit deduction found for action '{action}'. Assuming no credits required, so no deduction needed.")
            return True, "no_deduction_needed"
    except Exception as e:
        print(f"Error checking credit deduction for action '{action}': {e}")
        return False, "exception"
    
    deduction_value = credit_deduction.credits_deduction_value

    try:
        wp_number = whatsapp.replace(" ", "").strip() if isinstance(whatsapp, str) else whatsapp
        user = get_user_by_wp_number(wp_number)
        if user is None:
            print(f"No user found for WhatsApp number '{wp_number}'. Cannot deduct credits for action '{action}'.")
            return False, "user_not_found"
    except Exception as e:
        print(f"Error retrieving user for WhatsApp number '{wp_number}': {e}")
        return False, "exception"
    
    result = deduct_user_credits(user.id, deduction_value)
    if not result.get("success", False):
        print(f"Failed to deduct credits for user with WhatsApp number '{wp_number}' for action '{action}'. Reason: {result.get('message', 'unknown_error')}.")
        return False, result.get("message", "unknown_error")
    return True, "okay"
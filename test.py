from db_user import create_or_get_user, set_user_role

if __name__ == "__main__":

    # Example usage
    sender = "8801301807991"
    profile_name = "Business Noor"

    user = create_or_get_user(sender, profile_name)
    print(f"User created or retrieved: {user}")

    new_role = "professional"
    if set_user_role(sender, new_role):
        print(f"User role updated to {new_role}")
    else:
        print("Failed to update user role")
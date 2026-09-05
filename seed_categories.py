BUILTIN_CATEGORIES = {
    "Transport": ["Fuel", "Public Transit", "Parking", "Ride-share", "Vehicle Maintenance"],
    "Travel": ["Flights", "Hotels", "Vacation Activities", "Travel Insurance"],
    "Food": ["Groceries", "Dining Out", "Coffee/Snacks"],
    "Housing": ["Rent/Mortgage", "Utilities", "Maintenance"],
    "Health": ["Medical", "Pharmacy", "Fitness"],
    "Entertainment": ["Subscriptions", "Movies/Events", "Hobbies"],
    "Shopping": ["Clothing", "Electronics", "Household Goods"],
    "Education": ["Tuition", "Books/Supplies", "Courses"],
    "Other": ["Gifts/Donations", "Fees/Charges", "Miscellaneous"],
}


def seed_if_empty(conn) -> None:
    """Insert builtin categories and subcategories if the categories table is empty."""
    count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if count > 0:
        return

    for category_name, subcategories in BUILTIN_CATEGORIES.items():
        cursor = conn.execute(
            "INSERT INTO categories (name) VALUES (?)",
            (category_name,),
        )
        category_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO subcategories (category_id, name) VALUES (?, ?)",
            [(category_id, subcategory_name) for subcategory_name in subcategories],
        )

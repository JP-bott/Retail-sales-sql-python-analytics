"""
Generate the synthetic Westbridge Retail dataset.

Everything in data/raw/ is fictional and produced by this script with a fixed
random seed, so running it again gives identical CSV files.

Usage (from the repository root):
    python scripts/generate_data.py

Business logic built into the data:
- Customers differ in how often they buy: some buy once, some a few times,
  some buy regularly, and about 8% register but never place an order.
- About a quarter of customers "churn" - they stop buying part-way through.
- Orders never happen before the customer's registration date.
- Sales are seasonal (peak in November/December) and grow slightly over time.
- Online share rises over the two years; online and in-store baskets and
  category mixes differ; some categories gain popularity over time and others fade.
- Categories have different price ranges and margins.
- Discounts are more common in November and July and never exceed the gross
  line amount.
- A small share of orders is cancelled (more often online).
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

START_DATE = pd.Timestamp("2024-01-01")
END_DATE = pd.Timestamp("2025-12-31")

N_CUSTOMERS = 1000
N_ORDERS = 15000
NEVER_BUY_SHARE = 0.08      # registered but no orders at all
ONE_TIME_SHARE = 0.12       # exactly one order
OCCASIONAL_SHARE = 0.20     # 2-5 orders
CHURN_SHARE = 0.25          # stop buying before the end of the period

# --------------------------------------------------------------------------
# Categories and products
# --------------------------------------------------------------------------
# category_name: (popularity weight, margin range, max discount rate, products)
# Each product is (name, unit_price).
CATEGORY_DEFINITIONS = {
    "Electronics": (0.7, (0.18, 0.26), 0.10, [
        ("Wireless Earbuds Pro", 89.99), ("Bluetooth Speaker Mini", 49.99),
        ("Smart Watch Series 4", 199.99), ("4K Streaming Stick", 39.99),
        ("Noise-Cancelling Headphones", 149.99), ("Portable Power Bank 20K", 34.99),
        ("Smart Home Camera", 79.99), ("Fitness Tracker Band", 59.99),
        ("Digital Camera Compact", 329.99),
    ]),
    "Computers & Accessories": (0.6, (0.15, 0.22), 0.10, [
        ("Ultrabook 14-inch Laptop", 899.99), ("Mechanical Keyboard TKL", 79.99),
        ("Wireless Ergonomic Mouse", 29.99), ("27-inch IPS Monitor", 229.99),
        ("USB-C Docking Station", 119.99), ("1TB Portable SSD", 99.99),
        ("Laptop Backpack 15-inch", 44.99), ("Webcam 1080p", 49.99),
    ]),
    "Home & Kitchen": (1.1, (0.35, 0.45), 0.25, [
        ("Stainless Steel Cookware Set", 129.99), ("Programmable Coffee Maker", 69.99),
        ("Cast Iron Skillet 12-inch", 34.99), ("Chef's Knife 8-inch", 44.99),
        ("Air Fryer 5-Quart", 89.99), ("Glass Food Storage Set", 24.99),
        ("Cotton Bath Towel Set", 39.99), ("Bamboo Cutting Board", 19.99),
        ("Robot Vacuum Cleaner", 249.99),
    ]),
    "Furniture": (0.35, (0.40, 0.50), 0.25, [
        ("Oak Bookshelf 5-Tier", 189.99), ("Ergonomic Office Chair", 249.99),
        ("Standing Desk Adjustable", 399.99), ("Fabric Accent Chair", 219.99),
        ("Queen Platform Bed Frame", 449.99), ("Walnut Coffee Table", 159.99),
        ("TV Console Cabinet", 279.99),
    ]),
    "Men's Clothing": (0.9, (0.50, 0.60), 0.25, [
        ("Classic Oxford Shirt", 49.99), ("Slim Fit Chino Pants", 54.99),
        ("Merino Wool Sweater", 79.99), ("Waterproof Rain Jacket", 99.99),
        ("Cotton Crew T-Shirt 3-Pack", 29.99), ("Dark Wash Denim Jeans", 64.99),
        ("Performance Polo Shirt", 39.99), ("Fleece Zip Hoodie", 59.99),
    ]),
    "Women's Clothing": (1.0, (0.52, 0.62), 0.25, [
        ("Linen Blend Blouse", 44.99), ("High-Rise Straight Jeans", 69.99),
        ("Wrap Midi Dress", 79.99), ("Cashmere Blend Cardigan", 109.99),
        ("Everyday Leggings", 34.99), ("Quilted Puffer Vest", 89.99),
        ("Cotton Pajama Set", 39.99), ("Tailored Work Blazer", 119.99),
    ]),
    "Footwear": (0.8, (0.45, 0.55), 0.25, [
        ("Trail Running Shoes", 119.99), ("Leather Chelsea Boots", 149.99),
        ("Canvas Low-Top Sneakers", 54.99), ("Memory Foam Slippers", 29.99),
        ("Waterproof Hiking Boots", 139.99), ("Everyday Sandals", 34.99),
        ("Leather Dress Loafers", 99.99),
    ]),
    "Sports & Outdoors": (0.8, (0.38, 0.48), 0.25, [
        ("Yoga Mat Non-Slip", 29.99), ("Adjustable Dumbbell Pair", 149.99),
        ("2-Person Camping Tent", 139.99), ("Insulated Water Bottle 32oz", 24.99),
        ("Resistance Band Set", 19.99), ("Trekking Poles Pair", 59.99),
        ("Road Bike Helmet", 64.99), ("Foam Roller Deep Tissue", 22.99),
        ("Sleeping Bag 20F", 89.99),
    ]),
    "Beauty & Personal Care": (1.2, (0.55, 0.68), 0.25, [
        ("Vitamin C Face Serum", 28.99), ("Daily Moisturizer SPF 30", 22.99),
        ("Electric Toothbrush", 59.99), ("Argan Oil Shampoo", 14.99),
        ("Matte Lipstick Set", 24.99), ("Beard Grooming Kit", 32.99),
        ("Hydrating Sheet Masks 10-Pack", 16.99), ("Mineral Sunscreen SPF 50", 18.99),
        ("Hair Dryer Ionic", 49.99),
    ]),
    "Toys & Games": (0.7, (0.40, 0.50), 0.25, [
        ("Building Brick Set 500pc", 39.99), ("Strategy Board Game", 34.99),
        ("Remote Control Off-Road Car", 54.99), ("1000-Piece Jigsaw Puzzle", 19.99),
        ("Wooden Train Set", 44.99), ("Art Supplies Creative Kit", 27.99),
        ("Plush Bear Large", 24.99), ("Family Card Game Bundle", 14.99),
    ]),
    "Books & Stationery": (1.0, (0.35, 0.45), 0.25, [
        ("Hardcover Fiction Bestseller", 24.99), ("Cookbook: Weeknight Dinners", 29.99),
        ("Dotted Bullet Journal", 16.99), ("Gel Pen Set 24-Color", 12.99),
        ("Business Strategy Paperback", 18.99), ("Children's Picture Book", 12.99),
        ("Desk Planner 2025", 14.99), ("Sketchbook A4 Hardbound", 15.99),
        ("History Nonfiction Hardcover", 27.99),
    ]),
    "Grocery & Pantry": (1.5, (0.22, 0.30), 0.10, [
        ("Single-Origin Coffee Beans 12oz", 13.99), ("Organic Olive Oil 500ml", 11.99),
        ("Mixed Nuts Variety Tin", 9.99), ("Loose Leaf Green Tea", 8.99),
        ("Artisan Pasta Sampler", 7.99), ("Dark Chocolate Assortment", 12.99),
        ("Wildflower Honey Jar", 9.49), ("Granola Family Pack", 6.99),
        ("Hot Sauce Gift Set", 15.99),
    ]),
}

# Change in a category's popularity over the two years (-0.4 means demand
# weight falls by 40% by the end of 2025; +0.4 means it rises by 40%).
CATEGORY_DRIFT = {
    "Women's Clothing": 0.40, "Beauty & Personal Care": 0.35, "Computers & Accessories": 0.15,
    "Electronics": 0.10, "Men's Clothing": -0.40, "Toys & Games": -0.30,
    "Furniture": -0.20, "Footwear": -0.05,
}

# Channel preferences by category (multiplier on the category weight)
ONLINE_CATEGORY_MULTIPLIER = {
    "Electronics": 1.6, "Computers & Accessories": 1.7, "Books & Stationery": 1.3,
    "Furniture": 0.8, "Footwear": 0.8, "Grocery & Pantry": 0.7,
}
STORE_CATEGORY_MULTIPLIER = {
    "Electronics": 0.8, "Computers & Accessories": 0.7, "Grocery & Pantry": 1.4,
    "Footwear": 1.3, "Men's Clothing": 1.2, "Women's Clothing": 1.2,
}

# --------------------------------------------------------------------------
# Customer attributes
# --------------------------------------------------------------------------
REGION_CITIES = {
    "Northeast": ["Boston", "Philadelphia", "Pittsburgh", "Buffalo"],
    "Southeast": ["Atlanta", "Charlotte", "Nashville", "Tampa"],
    "Midwest": ["Chicago", "Columbus", "Minneapolis", "Kansas City"],
    "Southwest": ["Dallas", "Austin", "Phoenix", "Albuquerque"],
    "West": ["Seattle", "Portland", "Denver", "San Diego"],
}
REGION_WEIGHTS = {"Northeast": 0.22, "Southeast": 0.20, "Midwest": 0.20,
                  "Southwest": 0.16, "West": 0.22}

AGE_GROUPS = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
AGE_WEIGHTS = [0.10, 0.27, 0.23, 0.19, 0.13, 0.08]

FEMALE_FIRST_NAMES = [
    "Olivia", "Emma", "Sophia", "Isabella", "Mia", "Charlotte", "Amelia", "Harper",
    "Evelyn", "Abigail", "Emily", "Ella", "Elizabeth", "Sofia", "Avery", "Scarlett",
    "Grace", "Chloe", "Victoria", "Riley", "Aria", "Lily", "Hannah", "Natalie",
    "Zoe", "Nora", "Leah", "Hazel", "Violet", "Aurora", "Savannah", "Audrey",
    "Brooklyn", "Bella", "Claire", "Lucy", "Paisley", "Anna", "Caroline", "Nova",
    "Priya", "Mei", "Fatima", "Camila", "Rosa", "Aaliyah", "Keiko", "Imani",
]
MALE_FIRST_NAMES = [
    "Liam", "Noah", "Oliver", "James", "Elijah", "William", "Henry", "Lucas",
    "Benjamin", "Theodore", "Mateo", "Levi", "Sebastian", "Daniel", "Jack", "Michael",
    "Alexander", "Owen", "Asher", "Samuel", "Ethan", "Leo", "Jackson", "Mason",
    "Ezra", "John", "Hudson", "Luca", "Aiden", "Joseph", "David", "Jacob",
    "Logan", "Julian", "Wyatt", "Gabriel", "Carter", "Isaac", "Anthony", "Dylan",
    "Rajesh", "Wei", "Omar", "Diego", "Mateus", "Kofi", "Hiro", "Andre",
]
NEUTRAL_FIRST_NAMES = ["Alex", "Jordan", "Taylor", "Casey", "Morgan", "Quinn",
                       "Rowan", "Skyler", "Sage", "Emerson"]
LAST_NAMES = [
    "Anderson", "Bennett", "Carter", "Dawson", "Ellis", "Fischer", "Grant", "Hughes",
    "Ingram", "Jensen", "Keller", "Lawson", "Mitchell", "Nolan", "Oliver", "Parker",
    "Quinn", "Reynolds", "Sullivan", "Thornton", "Underwood", "Vaughn", "Walker",
    "Young", "Zimmerman", "Alvarez", "Brooks", "Castillo", "Delgado", "Espinoza",
    "Foster", "Gonzalez", "Harrison", "Iverson", "Johnson", "Kim", "Lopez", "Morales",
    "Nguyen", "Ortiz", "Patel", "Ramirez", "Santos", "Tran", "Vega", "Wong",
    "Yamamoto", "Zhang", "Murphy", "Okafor", "Singh", "Cohen", "Rossi", "Larsen",
    "Dubois", "Novak", "Hassan", "Kowalski", "Mendoza", "Chen",
]


def build_categories_and_products(rng):
    """Return the categories and products DataFrames plus lookup helpers."""
    category_rows = []
    product_rows = []
    product_id = 1
    for category_id, (category_name, definition) in enumerate(CATEGORY_DEFINITIONS.items(), start=1):
        _, margin_range, _, products = definition
        category_rows.append({"category_id": category_id, "category_name": category_name})
        for product_name, unit_price in products:
            margin = rng.uniform(*margin_range)
            unit_cost = round(unit_price * (1 - margin), 2)
            product_rows.append({
                "product_id": product_id,
                "product_name": product_name,
                "category_id": category_id,
                "unit_price": unit_price,
                "unit_cost": unit_cost,
            })
            product_id += 1
    return pd.DataFrame(category_rows), pd.DataFrame(product_rows)


def build_customers(rng):
    """Create customers with names, demographics, region and registration date."""
    regions = list(REGION_WEIGHTS)
    region_probs = np.array(list(REGION_WEIGHTS.values()))
    used_names = set()
    rows = []
    for customer_id in range(1, N_CUSTOMERS + 1):
        gender = rng.choice(["Female", "Male", "Non-binary"], p=[0.48, 0.48, 0.04])
        while True:
            if gender == "Female":
                first = rng.choice(FEMALE_FIRST_NAMES)
            elif gender == "Male":
                first = rng.choice(MALE_FIRST_NAMES)
            else:
                first = rng.choice(NEUTRAL_FIRST_NAMES)
            full_name = f"{first} {rng.choice(LAST_NAMES)}"
            if full_name not in used_names:
                used_names.add(full_name)
                break
        region = rng.choice(regions, p=region_probs)
        city = rng.choice(REGION_CITIES[region])
        age_group = rng.choice(AGE_GROUPS, p=AGE_WEIGHTS)
        # Registrations run from early 2023 to late 2025; most are before 2025.
        days_offset = int(rng.beta(1.3, 1.6) * (pd.Timestamp("2025-10-31") - pd.Timestamp("2023-01-01")).days)
        registration_date = pd.Timestamp("2023-01-01") + pd.Timedelta(days=days_offset)
        rows.append({
            "customer_id": customer_id,
            "customer_name": full_name,
            "gender": gender,
            "age_group": age_group,
            "city": city,
            "region": region,
            "registration_date": registration_date.strftime("%Y-%m-%d"),
        })
    return pd.DataFrame(rows)


def build_day_weights():
    """Relative likelihood of an order on each day: seasonality, growth, weekday."""
    days = pd.date_range(START_DATE, END_DATE, freq="D")
    month_weight = {1: 0.85, 2: 0.80, 3: 0.90, 4: 0.92, 5: 0.98, 6: 0.95,
                    7: 1.00, 8: 1.02, 9: 0.95, 10: 1.05, 11: 1.35, 12: 1.50}
    weekday_weight = {0: 0.90, 1: 0.90, 2: 0.92, 3: 0.95, 4: 1.05, 5: 1.25, 6: 1.15}
    trend = 1 + 0.25 * (np.arange(len(days)) / (len(days) - 1))
    weights = np.array([month_weight[d.month] * weekday_weight[d.weekday()] for d in days]) * trend
    return days, weights


def allocate_orders_per_customer(customers, rng):
    """Decide how many orders each customer places and the window they are active in."""
    n = len(customers)
    registration = pd.to_datetime(customers["registration_date"])
    window_start = registration.where(registration > START_DATE, START_DATE)

    # Churned customers stop buying part-way through the period.
    window_end = pd.Series(END_DATE, index=customers.index)
    churn_mask = rng.random(n) < CHURN_SHARE
    for idx in customers.index[churn_mask]:
        earliest = window_start[idx] + pd.Timedelta(days=90)
        latest = END_DATE - pd.Timedelta(days=75)
        if earliest < latest:
            span = (latest - earliest).days
            window_end[idx] = earliest + pd.Timedelta(days=int(rng.integers(0, span + 1)))

    # Customer type: never / one-time / occasional / regular.
    roll = rng.random(n)
    never_buy = roll < NEVER_BUY_SHARE
    one_time = (roll >= NEVER_BUY_SHARE) & (roll < NEVER_BUY_SHARE + ONE_TIME_SHARE)
    occasional = (roll >= NEVER_BUY_SHARE + ONE_TIME_SHARE) & (
        roll < NEVER_BUY_SHARE + ONE_TIME_SHARE + OCCASIONAL_SHARE)
    regular = ~(never_buy | one_time | occasional)

    order_counts = np.zeros(n, dtype=int)
    order_counts[one_time] = 1
    order_counts[occasional] = rng.integers(2, 6, size=occasional.sum())

    # Regular customers share the remaining orders, weighted by how often they
    # buy and how long they are active.
    remaining_orders = N_ORDERS - order_counts.sum()
    active_days = (window_end - window_start).dt.days.clip(lower=30).to_numpy()
    frequency_weight = rng.gamma(shape=2.2, scale=1.0, size=n) * (active_days / 731.0) ** 0.8
    regular_weights = np.where(regular, frequency_weight, 0.0)
    # Cap very large weights so no single customer places an implausible number of orders.
    weight_cap = 3.0 * regular_weights[regular].mean()
    regular_weights = np.minimum(regular_weights, weight_cap)
    regular_weights = regular_weights / regular_weights.sum()
    order_counts += rng.multinomial(remaining_orders, regular_weights)
    return order_counts, window_start, window_end


def build_orders_and_items(customers, products, categories, rng):
    """Create orders and line items that respect customer windows and business rules."""
    days, day_weights = build_day_weights()
    day_index = {d: i for i, d in enumerate(days)}
    order_counts, window_start, window_end = allocate_orders_per_customer(customers, rng)

    category_names = categories.set_index("category_id")["category_name"].to_dict()
    product_category_ids = products["category_id"].to_numpy()
    product_prices = products["unit_price"].to_numpy()
    product_costs = products["unit_cost"].to_numpy()
    n_products = len(products)

    category_base_weight = np.array([CATEGORY_DEFINITIONS[category_names[c]][0]
                                     for c in product_category_ids])
    category_drift = np.array([CATEGORY_DRIFT.get(category_names[c], 0.0)
                               for c in product_category_ids])
    category_max_discount = np.array([CATEGORY_DEFINITIONS[category_names[c]][2]
                                      for c in product_category_ids])
    # Some products sell much better than others within their category.
    product_popularity = rng.lognormal(mean=0.0, sigma=0.8, size=n_products)
    # Expensive items sell in fewer units than cheap ones.
    product_popularity = product_popularity * (product_prices / 40.0) ** -0.35
    online_multiplier = np.array([ONLINE_CATEGORY_MULTIPLIER.get(category_names[c], 1.0)
                                  for c in product_category_ids])
    store_multiplier = np.array([STORE_CATEGORY_MULTIPLIER.get(category_names[c], 1.0)
                                 for c in product_category_ids])

    category_ids = categories["category_id"].to_numpy()
    n_categories = len(category_ids)

    order_records = []
    for customer_index, customer_id in enumerate(customers["customer_id"]):
        n_orders = int(order_counts[customer_index])
        if n_orders == 0:
            continue

        start_pos = day_index[window_start.iloc[customer_index].normalize()]
        end_pos = day_index[window_end.iloc[customer_index].normalize()]
        window_weights = day_weights[start_pos:end_pos + 1]
        chosen_positions = rng.choice(np.arange(start_pos, end_pos + 1), size=n_orders,
                                      p=window_weights / window_weights.sum())

        # Customer-level tastes: favourite categories and online preference.
        customer_category_taste = rng.lognormal(0.0, 0.6, size=n_categories)
        taste_per_product = customer_category_taste[product_category_ids - 1]
        online_preference = rng.beta(2.0, 2.4)

        for position in chosen_positions:
            order_date = days[position]
            progress = position / (len(days) - 1)
            online_probability = np.clip(online_preference * (0.85 + 0.30 * progress), 0.05, 0.95)
            channel = "Online" if rng.random() < online_probability else "In-Store"

            cancel_probability = 0.07 if channel == "Online" else 0.03
            status = "Cancelled" if rng.random() < cancel_probability else "Completed"

            n_items = 1 + rng.poisson(0.8 if channel == "Online" else 1.15)
            n_items = int(min(n_items, 6))

            channel_multiplier = online_multiplier if channel == "Online" else store_multiplier
            trend_multiplier = 1 + category_drift * progress
            product_weight = (category_base_weight * product_popularity * taste_per_product
                              * channel_multiplier * trend_multiplier)
            product_probability = product_weight / product_weight.sum()
            chosen_products = rng.choice(n_products, size=n_items, replace=False, p=product_probability)

            promo_probability = 0.18 + (0.27 if order_date.month == 11 else 0.0) \
                + (0.12 if order_date.month == 7 else 0.0) + (0.05 if channel == "Online" else 0.0)

            items = []
            for product_index in chosen_products:
                price = float(product_prices[product_index])
                if price < 15:
                    quantity = int(rng.choice([1, 2, 3, 4], p=[0.50, 0.25, 0.15, 0.10]))
                elif price < 60:
                    quantity = int(rng.choice([1, 2, 3], p=[0.75, 0.18, 0.07]))
                else:
                    quantity = int(rng.choice([1, 2], p=[0.93, 0.07]))

                gross_amount = round(quantity * price, 2)
                discount_amount = 0.0
                if rng.random() < promo_probability:
                    max_rate = category_max_discount[product_index]
                    possible_rates = [r for r in (0.05, 0.10, 0.15, 0.20, 0.25) if r <= max_rate + 1e-9]
                    rate = float(rng.choice(possible_rates))
                    discount_amount = round(gross_amount * rate, 2)
                discount_amount = min(discount_amount, gross_amount)

                items.append({
                    "product_id": int(product_index) + 1,
                    "quantity": quantity,
                    "unit_price": price,
                    "discount_amount": discount_amount,
                })

            order_records.append({
                "customer_id": int(customer_id),
                "order_date": order_date.strftime("%Y-%m-%d"),
                "sales_channel": channel,
                "order_status": status,
                "items": items,
            })

    # Number orders chronologically so order_id increases with order_date.
    order_records.sort(key=lambda record: (record["order_date"], record["customer_id"]))
    order_rows = []
    item_rows = []
    order_item_id = 1
    for order_id, record in enumerate(order_records, start=1):
        order_rows.append({
            "order_id": order_id,
            "customer_id": record["customer_id"],
            "order_date": record["order_date"],
            "sales_channel": record["sales_channel"],
            "order_status": record["order_status"],
        })
        for item in record["items"]:
            item_rows.append({"order_item_id": order_item_id, "order_id": order_id, **item})
            order_item_id += 1

    return pd.DataFrame(order_rows), pd.DataFrame(item_rows)


def main():
    rng = np.random.default_rng(SEED)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    categories, products = build_categories_and_products(rng)
    customers = build_customers(rng)
    orders, order_items = build_orders_and_items(customers, products, categories, rng)

    categories.to_csv(RAW_DIR / "categories.csv", index=False)
    products.to_csv(RAW_DIR / "products.csv", index=False)
    customers.to_csv(RAW_DIR / "customers.csv", index=False)
    orders.to_csv(RAW_DIR / "orders.csv", index=False)
    order_items.to_csv(RAW_DIR / "order_items.csv", index=False)

    print("Synthetic Westbridge Retail data written to", RAW_DIR)
    print(f"  categories:  {len(categories):>6,}")
    print(f"  products:    {len(products):>6,}")
    print(f"  customers:   {len(customers):>6,}")
    print(f"  orders:      {len(orders):>6,}")
    print(f"  order_items: {len(order_items):>6,}")
    print(f"  cancelled orders: {(orders['order_status'] == 'Cancelled').mean():.1%}")
    print(f"  customers with no orders: {(~customers['customer_id'].isin(orders['customer_id'])).sum()}")


if __name__ == "__main__":
    main()

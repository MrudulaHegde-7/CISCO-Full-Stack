from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MenuItem, Order, OrderLine, User
from app.security.auth import hash_password

SEED_MENU = [
    ("Masala Dosa", "Breakfast", True, "90.00", 20, "Crisp rice crepe with spiced potato filling.", "Contains declared mustard; ask staff about cross-contact."),
    ("Paneer Biryani", "Main course", True, "180.00", 10, "Fragrant rice with paneer and whole spices.", "Contains dairy."),
    ("Idli Sambar", "Breakfast", True, "70.00", 18, "Steamed rice cakes served with lentil stew.", "Contains declared mustard in tempering."),
    ("Vegetable Pulao", "Main course", True, "150.00", 12, "Basmati rice with seasonal vegetables.", "Contains no declared allergens; cross-contact cannot be ruled out."),
    ("Chana Masala", "Main course", True, "160.00", 12, "Chickpeas simmered in tomato and spices.", "Contains no declared allergens; cross-contact cannot be ruled out."),
    ("Paneer Tikka", "Starters", True, "190.00", 8, "Grilled marinated paneer with peppers.", "Contains dairy."),
    ("Garden Salad", "Sides", True, "110.00", 15, "Seasonal greens, cucumber, tomato and lemon dressing.", "Dressing contains mustard."),
    ("Chicken Curry", "Main course", False, "220.00", 10, "Slow-cooked chicken curry with rice.", "Contains dairy in the curry base."),
    ("Gulab Jamun", "Desserts", True, "80.00", 16, "Milk-solid dumplings in rose syrup.", "Contains dairy and wheat."),
    ("Lemon Rice", "Sides", True, "95.00", 14, "Rice tempered with lemon, curry leaves and peanuts.", "Contains peanuts and declared mustard."),
]

FOOD_IMAGES = {
    "Masala Dosa": "https://images.unsplash.com/photo-1668236543090-82eba5ee5976?auto=format&fit=crop&w=800&q=80",
    "Paneer Biryani": "https://thumb.wikimedia.org/wikipedia/commons/thumb/c/cc/Paneer_Biriyani_02.jpg/960px-Paneer_Biriyani_02.jpg",
    "Idli Sambar": "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/02/Idli_Sambar-Noida-UP-SP004.jpg/960px-Idli_Sambar-Noida-UP-SP004.jpg",
    "Vegetable Pulao": "https://thumb.wikimedia.org/wikipedia/commons/thumb/9/98/Andhra_Vegetable_Pulao_-_WCI-Day0-Dinner.jpg/960px-Andhra_Vegetable_Pulao_-_WCI-Day0-Dinner.jpg",
    "Chana Masala": "https://thumb.wikimedia.org/wikipedia/commons/thumb/7/72/Chana_Masala_-_Mohammed_-_Spice_Of_Life_2024-05-27.jpg/960px-Chana_Masala_-_Mohammed_-_Spice_Of_Life_2024-05-27.jpg",
    "Paneer Tikka": "https://upload.wikimedia.org/wikipedia/commons/8/8b/Paneer_Tikka_Shashlik_PK012.jpg",
    "Garden Salad": "https://thumb.wikimedia.org/wikipedia/commons/thumb/8/81/Vegetable_Salad_%28Unsplash%29.jpg/960px-Vegetable_Salad_%28Unsplash%29.jpg",
    "Chicken Curry": "https://thumb.wikimedia.org/wikipedia/commons/thumb/4/46/Chicken_Curry_5.jpg/960px-Chicken_Curry_5.jpg",
    "Gulab Jamun": "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/61/Gulab_Jamun_as_a_Diwali_Sweet.jpg/960px-Gulab_Jamun_as_a_Diwali_Sweet.jpg",
    "Lemon Rice": "https://thumb.wikimedia.org/wikipedia/commons/thumb/b/bb/Lemon_Rice_in_Kerala.jpg/960px-Lemon_Rice_in_Kerala.jpg",
}
OLD_FOOD_PLACEHOLDER = "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=800&q=80"
OLD_FOOD_IMAGE_IDS = {
    "Masala Dosa": "photo-1668236543090-82eba5ee5976",
    "Paneer Biryani": "photo-1633945274405-b6c8069047b0",
    "Idli Sambar": "photo-1628294896516-344152572ee8",
    "Vegetable Pulao": "photo-1642821373181-696a54913e93",
    "Chana Masala": "photo-1603894584373-5ac82b2ae398",
    "Paneer Tikka": "photo-1599487488170-d11ec9c172f0",
    "Garden Salad": "photo-1540189549336-e6e99c3679fe",
    "Chicken Curry": "photo-1601050690597-df0568f70950",
    "Gulab Jamun": "photo-1488477181946-6428a0291777",
    "Lemon Rice": "photo-1512621776951-a57141f2eefd",
}


def food_image_url(title: str) -> str:
    return FOOD_IMAGES[title]


def seed_demo_data(session: Session) -> None:
    users = list(session.scalars(select(User).limit(1)))
    if not users:
        admin = User(
            username=settings.demo_admin_username,
            password_hash=hash_password(settings.demo_admin_password),
            role="ADMIN",
        )
        maya = User(
            username=settings.demo_user_one_username,
            password_hash=hash_password(settings.demo_user_one_password),
            role="USER",
        )
        arjun = User(
            username=settings.demo_user_two_username,
            password_hash=hash_password(settings.demo_user_two_password),
            role="USER",
        )
        session.add_all([admin, maya, arjun])
        session.flush()

    items = list(session.scalars(select(MenuItem).limit(1)))
    if not items:
        session.add_all(
            [
                MenuItem(
                    title=title,
                    category=category,
                    vegetarian=vegetarian,
                    price=Decimal(price),
                    capacity=capacity,
                    description=description,
                    declared_allergens=allergens,
                    image_url=food_image_url(title),
                )
                for title, category, vegetarian, price, capacity, description, allergens in SEED_MENU
            ]
        )
        session.flush()

    for item in session.scalars(select(MenuItem)):
        old_image_id = OLD_FOOD_IMAGE_IDS.get(item.title)
        old_image_url = (
            f"https://images.unsplash.com/{old_image_id}?auto=format&fit=crop&w=800&q=80"
            if old_image_id
            else None
        )
        if item.image_url in {OLD_FOOD_PLACEHOLDER, old_image_url}:
            item.image_url = food_image_url(item.title)

    if not list(session.scalars(select(Order).limit(1))):
        user_list = list(session.scalars(select(User).where(User.role == "USER").order_by(User.id)))
        menu = list(session.scalars(select(MenuItem).order_by(MenuItem.id)))
        samples = [(user_list[0], menu[0]), (user_list[0], menu[2]), (user_list[1], menu[1])]
        for index, (user, item) in enumerate(samples, start=1):
            if item.capacity > 0:
                item.capacity -= 1
            order = Order(
                user_id=user.id,
                status="CONFIRMED",
                total=item.price,
                idempotency_key=f"seed-order-{index}",
                request_fingerprint=f"seed-fingerprint-{index}",
            )
            order.lines.append(
                OrderLine(
                    item_id=item.id,
                    title_snapshot=item.title,
                    quantity=1,
                    unit_price=item.price,
                )
            )
            session.add(order)
    session.commit()
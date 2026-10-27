import asyncio, os, sys, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import config, asyncpg

def compute_discount(duration_days: int, service_type: str, region: str, currency: str, original_amount: float):
    # Rule: For foreigners / USD, NO DISCOUNT
    if region != "ETHIOPIA" or currency != "ETB":
        return {
            "has_discount": False,
            "discount_amount": 0,
            "discounted_amount": original_amount,
            "discount_pct": 0
        }
    
    # Ethiopian Tiered Discounts
    # 7 days: 800 Br
    # 14 days: 1000 Br
    # 30 days (Plan): 1200 Br
    # 30 days (Follow-up): 1400 Br
    if duration_days == 7:
        discount = 800.0
    elif duration_days == 14:
        discount = 1000.0
    elif duration_days == 30 and service_type == "FOLLOW_UP":
        discount = 1400.0
    elif duration_days == 30:
        discount = 1200.0
    else:
        discount = 1000.0
        
    discounted = max(original_amount - discount, 500.0)
    pct = round((discount / original_amount) * 100) if original_amount > 0 else 0
    return {
        "has_discount": True,
        "discount_amount": int(discount),
        "discounted_amount": int(discounted),
        "discount_pct": pct
    }

async def test_discounts():
    conn = await asyncpg.connect(config.settings.DATABASE_URL)
    orders = await conn.fetch("""
        SELECT mo.id as order_id, mo.user_id, u.full_name, u.gender, mo.duration_days, 
               mo.service_type, mo.region, mo.currency, mo.amount
        FROM meal_orders mo
        JOIN users u ON mo.user_id = u.telegram_id
        WHERE mo.state = 'AWAITING_PAYMENT'
        ORDER BY mo.amount DESC
    """)
    print(f"Total Awaiting Payment Orders: {len(orders)}")
    for o in orders[:10]:
        disc = compute_discount(o['duration_days'], o['service_type'], o['region'], o['currency'], float(o['amount']))
        print(f"Order #{o['order_id']} | User: {o['full_name'][:15]:<15} | {o['region']} | {o['duration_days']}d {o['service_type']} | Orig: {o['amount']} {o['currency']} -> Disc: -{disc['discount_amount']} -> Final: {disc['discounted_amount']} {o['currency']} ({disc['discount_pct']}% OFF)")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(test_discounts())

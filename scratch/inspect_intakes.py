import asyncio, os, sys, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import config, asyncpg

async def inspect_intakes():
    conn = await asyncpg.connect(config.settings.DATABASE_URL)
    
    # 1. Total intakes by state
    intake_counts = await conn.fetch("""
        SELECT state, count(*) FROM meal_intakes GROUP BY state ORDER BY count DESC
    """)
    print("=== INTAKE COUNTS BY STATE ===")
    for r in intake_counts:
        print(f"State: {r['state']:<25} Count: {r['count']}")
        
    # 2. Detailed query joining users, intakes, orders, and payments
    rows = await conn.fetch("""
        SELECT 
            i.id as intake_id,
            i.user_id,
            u.full_name,
            u.username,
            u.gender as u_gender,
            i.state as intake_state,
            i.country_region,
            i.language,
            i.answers,
            i.nutrition_profile,
            i.completed_at,
            i.created_at as intake_created_at,
            mo.id as order_id,
            mo.state as order_state,
            mo.duration_days,
            mo.service_type,
            mo.amount,
            mo.currency,
            mp.id as payment_id,
            mp.status as payment_status,
            (SELECT count(*) FROM payments p WHERE p.user_id = i.user_id AND p.status = 'approved') as past_workouts
        FROM meal_intakes i
        JOIN users u ON i.user_id = u.telegram_id
        LEFT JOIN meal_orders mo ON mo.intake_id = i.id
        LEFT JOIN meal_payments mp ON mp.order_id = mo.id
        ORDER BY i.completed_at DESC NULLS LAST, i.created_at DESC
    """)
    
    print(f"\nTotal Intakes in System: {len(rows)}")
    
    # Analyze stats
    completed = [r for r in rows if r['completed_at'] is not None or r['intake_state'] in ('PROFILE_READY', 'CHECKOUT_READY', 'CLOSED')]
    print(f"Completed Profiles: {len(completed)}")
    
    # Collect statistics
    goals = {}
    genders = {}
    regions = {}
    durations = {}
    amounts = {}
    service_types = {}
    past_buyer_count = 0
    
    for r in completed:
        ans = json.loads(r['answers']) if isinstance(r['answers'], str) else (r['answers'] or {})
        np = json.loads(r['nutrition_profile']) if isinstance(r['nutrition_profile'], str) else (r['nutrition_profile'] or {})
        
        goal = ans.get('primary_goal') or ans.get('goal') or np.get('primary_goal') or 'Unknown'
        goals[goal] = goals.get(goal, 0) + 1
        
        gender = ans.get('gender') or r['u_gender'] or 'Unknown'
        genders[gender] = genders.get(gender, 0) + 1
        
        reg = r['country_region'] or 'Unknown'
        regions[reg] = regions.get(reg, 0) + 1
        
        dur = r['duration_days'] or 'Unknown'
        durations[dur] = durations.get(dur, 0) + 1
        
        st = r['service_type'] or 'Unknown'
        service_types[st] = service_types.get(st, 0) + 1
        
        amt = f"{r['amount']} {r['currency']}" if r['amount'] else 'No Order'
        amounts[amt] = amounts.get(amt, 0) + 1
        
        if r['past_workouts'] > 0:
            past_buyer_count += 1
            
    print("\n--- STATISTICAL BREAKDOWN OF COMPLETED PROFILES ---")
    print(f"Past Workout Buyers: {past_buyer_count} ({past_buyer_count/len(completed)*100:.1f}%) | New/Cold Leads: {len(completed)-past_buyer_count}")
    print("\nGoals:", goals)
    print("Genders:", genders)
    print("Regions:", regions)
    print("Durations Selected:", durations)
    print("Service Types:", service_types)
    print("Price Tiers Chosen:", amounts)
    
    # Save 10 full representative profiles to scratch file
    sample_profiles = []
    # Pick diverse samples: male, female, past buyer, non-past buyer, Ethiopia, Diaspora
    for r in completed[:15]:
        ans = json.loads(r['answers']) if isinstance(r['answers'], str) else (r['answers'] or {})
        np = json.loads(r['nutrition_profile']) if isinstance(r['nutrition_profile'], str) else (r['nutrition_profile'] or {})
        sample_profiles.append({
            "user_id": r['user_id'],
            "full_name": r['full_name'],
            "username": r['username'],
            "user_gender": r['u_gender'],
            "intake_state": r['intake_state'],
            "order_state": r['order_state'],
            "payment_status": r['payment_status'],
            "duration_days": r['duration_days'],
            "amount": str(r['amount']),
            "currency": r['currency'],
            "country_region": r['country_region'],
            "past_workouts": r['past_workouts'],
            "answers": ans,
            "nutrition_profile": np,
            "completed_at": str(r['completed_at'])
        })
        
    with open("scratch/sample_intakes.json", "w", encoding="utf-8") as f:
        json.dump(sample_profiles, f, ensure_ascii=False, indent=2)
        
    print(f"\nWrote {len(sample_profiles)} sample profiles to scratch/sample_intakes.json")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(inspect_intakes())

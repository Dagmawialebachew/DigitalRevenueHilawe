with open("scheduler/retarget_hot_unpaid_leads.py", "r", encoding="utf-8") as f:
    code = f.read()

old_name = 'first_name = full_name.strip().split()[0].capitalize() if full_name else ""'
new_name = 'import html\n    first_name = html.escape(full_name.strip().split()[0].capitalize()) if full_name else ""'

code = code.replace(old_name, new_name)

old_launch_start = """async def run_launch(db: Database, bot: Bot):
    leads = await get_hot_leads(db)
    total = len(leads)
    print(f"🚀 LAUNCHING HOT LEADS RECOVERY BROADCAST to {total} users...")"""

new_launch_start = """async def run_launch(db: Database, bot: Bot):
    leads = await get_hot_leads(db)
    total = len(leads)
    print(f"🚀 LAUNCHING HOT LEADS RECOVERY BROADCAST to {total} users...")

    # Clear any old deal prices to lock in strictly 949 ETB full price
    await db.execute(\"\"\"
        UPDATE users
        SET deal_price = NULL, deal_expires_at = NULL
        WHERE onboarding_completed = TRUE 
          AND (has_paid = FALSE OR has_paid IS NULL)
          AND created_at >= NOW() - INTERVAL '7 days';
    \"\"\")
    logger.info("Cleared old deals for hot leads cohort. Enforcing full price 949 ETB.")"""

code = code.replace(old_launch_start, new_launch_start)

old_exc = """            except Exception as e:
                failed += 1
                logger.error(f"Error sending to {uid}: {e}")"""

new_exc = """            except Exception as e:
                try:
                    import re
                    clean_text = re.sub('<[^<]+?>', '', text)
                    msg = await bot.send_message(chat_id=uid, text=clean_text, reply_markup=kb, parse_mode=None)
                    sent += 1
                    await db.execute(
                        "UPDATE users SET last_broadcast_msg_id = $1, matched_product_id = $2 WHERE telegram_id = $3",
                        msg.message_id, u.get("product_id") or get_fallback_product_id(u.get("language", "AM"), u.get("gender", "MALE"), u.get("level", "BEGINNER"), u.get("frequency", 3)), uid
                    )
                except Exception as inner_e:
                    failed += 1
                    logger.error(f"Error sending to {uid}: {e} (fallback error: {inner_e})")"""

code = code.replace(old_exc, new_exc)

with open("scheduler/retarget_hot_unpaid_leads.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated scheduler/retarget_hot_unpaid_leads.py successfully!")

"""Interactive Kirana Store CLI Test Console.

Allows shopkeeper testing and demo walkthroughs directly in the terminal
without requiring Telegram, testing the agent loop, tool execution, database
state, and PDF/PPTX generation in real time.
"""

import asyncio
import sys
from app.config import settings
from app.core.db import get_db_session, init_db
from app.scripts.seed import seed_database
from app.agent.agent import agent
from app.telegram.formatting import format_bill_receipt, format_daily_close_message
from app.billing import service as billing_service
from app.preferences import service as pref_service

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


DEMO_PROMPTS = [
    "1. Stock Query: 'how much Maggi is left?'",
    "2. Receive Stock: '50 packets of Maggi came in, cost ₹12, MRP ₹14'",
    "3. Cut Draft Bill: 'make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, UPI'",
    "4. Mid-Build Edit: 'drop the butter, make it 6 Maggi'",
    "5. Confirm Bill: 'confirm and finalize the bill'",
    "6. PDF Invoice: 'send me that bill as a PDF invoice'",
    "7. Khata Credit: 'put ₹500 on Ramesh\\'s credit'",
    "8. Khata Payment: 'Ramesh paid ₹300'",
    "9. Daily Close: 'close the day'",
    "10. Analysis Deck: 'make this week\\'s sales analysis deck'",
    "11. Preference Memory: 'always assume UPI unless I say cash'",
    "12. Reset Memory: '/new'",
]


async def run_cli():
    print("=" * 65)
    print("🏪 SUPERMARKET OPS AGENT — INTERACTIVE TEST CONSOLE")
    print(f"📍 Shop: {settings.DEFAULT_SHOP_NAME}")
    print(f"🧾 GSTIN: {settings.DEFAULT_SHOP_GSTIN}")
    print("=" * 65)

    print("\n🌱 Initializing & Seeding Database...")
    await init_db()
    await seed_database()

    chat_id = "manual_cli_session"

    print("\n" + "=" * 65)
    print("💡 SUGGESTED DEMO COMMANDS:")
    for p in DEMO_PROMPTS:
        print(f"   {p}")
    print("=" * 65)
    print("\nType your message below (or 'exit' / 'quit' to end):\n")

    while True:
        try:
            user_input = input("👤 Shopkeeper > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit"]:
            print("👋 Exiting Supermarket Ops Agent CLI.")
            break

        if user_input == "/new":
            agent.reset_conversation(chat_id)
            print("\n🤖 Agent > 🔄 Conversation memory reset. Database state & preferences preserved.\n")
            continue

        async with get_db_session() as session:
            print("\n⏳ Agent is thinking and executing tools...")
            response = await agent.process_message(
                chat_id=chat_id,
                user_message=user_input,
                session=session,
            )
            await session.commit()

            print(f"\n🤖 Agent > {response.text}\n")

            if response.artifacts:
                for art in response.artifacts:
                    print(f"   📁 [Generated {art['type'].upper()} Artifact]: {art['path']}")

            if response.active_bill_id and response.action_type == "bill_preview":
                print(f"   👉 [Simulated Inline Action]: Type 'confirm and finalize the bill' to confirm Bill #{response.active_bill_id}")
            print("-" * 65)


if __name__ == "__main__":
    asyncio.run(run_cli())

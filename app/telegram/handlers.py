"""Telegram Bot Handlers: Commands, Conversational Agent Loop, Inline Callbacks, and Idempotency."""

import logging
from pathlib import Path
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from app.core.db import get_db_session
from app.core.idempotency import is_update_processed, mark_update_processed
from app.core.errors import BillAlreadyFinalizedError, InsufficientStockError
from app.agent.agent import agent
from app.preferences import service as pref_service
from app.billing import service as billing_service
from app.documents.invoice_pdf import generate_invoice_pdf
from app.telegram.formatting import (
    format_bill_receipt,
    get_bill_preview_keyboard,
    get_bill_finalized_keyboard,
)

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command with a branded introduction and example intents."""
    if not update.effective_chat or not update.message:
        return

    async with get_db_session() as session:
        prefs = await pref_service.get_all_preferences(session)
        shop_name = prefs.get("shop_name", "Maa Durga Kirana Store")

    text = (
        f"🙏 *Namaste! Welcome to {shop_name} Ops Agent.*\n\n"
        f"I am your store AI manager. Tell me what you need in plain English — "
        f"no forms, no complicated menus.\n\n"
        f"💡 *Example things you can say:*\n"
        f"• 📦 `50 packets of Maggi came in, cost ₹12, MRP ₹14`\n"
        f"• 🧾 `make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, UPI`\n"
        f"• ✏️ `drop the butter, make it 6 Maggi`\n"
        f"• 📦 `how much sugar is left?` or `what's running out?`\n"
        f"• 👤 `put ₹500 on Ramesh's credit` or `Ramesh paid ₹300`\n"
        f"• 📊 `today's sales?` or `close the day`\n"
        f"• 📄 `send me that bill as a PDF invoice`\n"
        f"• 📈 `make this week's sales analysis deck`\n"
        f"• ⚙️ `always assume UPI unless I say cash`\n\n"
        f"Type `/new` anytime to start a fresh topic while keeping your preferences intact!"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command with full capability overview."""
    if not update.message:
        return

    text = (
        f"📖 *Supermarket Ops Agent — Help & Commands*\n\n"
        f"• `/start` — Welcome message and quick start\n"
        f"• `/help` — View this reference guide\n"
        f"• `/new` — Clear current chat memory (store data & preferences persist!)\n\n"
        f"✨ *Key Capabilities:*\n"
        f"1. *Inventory*: Query stock, low-stock reorder warnings, receive new stock deliveries, add new SKUs with below-cost guards.\n"
        f"2. *Billing*: Multi-turn draft bills, grounded MRP prices, deterministic GST calculations, stock decrement with row-locks on confirmation.\n"
        f"3. *Khata Ledger*: Track customer credit debt, log cash/UPI payments, view running balances.\n"
        f"4. *Daily Close*: Full breakdown of revenue, tax collected, cash vs UPI share, top items.\n"
        f"5. *Documents*: Instant GST PDF invoices (ReportLab) & weekly analysis PowerPoint presentations (python-pptx).\n"
        f"6. *Preferences*: Custom defaults (default payment method, preferred brands, shop details) stored durably."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command: clears in-memory conversation while preserving DB data & preferences."""
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    agent.reset_conversation(chat_id)

    async with get_db_session() as session:
        prefs = await pref_service.get_all_preferences(session)
        shop_name = prefs.get("shop_name", "Maa Durga Kirana Store")

    text = (
        f"🔄 *Conversation reset for {shop_name}.*\n\n"
        f"Chat memory has been cleared. All inventory, khata balances, and store preferences remain permanently saved in the database.\n\n"
        f"How can I assist you now?"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main message handler: enforces idempotency, triggers agent control loop, and sends replies."""
    if not update.message or not update.message.text or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()
    update_id = update.update_id

    async with get_db_session() as session:
        # 1. Idempotency check
        if await is_update_processed(session, update_id):
            logger.warning(f"Skipping already processed update #{update_id}")
            return

        # Send typing action
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        # 2. Process through agent loop
        agent_response = await agent.process_message(
            chat_id=chat_id,
            user_message=user_text,
            session=session,
        )

        # 3. Determine keyboard
        reply_markup = None
        if agent_response.active_bill_id:
            if agent_response.action_type == "bill_preview":
                reply_markup = get_bill_preview_keyboard(agent_response.active_bill_id)
            elif agent_response.action_type == "bill_finalized":
                reply_markup = get_bill_finalized_keyboard(agent_response.active_bill_id)

        # 4. Send text response
        try:
            await update.message.reply_text(
                agent_response.text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
            )
        except Exception:
            # Fallback to plain text if Markdown parsing errors occur
            await update.message.reply_text(
                agent_response.text,
                reply_markup=reply_markup,
            )

        # 5. Dispatch generated artifacts (PDFs / PPTXs)
        for art in agent_response.artifacts:
            file_path = art["path"]
            if Path(file_path).exists():
                doc_caption = f"📄 {art['name']}"
                with open(file_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=Path(file_path).name,
                        caption=doc_caption,
                    )

        # 6. Mark update as processed
        await mark_update_processed(session, update_id, update_type="message")
        await session.commit()


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button clicks with two-layer idempotency protection."""
    query = update.callback_query
    if not query or not query.data or not update.effective_chat:
        return

    await query.answer()
    chat_id = update.effective_chat.id
    callback_data = query.data
    update_id = update.update_id

    async with get_db_session() as session:
        # Idempotency check on callback
        if await is_update_processed(session, update_id):
            logger.warning(f"Skipping already processed callback update #{update_id}")
            return

        if callback_data.startswith("finalize_bill_"):
            bill_id = int(callback_data.split("_")[-1])
            try:
                fin_res = await billing_service.finalize_bill(session, bill_id=bill_id)
                await session.commit()

                # Get bill preview for receipt
                bill_data = await billing_service.preview_bill(session, bill_id=bill_id)
                receipt_text = format_bill_receipt(bill_data)

                await query.edit_message_text(
                    receipt_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_bill_finalized_keyboard(bill_id),
                )
            except BillAlreadyFinalizedError:
                await query.edit_message_text(f"⚠️ Bill #{bill_id} is already finalized.")
            except InsufficientStockError as e:
                await query.edit_message_text(f"⚠️ Cannot finalize bill #{bill_id}: {str(e)}")
            except Exception as e:
                await query.edit_message_text(f"⚠️ Error finalizing bill #{bill_id}: {str(e)}")

        elif callback_data.startswith("cancel_bill_"):
            bill_id = int(callback_data.split("_")[-1])
            try:
                await billing_service.cancel_bill(session, bill_id=bill_id)
                await session.commit()
                await query.edit_message_text(f"❌ Bill #{bill_id} has been cancelled.")
            except Exception as e:
                await query.edit_message_text(f"⚠️ Error cancelling bill #{bill_id}: {str(e)}")

        elif callback_data.startswith("download_pdf_"):
            bill_id = int(callback_data.split("_")[-1])
            bill_data = await billing_service.preview_bill(session, bill_id=bill_id)
            shop_prefs = await pref_service.get_all_preferences(session)
            pdf_path = generate_invoice_pdf(bill_data=bill_data, shop_info=shop_prefs)

            if Path(pdf_path).exists():
                with open(pdf_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=Path(pdf_path).name,
                        caption=f"🧾 Official GST Tax Invoice for Bill #{bill_id:04d}",
                    )

        await mark_update_processed(session, update_id, update_type="callback_query")
        await session.commit()

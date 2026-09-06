"""Claude Agent Harness and Multi-Turn Control Loop."""

from dataclasses import dataclass, field
import json
import logging
from typing import Any
import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.agent.system_prompt import build_system_prompt
from app.agent.tool_registry import registry
from app.preferences import service as pref_service

# Ensure all tools are registered
import app.inventory.tools  # noqa: F401
import app.billing.tools    # noqa: F401
import app.khata.tools      # noqa: F401
import app.analytics.tools  # noqa: F401
import app.documents.tools  # noqa: F401
import app.preferences.tools  # noqa: F401

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    text: str
    artifacts: list[dict] = field(default_factory=list)  # list of {"type": "pdf"|"pptx", "path": str, "name": str}
    active_bill_id: int | None = None
    action_type: str | None = None  # "bill_preview", "bill_finalized", "report", etc.


class ClaudeAgent:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model or settings.ANTHROPIC_MODEL
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key) if self.api_key and not self.api_key.startswith("mock") else None
        self._conversations: dict[str, list[dict]] = {}

    def reset_conversation(self, chat_id: str | int) -> None:
        """Clear conversation memory for a chat session (used by /new command)."""
        cid = str(chat_id)
        if cid in self._conversations:
            del self._conversations[cid]
            logger.info(f"Reset conversation history for chat_id={cid}")

    async def process_message(
        self,
        chat_id: str | int,
        user_message: str,
        session: AsyncSession,
    ) -> AgentResponse:
        """
        Execute the agent control loop:
        Observe -> Reason -> Act (Call Tools) -> Feed Result Back -> Final Answer.
        """
        cid = str(chat_id)
        if cid not in self._conversations:
            self._conversations[cid] = []

        # 1. Fetch current owner preferences to inject into system prompt
        current_prefs = await pref_service.get_all_preferences(session)
        system_prompt = build_system_prompt(current_prefs)

        # 2. Append user message to history
        self._conversations[cid].append({
            "role": "user",
            "content": user_message,
        })

        artifacts_collected: list[dict] = []
        active_bill_id: int | None = None
        action_type: str | None = None

        # Check if live Anthropic client is available
        if self.client is None or not self.api_key or self.api_key.startswith("mock"):
            # Fallback grounded parser when testing without active Anthropic API key
            return await self._execute_grounded_fallback(
                user_message=user_message,
                session=session,
                artifacts_collected=artifacts_collected,
            )

        # 3. Multi-turn Tool Calling Loop
        tools = registry.get_anthropic_tools()
        max_iterations = 10
        iteration = 0

        final_response_text = ""

        while iteration < max_iterations:
            iteration += 1

            try:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    system=system_prompt,
                    messages=self._conversations[cid],
                    tools=tools,
                )
            except Exception as e:
                logger.error(f"Anthropic API call failed: {e}", exc_info=True)
                return AgentResponse(text=f"⚠️ LLM Error: {str(e)}")

            # Process response content blocks
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            # Append assistant turn to history
            self._conversations[cid].append({
                "role": "assistant",
                "content": response.content,
            })

            if text_blocks:
                final_response_text = "\n".join(b.text for b in text_blocks)

            if not tool_use_blocks or response.stop_reason != "tool_use":
                # Control loop finished reasoning
                break

            # Execute tool calls
            tool_results = []
            for tb in tool_use_blocks:
                tool_name = tb.name
                tool_input = tb.input
                logger.info(f"Agent calling tool '{tool_name}' with args: {tool_input}")

                result = await registry.execute(
                    name=tool_name,
                    session=session,
                    arguments=tool_input,
                )

                # Track artifacts or bill IDs if returned by tool
                if isinstance(result, dict):
                    if "file_path" in result:
                        ftype = "pdf" if result["file_path"].endswith(".pdf") else "pptx"
                        artifacts_collected.append({
                            "type": ftype,
                            "path": result["file_path"],
                            "name": result.get("file_name", "document"),
                        })
                    if "bill_id" in result:
                        active_bill_id = result["bill_id"]
                        action_type = "bill_preview" if tool_name in ["start_or_update_bill", "preview_bill"] else "bill_finalized"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tb.id,
                    "content": json.dumps(result),
                })

            # Feed tool results back into conversation
            self._conversations[cid].append({
                "role": "user",
                "content": tool_results,
            })

        return AgentResponse(
            text=final_response_text or "Processed request.",
            artifacts=artifacts_collected,
            active_bill_id=active_bill_id,
            action_type=action_type,
        )

    def _parse_items_from_text(self, msg: str) -> list[dict]:
        """Extract product names and quantities from natural language text."""
        import re
        items = []
        
        # 1. Sugar
        if "sugar" in msg:
            m1 = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|packets?|pk)?(?:\s+of)?\s*sugar", msg)
            m2 = re.search(r"sugar\s*(\d+(?:\.\d+)?)\s*(?:kg|packets?|pk)?", msg)
            q = 1.0
            if m1 and m1.group(1): q = float(m1.group(1))
            elif m2 and m2.group(1): q = float(m2.group(1))
            items.append({"product_name": "Loose Sugar", "quantity": q})

        # 2. Atta
        if "atta" in msg:
            m1 = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|packets?|pk)?(?:\s+of)?\s*(?:aashirvaad\s*)?atta", msg)
            m2 = re.search(r"atta\s*(\d+(?:\.\d+)?)\s*(?:kg|packets?|pk)?", msg)
            q = 1.0
            if m1 and m1.group(1): q = float(m1.group(1))
            elif m2 and m2.group(1): q = float(m2.group(1))
            
            if "loose" in msg or ("kg" in msg and "aashirvaad" not in msg and q > 10):
                items.append({"product_name": "Loose Wheat Atta", "quantity": q})
            else:
                items.append({"product_name": "Aashirvaad Atta 5kg", "quantity": q})

        # 3. Maggi
        if "maggi" in msg or "noodle" in msg:
            m1 = re.search(r"(\d+(?:\.\d+)?)\s*(?:packets?|pk)?(?:\s+of)?\s*maggi", msg)
            m2 = re.search(r"maggi\s*(\d+(?:\.\d+)?)\s*(?:packets?|pk)?", msg)
            q = 1.0
            if m1 and m1.group(1): q = float(m1.group(1))
            elif m2 and m2.group(1): q = float(m2.group(1))
            items.append({"product_name": "Maggi 70g", "quantity": q})

        # 4. Butter
        if "butter" in msg or ("amul" in msg and "atta" not in msg):
            m1 = re.search(r"(\d+(?:\.\d+)?)\s*(?:packets?|pk)?(?:\s+of)?\s*(?:amul\s*)?butter", msg)
            m2 = re.search(r"butter\s*(\d+(?:\.\d+)?)\s*(?:packets?|pk)?", msg)
            q = 1.0
            if m1 and m1.group(1): q = float(m1.group(1))
            elif m2 and m2.group(1): q = float(m2.group(1))
            items.append({"product_name": "Amul Butter 100g", "quantity": q})

        # 5. Salt
        if "salt" in msg:
            m1 = re.search(r"(\d+(?:\.\d+)?)\s*(?:packets?|pk)?(?:\s+of)?\s*(?:tata\s*)?salt", msg)
            m2 = re.search(r"salt\s*(\d+(?:\.\d+)?)\s*(?:packets?|pk)?", msg)
            q = 1.0
            if m1 and m1.group(1): q = float(m1.group(1))
            elif m2 and m2.group(1): q = float(m2.group(1))
            items.append({"product_name": "Tata Salt 1kg", "quantity": q})

        # 6. Oil
        if "oil" in msg:
            m1 = re.search(r"(\d+(?:\.\d+)?)\s*(?:pouches?|packets?|litres?|l)?(?:\s+of)?\s*(?:fortune\s*)?oil", msg)
            m2 = re.search(r"oil\s*(\d+(?:\.\d+)?)\s*(?:pouches?|packets?|litres?|l)?", msg)
            q = 1.0
            if m1 and m1.group(1): q = float(m1.group(1))
            elif m2 and m2.group(1): q = float(m2.group(1))
            items.append({"product_name": "Fortune Sunflower Oil 1L", "quantity": q})

        # 7. Rice
        if "rice" in msg:
            m1 = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg)?(?:\s+of)?\s*(?:basmati\s*)?rice", msg)
            m2 = re.search(r"rice\s*(\d+(?:\.\d+)?)\s*(?:kg)?", msg)
            q = 1.0
            if m1 and m1.group(1): q = float(m1.group(1))
            elif m2 and m2.group(1): q = float(m2.group(1))
            items.append({"product_name": "Loose Basmati Rice", "quantity": q})

        # 8. Dal
        if "dal" in msg:
            m1 = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg)?(?:\s+of)?\s*(?:toor\s*)?dal", msg)
            m2 = re.search(r"dal\s*(\d+(?:\.\d+)?)\s*(?:kg)?", msg)
            q = 1.0
            if m1 and m1.group(1): q = float(m1.group(1))
            elif m2 and m2.group(1): q = float(m2.group(1))
            items.append({"product_name": "Loose Toor Dal", "quantity": q})

        # 9. Surf / Detergent
        if "surf" in msg:
            m1 = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|packets?|pk)?(?:\s+of)?\s*surf", msg)
            m2 = re.search(r"surf\s*(\d+(?:\.\d+)?)\s*(?:kg|packets?|pk)?", msg)
            q = 1.0
            if m1 and m1.group(1): q = float(m1.group(1))
            elif m2 and m2.group(1): q = float(m2.group(1))
            items.append({"product_name": "Surf Excel Quick Wash 1kg", "quantity": q})

        # 10. Parle-G
        if "parle" in msg or "biscuit" in msg:
            m1 = re.search(r"(\d+(?:\.\d+)?)\s*(?:packets?|pk)?(?:\s+of)?\s*parle", msg)
            q = float(m1.group(1)) if m1 and m1.group(1) else 1.0
            items.append({"product_name": "Parle-G 250g", "quantity": q})

        return items

    async def _execute_grounded_fallback(
        self,
        user_message: str,
        session: AsyncSession,
        artifacts_collected: list[dict],
    ) -> AgentResponse:
        """Grounded execution engine that resolves shopkeeper intents to database tools."""
        import re
        from app.telegram.formatting import format_bill_receipt, format_daily_close_message
        msg = user_message.strip().lower()

        # 1. Add New Product / SKU ("new item: Amul Butter 100g, GST 12%, MRP ₹62")
        if ("new item" in msg or "new product" in msg or "add product" in msg) and any(k in msg for k in ["mrp", "gst", "%", "cost", "rs", "₹"]):
            mrp_match = re.search(r"mrp\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)", msg)
            gst_match = re.search(r"gst\s*(\d+(?:\.\d+)?)\s*%", msg)
            cost_match = re.search(r"cost\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)", msg)

            mrp = float(mrp_match.group(1)) if mrp_match else 60.0
            gst_pct = float(gst_match.group(1)) if gst_match else 0.0
            gst_rate = gst_pct / 100.0
            cost = float(cost_match.group(1)) if cost_match else round(mrp * 0.85, 2)
            selling = mrp

            clean_name_text = re.sub(r"^(?:new\s+item|new\s+product|add\s+product|add\s+item)[:\s]*", "", user_message.strip(), flags=re.IGNORECASE)
            clean_name = clean_name_text.split(",")[0].strip()
            if not clean_name:
                clean_name = "Amul Butter 100g"

            unit = "packet"
            if "kg" in clean_name.lower(): unit = "kg"
            elif "litre" in clean_name.lower() or "1l" in clean_name.lower(): unit = "pouch"
            elif "g" in clean_name.lower(): unit = "packet"

            res = await registry.execute(
                "add_product",
                session,
                {
                    "name": clean_name,
                    "unit": unit,
                    "cost_price": cost,
                    "selling_price": selling,
                    "mrp": mrp,
                    "gst_rate": gst_rate,
                    "hsn_code": "0405" if "butter" in clean_name.lower() else "0000",
                    "initial_stock": 20.0,
                    "reorder_level": 5.0,
                },
            )
            if "error" in res:
                if "already exists" in res["error"].lower():
                    rcv = await registry.execute(
                        "receive_stock",
                        session,
                        {"product_name": clean_name, "quantity": 10.0, "cost_price": cost, "mrp": mrp, "selling_price": selling},
                    )
                    return AgentResponse(text=f"📦 *Product Updated*\n\n{rcv.get('message', 'Updated product details.')}")
                return AgentResponse(text=f"⚠️ {res['error']}")
            
            return AgentResponse(
                text=f"📦 *New Product Added Successfully*\n\n"
                     f"• SKU: *{res['name']}*\n"
                     f"• MRP: *₹{res['mrp']:.2f}* (Selling: ₹{res['selling_price']:.2f})\n"
                     f"• GST Slab: *{int(res['gst_rate']*100)}%*\n"
                     f"• Initial Stock: *{res['stock_qty']} {res['unit']}*"
            )

        # 2. Ambiguity Handling for bare product names ("add atta", "atta", "need atta")
        if msg.strip() in ["add atta", "atta", "need atta", "get atta", "butter", "oil", "sugar", "rice", "dal"]:
            keyword = msg.replace("add", "").replace("need", "").replace("get", "").strip()
            stock_res = await registry.execute("check_stock", session, {"query": keyword})
            products = stock_res.get("products", [])
            
            if len(products) > 1:
                options = "\n".join([f"• *{p['name']}* — ₹{p['selling_price']:.0f} ({p['stock_qty']} {p['unit']} left)" for p in products])
                return AgentResponse(
                    text=f"🤔 *Which one would you like to select?*\n\nFound {len(products)} matching items for '{keyword}':\n{options}\n\nPlease specify the exact product and quantity (e.g. `1 Aashirvaad atta 5kg` or `2kg loose atta`)."
                )
            elif len(products) == 1:
                p = products[0]
                return AgentResponse(
                    text=f"📦 *{p['name']}*: ₹{p['selling_price']:.2f} (Stock: {p['stock_qty']} {p['unit']}, GST {int(p['gst_rate']*100)}%). How many would you like to bill or receive?"
                )

        # 3. Receive Stock ("50 packets of Maggi came in, cost ₹12, MRP ₹14")
        if "came in" in msg or "received" in msg or "delivery" in msg or "stock in" in msg:
            qty_match = re.search(r"(\d+(?:\.\d+)?)", msg)
            cost_match = re.search(r"cost\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)", msg)
            mrp_match = re.search(r"mrp\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)", msg)
            
            p_name = "Maggi 70g"
            if "atta" in msg:
                p_name = "Loose Wheat Atta" if "loose" in msg else "Aashirvaad Atta 5kg"
            elif "salt" in msg: p_name = "Tata Salt 1kg"
            elif "butter" in msg: p_name = "Amul Butter 100g"
            elif "oil" in msg: p_name = "Fortune Sunflower Oil 1L"
            elif "sugar" in msg: p_name = "Loose Sugar"
            elif "surf" in msg: p_name = "Surf Excel Quick Wash 1kg"

            qty = float(qty_match.group(1)) if qty_match else 50.0
            cost = float(cost_match.group(1)) if cost_match else None
            mrp = float(mrp_match.group(1)) if mrp_match else None

            res = await registry.execute(
                "receive_stock",
                session,
                {"product_name": p_name, "quantity": qty, "cost_price": cost, "mrp": mrp},
            )
            if "error" in res:
                return AgentResponse(text=f"⚠️ {res['error']}")
            return AgentResponse(text=f"📦 *Stock Updated Successfully*\n\n{res['message']}\n• Current Stock: *{res['current_stock']} {res['unit']}*")

        # 4. Stock Query & Low Stock Warning
        if "running out" in msg or "low stock" in msg or "reorder" in msg:
            res = await registry.execute("get_low_stock", session, {})
            items = res.get("low_stock_items", [])
            if not items:
                return AgentResponse(text="📦 *Stock Health Status*\n\n✅ All SKUs are currently well above reorder thresholds.")
            lines = ["⚠️ *Low Stock Warning — Items to Reorder:*", "```"]
            for itm in items:
                lines.append(f"• {itm['name']:<24} {itm['stock_qty']} left (reorder at {itm['reorder_level']})")
            lines.append("```")
            return AgentResponse(text="\n".join(lines))

        if "how much" in msg or "left" in msg or ("stock" in msg and "receive" not in msg and "came in" not in msg):
            query = None
            if "sugar" in msg: query = "Sugar"
            elif "maggi" in msg: query = "Maggi"
            elif "atta" in msg: query = "Atta"
            elif "butter" in msg: query = "Butter"
            elif "oil" in msg: query = "Oil"
            elif "salt" in msg: query = "Salt"
            elif "rice" in msg: query = "Rice"
            elif "dal" in msg: query = "Dal"

            res = await registry.execute("check_stock", session, {"query": query})
            if "error" in res:
                return AgentResponse(text=f"⚠️ {res['error']}")
            
            prods = res.get("products", [])
            if not prods:
                return AgentResponse(text=f"📦 No products found matching '{query}'.")
            
            lines = [f"📦 *Inventory Check ({len(prods)} SKUs)*", "```"]
            for p in prods:
                lines.append(f"• {p['name']:<22} {p['stock_qty']:>4} {p['unit']:<6} | ₹{p['selling_price']:.0f} (GST {int(p['gst_rate']*100)}%)")
            lines.append("```")
            return AgentResponse(text="\n".join(lines))

        # 5. Bill Edit ("drop the butter, make it 6 Maggi")
        if "drop" in msg or "remove" in msg or "make it" in msg or "change" in msg:
            items = []
            if "butter" in msg and ("drop" in msg or "remove" in msg or "cancel" in msg):
                items.append({"product_name": "Amul Butter 100g", "quantity": 0.0})
            if "sugar" in msg and ("drop" in msg or "remove" in msg):
                items.append({"product_name": "Loose Sugar", "quantity": 0.0})
            if "maggi" in msg:
                m = re.search(r"(\d+)\s*(?:packet|pk)?\s*maggi", msg)
                if m:
                    items.append({"product_name": "Maggi 70g", "quantity": float(m.group(1))})
            
            res = await registry.execute("start_or_update_bill", session, {"items": items})
            if "error" in res:
                return AgentResponse(text=f"⚠️ {res['error']}")
            
            receipt = format_bill_receipt(res)
            return AgentResponse(text=f"✏️ *Bill Updated*\n\n{receipt}", active_bill_id=res["bill_id"], action_type="bill_preview")

        # 6. Bill Creation / Adding Items (Universal Extractor)
        # Handles: "add sugar 1kg", "make a bill: 2kg sugar, 1 atta", "1kg sugar", "add 4 maggi", etc.
        extracted_items = self._parse_items_from_text(msg)
        if extracted_items or ("make a bill" in msg or "create a bill" in msg or "new bill" in msg or "cut a bill" in msg):
            if not extracted_items:
                return AgentResponse(
                    text="🧾 *New Bill Draft Started*\n\nWhich items would you like to add to this bill?\nExample: `2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, UPI`"
                )

            pay_mode = "Cash" if "cash" in msg else ("Card" if "card" in msg else ("Khata" if "khata" in msg else "UPI"))
            
            res = await registry.execute("start_or_update_bill", session, {"items": extracted_items, "payment_method": pay_mode})
            if "error" in res:
                return AgentResponse(text=f"⚠️ {res['error']}")
            
            receipt = format_bill_receipt(res)
            warning_text = ""
            if res.get("warnings"):
                warning_text = "\n\n" + "\n".join(res["warnings"]) + "\n*(Item added to draft, but you must adjust quantity before finalizing)*"

            action_title = "🧾 *Item Added to Bill Draft*" if ("add" in msg or len(extracted_items) == 1) else ""
            full_text = f"{action_title}\n\n{receipt}{warning_text}" if action_title else f"{receipt}{warning_text}"

            return AgentResponse(text=full_text, active_bill_id=res["bill_id"], action_type="bill_preview")

        # 8. Finalize Bill
        if msg in ["yes", "confirm", "finalize", "ok", "done", "close bill"] or "confirm" in msg or "finalize" in msg:
            res = await registry.execute("finalize_bill", session, {})
            if "error" in res:
                return AgentResponse(text=f"⚠️ {res['error']}")
            
            prev = await registry.execute("preview_bill", session, {"bill_id": res.get("bill_id")})
            receipt = format_bill_receipt(prev)
            return AgentResponse(text=f"✅ *Bill Finalized & Stock Decremented*\n\n{receipt}", active_bill_id=res.get("bill_id"), action_type="bill_finalized")

        # 9. PDF Invoice Generation ("first invoice" vs "previous invoice" vs "bill #2")
        if "pdf" in msg or "invoice" in msg:
            order = "last"
            bill_id = None

            b_match = re.search(r"bill\s*#?\s*(\d+)", msg)
            if b_match:
                bill_id = int(b_match.group(1))
                order = "specific"
            elif "first" in msg or "earliest" in msg or "oldest" in msg:
                order = "first"
            elif "previous" in msg or "last" in msg or "latest" in msg or "recent" in msg:
                order = "last"

            res = await registry.execute("generate_invoice_pdf", session, {"bill_id": bill_id, "order": order})
            if "error" in res:
                return AgentResponse(text=f"⚠️ {res['error']}")
            
            artifacts_collected.append({
                "type": "pdf",
                "path": res["file_path"],
                "name": res["file_name"],
            })
            b_id = res.get("bill_id", 1)
            b_date = res.get("created_at", "")
            return AgentResponse(
                text=f"📄 *GST Tax Invoice Generated*\n\nHere is **Bill #{b_id:04d}** (dated {b_date}) for ₹{res.get('total', 0.0):.2f}. The official PDF invoice is attached below.",
                artifacts=artifacts_collected,
            )

        # 10. PPTX Presentation Deck
        if "deck" in msg or "pptx" in msg or "powerpoint" in msg or "presentation" in msg or "weekly analysis" in msg:
            res = await registry.execute("generate_analysis_deck", session, {"days": 7})
            if "error" in res:
                return AgentResponse(text=f"⚠️ {res['error']}")
            
            artifacts_collected.append({
                "type": "pptx",
                "path": res["file_path"],
                "name": res["file_name"],
            })
            return AgentResponse(
                text=f"📊 *Weekly Sales Analysis Deck Ready*\n\nPowerPoint presentation with embedded sales trend charts, top SKU velocity, and payment distribution has been generated and sent below.",
                artifacts=artifacts_collected,
            )

        # 11. Khata (Credit / Payment / Balance)
        if "credit" in msg or "khata" in msg or "paid" in msg or "balance" in msg:
            if "paid" in msg or "settle" in msg:
                m_amt = re.search(r"(\d+(?:\.\d+)?)", msg)
                amt = float(m_amt.group(1)) if m_amt else 300.0
                cust = "Ramesh Kumar" if "ramesh" in msg else ("Priya Sharma" if "priya" in msg else "Suresh Patel")
                res = await registry.execute("record_payment", session, {"customer_name": cust, "amount": amt})
                if "error" in res:
                    return AgentResponse(text=f"⚠️ {res['error']}")
                return AgentResponse(text=f"👤 *Khata Payment Logged*\n\n{res['message']}\n• Current Balance Owed: *₹{res['current_balance']:.2f}*")
            
            if "put" in msg or "add" in msg or "on credit" in msg or "udhar" in msg:
                m_amt = re.search(r"(\d+(?:\.\d+)?)", msg)
                amt = float(m_amt.group(1)) if m_amt else 500.0
                cust = "Ramesh Kumar" if "ramesh" in msg else ("Priya Sharma" if "priya" in msg else "Suresh Patel")
                res = await registry.execute("add_credit", session, {"customer_name": cust, "amount": amt, "note": "Store purchase credit"})
                if "error" in res:
                    return AgentResponse(text=f"⚠️ {res['error']}")
                return AgentResponse(text=f"👤 *Khata Credit Added*\n\n{res['message']}\n• Total Balance Owed: *₹{res['current_balance']:.2f}*")

            cust = "Ramesh Kumar" if "ramesh" in msg else ("Priya Sharma" if "priya" in msg else ("Suresh Patel" if "suresh" in msg else None))
            res = await registry.execute("get_khata_balance", session, {"customer_name": cust})
            if "error" in res:
                return AgentResponse(text=f"⚠️ {res['error']}")
            
            if cust:
                return AgentResponse(text=f"👤 *Khata Balance for {res['customer_name']}*\n\n• Outstanding Balance: *₹{res['current_balance']:.2f}*")
            else:
                lines = [f"👤 *Store Khata Summary ({res['active_accounts']} Accounts)*", "```"]
                lines.append(f"{'Customer':<20} {'Balance':>12}")
                lines.append("-" * 34)
                for c in res.get("customers", []):
                    bal_str = f"₹{c['balance']:.2f}"
                    lines.append(f"{c['customer_name']:<20} {bal_str:>12}")
                lines.append("-" * 34)
                tot_str = f"₹{res['total_receivable']:.2f}"
                lines.append(f"{'TOTAL RECEIVABLE:':<20} {tot_str:>12}")
                lines.append("```")
                return AgentResponse(text="\n".join(lines))

        # 12. Daily Close
        if "close" in msg or "today's sales" in msg or "daily close" in msg or "day summary" in msg:
            res = await registry.execute("get_daily_close", session, {})
            if "error" in res:
                return AgentResponse(text=f"⚠️ {res['error']}")
            return AgentResponse(text=format_daily_close_message(res))

        # 13. Preferences
        if "assume" in msg or "preference" in msg or "default" in msg:
            if "upi" in msg:
                await registry.execute("set_preference", session, {"key": "default_payment_method", "value": "UPI"})
                return AgentResponse(text="⚙️ *Preference Saved*\n\nI will now default to *UPI* for all bills unless specified otherwise (persists across chats).")
            elif "cash" in msg:
                await registry.execute("set_preference", session, {"key": "default_payment_method", "value": "Cash"})
                return AgentResponse(text="⚙️ *Preference Saved*\n\nI will now default to *Cash* for all bills unless specified otherwise (persists across chats).")

        # 14. Dynamic Product Search Fallback
        search_res = await registry.execute("check_stock", session, {"query": user_message.strip()})
        prods = search_res.get("products", [])
        if prods:
            lines = [f"📦 *Found {len(prods)} matching SKU(s) in catalog:*", "```"]
            for p in prods:
                lines.append(f"• {p['name']:<22} {p['stock_qty']:>4} {p['unit']:<6} | ₹{p['selling_price']:.0f}")
            lines.append("```")
            return AgentResponse(text="\n".join(lines))

        # Direct clarifying response from agent
        return AgentResponse(
            text=f"❓ Could you please clarify what you'd like to do with '{user_message}'? (e.g. check stock, add a new SKU, or create a bill)."
        )


# Global Agent Singleton
agent = ClaudeAgent()


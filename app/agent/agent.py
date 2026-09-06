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
        if self.client is None:
            # Fallback mock agent response for offline / unit tests
            response_text = await self._mock_agent_turn(
                user_message=user_message,
                session=session,
                artifacts_collected=artifacts_collected,
            )
            return AgentResponse(
                text=response_text,
                artifacts=artifacts_collected,
                active_bill_id=active_bill_id,
                action_type=action_type,
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

    async def _mock_agent_turn(
        self,
        user_message: str,
        session: AsyncSession,
        artifacts_collected: list[dict],
    ) -> str:
        """Deterministic mock fallback when testing without active Anthropic API key."""
        msg = user_message.lower()

        if "stock" in msg or "left" in msg:
            res = await registry.execute("check_stock", session, {"query": None})
            return f"📦 Stock check complete: Found {res.get('count', 0)} products in database."
        elif "bill" in msg and ("make" in msg or "cut" in msg or "start" in msg):
            res = await registry.execute(
                "start_or_update_bill",
                session,
                {"items": [{"product_name": "Loose Sugar", "quantity": 2.0}]},
            )
            return f"🧾 Draft Bill #{res.get('bill_id')} created with total ₹{res.get('total', 0.0):.2f}."
        elif "credit" in msg or "khata" in msg:
            res = await registry.execute("get_khata_balance", session, {})
            return f"👤 Khata summary: {res.get('message', 'Checked balances.')}"
        elif "close" in msg or "sales" in msg:
            res = await registry.execute("get_daily_close", session, {})
            return f"📊 {res.get('message', 'Daily close calculated.')}"
        else:
            return f"🤖 Agent acknowledged: '{user_message}'."


# Global Agent Singleton
agent = ClaudeAgent()

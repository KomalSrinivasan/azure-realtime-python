"""Autonomous tool-calling agent."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from ..client import RealtimeClient, RealtimeSession
from ..types import (
    AuthConfig,
    ClientEvent,
    SessionConfig,
    ToolDefinition,
    ToolRegistration,
    ServerEvent,
)


@dataclass
class AgentStep:
    id: str
    type: str  # "message" | "tool_call" | "tool_result" | "error"
    content: str
    tool_name: str | None = None
    tool_args: Any = None
    timestamp: float = 0.0


@dataclass
class AgentRunResult:
    response: str
    steps: list[AgentStep]
    success: bool
    error: str | None = None
    tool_call_count: int = 0


class ToolAgent:
    """Autonomous agent that handles multi-turn tool calling.

    Example:
        >>> agent = ToolAgent(
        ...     resource="my-resource",
        ...     deployment="gpt-4o-realtime-preview",
        ...     auth=ApiKeyAuth(api_key="..."),
        ...     instructions="You are a research assistant.",
        ...     max_tool_rounds=10,
        ... )
        >>>
        >>> agent.register_tool(ToolRegistration(
        ...     definition=ToolDefinition(name="search", description="Search the web", parameters={...}),
        ...     handler=search_handler,
        ... ))
        >>>
        >>> async with agent.connect() as session:
        ...     result = await agent.run(session, "Find latest WebRTC news")
        ...     print(result.response)
    """

    def __init__(
        self,
        resource: str,
        deployment: str,
        auth: AuthConfig | None = None,
        ephemeral_token: str | None = None,
        instructions: str | None = None,
        base_url: str | None = None,
        max_tool_rounds: int = 10,
    ) -> None:
        self.max_tool_rounds = max_tool_rounds
        self._tools: dict[str, ToolRegistration] = {}
        self._step_counter = 0

        tool_defs: list[ToolDefinition] = []
        session_config = SessionConfig(
            instructions=instructions,
            tools=tool_defs,
            tool_choice="auto",
        )

        self._client = RealtimeClient(
            resource=resource,
            deployment=deployment,
            auth=auth,
            base_url=base_url,
            session=session_config,
            ephemeral_token=ephemeral_token,
        )
        self._tool_defs = tool_defs

    def register_tool(self, registration: ToolRegistration) -> "ToolAgent":
        self._tools[registration.definition.name] = registration
        self._tool_defs.append(registration.definition)
        return self

    def connect(self) -> RealtimeClient:
        return self._client

    async def run(self, session: RealtimeSession, task: str) -> AgentRunResult:
        """Run the agent with a task. Returns when the AI gives a final answer."""
        steps: list[AgentStep] = []
        tool_call_count = 0
        final_response = ""

        # Send the task
        task_step = self._step("message", task)
        steps.append(task_step)
        session.send_text(task)

        for _round in range(self.max_tool_rounds):
            text, tool_calls = await self._wait_for_response(session)

            if text:
                final_response = text
                steps.append(self._step("message", text))

            if not tool_calls:
                break

            for tc in tool_calls:
                tool_call_count += 1
                call_step = self._step("tool_call", f"{tc['name']}({tc['arguments']})")
                call_step.tool_name = tc["name"]
                try:
                    call_step.tool_args = json.loads(tc["arguments"])
                except (json.JSONDecodeError, TypeError):
                    call_step.tool_args = tc["arguments"]
                steps.append(call_step)

                # Execute
                reg = self._tools.get(tc["name"])
                if not reg:
                    result = json.dumps({"error": f"Unknown tool: {tc['name']}"})
                else:
                    try:
                        args = json.loads(tc["arguments"])
                        r = reg.handler(args)
                        if asyncio.iscoroutine(r):
                            r = await r
                        result = r if isinstance(r, str) else json.dumps(r)
                    except Exception as e:
                        result = json.dumps({"error": str(e)})

                result_step = self._step("tool_result", result)
                result_step.tool_name = tc["name"]
                steps.append(result_step)

                # Send result back
                session.send(ClientEvent(type="conversation.item.create", data={
                    "item": {
                        "type": "function_call_output",
                        "call_id": tc["call_id"],
                        "output": result,
                    }
                }))

            # Request next response
            session.send(ClientEvent(type="response.create"))

        return AgentRunResult(
            response=final_response,
            steps=steps,
            success=True,
            tool_call_count=tool_call_count,
        )

    async def _wait_for_response(
        self, session: RealtimeSession
    ) -> tuple[str, list[dict[str, str]]]:
        text = ""
        tool_calls: list[dict[str, str]] = []

        async for event in session.event_stream():
            if event.type in {
                "response.text.delta", "response.output_text.delta",
                "response.audio_transcript.delta", "response.output_audio_transcript.delta",
            }:
                text += event.data.get("delta", "")
            elif event.type == "response.function_call_arguments.done":
                tool_calls.append({
                    "name": event.data.get("name", ""),
                    "arguments": event.data.get("arguments", ""),
                    "call_id": event.data.get("call_id", ""),
                })
            elif event.type == "response.done":
                return text, tool_calls

        return text, tool_calls

    def _step(self, type: str, content: str) -> AgentStep:
        self._step_counter += 1
        return AgentStep(
            id=f"step_{self._step_counter}",
            type=type,
            content=content,
            timestamp=time.time(),
        )

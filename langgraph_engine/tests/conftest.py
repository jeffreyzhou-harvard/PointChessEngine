"""Shared fixtures for langgraph_engine tests.

We deliberately do NOT call the real Claude API in tests. The
``FakeChatModel`` here is the cheapest possible thing that satisfies
LangGraph's ``create_react_agent`` contract: it returns a single
``AIMessage`` containing the JSON contract our parser expects. Tests
that need different agent behaviour can subclass and override
``next_response``.
"""

from __future__ import annotations

from typing import Any, Iterator

import pytest

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


_DEFAULT_JSON = (
    "Done.\n"
    "```json\n"
    "{"
    "\"assumptions\":[],"
    "\"decisions\":[],"
    "\"files_changed\":[],"
    "\"tests_added\":[],"
    "\"risks\":[],"
    "\"notes\":\"fake-llm response\""
    "}\n"
    "```"
)


class FakeChatModel(BaseChatModel):
    """A no-API stand-in for ``ChatAnthropic``.

    * ``responses``: queue of strings -- one per ``invoke``. When the
      queue empties we fall back to ``_DEFAULT_JSON``.
    * ``bind_tools`` returns ``self`` so the ReAct agent works.
    * Every response is wrapped in a single ``AIMessage`` with no tool
      calls; the ReAct loop therefore terminates immediately, which is
      what we want for unit tests.
    """

    responses: list[str] = []

    @property
    def _llm_type(self) -> str:  # pragma: no cover - LangChain plumbing
        return "fake"

    def next_response(self) -> str:
        if self.responses:
            return self.responses.pop(0)
        return _DEFAULT_JSON

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        text = self.next_response()
        msg = AIMessage(content=text)
        return ChatResult(generations=[ChatGeneration(message=msg)])

    # LangGraph's create_react_agent requires bind_tools to be present
    # on the chat model; a no-op binding is fine for tests because we
    # never emit tool_calls in the fake response.
    def bind_tools(self, tools: Any, **kwargs: Any) -> "FakeChatModel":  # noqa: D401
        return self


@pytest.fixture
def fake_llm() -> Iterator[FakeChatModel]:
    yield FakeChatModel()

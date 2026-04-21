"""Unit tests for the commands module"""
from unittest.mock import MagicMock, patch

import pytest

import autogpt.agent.agent_manager as agent_manager
from autogpt.app import execute_command, list_agents, start_agent


@pytest.mark.integration_test
def test_make_agent() -> None:
    """Test the make_agent command"""
    # Patch the v1 SDK path used by llm_utils._get_client().chat.completions.create
    with patch("autogpt.llm_utils._get_client") as mock_get_client:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Acknowledged"
        mock_get_client.return_value.chat.completions.create.return_value = mock_response
        start_agent("Test Agent", "chat", "Hello, how are you?", "gpt2")
        agents = list_agents()
        assert "List of agents:\n0: chat" == agents
        start_agent("Test Agent 2", "write", "Hello, how are you?", "gpt2")
        agents = list_agents()
        assert "List of agents:\n0: chat\n1: write" == agents

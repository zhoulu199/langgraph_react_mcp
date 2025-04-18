"""Utility & helper functions."""

import json
from typing import Dict, Any
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
# from react_agent.mcp_config import mcp_servers

_mcp_client = None
_mcp_tools = None

def get_message_text(msg: BaseMessage) -> str:
    """Get the text content of a message."""
    content = msg.content
    if isinstance(content, str):
        return content
    elif isinstance(content, dict):
        return content.get("text", "")
    else:
        txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
        return "".join(txts).strip()


def load_chat_model(fully_specified_name: str) -> BaseChatModel:
    """Load a chat model from a fully specified name.

    Args:
        fully_specified_name (str): String in the format 'provider/model'.
    """
    provider, model = fully_specified_name.split("/", maxsplit=1)
    return init_chat_model(model, model_provider=provider)
    # return init_chat_model(f"{provider}:{model}", temperature=0)


def get_mcp_servers(config_path: str = 'src/react_agent/mcp_config.json') -> Dict[str, Dict[str, Any]]:
    """
    Load and return the mcpServers configuration from a JSON file.
    
    Args:
        config_path: Path to the JSON configuration file (default: 'mcp_config.json')
    
    Returns:
        Dictionary containing server configurations with server names as keys
        
    Raises:
        FileNotFoundError: If the config file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
        KeyError: If 'mcpServers' key is missing in the config
    """
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        return config['mcpServers']
        
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found at {config_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in {config_path}")
    except KeyError:
        raise KeyError(f"'mcpServers' key not found in {config_path}")


async def initialize_mcp_client():
    """Initialize the MCP client and keep it open.
    
    Returns:
        List of retrieved tools
    """
    global _mcp_client, _mcp_tools
    
    if _mcp_client is None:
        # Create MCP client instance
        _mcp_client = MultiServerMCPClient(get_mcp_servers())
        # Enter context manager to keep client open
        await _mcp_client.__aenter__()
        # Retrieve available tools
        _mcp_tools = _mcp_client.get_tools()
    
    return _mcp_tools

async def get_mcp_tools():
    """Get MCP tools, initializing the client if not already done.
    
    Returns:
        List of tools
    """
    global _mcp_tools
    
    if _mcp_tools is None:
        _mcp_tools = await initialize_mcp_client()
    
    return _mcp_tools

async def cleanup_mcp_client():

    global _mcp_client
    
    if _mcp_client is not None:
        try:
            await _mcp_client.__aexit__(None, None, None)
            _mcp_client = None
            _mcp_tools = None
        except Exception as e:
            print(f"Error cleaning up MCP client: {e}")
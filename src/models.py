"""Model configuration — selects LLM provider and model per pipeline node.

Configure via environment variables:
    INTAKE_MODEL_PROVIDER=groq          (anthropic|deepseek|groq|together)
    INTAKE_MODEL_ID=llama-3.3-70b-versatile
    ELIGIBILITY_MODEL_PROVIDER=deepseek
    ELIGIBILITY_MODEL_ID=deepseek-chat
    RANKER_MODEL_PROVIDER=groq
    RANKER_MODEL_ID=llama-3.3-70b-versatile

Falls back to Claude Haiku if not configured.
"""

from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel


# Provider → (module, class, env var for API key, extra kwargs)
PROVIDERS = {
    "anthropic": {
        "cls": "langchain_anthropic.ChatAnthropic",
        "key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-haiku-4-5-20251001",
    },
    "deepseek": {
        "cls": "langchain_openai.ChatOpenAI",
        "key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
        "extra": {"base_url": "https://api.deepseek.com"},
    },
    "groq": {
        "cls": "langchain_groq.ChatGroq",
        "key_env": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
    },
    "together": {
        "cls": "langchain_together.ChatTogether",
        "key_env": "TOGETHER_API_KEY",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    },
}

# Default fallback
DEFAULT_PROVIDER = "anthropic"


def _import_class(dotted_path: str):
    """Import a class from a dotted module path."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def get_model(node: str) -> BaseChatModel:
    """Return the configured LLM for a pipeline node.

    Reads {NODE}_MODEL_PROVIDER and {NODE}_MODEL_ID from env.
    Falls back to Anthropic Claude Haiku.
    """
    prefix = node.upper()
    provider_name = os.getenv(f"{prefix}_MODEL_PROVIDER", DEFAULT_PROVIDER).lower()
    provider = PROVIDERS.get(provider_name)

    if not provider:
        raise ValueError(
            f"Unknown provider '{provider_name}' for {node}. "
            f"Valid: {', '.join(PROVIDERS.keys())}"
        )

    model_id = os.getenv(f"{prefix}_MODEL_ID", provider["default_model"])
    api_key = os.getenv(provider["key_env"], "")

    cls = _import_class(provider["cls"])
    kwargs = {"model": model_id}

    if provider_name == "deepseek":
        kwargs["api_key"] = api_key
        kwargs.update(provider.get("extra", {}))
    elif provider_name == "anthropic":
        pass  # reads ANTHROPIC_API_KEY automatically
    else:
        kwargs["api_key"] = api_key

    return cls(**kwargs)


def get_model_info(node: str) -> dict:
    """Return metadata about the configured model for tracing."""
    prefix = node.upper()
    provider_name = os.getenv(f"{prefix}_MODEL_PROVIDER", DEFAULT_PROVIDER).lower()
    provider = PROVIDERS.get(provider_name, PROVIDERS[DEFAULT_PROVIDER])
    model_id = os.getenv(f"{prefix}_MODEL_ID", provider["default_model"])
    return {"provider": provider_name, "model_id": model_id}

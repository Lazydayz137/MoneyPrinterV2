import ollama
from openai import OpenAI

from config import (
    get_llm_provider,
    get_ollama_base_url,
    get_openrouter_api_key,
    get_openrouter_model,
    get_verbose
)

_selected_model: str | None = None


def _ollama_client() -> ollama.Client:
    return ollama.Client(host=get_ollama_base_url())


def _openrouter_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=get_openrouter_api_key()
    )


def list_models() -> list[str]:
    """
    Lists all models available on the local Ollama server.
    (OpenRouter doesn't have a simple list without API calls, so this is mostly for Ollama).

    Returns:
        models (list[str]): Sorted list of model names.
    """
    if get_llm_provider() == "openrouter":
        # For OpenRouter, return configured model or prompt user to configure one.
        return [get_openrouter_model()]

    response = _ollama_client().list()
    return sorted(m.model for m in response.models)


def select_model(model: str) -> None:
    """
    Sets the model to use for all subsequent generate_text calls.

    Args:
        model (str): An Ollama or OpenRouter model name.
    """
    global _selected_model
    _selected_model = model


def get_active_model() -> str | None:
    """
    Returns the currently selected model, or None if none has been selected.
    """
    return _selected_model


def generate_text(prompt: str, model_name: str = None) -> str:
    """
    Generates text using the configured LLM provider (Ollama or OpenRouter).

    Args:
        prompt (str): User prompt
        model_name (str): Optional model name override

    Returns:
        response (str): Generated text
    """
    provider = get_llm_provider()

    if provider == "openrouter":
        model = model_name or _selected_model or get_openrouter_model()
        if not model:
            raise RuntimeError("No OpenRouter model selected. Configure it in config.json.")

        client = _openrouter_client()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if get_verbose():
                print(f"OpenRouter Error: {str(e)}")
            raise e

    else:
        # Default to Ollama
        from config import get_ollama_model
        model = model_name or _selected_model or get_ollama_model()
        if not model:
            raise RuntimeError(
                "No Ollama model selected. Call select_model() first or pass model_name."
            )

        response = _ollama_client().chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )

        return response["message"]["content"].strip()

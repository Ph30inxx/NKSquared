"""
Compress full Agno text responses into short spoken sentences via Azure OpenAI.
Uses the gpt-4o-mini deployment — cheap (~$0.0001/call) and fast (~300ms).
Falls back to sentence truncation when the API call fails.
"""
import logging
import re

from openai import AzureOpenAI

from chatbot.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    VOICE_COMPRESSOR_API_VERSION,
    VOICE_COMPRESSOR_DEPLOYMENT,
)

logger = logging.getLogger("nk.chatbot.voice.compressor")

_MARKDOWN = re.compile(r"[*_#`>\[\]()]|^\s*[-•]\s*", re.MULTILINE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")

_client: AzureOpenAI | None = None


def _get_client() -> AzureOpenAI:
    global _client
    if _client is None:
        _client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=VOICE_COMPRESSOR_API_VERSION,
        )
    return _client


def compress_for_voice(text: str, max_sentences: int = 2) -> str:
    """
    Compress a backend response into short spoken sentences.

    Args:
        text: Raw Agno response — may contain markdown, tables, long paragraphs.
        max_sentences: 2 for data queries; 4 for summaries; 1 for write confirmations.

    Returns:
        Plain-text string suitable for ElevenLabs TTS.
        Falls back to sentence truncation if the Azure call fails.
    """
    clean = _MARKDOWN.sub("", text).strip()
    if not clean:
        return ""

    sentences = _SENTENCE.split(clean)
    if len(sentences) <= max_sentences and len(clean) <= 200:
        return clean

    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=VOICE_COMPRESSOR_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a voice response formatter for an investment analytics assistant. "
                        "Return only the spoken sentences. No markdown, no lists, no headers. "
                        "Always convert symbols to spoken form: write 'fifty crores' not '50 Cr', "
                        "'one point eight four times' not '1.84x', 'twenty-two percent' not '22%'."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Rewrite the following as exactly {max_sentences} short spoken "
                        f"sentences for a voice assistant. Keep key numbers. Natural speech only.\n\n{clean}"
                    ),
                },
            ],
            max_tokens=160,
            temperature=0.2,
        )
        compressed = resp.choices[0].message.content.strip()
        if compressed:
            return compressed
    except Exception as exc:
        logger.warning("Voice compressor failed, using truncation fallback: %s", exc)

    return " ".join(sentences[:max_sentences])

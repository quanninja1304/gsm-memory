"""Agent integration using selected, source-backed evidence bundles."""

from .reader import (EvidenceCitation, OpenAIResponsesProvider, ReaderAnswer,
                     ReaderConfig, ReaderError, answer_query, build_prompts)

__all__ = ["EvidenceCitation", "OpenAIResponsesProvider", "ReaderAnswer", "ReaderConfig",
           "ReaderError", "answer_query", "build_prompts"]

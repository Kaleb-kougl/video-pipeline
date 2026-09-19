#!/usr/bin/env python3
"""
Domain errors raised on purpose by the pipeline.

Why this module exists
----------------------
The failure paths in this repository were overwhelmingly ``except Exception:
log and return a falsy value``. That has two costs:

1. It converts a hard failure into a silent one. A caller that gets ``[]`` back
   cannot tell "the store holds nothing for this query" from "the store is
   unreachable", so the pipeline keeps running on empty data and reports
   success.
2. It catches our own bugs. A ``KeyError`` from a renamed field is indis-
   tinguishable from a network blip, so a typo survives for 24 commits.

The classes below give the genuinely recoverable boundaries a name, so callers
can write ``except CharacterStoreError`` and let everything else - a
``TypeError``, an ``AttributeError``, a ``KeyError`` - travel up and be fixed.

Kept deliberately small: a domain-error hierarchy is only worth the ceremony
where something actually catches it. Do not add a class here until a caller
needs to distinguish it.
"""

__all__ = ["PipelineError", "CharacterStoreError", "TranscriptSourceError"]


class PipelineError(Exception):
    """Base class for every error this pipeline raises deliberately."""


class CharacterStoreError(PipelineError):
    """
    A read or write against the ChromaDB character store failed.

    Raised instead of logging and returning ``None`` so a persistence failure
    cannot be mistaken for a successful store. See
    ``agents.character_analysis_agent``.
    """


class TranscriptSourceError(PipelineError):
    """
    A transcript source could not be fetched or parsed after retries.

    This is the expected, recoverable failure of one source out of several;
    callers iterating over sources catch it and move on to the next one.
    """

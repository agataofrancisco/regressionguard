"""Modelos de dados dos datasets golden (manifesto e casos)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Manifest(BaseModel):
    """Cabecalho do dataset (primeira linha do JSONL)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    target: str = Field(min_length=1)
    description: str = ""
    author: str = Field(min_length=1)
    date: str = Field(min_length=1, description="Data ISO AAAA-MM-DD")


class Case(BaseModel):
    """Um caso golden. `expected` ou `criteria` tem de existir."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    input: Any
    expected: Any = None
    criteria: dict[str, Any] = Field(default_factory=dict)
    category: str = Field(min_length=1)
    severity: Literal["critical", "normal"]
    source: str = Field(min_length=1, description="De onde veio o label")
    evaluators: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _has_label(self) -> Case:
        if self.expected is None and not self.criteria:
            raise ValueError("o caso precisa de 'expected' ou de 'criteria'")
        return self


class Dataset(BaseModel):
    """Dataset carregado e validado, com hash do conteudo canonico."""

    manifest: Manifest
    cases: list[Case]
    path: str
    content_hash: str

    @property
    def version_id(self) -> str:
        """Identificador da versao: versao declarada + prefixo do hash."""
        return f"{self.manifest.version}+{self.content_hash[:12]}"


def canonical_hash(manifest: Manifest, cases: list[Case]) -> str:
    """SHA-256 do conteudo canonico (ignora espacos e ordem das chaves)."""
    payload = {
        "manifest": manifest.model_dump(mode="json"),
        "cases": [case.model_dump(mode="json") for case in cases],
    }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

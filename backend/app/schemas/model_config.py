from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

WEIGHT_KEYS = ("euro", "asian", "goals", "intent", "compression", "team_stats")


def _validate_weights(v: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in WEIGHT_KEYS if k not in v]
    if missing:
        raise ValueError(f"weights_json missing keys: {missing}")
    for k in WEIGHT_KEYS:
        val = v[k]
        if not isinstance(val, int | float) or val < 0 or val > 100:
            raise ValueError(f"weights_json[{k}] must be in [0, 100]")
    return v


def _validate_kelly_bands(v: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(v, dict) or not v:
        raise ValueError("kelly_bands_json must be a non-empty object")
    for band_name, band in v.items():
        if not isinstance(band, dict):
            raise ValueError(f"kelly_bands_json[{band_name}] must be an object")
        for key in ("min_score", "max_score", "kelly_pct"):
            if key not in band:
                raise ValueError(f"kelly_bands_json[{band_name}] missing key {key}")
        if band["min_score"] >= band["max_score"]:
            raise ValueError(f"kelly_bands_json[{band_name}] min_score >= max_score")
        if band["kelly_pct"] < 0 or band["kelly_pct"] > 1:
            raise ValueError(
                f"kelly_bands_json[{band_name}].kelly_pct must be in [0, 1]"
            )
    return v


class ModelConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    weights_json: dict[str, Any]
    thresholds_json: dict[str, Any]
    kelly_bands_json: dict[str, Any]
    scrape_schedule_json: dict[str, Any] | None = None

    @field_validator("weights_json")
    @classmethod
    def _wv(cls, v):
        return _validate_weights(v)

    @field_validator("kelly_bands_json")
    @classmethod
    def _kv(cls, v):
        return _validate_kelly_bands(v)


class ModelConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    weights_json: dict[str, Any] | None = None
    thresholds_json: dict[str, Any] | None = None
    kelly_bands_json: dict[str, Any] | None = None
    scrape_schedule_json: dict[str, Any] | None = None

    @field_validator("weights_json")
    @classmethod
    def _wv(cls, v):
        return v if v is None else _validate_weights(v)

    @field_validator("kelly_bands_json")
    @classmethod
    def _kv(cls, v):
        return v if v is None else _validate_kelly_bands(v)


class ModelConfigClone(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ModelConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    name: str
    created_by: int | None
    parent_id: int | None
    is_active: bool
    weights_json: dict[str, Any]
    thresholds_json: dict[str, Any]
    kelly_bands_json: dict[str, Any]
    scrape_schedule_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class ModelConfigListResponse(BaseModel):
    items: list[ModelConfigRead]
    total: int


class ModelConfigActivateResponse(ModelConfigRead):
    """Activate response includes how many scores were recomputed for today."""

    scores_recomputed: int = 0

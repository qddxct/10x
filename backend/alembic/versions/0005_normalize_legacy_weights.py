"""normalize legacy model_configs.weights_json (1.0 dictionaries -> max-cap defaults)

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-21 20:30:00.000000

The ScoringService divides provided weights by the max-cap dict in scoring.py
(euro=25, asian=20, goals=20, intent=15, compression=20, team_stats=20).
Before P6, seed.py stored weights as {k: 1.0}, which collapsed total scores
to ~0-6 and made every match fail the recommend threshold. This migration
rewrites any default ModelConfig whose weights_json contains only numeric
values <= 1.0 to the new max-cap defaults so backtests and recommendations
start producing results on existing databases.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_WEIGHTS: dict[str, int] = {
    "euro": 25,
    "asian": 20,
    "goals": 20,
    "intent": 15,
    "compression": 20,
    "team_stats": 20,
}
_LEGACY_WEIGHTS_1_0: dict[str, float] = {k: 1.0 for k in _NEW_WEIGHTS}


def _is_legacy(value: object) -> bool:
    """Treat a weights_json dict as legacy when every numeric entry is <= 1."""
    if not isinstance(value, dict) or not value:
        return False
    for key in _NEW_WEIGHTS:
        if key not in value:
            return False
    for v in value.values():
        if not isinstance(v, int | float):
            return False
        if float(v) > 1.0:
            return False
    return True


def _rows(conn, table: str) -> list[tuple[int, object]]:
    res = conn.execute(sa.text(f"SELECT id, weights_json FROM {table}"))
    out: list[tuple[int, object]] = []
    for row in res:
        raw = row[1]
        parsed = json.loads(raw) if isinstance(raw, str | bytes | bytearray) else raw
        out.append((row[0], parsed))
    return out


def _update(conn, table: str, row_id: int, value: dict) -> None:
    conn.execute(
        sa.text(f"UPDATE {table} SET weights_json = :v WHERE id = :id"),
        {"v": json.dumps(value), "id": row_id},
    )


def upgrade() -> None:
    conn = op.get_bind()
    for row_id, weights in _rows(conn, "model_configs"):
        if _is_legacy(weights):
            _update(conn, "model_configs", row_id, dict(_NEW_WEIGHTS))


def downgrade() -> None:
    conn = op.get_bind()
    for row_id, weights in _rows(conn, "model_configs"):
        if weights == _NEW_WEIGHTS:
            _update(conn, "model_configs", row_id, dict(_LEGACY_WEIGHTS_1_0))


from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from app.analysis.fact_selection import (
    FactSelectionRequest,
    select_financial_fact,
)
from app.analysis.schemas import FinancialMetric


ResolutionStatus = Literal["resolved", "ambiguous", "not_found"]


@dataclass(frozen=True)
class ResolutionResult:
    status: ResolutionStatus
    selected: FinancialMetric | None
    candidates: tuple[FinancialMetric, ...]
    duplicate_sources: tuple[FinancialMetric, ...]
    rejected_count: int
    reason: str

    @property
    def is_resolved(self) -> bool:
        return self.status == "resolved"


def resolve_financial_fact(
    metrics: Iterable[FinancialMetric],
    request: FactSelectionRequest,
) -> ResolutionResult:
    """
    Resolve one financial fact from extracted financial metrics.

    A fact is resolved only when fact selection identifies exactly
    one unambiguous candidate.

    Conflicting or missing facts are never silently selected.
    """

    if not isinstance(request, FactSelectionRequest):
        raise TypeError("request must be a FactSelectionRequest")

    metric_list = list(metrics)

    if not all(isinstance(metric, FinancialMetric) for metric in metric_list):
        raise TypeError("All metrics must be FinancialMetric instances")

    selection = select_financial_fact(
        metric_list,
        request,
    )

    if selection.is_ambiguous:
        return ResolutionResult(
            status="ambiguous",
            selected=None,
            candidates=selection.candidates,
            duplicate_sources=selection.duplicate_sources,
            rejected_count=selection.rejected_count,
            reason=selection.reason,
        )

    if selection.selected is None:
        return ResolutionResult(
            status="not_found",
            selected=None,
            candidates=selection.candidates,
            duplicate_sources=selection.duplicate_sources,
            rejected_count=selection.rejected_count,
            reason=selection.reason,
        )

    return ResolutionResult(
        status="resolved",
        selected=selection.selected,
        candidates=selection.candidates,
        duplicate_sources=selection.duplicate_sources,
        rejected_count=selection.rejected_count,
        reason=selection.reason,
    )

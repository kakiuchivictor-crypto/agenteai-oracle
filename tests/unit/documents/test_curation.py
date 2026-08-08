from __future__ import annotations

import pytest

from app.core.exceptions import InvalidCurationTransitionError
from app.database.models.enums import CurationStatus
from app.documents.validators.curation import validate_transition


def test_allows_valid_transition() -> None:
    validate_transition(CurationStatus.PENDING_REVIEW, CurationStatus.APPROVED)


def test_allows_no_op_transition_to_same_status() -> None:
    validate_transition(CurationStatus.APPROVED, CurationStatus.APPROVED)


def test_rejects_invalid_transition() -> None:
    with pytest.raises(InvalidCurationTransitionError):
        validate_transition(CurationStatus.ARCHIVED, CurationStatus.APPROVED)


def test_rejects_skipping_review_from_replaced_to_pending() -> None:
    with pytest.raises(InvalidCurationTransitionError):
        validate_transition(CurationStatus.REPLACED, CurationStatus.PENDING_REVIEW)

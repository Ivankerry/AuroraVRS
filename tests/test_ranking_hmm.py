import asyncio
import math

from api.core.ranking import (
    PROBABILITY_FLOOR,
    normalize_to_probability_distribution,
    update_interest_vector_hmm,
)


def _run_update(
    *,
    event_tags: list[str],
    event_signal: float,
    event_count: int,
    current_weights: dict[str, float],
    is_watch_event: bool = False,
) -> dict[str, float]:
    return asyncio.run(
        update_interest_vector_hmm(
            user_id="test-user",
            event_tags=event_tags,
            event_signal=event_signal,
            event_count=event_count,
            current_weights=current_weights,
            is_watch_event=is_watch_event,
        )
    )


def _assert_probability_distribution(vec: dict[str, float]) -> None:
    assert vec, "Expected non-empty vector"
    total = sum(vec.values())
    assert math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9)
    for value in vec.values():
        assert 0.0 <= value <= 1.0
        assert value >= PROBABILITY_FLOOR - 1e-12


def test_math_invariant_sum_is_one_after_positive_and_negative_updates() -> None:
    base = {"tech": 0.5, "gaming": 0.3, "music": 0.2}

    positive = _run_update(
        event_tags=["tech"],
        event_signal=0.6,
        event_count=80,
        current_weights=base,
    )
    _assert_probability_distribution(positive)

    negative = _run_update(
        event_tags=["tech"],
        event_signal=-0.5,
        event_count=80,
        current_weights=positive,
    )
    _assert_probability_distribution(negative)


def test_hard_floor_under_repeated_negative_signals() -> None:
    vec = {"tech": 0.7, "gaming": 0.2, "music": 0.1}

    for _ in range(25):
        vec = _run_update(
            event_tags=["tech"],
            event_signal=-0.5,
            event_count=10,
            current_weights=vec,
        )

    _assert_probability_distribution(vec)
    assert math.isclose(vec["tech"], PROBABILITY_FLOOR, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(vec["gaming"] + vec["music"], 1.0 - PROBABILITY_FLOOR, rel_tol=0.0, abs_tol=1e-9)


def test_legacy_normalization_from_old_style_vector() -> None:
    legacy = {"tech": 0.8, "gaming": -0.5, "music": 0.0}

    normalized = normalize_to_probability_distribution(legacy)
    _assert_probability_distribution(normalized)

    updated = _run_update(
        event_tags=["tech"],
        event_signal=0.6,
        event_count=120,
        current_weights=legacy,
    )
    _assert_probability_distribution(updated)
    assert updated["tech"] > normalized["tech"]


def test_watch_override_uses_alpha_half_for_high_watch_ratio() -> None:
    start = {"tech": 0.5, "music": 0.5}

    watch_override = _run_update(
        event_tags=["tech"],
        event_signal=0.85,
        event_count=200,
        current_weights=start,
        is_watch_event=True,
    )
    no_override = _run_update(
        event_tags=["tech"],
        event_signal=0.85,
        event_count=200,
        current_weights=start,
        is_watch_event=False,
    )

    _assert_probability_distribution(watch_override)
    _assert_probability_distribution(no_override)

    # With alpha=0.5 and signal=0.85, delta is 0.425: tech 0.5 -> 0.925, music 0.5 -> 0.075.
    assert math.isclose(watch_override["tech"], 0.925, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(watch_override["music"], 0.075, rel_tol=0.0, abs_tol=1e-9)
    assert watch_override["tech"] > no_override["tech"]


def test_empty_initial_vector_initializes_cleanly() -> None:
    vec = _run_update(
        event_tags=["tech", "music"],
        event_signal=0.6,
        event_count=5,
        current_weights={},
    )

    _assert_probability_distribution(vec)
    assert set(vec.keys()) == {"tech", "music"}
    assert math.isclose(vec["tech"], 0.5, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(vec["music"], 0.5, rel_tol=0.0, abs_tol=1e-9)


def test_single_tag_vector_no_division_by_zero_and_stays_valid() -> None:
    one_tag = {"tech": 1.0}

    after_positive = _run_update(
        event_tags=["tech"],
        event_signal=0.9,
        event_count=100,
        current_weights=one_tag,
    )
    after_negative = _run_update(
        event_tags=["tech"],
        event_signal=-0.5,
        event_count=100,
        current_weights=after_positive,
    )

    _assert_probability_distribution(after_positive)
    _assert_probability_distribution(after_negative)
    assert math.isclose(after_positive["tech"], 1.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(after_negative["tech"], 1.0, rel_tol=0.0, abs_tol=1e-9)


def test_new_unseen_tag_introduction_preserves_floor_and_mass() -> None:
    start = {"tech": 0.7, "gaming": 0.3}

    updated = _run_update(
        event_tags=["music"],
        event_signal=0.6,
        event_count=120,
        current_weights=start,
    )

    _assert_probability_distribution(updated)
    assert set(updated.keys()) == {"tech", "gaming", "music"}
    assert updated["music"] > PROBABILITY_FLOOR

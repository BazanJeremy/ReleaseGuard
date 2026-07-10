"""Sanity checks on the ADR-001 policy constants.

If one of these fails, either the ADR changed (then supersede it) or a
threshold was edited casually (then revert it).
"""

from releaseguard import policy


def test_weights_sum_to_one():
    assert policy.WEIGHT_TESTS + policy.WEIGHT_COVERAGE + policy.WEIGHT_FLAKINESS == 1.0


def test_coverage_ramp_is_ordered():
    assert 0.0 < policy.COVERAGE_FLOOR < policy.COVERAGE_TARGET <= 1.0


def test_go_threshold_in_open_interval():
    assert 0.0 < policy.GO_THRESHOLD < 1.0


def test_flaky_penalty_positive():
    assert policy.FLAKY_PENALTY > 0

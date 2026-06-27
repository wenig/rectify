"""LoginRateLimiter — sliding-window lockout for /login."""

from __future__ import annotations

from rectify.platform.ratelimit import LoginRateLimiter


def test_locks_out_after_max_failures():
    rl = LoginRateLimiter(max_attempts=3, window_seconds=100)
    assert not rl.is_blocked("ip", now=0)
    for i in range(3):
        rl.record_failure("ip", now=i)
    assert rl.is_blocked("ip", now=3)


def test_window_expiry_unblocks():
    rl = LoginRateLimiter(max_attempts=3, window_seconds=100)
    for i in range(3):
        rl.record_failure("ip", now=i)
    assert rl.is_blocked("ip", now=50)
    # All failures fall outside the window.
    assert not rl.is_blocked("ip", now=200)


def test_reset_clears_failures():
    rl = LoginRateLimiter(max_attempts=2, window_seconds=100)
    rl.record_failure("ip", now=0)
    rl.record_failure("ip", now=1)
    assert rl.is_blocked("ip", now=2)
    rl.reset("ip")
    assert not rl.is_blocked("ip", now=2)


def test_per_key_isolation():
    rl = LoginRateLimiter(max_attempts=1, window_seconds=100)
    rl.record_failure("a", now=0)
    assert rl.is_blocked("a", now=0)
    assert not rl.is_blocked("b", now=0)

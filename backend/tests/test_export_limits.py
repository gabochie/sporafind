"""Plan-gated export limits + public pricing/stats/blog (no API key)."""

from types import SimpleNamespace

from app.routers.subscriber import PLAN_EXPORT_LIMITS, _plan_limit


def _user(plan_tier="free", subscription_status=None):
    return SimpleNamespace(plan_tier=plan_tier, subscription_status=subscription_status)


def test_plan_limits_match_db_seed():
    # DB seed: free 100-record CSV, pro 1000, enterprise unlimited-ish
    assert PLAN_EXPORT_LIMITS["free"] == 100
    assert PLAN_EXPORT_LIMITS["pro"] == 1000
    assert PLAN_EXPORT_LIMITS["enterprise"] == 100000


def test_free_user_capped():
    assert _plan_limit(_user("free")) == 100
    assert _plan_limit(_user("unknown-tier")) == 100


def test_paid_tiers():
    assert _plan_limit(_user("pro")) == 1000
    assert _plan_limit(_user("enterprise")) == 100000


def test_active_stripe_subscription_upgrades_free():
    assert _plan_limit(_user("free", "active")) == 1000
    assert _plan_limit(_user("free", "trialing")) == 1000


def test_pricing_route_is_public():
    from app.routers.pricing import get_pricing

    # Public marketing page must not depend on verify_public_access
    # (live pricing.html broke with 401 when key was required)
    src = get_pricing.__code__.co_varnames
    assert "x_api_key" not in src
    import inspect

    assert "verify_public_access" not in inspect.getsource(get_pricing)


def test_stats_route_is_public():
    from app.routers.stats import get_stats
    import inspect

    assert "verify_public_access" not in inspect.getsource(get_stats)

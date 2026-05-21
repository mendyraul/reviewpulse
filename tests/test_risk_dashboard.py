from src.risk_dashboard import build_pr_risk_panel


def test_build_pr_risk_panel_7d_counts_trend_and_hot_repos():
    rows = [
        {"repo": "a/x", "riskScore": 80, "updatedAt": "2026-05-12T00:00:00Z"},
        {"repo": "a/x", "riskScore": 75, "updatedAt": "2026-05-11T00:00:00Z"},
        {"repo": "b/y", "riskScore": 20, "updatedAt": "2026-05-10T00:00:00Z"},
        {"repo": "b/y", "riskScore": 90, "updatedAt": "2026-05-01T00:00:00Z"},
    ]
    panel = build_pr_risk_panel(rows, days=7, now_iso="2026-05-13T00:00:00Z")
    assert panel["highRiskCount"] == 2
    assert panel["highRiskTrend"] == 1
    assert panel["hotRepositories"][0] == {"repo": "a/x", "count": 2}
    assert "window=7" in panel["links"]["highRisk"]


def test_build_pr_risk_panel_30d_supported():
    rows = [{"repo": "a/x", "riskScore": 71, "updatedAt": "2026-05-12T00:00:00Z"}]
    panel = build_pr_risk_panel(rows, days=30, now_iso="2026-05-13T00:00:00Z")
    assert panel["windowDays"] == 30
    assert panel["highRiskCount"] == 1

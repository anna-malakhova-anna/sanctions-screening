"""End-to-end tests against the real FastAPI app, using the real bundled data
(the actual OFAC snapshot + labelled test set + demo CSV) -- not mocks. This
is the app a recruiter would actually run, so it's worth testing as such,
even though the fixture loading (building a 44k-row index) makes this
module slower than the rest of the suite.
"""

import io

import pytest
from fastapi.testclient import TestClient

from sanctions_screening.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestGetState:
    def test_loads_demo_batch_on_startup(self, client):
        resp = client.get("/api/state")
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["batch_source"] == "demo"
        assert body["summary"]["total_rows"] > 100
        assert body["summary"]["list_name"] == "OFAC SDN"
        assert len(body["rows"]) == body["summary"]["total_rows"]

    def test_rows_have_status_and_candidates(self, client):
        resp = client.get("/api/state")
        rows = resp.json()["rows"]
        assert any(r["status"] in ("auto_clear", "review", "auto_escalate") for r in rows)
        scored_rows = [r for r in rows if r["candidates"]]
        assert scored_rows, "expected at least one row with candidates"

    def test_metrics_present(self, client):
        resp = client.get("/api/state")
        metrics = resp.json()["metrics"]
        assert 0.0 <= metrics["ground_truth"]["recall_not_missed"] <= 1.0
        assert metrics["batch_volume"]["total"] == resp.json()["summary"]["total_rows"]


class TestThresholds:
    def test_updating_thresholds_changes_volume_breakdown(self, client):
        low = client.put("/api/thresholds", json={"clear_threshold": 0.0, "escalate_threshold": 0.01}).json()
        assert low["metrics"]["batch_volume"]["auto_clear"] == 0

        # raising the escalate threshold to the max only leaves rows that
        # score a literal 1.0 (a real exact match) in auto_escalate
        high = client.put("/api/thresholds", json={"clear_threshold": 0.99, "escalate_threshold": 1.0}).json()
        exact_score_rows = sum(1 for r in high["rows"] if r["best_score"] == 1.0)
        assert high["metrics"]["batch_volume"]["auto_escalate"] == exact_score_rows

        # restore sane defaults for subsequent tests in this module
        client.put("/api/thresholds", json={"clear_threshold": 0.80, "escalate_threshold": 0.97})

    def test_rejects_clear_above_escalate(self, client):
        resp = client.put("/api/thresholds", json={"clear_threshold": 0.9, "escalate_threshold": 0.5})
        assert resp.status_code == 400

    def test_rejects_out_of_range(self, client):
        resp = client.put("/api/thresholds", json={"clear_threshold": -0.1, "escalate_threshold": 0.5})
        assert resp.status_code == 400


class TestUpload:
    def test_upload_replaces_batch(self, client):
        csv_bytes = b"name\nAcme Trading Ltd\nMuhammad Hassan\n"
        resp = client.post("/api/upload", files={"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")})
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["total_rows"] == 2
        assert body["summary"]["batch_source"] == "test.csv"
        assert {r["query_name"] for r in body["rows"]} == {"Acme Trading Ltd", "Muhammad Hassan"}

    def test_upload_rejects_missing_name_column(self, client):
        csv_bytes = b"company\nAcme Trading Ltd\n"
        resp = client.post("/api/upload", files={"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")})
        assert resp.status_code == 400

    def test_upload_rejects_empty_file(self, client):
        csv_bytes = b"name\n"
        resp = client.post("/api/upload", files={"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")})
        assert resp.status_code == 400

    def test_load_demo_restores_demo_batch(self, client):
        client.post("/api/upload", files={"file": ("test.csv", io.BytesIO(b"name\nAcme Ltd\n"), "text/csv")})
        resp = client.post("/api/load-demo")
        assert resp.status_code == 200
        assert resp.json()["summary"]["batch_source"] == "demo"
        assert resp.json()["summary"]["total_rows"] > 100


class TestDecisions:
    def test_deciding_a_row_moves_it_out_of_review(self, client):
        client.post("/api/load-demo")
        client.put("/api/thresholds", json={"clear_threshold": 0.80, "escalate_threshold": 0.97})
        state = client.get("/api/state").json()
        review_row = next((r for r in state["rows"] if r["status"] == "review"), None)
        assert review_row is not None, "expected at least one row in review at default thresholds"

        resp = client.post(f"/api/rows/{review_row['row_id']}/decision", json={"decision": "clear"})
        assert resp.status_code == 200
        updated_row = next(r for r in resp.json()["rows"] if r["row_id"] == review_row["row_id"])
        assert updated_row["status"] == "cleared"
        assert updated_row["decided_by"] == "human"

    def test_decision_on_unknown_row_404s(self, client):
        resp = client.post("/api/rows/row-99999/decision", json={"decision": "clear"})
        assert resp.status_code == 404

    def test_decided_row_survives_threshold_change(self, client):
        client.post("/api/load-demo")
        client.put("/api/thresholds", json={"clear_threshold": 0.80, "escalate_threshold": 0.97})
        state = client.get("/api/state").json()
        review_row = next(r for r in state["rows"] if r["status"] == "review")
        client.post(f"/api/rows/{review_row['row_id']}/decision", json={"decision": "escalate"})

        moved = client.put("/api/thresholds", json={"clear_threshold": 0.1, "escalate_threshold": 0.99}).json()
        updated_row = next(r for r in moved["rows"] if r["row_id"] == review_row["row_id"])
        assert updated_row["status"] == "escalated"


class TestSimulateReview:
    def test_resolves_every_pending_review_row(self, client):
        client.post("/api/load-demo")
        client.put("/api/thresholds", json={"clear_threshold": 0.80, "escalate_threshold": 0.97})
        before = client.get("/api/state").json()
        assert before["metrics"]["batch_volume"]["review"] > 0

        resp = client.post("/api/simulate-review")
        assert resp.status_code == 200
        after = resp.json()
        assert after["metrics"]["batch_volume"]["review"] == 0
        decided = [r for r in after["rows"] if r["decided_by"] == "simulated_reviewer"]
        assert len(decided) > 0
        assert all(r["decision_note"] for r in decided)


class TestDecisionLogExport:
    def test_export_is_csv_with_header_and_one_row_per_batch_entry(self, client):
        client.post("/api/load-demo")
        state = client.get("/api/state").json()
        resp = client.get("/api/decision-log/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        lines = resp.text.strip().splitlines()
        assert len(lines) == state["summary"]["total_rows"] + 1  # header + one per row
        assert "matched_alias" in lines[0]
        assert "reviewer" in lines[0]

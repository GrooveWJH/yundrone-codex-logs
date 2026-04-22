from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from switchbase_teamview.feishu_group_reporter import BroadcastStateStore, FeishuGroupReporter


_TZ = ZoneInfo("Asia/Shanghai")


def _payload(period: str, generated_at: datetime) -> dict[str, object]:
    return {
        "scope": "all-members",
        "ranking_type": period,
        "generated_at": int(generated_at.timestamp()),
        "items": [
            {"email": "a@example.com", "display_name": "吴建豪", "used_tokens": 12_345_678, "request_count": 10},
            {"email": "b@example.com", "display_name": "宋博文", "used_tokens": 9_876_543, "request_count": 8},
        ],
    }


def test_state_store_tracks_last_successful_slot(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"combined": "combined:202604220930"}), encoding="utf-8")
    store = BroadcastStateStore(path)

    assert store.last_sent_slot() == "combined:202604220930"


def test_group_reporter_sends_single_post_and_marks_state(tmp_path: Path) -> None:
    sends: list[dict[str, object]] = []
    calls: list[tuple[str, int, int, int]] = []

    class FakeDashboardService:
        def build_ranking(
            self,
            *,
            scope: str,
            ranking_type: str,
            start_timestamp: int,
            end_timestamp: int,
            limit: int,
        ) -> dict[str, object]:
            calls.append((ranking_type, start_timestamp, end_timestamp, limit))
            return _payload(ranking_type, datetime.fromtimestamp(end_timestamp, tz=_TZ))

    class FakeFeishuClient:
        def send_post_with_image_by_chat_id(self, *, chat_id: str, title: str, lines: list[str], image_path: Path) -> None:
            sends.append(
                {
                    "chat_id": chat_id,
                    "title": title,
                    "lines": lines,
                    "image_path": image_path,
                    "exists": image_path.exists(),
                }
            )

    reporter = FeishuGroupReporter(
        feishu_client=FakeFeishuClient(),
        dashboard_service=FakeDashboardService(),
        chat_id="oc_target_group",
        output_dir=tmp_path / "outputs",
        state_store=BroadcastStateStore(tmp_path / "state.json"),
        now_provider=lambda: datetime(2026, 4, 22, 9, 30, 0, tzinfo=_TZ),
        sleep_fn=lambda _: None,
    )

    reporter.run_pending()

    assert [call[0] for call in calls] == ["daily", "weekly", "monthly"]
    assert calls[0][1:3] == (int(datetime(2026, 4, 21, 0, 0, tzinfo=_TZ).timestamp()), int(datetime(2026, 4, 22, 0, 0, tzinfo=_TZ).timestamp()))
    assert calls[1][1:3] == (int(datetime(2026, 4, 20, 0, 0, tzinfo=_TZ).timestamp()), int(datetime(2026, 4, 22, 9, 30, tzinfo=_TZ).timestamp()))
    assert calls[2][1:3] == (int(datetime(2026, 4, 1, 0, 0, tzinfo=_TZ).timestamp()), int(datetime(2026, 4, 22, 9, 30, tzinfo=_TZ).timestamp()))
    assert sends[0]["chat_id"] == "oc_target_group"
    assert sends[0]["title"] == "Codex token 用量播报"
    assert sends[0]["exists"] is True
    assert "统计口径：昨日 / 周统计 / 月统计" in sends[0]["lines"]
    assert "周、月统计均截止到今日 09:30。" in sends[0]["lines"]
    assert "展示范围：全员榜，最多显示前 10 位。" in sends[0]["lines"]
    assert json.loads((tmp_path / "state.json").read_text(encoding="utf-8")) == {"combined": "combined:202604220930"}


def test_group_reporter_includes_previous_period_tags_for_monday_month_start(tmp_path: Path) -> None:
    sends: list[list[str]] = []

    class FakeDashboardService:
        def build_ranking(self, *, scope: str, ranking_type: str, start_timestamp: int, end_timestamp: int, limit: int) -> dict[str, object]:
            return _payload(ranking_type, datetime.fromtimestamp(end_timestamp, tz=_TZ))

    class FakeFeishuClient:
        def send_post_with_image_by_chat_id(self, *, chat_id: str, title: str, lines: list[str], image_path: Path) -> None:
            sends.append(lines)

    reporter = FeishuGroupReporter(
        feishu_client=FakeFeishuClient(),
        dashboard_service=FakeDashboardService(),
        chat_id="oc_target_group",
        output_dir=tmp_path / "outputs",
        state_store=BroadcastStateStore(tmp_path / "state.json"),
        now_provider=lambda: datetime(2026, 6, 1, 9, 30, 0, tzinfo=_TZ),
        sleep_fn=lambda _: None,
    )

    reporter.run_pending()

    assert "周统计为 <上周总览>，月统计为 <上月总览>。" in sends[0]


def test_group_reporter_skips_slot_already_sent(tmp_path: Path) -> None:
    class FakeDashboardService:
        def build_ranking(self, *, scope: str, ranking_type: str, start_timestamp: int, end_timestamp: int, limit: int) -> dict[str, object]:
            raise AssertionError((scope, ranking_type, start_timestamp, end_timestamp, limit))

    class FakeFeishuClient:
        def send_post_with_image_by_chat_id(self, *, chat_id: str, title: str, lines: list[str], image_path: Path) -> None:
            raise AssertionError((chat_id, title, lines, image_path))

    store = BroadcastStateStore(tmp_path / "state.json")
    store.mark_sent(slot_id="combined:202604220930")
    reporter = FeishuGroupReporter(
        feishu_client=FakeFeishuClient(),
        dashboard_service=FakeDashboardService(),
        chat_id="oc_target_group",
        output_dir=tmp_path / "outputs",
        state_store=store,
        now_provider=lambda: datetime(2026, 4, 22, 9, 30, 0, tzinfo=_TZ),
        sleep_fn=lambda _: None,
    )

    reporter.run_pending()


def test_group_reporter_does_not_mark_slot_when_send_fails(tmp_path: Path) -> None:
    class FakeDashboardService:
        def build_ranking(self, *, scope: str, ranking_type: str, start_timestamp: int, end_timestamp: int, limit: int) -> dict[str, object]:
            return _payload(ranking_type, datetime.fromtimestamp(end_timestamp, tz=_TZ))

    class FakeFeishuClient:
        def send_post_with_image_by_chat_id(self, *, chat_id: str, title: str, lines: list[str], image_path: Path) -> None:
            raise RuntimeError((chat_id, title, lines, image_path))

    reporter = FeishuGroupReporter(
        feishu_client=FakeFeishuClient(),
        dashboard_service=FakeDashboardService(),
        chat_id="oc_target_group",
        output_dir=tmp_path / "outputs",
        state_store=BroadcastStateStore(tmp_path / "state.json"),
        now_provider=lambda: datetime(2026, 4, 22, 9, 30, 0, tzinfo=_TZ),
        sleep_fn=lambda _: None,
    )

    reporter.run_pending()

    assert not (tmp_path / "state.json").exists()


def test_group_reporter_does_not_send_when_started_after_due_time(tmp_path: Path) -> None:
    class FakeDashboardService:
        def build_ranking(self, *, scope: str, ranking_type: str, start_timestamp: int, end_timestamp: int, limit: int) -> dict[str, object]:
            raise AssertionError((scope, ranking_type, start_timestamp, end_timestamp, limit))

    class FakeFeishuClient:
        def send_post_with_image_by_chat_id(self, *, chat_id: str, title: str, lines: list[str], image_path: Path) -> None:
            raise AssertionError((chat_id, title, lines, image_path))

    reporter = FeishuGroupReporter(
        feishu_client=FakeFeishuClient(),
        dashboard_service=FakeDashboardService(),
        chat_id="oc_target_group",
        output_dir=tmp_path / "outputs",
        state_store=BroadcastStateStore(tmp_path / "state.json"),
        now_provider=lambda: datetime(2026, 4, 22, 20, 0, 0, tzinfo=_TZ),
        sleep_fn=lambda _: None,
    )

    reporter.run_pending()

from failure_tracking import FailureTracker


class Response:
    status_code = 200
    headers: dict[str, str] = {}

    def json(self) -> dict:
        return {"ok": True, "data": {"event_id": "evt_1"}, "error": None, "metadata": {}}

    def raise_for_status(self) -> None:
        raise AssertionError("success must not raise")


class Session:
    def __init__(self) -> None:
        self.call: dict = {}

    def request(self, **kwargs) -> Response:
        self.call = kwargs
        return Response()


def test_capture_uses_exception_payload_and_idempotency_header() -> None:
    session = Session()
    tracker = FailureTracker(api_key="test-key", session=session)

    result = tracker.capture("ValueError: invalid slot", idempotency_key="appointment:apt-1:confirm")

    assert result == {"event_id": "evt_1"}
    assert session.call["method"] == "POST"
    assert session.call["url"].endswith("/v1/errors/capture")
    assert session.call["json"] == {"exception": "ValueError: invalid slot"}
    assert session.call["headers"]["Idempotency-Key"] == "appointment:apt-1:confirm"

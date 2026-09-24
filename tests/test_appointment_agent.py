from appointment_agent import AppointmentRequest, process_appointment


class RecordingTracker:
    def __init__(self) -> None:
        self.captures: list[tuple[str, str]] = []

    def capture(self, exception: str, *, idempotency_key: str) -> dict:
        self.captures.append((exception, idempotency_key))
        return {"event_id": "evt_test"}


def test_notification_failure_holds_appointment_for_staff_review() -> None:
    tracker = RecordingTracker()
    request = AppointmentRequest(
        appointment_id="apt-1042",
        patient_id="patient-7",
        action="confirm",
        contact_channel="sms",
    )

    def rejected_notice(_: AppointmentRequest) -> None:
        raise ConnectionError("notification provider rejected delivery")

    result = process_appointment(request, tracker, rejected_notice)

    assert result.status == "held_for_staff_review"
    assert result.patient_notice == (
        "We could not complete your appointment request. Clinic staff will review it."
    )
    assert "patient-7" not in result.patient_notice
    assert tracker.captures[0][1] == "appointment:apt-1042:confirm"
    assert "ConnectionError" in tracker.captures[0][0]

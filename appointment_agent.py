"""Appointment agent service with a patient-safe failure transition."""

from __future__ import annotations

import traceback
from enum import Enum
from typing import Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from failure_tracking import FailureTracker, InfraiError


class AppointmentAction(str, Enum):
    confirm = "confirm"
    cancel = "cancel"


class AppointmentRequest(BaseModel):
    appointment_id: str = Field(min_length=1)
    patient_id: str = Field(min_length=1)
    action: AppointmentAction
    contact_channel: str = Field(pattern="^(sms|email)$")


class AppointmentResult(BaseModel):
    appointment_id: str
    status: str
    patient_notice: str


Notifier = Callable[[AppointmentRequest], None]


def send_operational_notice(request: AppointmentRequest) -> None:
    """Example tool boundary; replace its body with the clinic notifier."""
    print(f"notice queued via {request.contact_channel} for {request.patient_id}")


def process_appointment(
    request: AppointmentRequest,
    tracker: FailureTracker,
    notifier: Notifier = send_operational_notice,
) -> AppointmentResult:
    """Apply the appointment action only after its operational notice is accepted."""
    try:
        notifier(request)
    except Exception:
        tracker.capture(
            traceback.format_exc(),
            idempotency_key=f"appointment:{request.appointment_id}:{request.action.value}",
        )
        return AppointmentResult(
            appointment_id=request.appointment_id,
            status="held_for_staff_review",
            patient_notice="We could not complete your appointment request. Clinic staff will review it.",
        )

    return AppointmentResult(
        appointment_id=request.appointment_id,
        status="confirmed" if request.action is AppointmentAction.confirm else "cancelled",
        patient_notice="Your appointment request was completed.",
    )


app = FastAPI(title="Appointment agent failure tracking")


@app.post("/appointment-workflows", response_model=AppointmentResult)
def appointment_workflow(request: AppointmentRequest) -> AppointmentResult:
    try:
        return process_appointment(request, FailureTracker())
    except InfraiError as exc:
        status_code = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status_code, detail={"code": exc.code}) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("appointment_agent:app", host="127.0.0.1", port=8000)

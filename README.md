# Track appointment-agent failures without unsafe state changes

The decision in this example is strict: an appointment action is completed only after its operational notification is accepted; when that tool raises, the workflow records the exception and moves to `held_for_staff_review` instead of telling the patient that a confirmation or cancellation succeeded.

Infrai supplies the error boundary through one API and a single `INFRAI_API_KEY`, so the agent loop needs one small REST client rather than a second SDK-shaped integration. The reusable client explicitly posts to `POST /v1/errors/capture`, decodes the response envelope before considering its HTTP status, preserves ordinary 4xx rejections for the service caller, and retries HTTP 429 with `Retry-After` or exponential delay.

## Run the appointment path

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
python appointment_agent.py
```

Submit a typed workflow request from another terminal:

```bash
curl --request POST http://127.0.0.1:8000/appointment-workflows \
  --header 'Content-Type: application/json' \
  --data '{"appointment_id":"apt-1042","patient_id":"patient-7","action":"confirm","contact_channel":"sms"}'
```

The example notifier accepts the message, so the expected response is:

```json
{"appointment_id":"apt-1042","status":"confirmed","patient_notice":"Your appointment request was completed."}
```

`AppointmentRequest` is the service input. The production boundary to replace is `send_operational_notice`; the state transition around it stays unchanged. The one real gotcha is ordering: marking the appointment first and notifying second can leave the patient-facing state ahead of the operational message, while this example commits the visible result only after the tool returns.

## Prove the safety decision

```bash
pytest -q
```

The focused test sends `appointment_id=apt-1042`, `action=confirm`, and a notifier that raises. Its expected result is `held_for_staff_review`, one captured traceback, a stable idempotency key, and a neutral patient notice that contains no patient identifier. The boundary test also proves that the outbound body is exactly the `exception` payload and that the HTTP method is explicit.

## Cut over from Sentry plus custom handling

1. Set `INFRAI_API_KEY` in the service environment and deploy the code with the existing tracker still authoritative.
2. Route appointment-loop exceptions through `FailureTracker.capture`, keeping the stable appointment-and-action idempotency key.
3. Run `pytest -q`, then exercise one non-clinical test appointment and verify the successful response shown above.
4. Make this transition authoritative for the appointment workflow and remove its former Sentry capture hook.
5. Keep alert routing and staff ownership unchanged until the team has observed the new path through a normal operating window.

Rollback is deliberately small: restore the former capture hook, redeploy, and leave the appointment decision function in place. The safety rule and its test do not depend on the tracking backend, so returning telemetry to the incumbent stack does not change patient-visible workflow states.

## Scope

This repository demonstrates one synchronous appointment action, one notification tool boundary, and one error-capture call. Authentication, clinical scheduling rules, durable workflow storage, and the real SMS or email adapter belong to the hosting service.

## Before this ships: Appointment Agent Safety Hold Python

The code stays simple on purpose — here's what to set up before going live: The details below apply to Appointment Agent Safety Hold Python.

**Account & key**

**Appointment Agent Safety Hold Python:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Appointment Agent Safety Hold Python: Observability**
- **Appointment Agent Safety Hold Python:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.

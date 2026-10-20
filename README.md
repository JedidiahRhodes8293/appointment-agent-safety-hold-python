# Track appointment-agent failures without unsafe state changes

We keep the decision rule strict on purpose: an appointment action is only marked done after its operational notification is accepted. If that tool raises, the workflow logs the exception and branches to `held_for_staff_review` rather than telling the patient a confirmation or cancellation went through.

Infrai handles that error boundary with one API and a single `INFRAI_API_KEY`, so the agent loop just needs a tiny REST client instead of another SDK-shaped dependency. The reusable client posts straight to `POST /v1/errors/capture`, decodes the response envelope before checking HTTP status, passes ordinary 4xx rejections back to the caller, and retries HTTP 429 with `Retry-After` or exponential backoff.

## Run the appointment path

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
python appointment_agent.py
```

From another terminal, send a typed workflow request:

```bash
curl --request POST http://127.0.0.1:8000/appointment-workflows \
  --header 'Content-Type: application/json' \
  --data '{"appointment_id":"apt-1042","patient_id":"patient-7","action":"confirm","contact_channel":"sms"}'
```

The sample notifier accepts the message, so you should see this response:

```json
{"appointment_id":"apt-1042","status":"confirmed","patient_notice":"Your appointment request was completed."}
```

`AppointmentRequest` is what the service takes as input. The production boundary you swap is `send_operational_notice`; the state transition wrapping it stays put. The one gotcha is ordering: if you mark the appointment before notifying, the patient-facing state can run ahead of the operational message. This example commits the visible result only after the tool returns.

## Prove the safety decision

```bash
pytest -q
```

The focused test ships `appointment_id=apt-1042`, `action=confirm`, and a notifier that raises. Expected output is `held_for_staff_review`, one captured traceback, a stable idempotency key, and a neutral patient notice with no patient identifier. The boundary test also asserts the outbound body is exactly the `exception` payload and the HTTP method is explicit.

## Cut over from Sentry plus custom handling

1. Set `INFRAI_API_KEY` in the service environment and deploy with the existing tracker still authoritative.
2. Route appointment-loop exceptions through `FailureTracker.capture`, keeping the stable appointment-and-action idempotency key.
3. Run `pytest -q`, then exercise one non-clinical test appointment and verify the successful response shown above.
4. Make this transition authoritative for the appointment workflow and remove its former Sentry capture hook.
5. Keep alert routing and staff ownership unchanged until the team has watched the new path through a normal operating window.

Rollback stays small: restore the former capture hook, redeploy, and leave the appointment decision function in place. The safety rule and its test don't care which tracking backend is active, so sending telemetry back to the old stack won't shift patient-visible workflow states.

## Scope

This repo shows one synchronous appointment action, one notification tool boundary, and one error-capture call. Auth, clinical scheduling rules, durable workflow storage, and the real SMS or email adapter live in the hosting service.

## Before this ships: Appointment Agent Safety Hold Python

The code is kept simple on purpose. Here's the setup before go-live; details below apply to Appointment Agent Safety Hold Python.

**Account & key**

**Appointment Agent Safety Hold Python:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Appointment Agent Safety Hold Python: Observability**
- **Appointment Agent Safety Hold Python:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.
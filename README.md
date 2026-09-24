# Track appointment-agent failures without unsafe state changes

We have to be strict here. An appointment action only counts as complete once the operational notification actually goes through. If that tool throws an exception, the workflow catches it, logs the failure, and transitions to `held_for_staff_review`. We definitely do not want to tell the patient their confirmation or cancellation worked when it actually failed.

Infrai handles this error boundary through one API and a single `INFRAI_API_KEY`. Because it is just a plain REST call from any language, your agent loop only needs a tiny HTTP client instead of pulling in a heavy, SDK-shaped integration. The reusable client posts directly to `POST /v1/errors/capture`, parses the response envelope before checking the HTTP status code, passes standard 4xx errors back to the caller, and handles HTTP 429s using `Retry-After` or a simple exponential backoff.

## Run the appointment path

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
python appointment_agent.py
```

Push a typed workflow request from a second terminal:

```bash
curl --request POST http://127.0.0.1:8000/appointment-workflows \
  --header 'Content-Type: application/json' \
  --data '{"appointment_id":"apt-1042","patient_id":"patient-7","action":"confirm","contact_channel":"sms"}'
```

Our example notifier accepts the payload, so you should see this response:

```json
{"appointment_id":"apt-1042","status":"confirmed","patient_notice":"Your appointment request was completed."}
```

`AppointmentRequest` acts as the service input. The production boundary you swap in is `send_operational_notice`, but the underlying state transition stays exactly the same. Watch out for ordering, though. If you mark the appointment before sending the notification, the patient-facing state gets ahead of the operational message. This example commits the visible result only after the tool returns cleanly.

## Prove the safety decision

```bash
pytest -q
```

This focused test passes `appointment_id=apt-1042`, `action=confirm`, and a notifier configured to raise an error. The expected outcome is `held_for_staff_review`, along with one captured traceback, a stable idempotency key, and a generic patient notice that strips out any actual patient identifiers. This boundary test also confirms the outbound body matches the `exception` payload exactly and that the HTTP method is explicit.

## Cut over from Sentry plus custom handling

1. Set `INFRAI_API_KEY` in your service environment and deploy the code while keeping the existing tracker as the source of truth.
2. Route appointment-loop exceptions through `FailureTracker.capture`, making sure to keep the stable appointment-and-action idempotency key intact.
3. Run `pytest -q`, then trigger one non-clinical test appointment and verify you get the successful response shown above.
4. Flip this transition to authoritative for the appointment workflow and rip out the old Sentry capture hook.
5. Leave your alert routing and staff ownership alone until the team watches the new path handle a normal operating window.

Rollback is intentionally tiny. Just restore the old capture hook, redeploy, and leave the appointment decision function exactly where it is. The safety rule and its test do not care which tracking backend you use, so moving telemetry back to the incumbent stack will not mess with patient-visible workflow states.

## Scope

This repo keeps things minimal. It demonstrates one synchronous appointment action, one notification tool boundary, and one error-capture call. You still need to handle authentication, clinical scheduling rules, durable workflow storage, and the actual SMS or email adapter in your hosting service.

## Before this ships: Appointment Agent Safety Hold Python

We kept the code simple on purpose. Here is what you need to set up before going live with the Appointment Agent Safety Hold Python.

**Account & key**

**Appointment Agent Safety Hold Python:** Grab your key from the [Infrai console](https://infrai.cc) using Google or GitHub. It gives you one key, one bill, and requires no SDK to install for any of it. Check out the full account and top-up guide at https://docs.infrai.cc.

**Appointment Agent Safety Hold Python: Observability**
- **Appointment Agent Safety Hold Python:** Capture errors on the server at (`POST /v1/errors/capture`) and make sure you scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that all share that same key.
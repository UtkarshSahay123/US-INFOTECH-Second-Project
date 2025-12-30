# CardioSentinel Workflow

CardioSentinel is an end-to-end heart attack risk workflow that marries a privacy-friendly Flask backend, a handcrafted logistic regression model, and an immersive frontend that honors the workflow brief (data collection → AI analysis → graphing → emergency automation).

## Key Capabilities

- **Pure-Python ML pipeline** – custom logistic regression trained on the UCI dataset, persisted to JSON so it runs on any laptop without compiled dependencies.
- **Guided intake** – captures demographics, vitals (BP, cholesterol, sugar, chest pain type, etc.), calories burned, and free-form notes demanded by the workflow.
- **Visual analytics** – Chart.js comparison of patient metrics versus dataset percentiles plus contextual insights and recommended actions.
- **Safety automation** – inactivity monitor, auto voice typing after 5 minutes of silence (with audible “voice typing is enabled” prompt), emergency escalation 2 minutes later if input is still missing.
- **OpenCV.js vision failsafe** – after 40 seconds of no input, webcam-based panic/eye-closure detection (Haar cascades) sends SMS/calls with live geolocation.
- **Emergency dispatching** – Twilio-backed SMS + voice calls that include vitals and Google Maps links for both manual and automated triggers.
- **Firebase-gated access** – login, signup, and password-reset flows powered by Firebase Authentication block the intake UI until staff members authenticate.
- **Contact directory** – expanding top-left CardioSentinel badge stores per-user emergency phones/emails in Firestore and auto-populates dispatches.

## Project Layout

```
backend/
  api/            # Flask app, routing, payload parsing
  ml/             # Training script, trained artifacts, model stats
  services/       # Twilio dispatcher
  utils/          # Environment configuration helper
frontend/         # Static UI (HTML/CSS/JS, Chart.js, OpenCV.js)
data/heart_uci.csv
requirements.txt
README.md
```

## Setup & Usage

1. **Create / activate the existing virtual environment** (folder `.venv` already present). If you need to recreate it:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install dependencies** (already done if you ran the automated steps):
   ```powershell
   python -m pip install -r requirements.txt
   ```

3. **Train the model** – generates `backend/ml/models/heart_attack_model.json`, `feature_stats.json`, and a training report:
   ```powershell
   python -m backend.ml.train_model
   ```

4. **Configure environment variables** – copy `.env.example` to `.env` and fill in Twilio + contact info if available. Example:
   ```env
   ALLOWED_ORIGINS=http://localhost:5000
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_token
   TWILIO_FROM_NUMBER=+1234567890
   EMERGENCY_PRIMARY_NUMBER=+1234567890
   EMERGENCY_CONTACTS=+1234567891,+1234567892
   ```
   If Twilio credentials are omitted, the dispatcher falls back to dry-run logging so the workflow can still be demonstrated.

5. **Run the Flask server** (serves both API and frontend):
   ```powershell
   $env:FLASK_APP = "backend.api.main:app"
   flask run --reload
   ```
   Visit `http://localhost:5000` to access the UI.

### Firebase Authentication

1. Create or reuse a Firebase project at https://console.firebase.google.com and enable the **Email/Password** provider under *Build → Authentication*.
2. The repository ships with the CardioSentinel project keys already wired into `window.firebaseConfig` inside `frontend/index.html`. Replace those values with your own Firebase project settings if you fork or deploy elsewhere (alternatively, define `window.firebaseConfig` before `app.js`).
3. Enable **Cloud Firestore** in the same Firebase project (Native or Datastore mode is fine). The UI writes to a `userContacts/{uid}/entries` collection tree and stores `ownerUid` on each document, so you can keep the default rules or restrict them via `request.auth.uid == resource.data.ownerUid`.
4. Reload the app. A login screen now renders first; successful authentication immediately reveals the full CardioSentinel UI, while signup and forgot-password actions use the same Firebase project. Each server restart (or hard reload) signs out active sessions so staff must re-enter their email and password every time the workflow boots.

Firestore contact documents contain `name`, `phone`, `email`, `ownerUid`, and `createdAt` fields and sync live to the contact drawer UI.

## API Snapshot

- `GET /api/health` – readiness probe.
- `POST /api/predict` – JSON body matching the intake form; returns risk classification, probability, chart payloads, insights, and recommended actions.
- `POST /api/emergency/notify` – triggers SMS + calls (used by both the UI emergency button and automated workflows).

All responses are JSON-safe conversions of the internal dataclasses.

## Frontend Workflow Highlights

- Responsive, purposeful UI with custom typography and gradients (no default stacks).
- Chart.js bar visualization comparing patient vitals to recommended midpoints and population averages.
- Status widgets for inactivity, voice typing, and OpenCV vision.
- Inactivity logic:
   - 40 sec idle → OpenCV monitoring starts.
  - 5 min idle → speech synthesis announces “voice typing is enabled” and the Web Speech API starts capturing dictated text.
  - +2 min idle → automatic emergency escalation (point 7 in the workflow).
- Authentication gateway:
   - Login interface appears first on load; successful Firebase auth unlocks the intake, analysis, and emergency cards.
   - Signup and password-reset flows share the same Firebase project so the team can self-manage access without code changes.
- Emergency contacts button:
   - The “CS” logo button on the top-left opens a drawer to add/view phone numbers and emails for the signed-in user.
   - Entries are stored in Firestore under `userContacts/{uid}/entries`, tagged with `ownerUid`, and are injected automatically into predictions and emergency escalations.
- Emergency button allows manual escalation at any time (also transmits geolocation and latest vitals to the backend dispatcher).

## Notes & Next Steps

- Twilio numbers must be in E.164 format and verified in your Twilio project during development.
- The OpenCV cascade files are fetched from the official repository at runtime; ensure the browser allows camera access.
- Voice typing relies on the Web Speech API (Chrome/Edge). Provide a manual warning to Safari/Firefox users.
- Extend `backend/ml/train_model.py` if you want more sophisticated algorithms (the JSON artifact format is intentionally simple to swap in new weights).

With these pieces in place, you can demo the entire workflow—from data capture to AI insight to automated emergency handling—on any laptop without compiling scientific stacks.

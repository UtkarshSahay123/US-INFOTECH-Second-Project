const form = document.getElementById("predictionForm");
const reportPlaceholder = document.getElementById("reportPlaceholder");
const reportContent = document.getElementById("reportContent");
const advisoryEl = document.getElementById("advisory");
const probabilityPill = document.getElementById("probabilityPill");
const insightsEl = document.getElementById("insights");
const actionsEl = document.getElementById("actions");
const riskBadge = document.getElementById("riskBadge");
const emergencyStatus = document.getElementById("emergencyStatus");
const inactivityStatus = document.getElementById("inactivityStatus");
const voiceStatus = document.getElementById("voiceStatus");
const visionStatus = document.getElementById("visionStatus");
const emergencyButton = document.getElementById("triggerEmergency");
const videoElement = document.getElementById("cameraFeed");
const mapElement = document.getElementById("liveMap");
const appShell = document.getElementById("appShell");
const authShell = document.getElementById("authShell");
const authMessage = document.getElementById("authMessage");
const loginForm = document.getElementById("loginForm");
const signupForm = document.getElementById("signupForm");
const forgotForm = document.getElementById("forgotForm");
const authViewButtons = document.querySelectorAll("[data-auth-view]");
const contactLauncher = document.getElementById("contactLauncher");
const contactDrawer = document.getElementById("contactDrawer");
const contactForm = document.getElementById("contactForm");
const contactListEl = document.getElementById("contactList");
const contactStatus = document.getElementById("contactStatus");
const contactDrawerClose = contactDrawer ? contactDrawer.querySelector(".close-drawer") : null;

let chartInstance = null;
let currentLocation = { lat: null, lon: null };
let mapInstance = null;
let mapMarker = null;
let lastInputTime = Date.now();
let voiceTypingEnabled = false;
let postVoiceTimer = null;
let visionActivated = false;
let panicTriggered = false;
let recognition;
let cameraStream;
let faceClassifier;
let eyeClassifier;
let firebaseAuth;
let firestoreDb;
let contactUnsubscribe = null;
let activeUserEmail = null;
let contactRecords = [];
const CONTACT_COLLECTION_ROOT = "userContacts";
const DEFAULT_MAP_CENTER = { lat: 20.5937, lng: 78.9629 };
const MAP_READY_CHECK_INTERVAL = 1000;
let mapApiReadyPoll = null;

let cvReadyResolver;
const cvReady = new Promise((resolve) => {
  cvReadyResolver = resolve;
});

function waitForOpenCv() {
  if (window.cv && window.cv.Mat) {
    cvReadyResolver();
    return;
  }
  if (window.cv) {
    window.cv.onRuntimeInitialized = () => cvReadyResolver();
    return;
  }
  setTimeout(waitForOpenCv, 50);
}

waitForOpenCv();

function setContactStatus(message = "", tone = "info") {
  if (!contactStatus) return;
  contactStatus.textContent = message;
  if (tone === "info") {
    contactStatus.removeAttribute("data-tone");
  } else {
    contactStatus.dataset.tone = tone;
  }
}

function getFriendlyFirestoreError(error) {
  if (!error) return "Unable to save contact.";
  if (typeof error.code === "string" && error.code.includes("permission")) {
    return "Permission denied. Update Firestore security rules for user contacts.";
  }
  if (typeof error.message === "string" && error.message.trim()) {
    return error.message;
  }
  return "Firestore request failed.";
}

function renderContactList() {
  if (!contactListEl) return;
  contactListEl.innerHTML = "";
  if (!contactRecords.length) {
    contactListEl.classList.add("empty");
    return;
  }
  contactListEl.classList.remove("empty");
  contactRecords.forEach((entry, index) => {
    const item = document.createElement("li");
    item.className = "contact-entry";

    const header = document.createElement("header");
    const title = document.createElement("span");
    title.textContent = entry.name || `Contact ${index + 1}`;
    header.appendChild(title);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "Remove";
    removeBtn.dataset.contactId = entry.id || String(index);
    removeBtn.setAttribute("aria-label", `Remove ${title.textContent}`);
    header.appendChild(removeBtn);

    item.appendChild(header);

    if (entry.phone) {
      const phoneLine = document.createElement("small");
      phoneLine.textContent = `Phone: ${entry.phone}`;
      item.appendChild(phoneLine);
    }
    if (entry.email) {
      const emailLine = document.createElement("small");
      emailLine.textContent = `Email: ${entry.email}`;
      item.appendChild(emailLine);
    }

    contactListEl.appendChild(item);
  });
}

function getStoredContactNumbers() {
  const seen = new Set();
  return contactRecords.reduce((acc, entry) => {
    const phone = (entry.phone || "").trim();
    if (phone && !seen.has(phone)) {
      seen.add(phone);
      acc.push(phone);
    }
    return acc;
  }, []);
}

function closeContactDrawer() {
  if (!contactDrawer || !contactLauncher) return;
  contactDrawer.classList.remove("open");
  contactLauncher.setAttribute("aria-expanded", "false");
}

function openContactDrawer() {
  if (!contactDrawer || !contactLauncher) return;
  contactDrawer.classList.remove("hidden");
  contactDrawer.classList.add("open");
  contactLauncher.setAttribute("aria-expanded", "true");
}

function setContactUiVisibility(isVisible) {
  if (!contactLauncher || !contactDrawer) return;
  if (isVisible) {
    contactLauncher.classList.remove("hidden");
    contactDrawer.classList.remove("hidden");
    closeContactDrawer();
  } else {
    contactLauncher.classList.add("hidden");
    contactDrawer.classList.add("hidden");
    closeContactDrawer();
  }
}

function getContactCollection() {
  if (!firestoreDb) return null;
  return firestoreDb.collection(CONTACT_COLLECTION_ROOT);
}

function detachContactSubscription() {
  if (typeof contactUnsubscribe === "function") {
    contactUnsubscribe();
    contactUnsubscribe = null;
  }
}

function subscribeToContacts(user) {
  detachContactSubscription();
  if (!user) {
    contactRecords = [];
    renderContactList();
    return;
  }
  const collectionRef = getContactCollection();
  if (!collectionRef) {
    contactRecords = [];
    renderContactList();
    return;
  }
  contactUnsubscribe = collectionRef.where("ownerUid", "==", user.uid).onSnapshot(
    (snapshot) => {
      contactRecords = snapshot.docs
        .map((doc, index) => ({
          id: doc.id,
          name: doc.get("name") || `Contact ${index + 1}`,
          phone: doc.get("phone") || "",
          email: doc.get("email") || "",
          createdAt: doc.get("createdAt")?.toMillis() || 0,
        }))
        .sort((a, b) => b.createdAt - a.createdAt);
      renderContactList();
      setContactStatus(snapshot.empty ? "No contacts yet." : "");
    },
    (error) => {
      console.error("Contact subscription failed", error);
      setContactStatus("Unable to load contacts.", "error");
    }
  );
}

function initializeContactUi() {
  if (contactLauncher) {
    contactLauncher.addEventListener("click", () => {
      if (contactDrawer?.classList.contains("hidden")) return;
      if (contactDrawer.classList.contains("open")) {
        closeContactDrawer();
      } else {
        openContactDrawer();
      }
    });
  }

  if (contactDrawerClose) {
    contactDrawerClose.addEventListener("click", closeContactDrawer);
  }

  document.addEventListener("click", (event) => {
    if (!contactDrawer || !contactLauncher) return;
    if (!contactDrawer.classList.contains("open")) return;
    const target = event.target;
    if (target === contactDrawer || target === contactLauncher) {
      return;
    }
    if (contactDrawer.contains(target) || contactLauncher.contains(target)) {
      return;
    }
    closeContactDrawer();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && contactDrawer?.classList.contains("open")) {
      closeContactDrawer();
    }
  });

  if (contactForm) {
    contactForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const currentUser = firebaseAuth?.currentUser;
      if (!currentUser) {
        setContactStatus("Sign in to store contacts.", "error");
        return;
      }
      const collectionRef = getContactCollection();
      if (!collectionRef) {
        setContactStatus("Firestore unavailable.", "error");
        return;
      }
      const formData = new FormData(contactForm);
      const name = (formData.get("contactName") || "").toString().trim();
      const phone = (formData.get("contactPhone") || "").toString().trim();
      const email = (formData.get("contactEmail") || "").toString().trim();
      if (!phone && !email) {
        setContactStatus("Provide at least a phone or email.", "error");
        return;
      }
      setContactStatus("Saving contact...");
      try {
        await collectionRef.add({
          name: name || null,
          phone: phone || null,
          email: email || null,
          ownerUid: currentUser.uid,
          createdAt: window.firebase.firestore.FieldValue.serverTimestamp(),
        });
        contactForm.reset();
        setContactStatus("Contact saved.", "success");
      } catch (error) {
        console.error("Failed to save contact", error);
        setContactStatus(getFriendlyFirestoreError(error), "error");
      }
    });
  }

  if (contactListEl) {
    contactListEl.addEventListener("click", async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const contactId = target.dataset.contactId;
      if (!contactId) return;
      const currentUser = firebaseAuth?.currentUser;
      if (!currentUser) {
        setContactStatus("Sign in to manage contacts.", "error");
        return;
      }
      const collectionRef = getContactCollection();
      if (!collectionRef) {
        setContactStatus("Firestore unavailable.", "error");
        return;
      }
      try {
        await collectionRef.doc(contactId).delete();
        setContactStatus("Contact removed.", "info");
      } catch (error) {
        console.error("Failed to remove contact", error);
        setContactStatus(getFriendlyFirestoreError(error), "error");
      }
    });
  }
}

initializeContactUi();

function setAuthMessage(message, tone = "info") {
  if (!authMessage) return;
  authMessage.textContent = message;
  if (tone === "info") {
    authMessage.removeAttribute("data-tone");
  } else {
    authMessage.dataset.tone = tone;
  }
}

function switchAuthView(targetView) {
  const map = { login: loginForm, signup: signupForm, forgot: forgotForm };
  Object.entries(map).forEach(([key, formEl]) => {
    if (!formEl) return;
    const isActive = key === targetView;
    formEl.classList.toggle("auth-form-active", isActive);
    if (!isActive) {
      formEl.reset();
    }
  });
}

function showAppShell() {
  if (authShell) {
    authShell.classList.add("hidden");
  }
  if (appShell) {
    appShell.classList.remove("hidden");
  }
  setContactUiVisibility(true);
}

function showAuthShell() {
  if (appShell) {
    appShell.classList.add("hidden");
  }
  if (authShell) {
    authShell.classList.remove("hidden");
  }
  setContactUiVisibility(false);
}

function formatFirebaseError(error) {
  if (!error) return "Authentication failed";
  if (error.code && error.code.includes("auth/")) {
    return error.code.replace("auth/", "").replace(/-/g, " ");
  }
  return error.message || "Authentication failed";
}

async function initializeFirebaseAuth() {
  if (!loginForm || !window.firebase) {
    setAuthMessage("Firebase SDK missing. Ensure firebaseConfig and scripts load.", "error");
    return;
  }

  const config = window.firebaseConfig;
  if (!config || !config.apiKey) {
    setAuthMessage("Provide window.firebaseConfig with your Firebase keys.", "error");
    return;
  }

  if (!window.firebase.apps.length) {
    window.firebase.initializeApp(config);
  }
  firebaseAuth = window.firebase.auth();
  if (window.firebase.firestore) {
    firestoreDb = window.firebase.firestore();
  } else {
    setAuthMessage("Firebase Firestore SDK missing.", "error");
  }

  try {
    await firebaseAuth.setPersistence(window.firebase.auth.Auth.Persistence.SESSION);
  } catch (error) {
    console.warn("Failed to enforce session persistence", error);
  }

  try {
    await firebaseAuth.signOut();
  } catch (error) {
    console.warn("Failed to reset auth session", error);
  }

  firebaseAuth.onAuthStateChanged((user) => {
    if (user) {
      activeUserEmail = user.email || null;
      subscribeToContacts(user);
      setContactStatus("", "info");
      setAuthMessage(`Signed in as ${user.email}`, "success");
      showAppShell();
      registerActivity();
    } else {
      activeUserEmail = null;
      detachContactSubscription();
      contactRecords = [];
      renderContactList();
      setContactStatus("", "info");
      setAuthMessage("Use your clinical email to continue.");
      switchAuthView("login");
      showAuthShell();
    }
  });

  authViewButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.authView;
      switchAuthView(target);
      if (target === "signup") {
        setAuthMessage("Enter an email and password to create an account.");
      } else if (target === "forgot") {
        setAuthMessage("We will email you a reset link.");
      } else {
        setAuthMessage("Use your clinical email to continue.");
      }
    });
  });

  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const email = event.target.loginEmail.value.trim();
      const password = event.target.loginPassword.value;
      setAuthMessage("Signing in...");
      try {
        await firebaseAuth.signInWithEmailAndPassword(email, password);
      } catch (error) {
        setAuthMessage(formatFirebaseError(error), "error");
      }
    });
  }

  if (signupForm) {
    signupForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const email = event.target.signupEmail.value.trim();
      const password = event.target.signupPassword.value;
      setAuthMessage("Creating account...");
      try {
        await firebaseAuth.createUserWithEmailAndPassword(email, password);
        setAuthMessage("Account created. You are signed in.", "success");
      } catch (error) {
        setAuthMessage(formatFirebaseError(error), "error");
      }
    });
  }

  if (forgotForm) {
    forgotForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const email = event.target.forgotEmail.value.trim();
      setAuthMessage("Sending reset email...");
      try {
        await firebaseAuth.sendPasswordResetEmail(email);
        setAuthMessage("Reset link sent. Check your inbox.", "success");
        switchAuthView("login");
      } catch (error) {
        setAuthMessage(formatFirebaseError(error), "error");
      }
    });
  }
}

switchAuthView("login");
initializeFirebaseAuth().catch((error) => {
  console.error("Firebase initialization error", error);
  setAuthMessage("Unable to initialize authentication.", "error");
});

const INACTIVITY_FOR_VISION = 40 * 1000;
const INACTIVITY_FOR_VOICE = 5 * 60 * 1000;
const POST_VOICE_TO_EMERGENCY = 2 * 60 * 1000;

const FACE_CASCADE_URL =
  "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml";
const EYE_CASCADE_URL =
  "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_eye_tree_eyeglasses.xml";

function registerActivity() {
  lastInputTime = Date.now();
  inactivityStatus.textContent = "Input detected just now";
  if (visionActivated) {
    stopVisionMonitoring();
  }
  if (voiceTypingEnabled) {
    stopVoiceTyping();
  }
  if (postVoiceTimer) {
    clearTimeout(postVoiceTimer);
    postVoiceTimer = null;
  }
}

document
  .querySelectorAll("#predictionForm input, #predictionForm select, #predictionForm textarea")
  .forEach((element) => {
    element.addEventListener("input", registerActivity);
    element.addEventListener("change", registerActivity);
  });

function collectVitalsSummary() {
  return {
    bp: `${form.bp_systolic.value || "?"}/${form.bp_diastolic.value || "?"}`,
    cholesterol: form.cholesterol.value || "?",
    sugar: form.sugar_level.value || "?",
    hr: form.max_heart_rate.value || "?",
    name: form.name.value || "Unknown",
  };
}

async function triggerEmergency(reason) {
  emergencyStatus.textContent = "Dispatching";
  const payload = {
    reason,
    vitals: collectVitalsSummary(),
    latitude: currentLocation.lat,
    longitude: currentLocation.lon,
    contacts: getStoredContactNumbers(),
  };

  try {
    const res = await fetch("https://us-infotech-second-project.onrender.com/api/emergency/notify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error("Failed to notify emergency services");
    }
    const data = await res.json();
    const mode = data.dry_run ? "Dry run" : "Live";
    emergencyStatus.textContent = `${mode}: SMS ${data.sms_dispatched.length}, Calls ${data.calls_triggered.length}`;
  } catch (error) {
    emergencyStatus.textContent = "Emergency failed";
    console.error(error);
  }
}

emergencyButton.addEventListener("click", () => triggerEmergency("Manual emergency trigger"));

async function submitPrediction(event) {
  event.preventDefault();
  const formData = new FormData(form);
  const payload = {
    name: formData.get("name"),
    age: Number(formData.get("age")),
    sex: formData.get("sex"),
    chest_pain_type: formData.get("chest_pain_type"),
    bp_systolic: Number(formData.get("bp_systolic")),
    bp_diastolic: Number(formData.get("bp_diastolic")),
    cholesterol: Number(formData.get("cholesterol")),
    sugar_level: Number(formData.get("sugar_level")),
    calories_burned: Number(formData.get("calories_burned")),
    max_heart_rate: Number(formData.get("max_heart_rate")),
    resting_ecg: formData.get("resting_ecg"),
    exercise_angina: formData.get("exercise_angina") === "true",
    st_depression: Number(formData.get("st_depression")),
    slope: formData.get("slope"),
    num_major_vessels: Number(formData.get("num_major_vessels")),
    thalassemia: formData.get("thalassemia"),
    fasting_hours: Number(formData.get("fasting_hours")),
    smoker: formData.get("smoker") === "true",
    diabetic: formData.get("diabetic") === "true",
    emergency_contacts: getStoredContactNumbers(),
    notes: formData.get("notes") || null,
  };

  try {
    const res = await fetch("https://us-infotech-second-project.onrender.com/api/emergency/notify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error("Prediction failed");
    }
    const data = await res.json();
    renderReport(data);
    riskBadge.textContent = `${data.risk_category} (${data.risk_score}%)`;
  } catch (error) {
    reportPlaceholder.innerHTML = `<p class="error">${error.message}</p>`;
    reportContent.classList.add("hidden");
    console.error(error);
  }
}

form.addEventListener("submit", submitPrediction);

function renderReport(data) {
  reportPlaceholder.classList.add("hidden");
  reportContent.classList.remove("hidden");
  advisoryEl.textContent = data.advisory_message;
  probabilityPill.textContent = `Probability ${(data.probability * 100).toFixed(1)}%`;

  insightsEl.innerHTML = data.key_insights.map((item) => `<li>${item}</li>`).join("");
  actionsEl.innerHTML = data.recommended_actions.map((item) => `<li>${item}</li>`).join("");

  const labels = data.chart.map((point) => point.label);
  const userValues = data.chart.map((point) => point.user_value);
  const recommendedMid = data.chart.map(
    (point) => (point.recommended.low + point.recommended.high) / 2
  );
  const populationAvg = data.chart.map((point) => point.population_avg);

  const ctx = document.getElementById("vitalsChart").getContext("2d");
  if (chartInstance) {
    chartInstance.destroy();
  }
  chartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Patient",
          data: userValues,
          backgroundColor: "rgba(255, 165, 0, 0.6)",
        },
        {
          label: "Recommended mid",
          data: recommendedMid,
          backgroundColor: "rgba(91, 231, 169, 0.4)",
        },
        {
          label: "Population avg",
          data: populationAvg,
          backgroundColor: "rgba(109, 169, 195, 0.5)",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: "#f1f5f9" } },
      },
      scales: {
        x: { ticks: { color: "#f1f5f9" } },
        y: { ticks: { color: "#f1f5f9" }, beginAtZero: true },
      },
    },
  });
}

function monitorInactivity() {
  const now = Date.now();
  const delta = now - lastInputTime;
  inactivityStatus.textContent = `No input for ${(delta / 60000).toFixed(1)} min`;

  if (!visionActivated && delta >= INACTIVITY_FOR_VISION) {
    activateVisionMonitoring();
  }

  if (!voiceTypingEnabled && delta >= INACTIVITY_FOR_VOICE) {
    enableVoiceTyping();
    startPostVoiceCountdown();
  }
}

setInterval(monitorInactivity, 15000);

function broadcastVoiceMessage(text) {
  if (!("speechSynthesis" in window)) {
    return;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  speechSynthesis.speak(utterance);
}

function enableVoiceTyping() {
  if (voiceTypingEnabled) return;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    voiceStatus.textContent = "Voice typing unsupported";
    return;
  }
  voiceTypingEnabled = true;
  voiceStatus.textContent = "Voice typing enabled";
  broadcastVoiceMessage("Voice typing is enabled");
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.onresult = (event) => {
    let transcript = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) {
        transcript += event.results[i][0].transcript;
      }
    }
    if (transcript) {
      const notes = document.getElementById("notes");
      notes.value = `${notes.value} ${transcript}`.trim();
      registerActivity();
    }
  };
  recognition.onerror = (event) => {
    console.warn("Voice typing error", event.error);
    stopVoiceTyping();
  };
  recognition.start();
}

function stopVoiceTyping() {
  if (!voiceTypingEnabled) return;
  voiceTypingEnabled = false;
  voiceStatus.textContent = "Voice typing stopped";
  if (recognition) {
    recognition.stop();
    recognition = null;
  }
}

function startPostVoiceCountdown() {
  if (postVoiceTimer) return;
  postVoiceTimer = setTimeout(() => {
    if (Date.now() - lastInputTime >= INACTIVITY_FOR_VOICE + POST_VOICE_TO_EMERGENCY) {
      visionStatus.textContent = "Escalating due to silence";
      triggerEmergency("Auto escalation after voice prompt");
    }
  }, POST_VOICE_TO_EMERGENCY);
}

async function loadCascade(url, filename) {
  const response = await fetch(url);
  const data = await response.arrayBuffer();
  const dataView = new Uint8Array(data);
  try {
    cv.FS_unlink(filename);
  } catch (error) {
    // ignore if file does not exist yet
  }
  cv.FS_createDataFile("/", filename, dataView, true, false, false);
  const classifier = new cv.CascadeClassifier();
  classifier.load(filename);
  return classifier;
}

async function activateVisionMonitoring() {
  if (visionActivated) return;
  visionActivated = true;
  visionStatus.textContent = "Preparing camera";
  try {
    await cvReady;
    [faceClassifier, eyeClassifier] = await Promise.all([
      loadCascade(FACE_CASCADE_URL, "haarcascade_frontalface_default.xml"),
      loadCascade(EYE_CASCADE_URL, "haarcascade_eye_tree.xml"),
    ]);
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    videoElement.srcObject = cameraStream;
    visionStatus.textContent = "Monitoring facial cues";
    runVisionLoop();
  } catch (error) {
    console.error(error);
    visionStatus.textContent = "Vision failed";
    visionActivated = false;
  }
}

function stopVisionMonitoring() {
  visionActivated = false;
  panicTriggered = false;
  visionStatus.textContent = "Vision paused (input resumed)";
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop());
    cameraStream = null;
  }
}

function runVisionLoop() {
  if (!visionActivated) return;
  const cap = new cv.VideoCapture(videoElement);
  const width = videoElement.videoWidth || 320;
  const height = videoElement.videoHeight || 240;
  const frame = new cv.Mat(height, width, cv.CV_8UC4);
  const gray = new cv.Mat();
  const faces = new cv.RectVector();
  const eyes = new cv.RectVector();

  let closedFrames = 0;
  let lostFrames = 0;

  const process = () => {
    if (!visionActivated) {
      frame.delete();
      gray.delete();
      faces.delete();
      eyes.delete();
      return;
    }

    cap.read(frame);
    cv.cvtColor(frame, gray, cv.COLOR_RGBA2GRAY, 0);
    cv.equalizeHist(gray, gray);

    faceClassifier.detectMultiScale(gray, faces, 1.1, 3, 0, new cv.Size(80, 80));

    if (faces.size() > 0) {
      const faceROI = gray.roi(faces.get(0));
      eyeClassifier.detectMultiScale(faceROI, eyes, 1.1, 3, 0, new cv.Size(30, 30));
      if (eyes.size() === 0) {
        closedFrames += 1;
      } else {
        closedFrames = 0;
      }
      faceROI.delete();
      lostFrames = 0;
    } else {
      lostFrames += 1;
    }

    if (!panicTriggered && (closedFrames > 60 || lostFrames > 90)) {
      panicTriggered = true;
      visionStatus.textContent = "Panic detected - escalating";
      triggerEmergency("OpenCV detected panic / eyes closed");
    }

    requestAnimationFrame(process);
  };

  requestAnimationFrame(process);
}

function hasGoogleMaps() {
  return typeof window.google === "object" && typeof window.google.maps === "object";
}

function scheduleMapBootstrap() {
  if (hasGoogleMaps()) {
    return;
  }
  if (mapApiReadyPoll) {
    return;
  }
  mapApiReadyPoll = setInterval(() => {
    if (hasGoogleMaps()) {
      clearInterval(mapApiReadyPoll);
      mapApiReadyPoll = null;
      updateMapLocation();
    }
  }, MAP_READY_CHECK_INTERVAL);
}

function getLatLngFromState() {
  if (typeof currentLocation.lat === "number" && typeof currentLocation.lon === "number") {
    return { lat: currentLocation.lat, lng: currentLocation.lon };
  }
  return null;
}

function ensureMapReady(seedPosition) {
  if (!mapElement || !hasGoogleMaps()) {
    return false;
  }
  const center = seedPosition || DEFAULT_MAP_CENTER;
  if (!mapInstance) {
    mapInstance = new window.google.maps.Map(mapElement, {
      center,
      zoom: 15,
      disableDefaultUI: true,
      styles: [
        { featureType: "poi", stylers: [{ visibility: "off" }] },
        { featureType: "transit", stylers: [{ visibility: "off" }] },
      ],
    });
  }
  if (!mapMarker) {
    const animation = window.google.maps.Animation
      ? window.google.maps.Animation.DROP
      : undefined;
    mapMarker = new window.google.maps.Marker({
      map: mapInstance,
      position: center,
      animation,
    });
  }
  return Boolean(mapInstance && mapMarker);
}

function updateMapLocation() {
  if (!mapElement) {
    return;
  }
  if (!hasGoogleMaps()) {
    scheduleMapBootstrap();
    return;
  }
  const livePosition = getLatLngFromState();
  if (!ensureMapReady(livePosition)) {
    return;
  }
  if (livePosition) {
    mapMarker.setPosition(livePosition);
    mapInstance.panTo(livePosition);
  }
}

window.addEventListener("load", updateMapLocation);
scheduleMapBootstrap();

function initGeolocation() {
  if (!("geolocation" in navigator)) return;
  navigator.geolocation.watchPosition(
    (position) => {
      currentLocation = {
        lat: position.coords.latitude,
        lon: position.coords.longitude,
      };
      updateMapLocation();
    },
    (error) => console.warn("Geolocation error", error),
    { enableHighAccuracy: true }
  );
}

initGeolocation();

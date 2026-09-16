// ─────────────────────────────────────────────────────────────────────────────
// HireWise — script.js v4
// UI enhancements:
//   1. Scan-line sweep on analysis start
//   2. Radial SVG gauge (needle + arc)
//   3. Inline phrase highlighting in offer text
//   4. Full-page verdict colour pulse
//   5. Flag cards as animated timeline
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE      = "https://hirewise-backend-r748.onrender.com";
const MAX_INPUT     = 10_000;
const HISTORY_KEY   = "hirewise_history_v4";

// ─── DOM refs ────────────────────────────────────────────────────────────────
const offerText         = document.getElementById("offerText");
const analyzeBtn        = document.getElementById("analyzeBtn");
const loadingState      = document.getElementById("loadingState");
const loadingMsg        = document.getElementById("loadingMsg");
const resultsSection    = document.getElementById("resultsSection");
const verdictBanner     = document.getElementById("verdictBanner");
const verdictPulse      = document.getElementById("verdictPulse");
const scoreValue        = document.getElementById("scoreValue");
const scoreRingLabel    = document.getElementById("scoreRing");
const scoreLabel        = document.getElementById("scoreLabel");
const gaugeArc          = document.getElementById("gaugeArc");
const gaugeNeedle       = document.getElementById("gaugeNeedle");
const flagsList         = document.getElementById("flagsList");
const verificationMessage = document.getElementById("verificationMessage");
const aiReviewMessage   = document.getElementById("aiReviewMessage");
const copyBtn           = document.getElementById("copyBtn");
const downloadPdfBtn    = document.getElementById("downloadPdfBtn");
const copyStatus        = document.getElementById("copyStatus");
const resetBtn          = document.getElementById("resetBtn");
const detectedEmailVal  = document.getElementById("detectedEmailValue");
const detectedDomainVal = document.getElementById("detectedDomainValue");
const riskSummaryVal    = document.getElementById("riskSummaryValue");
const themeToggle       = document.getElementById("themeToggle");
const themeIcon         = document.getElementById("themeIcon");
const charCount         = document.getElementById("charCount");
const historyPanel      = document.getElementById("historyPanel");
const historyList       = document.getElementById("historyList");
const scanLine          = document.getElementById("scanLine");
const scanContainer     = document.getElementById("scanContainer");
const highlightOverlay  = document.getElementById("highlightOverlay");
const highlightNotice   = document.getElementById("highlightNotice");
const backendDot        = document.getElementById("backendDot");
const backendStatus     = document.getElementById("backendStatus");
const lstep1            = document.getElementById("lstep1");
const lstep2            = document.getElementById("lstep2");
const lstep3            = document.getElementById("lstep3");
const fileUploadInput   = document.getElementById("fileUpload");
const fileUploadLabel   = document.getElementById("fileUploadLabel");

let latestAnalysis = null;
let currentTheme   = "dark";
let backendReady   = false;

// ─── Sample texts ────────────────────────────────────────────────────────────
const samples = {
  fake: `Dear Candidate, Congratulations! You are selected for a Data Entry Executive role at TechGrow Solutions with salary Rs. 12,00,000 per annum. To confirm your selection, please pay a registration fee before joining. This offer is valid for the next 2 hours only. Contact: techgrow.hr@gmail.com immediately.`,
  borderline: `Dear Applicant, We are pleased to offer you the position of Junior Support Associate at BrightPath Services with annual compensation of INR 6,80,000. Please confirm your acceptance within 24 hours so that we can proceed with onboarding formalities. For any questions, contact brightpathcareers@yahoo.com. Regards, Hiring Desk, BrightPath Services.`,
  legit: `Dear Aditi Sharma, We are pleased to offer you the position of Software Engineer at NexaSoft Technologies, Bengaluru. Your annual compensation will be INR 7,20,000 per annum, subject to standard payroll deductions and company policy. Your tentative date of joining is 12 August 2026. Please review the attached offer details and confirm your acceptance by 24 July 2026. For any questions, contact us at hr@nexasofttech.com. Best regards, Riya Mehta, HR Team, NexaSoft Technologies.`,
};

// ─── Risk phrase dictionaries (mirrors backend keywords for client-side highlighting) ─
const RISK_PHRASES = [
  "registration fee", "security deposit", "processing fee", "pay immediately",
  "advance fee", "training fee", "registration amount", "refundable fee",
  "pay before joining", "screening fee", "onboarding fee", "pay the amount",
  "payment", "deposit",
  "selected without interview", "guaranteed job", "instant joining",
  "no interview required", "pay and confirm", "transfer the amount",
  "whatsapp only", "kindly pay",
];

const WARN_PHRASES = [
  "urgent", "immediately", "within 24 hours", "as soon as possible",
  "limited time", "today itself", "next 2 hours", "act now",
  "final deadline", "respond today", "confirm immediately",
  "congratulations", "selected",
];

// ─── Cold-start wake ──────────────────────────────────────────────────────────
async function wakeBackend() {
  try {
    await fetch(`${API_BASE}/api/ping`);
    backendReady = true;
    if (backendDot) { backendDot.className = "status-dot online"; }
    if (backendStatus) backendStatus.textContent = "Online";
  } catch {
    backendReady = false;
    if (backendDot) { backendDot.className = "status-dot offline"; }
    if (backendStatus) backendStatus.textContent = "Offline";
  }
}
wakeBackend();

// ─── Theme ───────────────────────────────────────────────────────────────────
function setTheme(t) {
  currentTheme = t;
  document.body.classList.toggle("light", t === "light");
  if (themeIcon) themeIcon.textContent = t === "light" ? "◑" : "◐";
}

themeToggle.addEventListener("click", () => {
  setTheme(currentTheme === "dark" ? "light" : "dark");
  themeToggle.animate(
    [{ transform: "rotate(0deg)" }, { transform: "rotate(180deg)" }, { transform: "rotate(0deg)" }],
    { duration: 340, easing: "ease-out" }
  );
});

// ─── Character counter ───────────────────────────────────────────────────────
offerText.addEventListener("input", () => {
  const n = offerText.value.length;
  if (charCount) {
    charCount.textContent = `${n.toLocaleString()} / ${MAX_INPUT.toLocaleString()}`;
    charCount.className = "char-count" +
      (n > MAX_INPUT ? " char-count-over" : n > MAX_INPUT * 0.9 ? " char-count-warn" : "");
  }
  // Clear highlights when text changes
  clearHighlights();
  if (highlightNotice) highlightNotice.classList.add("hidden");
});

// ─── Sample buttons ───────────────────────────────────────────────────────────
document.querySelectorAll(".sample-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    offerText.value = samples[btn.dataset.type];
    offerText.dispatchEvent(new Event("input"));
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// ENHANCEMENT 1 — Scan-line sweep
// ─────────────────────────────────────────────────────────────────────────────
function startScanLine() {
  if (!scanLine) return;
  scanLine.classList.remove("scanning");
  void scanLine.offsetWidth; // reflow to restart animation
  scanLine.classList.add("scanning");
}

function stopScanLine() {
  if (!scanLine) return;
  scanLine.classList.remove("scanning");
}

// ─────────────────────────────────────────────────────────────────────────────
// ENHANCEMENT 2 — Radial SVG gauge
// Arc length for a semicircle of radius 80 ≈ π×80 = 251.2
// ─────────────────────────────────────────────────────────────────────────────
const ARC_LENGTH = 251.2;

function setGauge(score, colorClass) {
  if (!gaugeArc || !gaugeNeedle) return;

  const ratio   = score / 100;
  const offset  = ARC_LENGTH - ratio * ARC_LENGTH;
  const degrees = -90 + ratio * 180; // -90° (left) → +90° (right)

  // Arc fill
  gaugeArc.style.strokeDashoffset = offset;
  gaugeArc.className = `gauge-arc arc-${colorClass}`;

  // Needle rotation
  gaugeNeedle.style.transform = `rotate(${degrees}deg)`;
}

function resetGauge() {
  if (!gaugeArc) return;
  gaugeArc.style.strokeDashoffset = ARC_LENGTH;
  gaugeArc.className = "gauge-arc";
  if (gaugeNeedle) gaugeNeedle.style.transform = "rotate(-90deg)";
}

// ─────────────────────────────────────────────────────────────────────────────
// ENHANCEMENT 3 — Inline phrase highlighting
// ─────────────────────────────────────────────────────────────────────────────
function buildHighlightLayer(text) {
  // Remove any existing layer
  clearHighlights();

  const layer = document.createElement("div");
  layer.className = "highlight-layer";
  layer.id = "highlightLayer";

  // We need to mark words in the text. We'll escape HTML, then replace phrases.
  // Since we're setting textContent-style content via DOM, we use a careful
  // approach: build a list of ranges, sort, then splice spans in.

  const lower = text.toLowerCase();
  const ranges = []; // { start, end, cls }

  function addRanges(phrases, cls) {
    for (const phrase of phrases) {
      let idx = 0;
      while ((idx = lower.indexOf(phrase, idx)) !== -1) {
        // Avoid overlapping — only add if not already covered
        const end = idx + phrase.length;
        const overlaps = ranges.some(r => idx < r.end && end > r.start);
        if (!overlaps) ranges.push({ start: idx, end, cls });
        idx += phrase.length;
      }
    }
  }

  addRanges(RISK_PHRASES, "hl-risk");
  addRanges(WARN_PHRASES, "hl-warn");

  if (ranges.length === 0) return null;

  // Sort by start position
  ranges.sort((a, b) => a.start - b.start);

  // Build child nodes
  let cursor = 0;
  for (const { start, end, cls } of ranges) {
    if (cursor < start) {
      layer.appendChild(document.createTextNode(text.slice(cursor, start)));
    }
    const mark = document.createElement("mark");
    mark.className = cls;
    mark.textContent = text.slice(start, end);
    layer.appendChild(mark);
    cursor = end;
  }

  if (cursor < text.length) {
    layer.appendChild(document.createTextNode(text.slice(cursor)));
  }

  return ranges.length > 0 ? layer : null;
}

function applyHighlights(text) {
  const layer = buildHighlightLayer(text);
  if (!layer || !scanContainer) return;

  scanContainer.appendChild(layer);

  // Make the textarea background transparent so the layer shows through
  offerText.style.background = "transparent";
  offerText.style.color = "transparent";
  offerText.style.caretColor = "var(--text)";

  if (highlightOverlay) highlightOverlay.classList.add("visible");
  if (highlightNotice) highlightNotice.classList.remove("hidden");

  // Sync scroll between textarea and layer
  offerText.addEventListener("scroll", syncHighlightScroll);
}

function syncHighlightScroll() {
  const layer = document.getElementById("highlightLayer");
  if (layer) layer.scrollTop = offerText.scrollTop;
}

function clearHighlights() {
  const layer = document.getElementById("highlightLayer");
  if (layer) layer.remove();

  offerText.style.background = "";
  offerText.style.color = "";
  offerText.style.caretColor = "";

  if (highlightOverlay) highlightOverlay.classList.remove("visible");
  offerText.removeEventListener("scroll", syncHighlightScroll);
}

// ─────────────────────────────────────────────────────────────────────────────
// ENHANCEMENT 4 — Full-page verdict colour pulse
// ─────────────────────────────────────────────────────────────────────────────
function fireVerdictPulse(color) {
  if (!verdictPulse) return;
  verdictPulse.className = `verdict-pulse pulse-${color}`;
  void verdictPulse.offsetWidth; // reflow
  verdictPulse.classList.add("firing");
  verdictPulse.addEventListener("animationend", () => {
    verdictPulse.className = "verdict-pulse";
  }, { once: true });
}

// ─────────────────────────────────────────────────────────────────────────────
// ENHANCEMENT 5 — Timeline flag cards (slideInLeft with stagger)
// (CSS handles the visual; JS handles the stagger via animationDelay)
// ─────────────────────────────────────────────────────────────────────────────

// ─── Severity helpers ─────────────────────────────────────────────────────────
function getSeverityClasses(severity) {
  switch (severity) {
    case "high":   return { card: "flag-risk",  chip: "chip-risk",  label: "High risk" };
    case "medium": return { card: "flag-mid",   chip: "chip-mid",   label: "Review" };
    case "safe":   return { card: "flag-safe",  chip: "chip-safe",  label: "Looks good" };
    default:       return { card: "flag-mid",   chip: "chip-mid",   label: "Low concern" };
  }
}

function buildFlagCard(title, detail, severity, delay = 0) {
  const { card, chip, label } = getSeverityClasses(severity);

  const el    = document.createElement("div");
  el.className = `flag-card ${card}`;
  el.setAttribute("role", "listitem");
  el.style.animationDelay = `${delay}ms`;

  const chipEl = document.createElement("div");
  chipEl.className = `flag-chip ${chip}`;
  chipEl.textContent = label;

  const h4 = document.createElement("h4");
  h4.textContent = title;

  const p = document.createElement("p");
  p.textContent = detail;

  el.appendChild(chipEl);
  el.appendChild(h4);
  el.appendChild(p);
  return el;
}

// ─── Score helpers ────────────────────────────────────────────────────────────
function getColorClass(score) {
  if (score >= 80) return "green";
  if (score >= 50) return "yellow";
  return "red";
}

function getRiskSummary(score) {
  if (score >= 80) return "Low concern";
  if (score >= 50) return "Needs review";
  return "High risk";
}

function getScoreLabel(score) {
  if (score >= 80) return "Low-friction result. Still verify with the employer before sharing sensitive documents.";
  if (score >= 50) return "Mixed signals detected. Pause and verify before you proceed.";
  return "Multiple scam-like patterns detected. Treat this offer as high risk.";
}

function applyScoreStyles(score) {
  const cls = getColorClass(score);
  scoreValue.className = `score-value score-${cls === "green" ? "safe" : cls === "yellow" ? "mid" : "risk"}`;
}

function animateCounter(el, end, duration = 800) {
  const t0 = performance.now();
  function tick(now) {
    const p = Math.min((now - t0) / duration, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(eased * end);
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

// ─── Loading step animator ────────────────────────────────────────────────────
function animateLoadingSteps() {
  if (!lstep1) return;
  [lstep1, lstep2, lstep3].forEach(s => { s.className = "lstep"; });
  lstep1.classList.add("active");
  const t1 = setTimeout(() => {
    lstep1.classList.replace("active", "done");
    lstep2.classList.add("active");
  }, 1200);
  const t2 = setTimeout(() => {
    lstep2.classList.replace("active", "done");
    lstep3.classList.add("active");
  }, 2800);
  return () => { clearTimeout(t1); clearTimeout(t2); };
}

// ─────────────────────────────────────────────────────────────────────────────
// Render results
// ─────────────────────────────────────────────────────────────────────────────
function renderResults(data, originalText) {
  const color = data.verdict.color;

  // 4. Full-page verdict pulse
  fireVerdictPulse(color);

  // Verdict banner
  verdictBanner.textContent = data.verdict.label;
  verdictBanner.className = `verdict-banner verdict-${color}`;
  verdictBanner.animate(
    [{ opacity: 0, transform: "translateY(-6px) scale(0.98)" }, { opacity: 1, transform: "translateY(0) scale(1)" }],
    { duration: 320, easing: "ease-out" }
  );

  // Score
  applyScoreStyles(data.confidenceScore);
  animateCounter(scoreValue, data.confidenceScore);
  if (scoreRingLabel) scoreRingLabel.textContent = getRiskSummary(data.confidenceScore);
  if (scoreLabel) scoreLabel.textContent = getScoreLabel(data.confidenceScore);

  // 2. Radial gauge
  setTimeout(() => setGauge(data.confidenceScore, getColorClass(data.confidenceScore)), 80);

  // Summary
  detectedEmailVal.textContent  = data.detectedEmail  || "Not detected";
  detectedDomainVal.textContent = data.detectedDomain || "Not detected";
  riskSummaryVal.textContent    = getRiskSummary(data.confidenceScore);

  // 5. Timeline flags with stagger
  flagsList.innerHTML = "";
  if (!data.flags || data.flags.length === 0) {
    flagsList.appendChild(buildFlagCard(
      "No major red flags detected",
      "No common scam patterns found. Direct verification with the employer is still recommended.",
      "safe", 0
    ));
  } else {
    // Sort: high → medium → low → safe
    const order = { high: 0, medium: 1, low: 2, safe: 3 };
    const sorted = [...data.flags].sort((a, b) => (order[a.severity] ?? 2) - (order[b.severity] ?? 2));
    sorted.forEach((flag, i) => {
      flagsList.appendChild(buildFlagCard(flag.title, flag.detail, flag.severity || "medium", i * 80));
    });
  }

  // Verification + AI review
  verificationMessage.value = data.verificationMessage || "";
  if (aiReviewMessage) {
    aiReviewMessage.value = data.aiReview ||
      "AI review is currently unavailable. The rule-based analysis above is still accurate.";
  }

  // 3. Inline highlights (after results shown, so scroll UX is good)
  if (originalText) {
    clearHighlights();
    setTimeout(() => applyHighlights(originalText), 600);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Analyze
// ─────────────────────────────────────────────────────────────────────────────
analyzeBtn.addEventListener("click", async () => {
  const text = offerText.value.trim();

  if (!text) {
    offerText.focus();
    offerText.classList.add("shake");
    setTimeout(() => offerText.classList.remove("shake"), 400);
    return;
  }

  if (text.length > MAX_INPUT) {
    alert(`Text is too long (${text.length.toLocaleString()} chars). Max is ${MAX_INPUT.toLocaleString()}.`);
    return;
  }

  // 1. Scan line
  startScanLine();

  loadingState.classList.remove("hidden");
  resultsSection.classList.add("hidden");
  if (highlightNotice) highlightNotice.classList.add("hidden");
  copyStatus.textContent = "";

  const stopSteps = animateLoadingSteps();

  if (loadingMsg && !backendReady) {
    loadingMsg.textContent = "Server is starting up — this can take up to 30 s on first use…";
  }

  try {
    const resp = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ offerText: text }),
    });

    if (resp.status === 429) {
      alert("Too many requests. Please wait a minute and try again.");
      return;
    }
    if (!resp.ok) throw new Error(`Server error (${resp.status})`);

    const data = await resp.json();
    if (data.error) { alert(`Analysis error: ${data.error}`); return; }

    latestAnalysis = data;
    renderResults(data, text);
    saveToHistory(data, text);

    resultsSection.classList.remove("hidden");
    setTimeout(() => resultsSection.scrollIntoView({ behavior: "smooth", block: "start" }), 80);

  } catch (err) {
    console.error(err);
    const msg = err.name === "TypeError"
      ? "Could not reach the server. It may be starting — wait 30 s and try again."
      : `Something went wrong: ${err.message}`;
    alert(msg);
  } finally {
    stopSteps();
    stopScanLine();
    loadingState.classList.add("hidden");
    if (loadingMsg) loadingMsg.textContent = "Scanning the letter for risk signals…";
    if (lstep1) [lstep1, lstep2, lstep3].forEach(s => s.className = "lstep");
    lstep1 && lstep1.classList.add("active");
  }
});

// ─── File upload ──────────────────────────────────────────────────────────────
if (fileUploadInput) {
  fileUploadInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const isPdf = file.type === "application/pdf" || file.name.endsWith(".pdf");
    const isTxt = file.type === "text/plain" || file.name.endsWith(".txt");

    if (!isPdf && !isTxt) { alert("Only .pdf and .txt files are supported."); fileUploadInput.value = ""; return; }
    if (file.size > 2 * 1024 * 1024) { alert("File too large (max 2 MB)."); fileUploadInput.value = ""; return; }

    if (isTxt) {
      const reader = new FileReader();
      reader.onload = ev => {
        offerText.value = ev.target.result.slice(0, MAX_INPUT);
        offerText.dispatchEvent(new Event("input"));
      };
      reader.readAsText(file);
      if (fileUploadLabel) fileUploadLabel.textContent = file.name;
      return;
    }

    if (fileUploadLabel) fileUploadLabel.textContent = "Extracting…";
    const fd = new FormData();
    fd.append("file", file);

    try {
      const r = await fetch(`${API_BASE}/api/extract`, { method: "POST", body: fd });
      if (!r.ok) throw new Error(`${r.status}`);
      const res = await r.json();
      if (res.error) { alert(`Extraction failed: ${res.error}`); return; }
      offerText.value = (res.text || "").slice(0, MAX_INPUT);
      offerText.dispatchEvent(new Event("input"));
      if (fileUploadLabel) fileUploadLabel.textContent = file.name;
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
      if (fileUploadLabel) fileUploadLabel.textContent = "Upload .pdf or .txt";
    } finally {
      fileUploadInput.value = "";
    }
  });
}

// ─── Copy ─────────────────────────────────────────────────────────────────────
copyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(verificationMessage.value);
    copyStatus.textContent = "✓ Copied";
    setTimeout(() => { copyStatus.textContent = ""; }, 2000);
  } catch {
    copyStatus.textContent = "Copy failed";
  }
});

// ─── PDF ──────────────────────────────────────────────────────────────────────
downloadPdfBtn.addEventListener("click", () => {
  if (!latestAnalysis) { alert("Run an analysis first."); return; }

  const { jsPDF } = window.jspdf;
  const doc  = new jsPDF();
  const data = latestAnalysis;
  const lines = [
    "HireWise Safety Report", "",
    `Verdict: ${data.verdict.label}`,
    `Score:   ${data.confidenceScore} / 100`,
    `Email:   ${data.detectedEmail  || "Not detected"}`,
    `Domain:  ${data.detectedDomain || "Not detected"}`,
    `Risk:    ${getRiskSummary(data.confidenceScore)}`, "",
    "── Detected Signals ──────────────────────────────────────────",
  ];

  (data.flags || []).forEach((f, i) => {
    lines.push(`${i + 1}. [${(f.severity || "—").toUpperCase()}] ${f.title}`);
    lines.push(`   ${f.detail}`);
    lines.push("");
  });

  lines.push("── AI Review ─────────────────────────────────────────────────");
  lines.push(data.aiReview || "Not available.");
  lines.push("");
  lines.push("── Verification Message ──────────────────────────────────────");
  lines.push(data.verificationMessage || "");

  let y = 20;
  doc.setFont("helvetica", "bold"); doc.setFontSize(18);
  doc.text("HireWise Safety Report", 14, y); y += 10;
  doc.setFont("helvetica", "normal"); doc.setFontSize(10.5);
  doc.text(doc.splitTextToSize(lines.join("\n"), 182), 14, y);
  doc.save("hirewise-report.pdf");
});

// ─── Reset ────────────────────────────────────────────────────────────────────
resetBtn.addEventListener("click", () => {
  offerText.value = "";
  offerText.dispatchEvent(new Event("input"));
  clearHighlights();

  resultsSection.classList.add("hidden");
  verdictBanner.className = "verdict-banner";
  scoreValue.className = "score-value";
  scoreValue.textContent = "--";
  if (scoreRingLabel) scoreRingLabel.textContent = "—";
  if (scoreLabel) scoreLabel.textContent = "Waiting for analysis…";
  resetGauge();

  flagsList.innerHTML = "";
  verificationMessage.value = "";
  if (aiReviewMessage) aiReviewMessage.value = "";
  detectedEmailVal.textContent  = "—";
  detectedDomainVal.textContent = "—";
  riskSummaryVal.textContent    = "—";
  copyStatus.textContent = "";
  if (highlightNotice) highlightNotice.classList.add("hidden");
  if (fileUploadLabel) fileUploadLabel.textContent = "Upload .pdf or .txt";
  latestAnalysis = null;
  offerText.focus();
});

// ─── Session history ──────────────────────────────────────────────────────────
function loadHistory() {
  try { return JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]"); }
  catch { return []; }
}

function saveToHistory(data, text) {
  const h = loadHistory();
  h.unshift({
    ts: new Date().toISOString(),
    snippet: text.slice(0, 80) + (text.length > 80 ? "…" : ""),
    verdict: data.verdict,
    score: data.confidenceScore,
    data,
    text: text.slice(0, MAX_INPUT),
  });
  sessionStorage.setItem(HISTORY_KEY, JSON.stringify(h.slice(0, 10)));
  renderHistory();
}

function renderHistory() {
  if (!historyPanel || !historyList) return;
  const h = loadHistory();
  if (!h.length) { historyPanel.classList.add("hidden"); return; }

  historyPanel.classList.remove("hidden");
  historyList.innerHTML = "";

  h.forEach((entry, idx) => {
    const btn = document.createElement("button");
    btn.className = `history-item history-item-${entry.verdict.color}`;
    btn.setAttribute("aria-label", `Load previous analysis ${idx + 1}`);

    const t = document.createElement("span");
    t.className = "history-time";
    t.textContent = new Date(entry.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    const s = document.createElement("span");
    s.className = "history-score";
    s.textContent = entry.score;

    const sn = document.createElement("span");
    sn.className = "history-snippet";
    sn.textContent = entry.snippet;

    btn.appendChild(t); btn.appendChild(s); btn.appendChild(sn);
    btn.addEventListener("click", () => {
      latestAnalysis = entry.data;
      if (entry.text) { offerText.value = entry.text; offerText.dispatchEvent(new Event("input")); }
      renderResults(entry.data, entry.text);
      resultsSection.classList.remove("hidden");
      resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    historyList.appendChild(btn);
  });
}

// ─── Init ─────────────────────────────────────────────────────────────────────
setTheme("dark");
renderHistory();

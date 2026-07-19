const offerText = document.getElementById("offerText");
const analyzeBtn = document.getElementById("analyzeBtn");
const loadingState = document.getElementById("loadingState");
const resultsSection = document.getElementById("resultsSection");
const verdictBanner = document.getElementById("verdictBanner");
const scoreValue = document.getElementById("scoreValue");
const scoreFill = document.getElementById("scoreFill");
const scoreLabel = document.getElementById("scoreLabel");
const flagsList = document.getElementById("flagsList");
const verificationMessage = document.getElementById("verificationMessage");
const copyBtn = document.getElementById("copyBtn");
const downloadPdfBtn = document.getElementById("downloadPdfBtn");
const copyStatus = document.getElementById("copyStatus");
const resetBtn = document.getElementById("resetBtn");
const detectedEmailValue = document.getElementById("detectedEmailValue");
const detectedDomainValue = document.getElementById("detectedDomainValue");
const riskSummaryValue = document.getElementById("riskSummaryValue");
const themeToggle = document.getElementById("themeToggle");
const aiReviewMessage = document.getElementById("aiReviewMessage");

let latestAnalysis = null;
let currentTheme = "dark";

const samples = {
  fake: `Dear Candidate, Congratulations! You are selected for a Data Entry Executive role at TechGrow Solutions with salary Rs. 12,00,000 per annum. To confirm your selection, please pay a registration fee before joining. This offer is valid for the next 2 hours only. Contact: techgrow.hr@gmail.com immediately.`,
  borderline: `Dear Applicant, We are pleased to offer you the position of Junior Support Associate at BrightPath Services with annual compensation of INR 6,80,000. Please confirm your acceptance within 24 hours so that we can proceed with onboarding formalities. For any questions, contact brightpathcareers@yahoo.com. Regards, Hiring Desk, BrightPath Services.`,
  legit: `Dear Aditi Sharma, We are pleased to offer you the position of Software Engineer at NexaSoft Technologies, Bengaluru. Your annual compensation will be INR 7,20,000 per annum, subject to standard payroll deductions and company policy. Your tentative date of joining is 12 August 2026. Please review the attached offer details and confirm your acceptance by 24 July 2026. For any questions, contact us at hr@nexasofttech.com. Best regards, Riya Mehta, HR Team, NexaSoft Technologies.`
};

function setTheme(theme) {
  currentTheme = theme;
  document.body.classList.toggle("light", theme === "light");
  themeToggle.textContent = theme === "light" ? "◑" : "◐";
}

themeToggle.addEventListener("click", () => {
  setTheme(currentTheme === "dark" ? "light" : "dark");
  themeToggle.animate(
    [
      { transform: "rotate(0deg)" },
      { transform: "rotate(180deg)" },
      { transform: "rotate(0deg)" }
    ],
    { duration: 320, easing: "ease-out" }
  );
});

document.querySelectorAll(".sample-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    offerText.value = samples[btn.dataset.type];
  });
});

function getScoreLabel(score) {
  if (score >= 80) {
    return "Low-friction result. Still verify with the employer before sharing sensitive documents.";
  }
  if (score >= 50) {
    return "Mixed signals detected. Pause and verify before you proceed.";
  }
  return "Multiple scam-like patterns detected. Treat this offer as high risk.";
}

function getRiskSummary(score) {
  if (score >= 80) return "Low concern";
  if (score >= 50) return "Needs review";
  return "High risk";
}

function applyScoreStyles(score) {
  scoreValue.className = "score-value";
  scoreFill.className = "meter-fill";

  if (score >= 80) {
    scoreValue.classList.add("score-safe");
    scoreFill.classList.add("fill-safe");
  } else if (score >= 50) {
    scoreValue.classList.add("score-mid");
    scoreFill.classList.add("fill-mid");
  } else {
    scoreValue.classList.add("score-risk");
    scoreFill.classList.add("fill-risk");
  }
}

function animateCounter(element, endValue) {
  const duration = 700;
  const start = 0;
  const startTime = performance.now();

  function update(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.round(start + (endValue - start) * eased);
    element.textContent = current;
    if (progress < 1) requestAnimationFrame(update);
  }

  requestAnimationFrame(update);
}

function getFlagClass(color) {
  if (color === "green") return "flag-safe";
  if (color === "yellow") return "flag-mid";
  return "flag-risk";
}

function getChipClass(color) {
  if (color === "green") return "chip-safe";
  if (color === "yellow") return "chip-mid";
  return "chip-risk";
}

function getChipLabel(color) {
  if (color === "green") return "Low concern";
  if (color === "yellow") return "Review needed";
  return "High risk";
}

analyzeBtn.addEventListener("click", async () => {
  const text = offerText.value.trim();

  if (!text) {
    alert("Please paste an offer letter first.");
    offerText.focus();
    return;
  }

  loadingState.classList.remove("hidden");
  resultsSection.classList.add("hidden");
  copyStatus.textContent = "";

  try {
    const response = await fetch("http://localhost:5000/api/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ offerText: text })
    });

    const data = await response.json();
    latestAnalysis = data;

    verdictBanner.textContent = data.verdict.label;
    verdictBanner.className = "verdict-banner";
    verdictBanner.classList.add(`verdict-${data.verdict.color}`);
    verdictBanner.animate(
      [
        { opacity: 0, transform: "translateY(8px)" },
        { opacity: 1, transform: "translateY(0)" }
      ],
      { duration: 280, easing: "ease-out" }
    );

    applyScoreStyles(data.confidenceScore);
    animateCounter(scoreValue, data.confidenceScore);
    scoreFill.style.width = `${data.confidenceScore}%`;
    scoreLabel.textContent = getScoreLabel(data.confidenceScore);

    detectedEmailValue.textContent = data.detectedEmail || "Not found";
    detectedDomainValue.textContent = data.detectedDomain || "Not found";
    riskSummaryValue.textContent = getRiskSummary(data.confidenceScore);

    flagsList.innerHTML = "";

    if (!data.flags || data.flags.length === 0) {
      const card = document.createElement("div");
      card.className = "flag-card flag-safe";
      card.innerHTML = `
        <div class="flag-chip chip-safe">Low concern</div>
        <h4>No major red flags detected</h4>
        <p>No common scam patterns were found in this letter, but direct verification is still recommended.</p>
      `;
      flagsList.appendChild(card);
    } else {
      data.flags.forEach((flag, index) => {
        const card = document.createElement("div");
        card.className = `flag-card ${getFlagClass(data.verdict.color)}`;
        card.style.animationDelay = `${index * 70}ms`;
        card.innerHTML = `
          <div class="flag-chip ${getChipClass(data.verdict.color)}">${getChipLabel(data.verdict.color)}</div>
          <h4>${flag.title}</h4>
          <p>${flag.detail}</p>
        `;
        flagsList.appendChild(card);
      });
    }

    verificationMessage.value = data.verificationMessage;
    if (aiReviewMessage) {
      aiReviewMessage.value = data.aiReview || "No AI review available";
    }

    resultsSection.classList.remove("hidden");
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    console.error("Frontend error:", error);
    alert("Something went wrong while analyzing the offer.");
  } finally {
    loadingState.classList.add("hidden");
  }
});

copyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(verificationMessage.value);
    copyStatus.textContent = "Copied!";
    setTimeout(() => {
      copyStatus.textContent = "";
    }, 1600);
  } catch (error) {
    console.error("Copy failed:", error);
    copyStatus.textContent = "Copy failed";
  }
});

downloadPdfBtn.addEventListener("click", () => {
  if (!latestAnalysis) {
    alert("Run an analysis first.");
    return;
  }

  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();
  const lines = [];

  lines.push("HireWise Report");
  lines.push("");
  lines.push(`Verdict: ${latestAnalysis.verdict.label}`);
  lines.push(`Confidence Score: ${latestAnalysis.confidenceScore}`);
  lines.push(`Detected Email: ${latestAnalysis.detectedEmail || "Not found"}`);
  lines.push(`Detected Domain: ${latestAnalysis.detectedDomain || "Not found"}`);
  lines.push(`Risk Summary: ${getRiskSummary(latestAnalysis.confidenceScore)}`);
  lines.push("");

  lines.push("Detected Red Flags:");
  if (latestAnalysis.flags && latestAnalysis.flags.length > 0) {
    latestAnalysis.flags.forEach((flag, index) => {
      lines.push(`${index + 1}. ${flag.title}`);
      lines.push(`   ${flag.detail}`);
      lines.push("");
    });
  } else {
    lines.push("No major red flags detected.");
    lines.push("");
  }

  lines.push("AI Review:");
  lines.push(latestAnalysis.aiReview || "No AI review available.");
  lines.push("");

  lines.push("Verification Message:");
  lines.push(latestAnalysis.verificationMessage);

  let y = 20;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.text("HireWise Report", 14, y);
  y += 10;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  const wrapped = doc.splitTextToSize(lines.join("\n"), 180);
  doc.text(wrapped, 14, y);
  doc.save("hirewise-report.pdf");
});

resetBtn.addEventListener("click", () => {
  offerText.value = "";
  resultsSection.classList.add("hidden");
  verdictBanner.className = "verdict-banner";
  scoreValue.className = "score-value";
  scoreValue.textContent = "--";
  scoreFill.className = "meter-fill";
  scoreFill.style.width = "0%";
  scoreLabel.textContent = "Waiting for analysis...";
  flagsList.innerHTML = "";
  verificationMessage.value = "";
  if (aiReviewMessage) {
    aiReviewMessage.value = "";
  }
  detectedEmailValue.textContent = "—";
  detectedDomainValue.textContent = "—";
  riskSummaryValue.textContent = "—";
  copyStatus.textContent = "";
  latestAnalysis = null;
  offerText.focus();
});

setTheme("dark");
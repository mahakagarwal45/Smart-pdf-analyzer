const form = document.getElementById("uploadForm");
const progress = document.getElementById("progressArea");
const result = document.getElementById("resultSummary");
const dashboard = document.getElementById("dashboardArea");
const qaSection = document.getElementById("qaSection");

// ===================== FORM SUBMIT =====================
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const fileInput = document.getElementById("pdfFile");
  const persona = document.getElementById("persona").value;
  const top_k = document.getElementById("top_k").value;

  if (!fileInput.files.length) {
    alert("Please upload a PDF first!");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("persona", persona);
  formData.append("top_k", top_k);

  progress.classList.remove("hidden");
  result.classList.add("hidden");
  if (dashboard) dashboard.classList.add("hidden");
  qaSection.classList.add("hidden");
  document.getElementById("progressText").innerText = "Processing your document...";

  try {
    const res = await fetch("/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      alert("Error: " + (data.error || "Unknown error"));
      progress.classList.add("hidden");
      return;
    }

    document.getElementById("uidInput").value = data.uid;
    document.getElementById("summaryText").innerText = data.summary || "No summary generated.";

    document.getElementById("downloadLink").href = data.download_url;

    result.classList.remove("hidden");
    qaSection.classList.remove("hidden");
    progress.classList.add("hidden");

    // ===== Dashboard Chart =====
    if (dashboard) {
      // Show chart
      dashboard.classList.remove("hidden");
      const ctx = document.getElementById("pageChart").getContext("2d");

      // Define all possible colors
      const allColors = ["#f84949ff", "#f89545ff", "#fdd740ff", "#42e67eff", "#93c5fd"];
      const allLabels = ["Red", "Orange", "Yellow", "Green", "Blue"];

      // Trim colors based on top_k (so if top_k = 3, only 3 colors show)
      const k = parseInt(document.getElementById("top_k").value) || 3;
      const colors = allColors.slice(0, k);
      const labels = allLabels.slice(0, k);

      // Make dummy stats if backend doesn’t provide color_stats
      const colorStats = data.hits ? data.hits.slice(0, k).map(() => 1) : new Array(k).fill(1);

      // Destroy previous chart instance if it exists
      if (window.currentChart) {
        window.currentChart.destroy();
      }

      window.currentChart = new Chart(ctx, {
        type: "pie",
        data: {
          labels: labels,
          datasets: [{
          label: "Top " + k + " Highlight Distribution",
          data: colorStats,
          backgroundColor: colors,
          borderWidth: 1
        }]
      },
        options: {
          responsive: true,
          plugins: {
            legend: {
              position: "top",
              labels: { color: "#333", font: { size: 14 } }
            },
            tooltip: { enabled: true }
         }
        }
    });


    }


    // ===== Search Feature =====
    const searchBox = document.getElementById("searchBox");
    const resultList = document.getElementById("searchResults");
    if (searchBox && resultList && data.hits) {
      searchBox.addEventListener("input", e => {
        const q = e.target.value.toLowerCase();
        resultList.innerHTML = "";
        data.hits.filter(h => h.text.toLowerCase().includes(q)).forEach(h => {
          const li = document.createElement("li");
          li.innerText = `[Pg ${h.page}] ${h.text.slice(0, 80)}...`;
          resultList.appendChild(li);
        });
      });
    }

    // ===== PDF Preview =====
    const preview = document.getElementById("previewFrame");
    if (preview) {
      preview.src = data.download_url;
      preview.classList.remove("hidden");
    }

  } catch (err) {
    alert("Request failed: " + err.message);
  }
});

// ===================== HELP MODAL =====================
document.addEventListener("DOMContentLoaded", () => {
  const helpBtn = document.getElementById("helpBtn");
  const helpModal = document.getElementById("helpModal");
  const closeHelp = document.getElementById("closeHelp");

  if (helpBtn && helpModal && closeHelp) {
    helpBtn.addEventListener("click", () => helpModal.classList.remove("hidden"));
    closeHelp.addEventListener("click", () => helpModal.classList.add("hidden"));
    window.addEventListener("click", (event) => {
      if (event.target === helpModal) helpModal.classList.add("hidden");
    });
  }
});

// ===================== Q&A SECTION =====================
document.addEventListener("DOMContentLoaded", () => {
  const askBtn = document.getElementById("askBtn");
  const questionInput = document.getElementById("questionInput");
  const answerText = document.getElementById("answerText");
  const sourceList = document.getElementById("sourceList");
  const qaResult = document.getElementById("qaResult");
  const uidInput = document.getElementById("uidInput");

  if (!askBtn) return;

  askBtn.addEventListener("click", async () => {
    const question = questionInput.value.trim();
    const uid = uidInput.value.trim();
    if (!question || !uid) {
      alert("Please enter a question after processing the PDF.");
      return;
    }

    askBtn.disabled = true;
    askBtn.innerText = "⏳ Asking...";

    try {
      const res = await fetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uid, question, top_k: 5 })
      });
      const data = await res.json();

      if (data.error) {
        alert("Error: " + data.error);
      } else {
        qaResult.classList.remove("hidden");
        answerText.innerText = data.answer || "No answer found.";
        sourceList.innerHTML = "";
        if (data.sources) {
          data.sources.forEach(s => {
            const li = document.createElement("li");
            li.textContent = `[Pg ${s.page}] ${s.snippet}`;
            sourceList.appendChild(li);
          });
        }
      }
    } catch (err) {
      alert("Request failed: " + err.message);
    } finally {
      askBtn.disabled = false;
      askBtn.innerText = "🔍 Ask";
    }
  });
});

// ===================== ONBOARDING TUTORIAL =====================
function startTutorial() {
  introJs().setOptions({
    steps: [
      { intro: "Welcome to Smart PDF Analyzer!" },
      { element: "#pdfFile", intro: "Upload your PDF here" },
      { element: "#persona", intro: "Describe your research goal/persona" },
      { element: "#processBtn", intro: "Click to process your document" },
      { element: "#qaSection", intro: "Ask questions about your analyzed PDF" }
    ],
    showProgress: true,
    showSkipButton: true
  }).start();
}
// --- Word limit for persona ---
const personaInput = document.getElementById('persona');
const personaCount = document.getElementById('personaCount');

personaInput.addEventListener('input', () => {
  const words = personaInput.value.trim().split(/\s+/).filter(Boolean);
  personaCount.textContent = `${words.length} / 100 words`;

  if (words.length > 100) {
    personaCount.style.color = 'red';
    personaInput.value = words.slice(0, 100).join(' ');
  } else {
    personaCount.style.color = '#1e293b';
  }
});

// --- Enforce top_k limit ---
const topkInput = document.getElementById('top_k');
topkInput.addEventListener('input', () => {
  if (parseInt(topkInput.value) > 5) topkInput.value = 5;
});


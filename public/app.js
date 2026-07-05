const form = document.getElementById("listing-form");
const submitBtn = document.getElementById("submit-btn");
const resetBtn = document.getElementById("reset-btn");
const copyAllBtn = document.getElementById("copy-all-btn");
const errorMessage = document.getElementById("error-message");
const resultsSection = document.getElementById("results");
const resultTitle = document.getElementById("result-title");
const resultDescription = document.getElementById("result-description");
const resultTags = document.getElementById("result-tags");

let listingData = { title: "", description: "", tags: "" };

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function hideError() {
  errorMessage.hidden = true;
  errorMessage.textContent = "";
}

function showResults(data) {
  listingData = data;
  resultTitle.textContent = data.title;
  resultDescription.textContent = data.description;
  resultTags.textContent = data.tags;
  resultsSection.hidden = false;
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetForm() {
  form.reset();
  form.fileType.selectedIndex = 0;
  listingData = { title: "", description: "", tags: "" };
  resultsSection.hidden = true;
  hideError();
  form.productName.focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function formatAllListing(data) {
  return `TITLE:\n${data.title}\n\nDESCRIPTION:\n${data.description}\n\nTAGS:\n${data.tags}`;
}

async function copyText(text, button, labels = { default: "Copy", success: "Copied!" }) {
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = labels.success;
    button.classList.add("copied");
    setTimeout(() => {
      button.textContent = labels.default;
      button.classList.remove("copied");
    }, 2000);
  } catch {
    button.textContent = "Failed";
    setTimeout(() => {
      button.textContent = labels.default;
    }, 2000);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideError();

  const productName = form.productName.value.trim();
  const productDescription = form.productDescription.value.trim();
  const fileType = form.fileType.value;

  submitBtn.disabled = true;
  submitBtn.textContent = "Generating…";

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ productName, productDescription, fileType }),
    });

    const data = await response.json();

    if (!response.ok) {
      showError(data.error || "Something went wrong. Please try again.");
      return;
    }

    showResults(data);
  } catch {
    showError("Could not reach the server. Please try again.");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Generate My Listing";
  }
});

document.querySelectorAll(".btn-copy").forEach((button) => {
  button.addEventListener("click", () => {
    if (button.id === "copy-all-btn") {
      copyText(formatAllListing(listingData), button, {
        default: "Copy All",
        success: "Copied!",
      });
      return;
    }

    const key = button.dataset.copy;
    copyText(listingData[key], button);
  });
});

resetBtn.addEventListener("click", resetForm);

document.addEventListener("DOMContentLoaded", function () {
  const checkAll = document.getElementById("check-all");
  const individualCheckboxes = document.querySelectorAll(".check-individual");
  const importButton = document.getElementById("import-selected");

  // Check All functionality
  if (checkAll) {
    checkAll.addEventListener("change", function () {
      individualCheckboxes.forEach((checkbox) => {
        checkbox.checked = this.checked;
      });
      updateCounter();
    });
  }

  // Individual checkbox functionality
  individualCheckboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", updateCounter);
  });

  // Bulk import functionality
  if (importButton) {
    importButton.addEventListener("click", function () {
      const checkedIssues = Array.from(
        document.querySelectorAll(".check-individual:checked")
      );
      const issueIds = checkedIssues.map((checkbox) =>
        checkbox.getAttribute("data-issue-id")
      );
      const issueTitles = checkedIssues.map((checkbox) =>
        checkbox.getAttribute("data-issue-title")
      );

      if (confirm(`Import ${issueIds.length} selected issues to YouTrack?`)) {
        importBulkIssues(issueIds, issueTitles);
      }
    });
  }

  // Initial counter update
  updateCounter();
});

// Toggle token visibility
function toggleTokenVisibility() {
  const tokenInput = document.getElementById("token-display");
  const toggleBtn = document.querySelector(".btn-toggle");

  if (tokenInput.type === "password") {
    tokenInput.type = "text";
    toggleBtn.textContent = "Hide";
  } else {
    tokenInput.type = "password";
    toggleBtn.textContent = "Show";
  }
}
// Check All functionality with counter
function updateCounter() {
  const checkedBoxes = document.querySelectorAll(".check-individual:checked");
  const totalBoxes = document.querySelectorAll(".check-individual");
  const counter = document.getElementById("checked-counter");
  const importCount = document.getElementById("import-count");
  const importButton = document.getElementById("import-selected");

  const checkedCount = checkedBoxes.length;
  counter.textContent = checkedCount;
  importCount.textContent = checkedCount;

  // Enable/disable bulk import button
  importButton.disabled = checkedCount === 0;

  // Update check-all checkbox state
  const checkAll = document.getElementById("check-all");
  if (checkAll) {
    checkAll.checked =
      checkedCount === totalBoxes.length && totalBoxes.length > 0;
    checkAll.indeterminate =
      checkedCount > 0 && checkedCount < totalBoxes.length;
  }
}
// Single issue import
function importSingleIssue(issueId, issueTitle) {
  if (confirm(`Import issue #${issueId}: "${issueTitle}" to YouTrack?`)) {
    fetch("/import-issue/" + issueId, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    })
      .then((response) => response.json())
      .then((data) => {
        alert(data.message || `Issue #${issueId} imported successfully!`);
      })
      .catch((error) => {
        console.error("Error:", error);
        alert("Error importing issue");
      });
  }
}

// Bulk issues import
function importBulkIssues(issueIds, issueTitles) {
  fetch("/import-bulk-issues", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      issue_ids: issueIds,
      issue_titles: issueTitles,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      alert(`Successfully imported ${data.imported_count} issues!`);
      // Uncheck all boxes after import
      document.querySelectorAll(".check-individual").forEach((checkbox) => {
        checkbox.checked = false;
      });
      updateCounter();
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("Error importing issues");
    });
}

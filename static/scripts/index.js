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
// Sync functionality
function syncAllIssues() {
  const btn = document.getElementById("sync-all-issues");
  const progress = document.getElementById("sync-progress");
  const progressFill = document.getElementById("progress-fill");
  const progressText = document.getElementById("progress-text");
  const results = document.getElementById("sync-results");

  btn.disabled = true;
  progress.style.display = "block";
  results.innerHTML = "<p>Starting synchronization...</p>";

  // Reset progress
  progressFill.style.width = "0%";
  progressText.textContent = "Starting sync...";

  fetch("/sync-issues", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      displaySyncResults(data);
      updateProgress(100, "Sync completed");

      // Update individual issue statuses
      if (data.results) {
        data.results.forEach((result) => {
          updateIssueSyncStatus(
            result.github_number,
            result.status,
            result.message
          );
        });
      }
    })
    .catch((error) => {
      results.innerHTML = `<div class="sync-result-item error">Error: ${error.message}</div>`;
      updateProgress(0, "Sync failed");
      console.error("Sync error:", error);
    })
    .finally(() => {
      setTimeout(() => {
        btn.disabled = false;
        progress.style.display = "none";
      }, 2000);
    });
}

function syncSingleIssue(issueNumber, issueTitle) {
  const issueElement = document.querySelector(
    `[data-issue-id="${issueNumber}"]`
  );
  const syncStatus = document.getElementById(`sync-status-${issueNumber}`);
  const syncButton = issueElement.querySelector(".btn-sync-single");

  // Update UI to show syncing state
  issueElement.classList.add("syncing");
  syncStatus.innerHTML = '<span class="sync-status syncing">Syncing...</span>';
  syncButton.disabled = true;
  syncButton.textContent = "Syncing...";

  fetch(`/sync-issue/${issueNumber}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      let statusClass = "error";
      let statusText = "Error";

      if (data.results && data.results.length > 0) {
        const result = data.results[0];
        statusClass = result.status;
        statusText = result.status
          .replace("_", " ")
          .replace(/\b\w/g, (l) => l.toUpperCase());

        // Show notification
        showNotification(
          `Issue #${issueNumber} sync: ${statusText}`,
          statusClass
        );
      }

      updateIssueSyncStatus(
        issueNumber,
        statusClass,
        data.message || "Sync completed"
      );
    })
    .catch((error) => {
      updateIssueSyncStatus(
        issueNumber,
        "error",
        `Sync failed: ${error.message}`
      );
      showNotification(`Failed to sync issue #${issueNumber}`, "error");
      console.error("Single issue sync error:", error);
    })
    .finally(() => {
      issueElement.classList.remove("syncing");
      syncButton.disabled = false;
      syncButton.textContent = "Sync Now";
    });
}

function checkSyncStatus() {
  const btn = document.getElementById("check-sync-status");
  const results = document.getElementById("sync-results");

  btn.disabled = true;
  results.innerHTML = "<p>Checking sync status...</p>";

  // This would need a new endpoint to check status without syncing
  // For now, we'll use the sync endpoint but show status only
  fetch("/sync-issues", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      displaySyncStatus(data);
    })
    .catch((error) => {
      results.innerHTML = `<div class="sync-result-item error">Error checking status: ${error.message}</div>`;
      console.error("Status check error:", error);
    })
    .finally(() => {
      btn.disabled = false;
    });
}

function displaySyncResults(data) {
  const results = document.getElementById("sync-results");

  if (data.error) {
    results.innerHTML = `<div class="sync-result-item error">Error: ${data.error}</div>`;
    return;
  }

  let html = `
        <div class="sync-summary">
            <h3>Sync Summary</h3>
            <p>Total checked: ${data.total_checked || data.results.length} | 
               Updated: ${data.synced || 0} | 
               Errors: ${data.errors || 0}</p>
        </div>
    `;

  if (data.results && data.results.length > 0) {
    data.results.forEach((result) => {
      const statusClass = result.status || "unknown";
      html += `
                <div class="sync-result-item ${statusClass}">
                    <strong>Issue #${result.github_number}</strong> (YT: ${
        result.youtrack_id
      })<br>
                    Status: ${statusClass.replace("_", " ")}<br>
                    ${result.message ? `Message: ${result.message}` : ""}
                    ${
                      result.github_updated
                        ? `<br>GitHub updated: ${new Date(
                            result.github_updated
                          ).toLocaleString()}`
                        : ""
                    }
                </div>
            `;
    });
  } else {
    html += "<p>No results to display.</p>";
  }

  results.innerHTML = html;
}

function displaySyncStatus(data) {
  const results = document.getElementById("sync-results");

  let html = "<h3>Sync Status Report</h3>";

  if (data.results && data.results.length > 0) {
    const statusCounts = {};
    data.results.forEach((result) => {
      const status = result.status || "unknown";
      statusCounts[status] = (statusCounts[status] || 0) + 1;
    });

    html += '<div class="status-summary">';
    for (const [status, count] of Object.entries(statusCounts)) {
      html += `<span class="status-badge ${status}">${status}: ${count}</span> `;
    }
    html += "</div>";

    data.results.forEach((result) => {
      const statusClass = result.status || "unknown";
      html += `
                <div class="sync-result-item ${statusClass}">
                    <strong>Issue #${
                      result.github_number
                    }</strong>: ${statusClass.replace("_", " ")}
                    ${result.message ? ` - ${result.message}` : ""}
                </div>
            `;
    });
  } else {
    html += "<p>No sync status information available.</p>";
  }

  results.innerHTML = html;
}

function updateIssueSyncStatus(issueNumber, status, message) {
  const syncStatus = document.getElementById(`sync-status-${issueNumber}`);
  const issueElement = document.querySelector(
    `[data-issue-id="${issueNumber}"]`
  );

  if (!syncStatus) return;

  const statusClass = status.replace("_", "-");
  const statusText = status
    .replace("_", " ")
    .replace(/\b\w/g, (l) => l.toUpperCase());

  syncStatus.innerHTML = `<span class="sync-status ${statusClass}" title="${message}">${statusText}</span>`;

  // Update issue card appearance
  issueElement.classList.remove("needs-update", "syncing", "in-sync");
  if (status === "needs_update" || status === "github_newer") {
    issueElement.classList.add("needs-update");
  } else if (status === "in_sync" || status === "up_to_date") {
    issueElement.classList.add("in-sync");
  }
}

function updateProgress(percent, text) {
  const progressFill = document.getElementById("progress-fill");
  const progressText = document.getElementById("progress-text");

  progressFill.style.width = percent + "%";
  progressText.textContent = text;
}

function showNotification(message, type = "info") {
  // Create notification element
  const notification = document.createElement("div");
  notification.className = `notification ${type}`;
  notification.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()">&times;</button>
    `;

  // Add styles if not already added
  if (!document.querySelector("#notification-styles")) {
    const styles = document.createElement("style");
    styles.id = "notification-styles";
    styles.textContent = `
            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px;
                border-radius: 5px;
                color: white;
                z-index: 1000;
                max-width: 300px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .notification.success { background-color: #28a745; }
            .notification.error { background-color: #dc3545; }
            .notification.info { background-color: #17a2b8; }
            .notification button {
                background: none;
                border: none;
                color: white;
                font-size: 18px;
                cursor: pointer;
                margin-left: 10px;
            }
        `;
    document.head.appendChild(styles);
  }

  document.body.appendChild(notification);

  // Auto-remove after 5 seconds
  setTimeout(() => {
    if (notification.parentElement) {
      notification.remove();
    }
  }, 5000);
}

document.addEventListener("DOMContentLoaded", function () {
  const syncAllBtn = document.getElementById("sync-all-issues");
  if (syncAllBtn) {
    syncAllBtn.addEventListener("click", syncAllIssues);
  }

  const checkStatusBtn = document.getElementById("check-sync-status");
  if (checkStatusBtn) {
    checkStatusBtn.addEventListener("click", checkSyncStatus);
  }
  window.syncSingleIssue = syncSingleIssue;
});

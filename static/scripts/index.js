// Add this script to your template
document.addEventListener("DOMContentLoaded", function () {
  const checkAll = document.getElementById("check-all");
  const individualCheckboxes = document.querySelectorAll(".check-individual");

  // Check All functionality
  if (checkAll) {
    checkAll.addEventListener("change", function () {
      individualCheckboxes.forEach((checkbox) => {
        checkbox.checked = this.checked;
      });
    });
  }

  // Individual checkbox logic (uncheck "Check All" if any individual is unchecked)
  individualCheckboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", function () {
      if (!this.checked) {
        checkAll.checked = false;
      } else {
        // Check if all individual boxes are checked
        const allChecked = Array.from(individualCheckboxes).every(
          (cb) => cb.checked
        );
        checkAll.checked = allChecked;
      }
    });
  });
});

// stellaris-studio/src/js/ui.js
/**
 * All general UI interactions.
 */

export function initUI() {
  // Smooth scrolling for anchor links (if any)
  // Add active class to header on scroll
  // etc.
  // For this mock, we'll just log that it's initialized.
  console.log(
    "UI Initialized: Event listeners for buttons, etc. would go here.",
  );

  const ctaButton = document.querySelector(".c-cta-button");
  if (ctaButton) {
    ctaButton.addEventListener("click", () => {
      window.location.href = "contact.html";
    });
  }
}

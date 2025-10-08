/* script.js */
document.addEventListener("DOMContentLoaded", function () {
  // --- Mobile Navigation Toggle ---
  const mobileNavToggle = document.querySelector(".mobile-nav-toggle");
  const mainNav = document.querySelector(".main-nav");
  if (mobileNavToggle) {
    // This is a placeholder for a full mobile menu implementation.
    // For this mock, it just adds a class to the button.
    mobileNavToggle.addEventListener("click", () => {
      mobileNavToggle.classList.toggle("is-active");
      // A real implementation would show/hide a mobile menu here.
      console.log("Mobile nav toggled. Implement menu display logic.");
    });
  }

  // --- Pricing Toggle (Monthly/Annual) ---
  const billingToggle = document.getElementById("billing-toggle");
  if (billingToggle) {
    billingToggle.addEventListener("change", function () {
      if (this.checked) {
        document.body.classList.add("show-annual");
      } else {
        document.body.classList.remove("show-annual");
      }
    });
  }

  // --- FAQ Accordion ---
  const faqItems = document.querySelectorAll(".faq-item");
  faqItems.forEach((item) => {
    const question = item.querySelector(".faq-question");
    const answer = item.querySelector(".faq-answer");

    question.addEventListener("click", () => {
      const isActive = item.classList.contains("active");

      // Close all other items
      faqItems.forEach((otherItem) => {
        otherItem.classList.remove("active");
        otherItem.querySelector(".faq-answer").style.maxHeight = 0;
      });

      // Open the clicked item if it wasn't already active
      if (!isActive) {
        item.classList.add("active");
        answer.style.maxHeight = answer.scrollHeight + "px";
      }
    });
  });

  // --- Scroll Animations ---
  const animatedElements = document.querySelectorAll(".animate-on-scroll");

  if (animatedElements.length > 0) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target); // Optional: stop observing once visible
          }
        });
      },
      {
        threshold: 0.1, // Trigger when 10% of the element is visible
      },
    );

    animatedElements.forEach((el) => {
      observer.observe(el);
    });
  }
});

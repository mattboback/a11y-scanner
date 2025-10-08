// stellaris-studio/src/js/animations.js
/**
 * All GSAP-based animations for the site.
 */

// Preloader Animation
export function initPreloader() {
  const preloader = document.querySelector(".c-preloader");
  if (!preloader) return;

  gsap.to(preloader, {
    duration: 1.5,
    opacity: 0,
    delay: 2,
    ease: "power2.inOut",
    onComplete: () => {
      preloader.style.display = "none";
    },
  });

  gsap.from(".c-preloader__text", {
    duration: 1,
    y: 30,
    opacity: 0,
    delay: 0.5,
    ease: "power2.out",
  });
}

// Scroll-triggered Animations
export function initScrollAnimations() {
  gsap.registerPlugin(ScrollTrigger);

  // Hero title line reveal
  gsap.from(".c-hero__title .line", {
    y: 100,
    opacity: 0,
    duration: 1,
    stagger: 0.2,
    ease: "power3.out",
    delay: 2.5, // Wait for preloader
  });

  // General section title reveal
  document.querySelectorAll("[data-reveal]").forEach((elem) => {
    gsap.from(elem, {
      scrollTrigger: {
        trigger: elem,
        start: "top 80%",
      },
      y: 50,
      opacity: 0,
      duration: 1,
      ease: "power3.out",
    });
  });
}

// Parallax effect for showcase images
export function initParallax() {
  gsap.utils.toArray("[data-parallax-speed]").forEach((section) => {
    const image = section.querySelector("img");
    const speed = parseFloat(section.dataset.parallaxSpeed) || 0.1;

    gsap.to(image, {
      y: (i, target) => -ScrollTrigger.maxScroll(window) * speed,
      ease: "none",
      scrollTrigger: {
        trigger: "body",
        start: "top top",
        end: "bottom bottom",
        scrub: 1.5,
      },
    });
  });
}

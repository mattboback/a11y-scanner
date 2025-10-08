// stellaris-studio/src/js/main.js
import {
  initPreloader,
  initScrollAnimations,
  initParallax,
} from "./animations.js";
import { initUI } from "./ui.js";

document.addEventListener("DOMContentLoaded", () => {
  // Initialize all UI components
  initUI();

  // Initialize all animations
  initPreloader();
  initScrollAnimations();
  initParallax();
});


//utils.js:

// Utility functions
const utils = {
  // Format price with currency symbol
  formatPrice: function(price) {
    return '$' + parseFloat(price).toFixed(2);
  },
  
  // Get element by ID with error handling
  getElement: function(id) {
    const element = document.getElementById(id);
    if (!element) {
      console.error(`Element with ID "${id}" not found`);
      return null;
    }
    return element;
  },
  
  // Simple event handler helper
  addEvent: function(element, eventType, handler) {
    if (element) {
      element.addEventListener(eventType, handler);
    }
  },
  
  // Toggle visibility of an element
  toggleVisibility: function(element, isVisible) {
    if (element) {
      element.style.display = isVisible ? 'flex' : 'none';
    }
  }
};

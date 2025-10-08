
//script.js:

// Main script - depends on utils.js and cart.js
document.addEventListener('DOMContentLoaded', function() {
  // Initialize preview modal functionality
  initPreviewModal();
  
  // Initialize price filter
  initPriceFilter();
  
  // Initialize category filter
  initCategoryFilter();
  
  // Add keyboard accessibility
  enhanceKeyboardAccessibility();
});

function initPreviewModal() {
  const previewButtons = document.querySelectorAll('.preview-btn');
  const modal = document.querySelector('.book-preview-modal');
  const closeButton = modal.querySelector('.close-modal');
  
  // Open modal on preview button click
  previewButtons.forEach(button => {
    button.addEventListener('click', function() {
      const bookCard = this.closest('.book-card');
      if (bookCard) {
        openBookPreview(bookCard, modal);
      }
    });
  });
  
  // Close modal when close button is clicked
  closeButton.addEventListener('click', function() {
    utils.toggleVisibility(modal, false);
  });
  
  // Close modal when clicking outside of content
  modal.addEventListener('click', function(event) {
    if (event.target === modal) {
      utils.toggleVisibility(modal, false);
    }
  });
  
  // Close modal on ESC key press
  document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape' && modal.style.display === 'flex') {
      utils.toggleVisibility(modal, false);
    }
  });
}

function openBookPreview(bookCard, modal) {
  // Get book information
  const image = bookCard.querySelector('img');
  const title = bookCard.querySelector('h2').textContent;
  const author = bookCard.querySelector('.author').textContent;
  
  // Update modal content
  const previewImage = utils.getElement('preview-image');
  const previewTitle = utils.getElement('preview-book-title');
  const previewAuthor = utils.getElement('preview-author');
  
  if (previewImage && image) {
    previewImage.src = image.src;
    previewImage.alt = image.alt || `${title} book cover`;
  }
  
  if (previewTitle) {
    previewTitle.textContent = title;
  }
  
  if (previewAuthor) {
    previewAuthor.textContent = author;
  }
  
  // Show modal
  utils.toggleVisibility(modal, true);
  
  // Focus the close button for keyboard accessibility
  const closeButton = modal.querySelector('.close-modal');
  if (closeButton) {
    closeButton.focus();
  }
}

function initPriceFilter() {
  const priceFilter = utils.getElement('price-filter');
  const priceValue = utils.getElement('price-value');
  
  if (priceFilter && priceValue) {
    priceFilter.addEventListener('input', function() {
      priceValue.textContent = this.value;
    });
  }
  
  // Apply button functionality
  const filterButton = document.querySelector('.filter-button');
  if (filterButton) {
    filterButton.addEventListener('click', applyFilters);
  }
}

function initCategoryFilter() {
  const categoryFilter = utils.getElement('category-filter');
  
  if (categoryFilter) {
    categoryFilter.addEventListener('change', function() {
      // We'll apply filters on button click, not on change
    });
  }
}

function applyFilters() {
  const categoryFilter = utils.getElement('category-filter');
  const priceFilter = utils.getElement('price-filter');
  
  if (!categoryFilter || !priceFilter) return;
  
  const selectedCategory = categoryFilter.value;
  const maxPrice = parseInt(priceFilter.value);
  
  alert(`Filters applied: Category - ${selectedCategory || 'All'}, Max Price - $${maxPrice}`);
  
  // In a real application, we would filter the book display
  // This is just a mockup, so we'll show an alert instead
}

function enhanceKeyboardAccessibility() {
  // Make cart icon properly focusable
  const cartIcon = document.querySelector('.cart-icon');
  if (cartIcon) {
    cartIcon.setAttribute('tabindex', '0');
    cartIcon.addEventListener('keydown', function(event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        this.click();
      }
    });
  }
  
  // Ensure all interactive elements can be accessed via keyboard
  const interactiveElements = document.querySelectorAll('button, a, select, input');
  interactiveElements.forEach(element => {
    element.addEventListener('focus', function() {
      this.style.outline = '2px solid #0066cc';
    });
    
    element.addEventListener('blur', function() {
      this.style.outline = '';
    });
  });
}








/*cart.js:*/

// Cart functionality - depends on utils.js
class ShoppingCart {
  constructor() {
    this.items = [];
    this.cartCount = document.querySelector('.cart-count');
    this.bindEvents();
  }
  
  bindEvents() {
    // Add event listeners to all "Add to Cart" buttons
    const addToCartButtons = document.querySelectorAll('.add-to-cart-btn');
    addToCartButtons.forEach(button => {
      utils.addEvent(button, 'click', (event) => {
        this.addToCart(event.target.closest('.book-card'));
      });
    });
    
    // Add event listener to cart icon
    const cartIcon = document.querySelector('.cart-icon');
    utils.addEvent(cartIcon, 'click', () => {
      alert('Cart functionality coming soon!');
    });
  }
  
  addToCart(bookCard) {
    if (!bookCard) return;
    
    // Extract book information
    const title = bookCard.querySelector('h2').textContent;
    const priceText = bookCard.querySelector('.price').textContent;
    const price = parseFloat(priceText.replace('$', ''));
    
    // Add to cart array
    this.items.push({
      title: title,
      price: price
    });
    
    // Update cart count
    this.updateCartCount();
    
    // Give feedback to user
    alert(`"${title}" added to cart!`);
  }
  
  updateCartCount() {
    if (this.cartCount) {
      this.cartCount.textContent = this.items.length;
    }
  }
  
  getTotal() {
    return this.items.reduce((total, item) => total + item.price, 0);
  }
}

// Initialize cart when DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
  window.cart = new ShoppingCart();
});

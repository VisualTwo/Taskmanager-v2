/**
 * Toast Notifications Module
 * Handles success, error, and info notifications
 */

class ToastNotifications {
  constructor() {
    this.init();
  }

  init() {
    // No initial bindings needed
  }

  show(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  success(message) {
    this.show(message, 'success');
  }

  error(message) {
    this.show(message, 'error');
  }

  info(message) {
    this.show(message, 'info');
  }
}

// Global instance
window.toast = new ToastNotifications();
window.showToast = (message, type) => window.toast.show(message, type);
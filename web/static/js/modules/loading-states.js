/**
 * Loading States Module
 * Handles loading indicators and auto-save states
 */

class LoadingStates {
  constructor() {
    this.init();
  }

  init() {
    this.bindHTMXEvents();
  }

  bindHTMXEvents() {
    document.addEventListener('htmx:beforeRequest', (e) => {
      const el = e.target;
      
      // Add loading indicator to buttons
      if (el.matches('button:not(.no-loading)')) {
        const originalText = el.textContent;
        el.dataset.originalText = originalText;
        el.innerHTML = originalText + ' <span class="loading-indicator"></span>';
        el.disabled = true;
      }
      
      // Show auto-save indicator for inputs
      if (el.matches('input[name="name"], select')) {
        const indicator = el.parentElement.querySelector('.auto-save-indicator') || this.createAutoSaveIndicator(el);
        indicator.textContent = 'Speichern...';
        indicator.classList.add('show');
      }
    });

    document.addEventListener('htmx:afterRequest', (e) => {
      const el = e.target;
      
      // Remove loading indicator from buttons
      if (el.matches('button') && el.dataset.originalText) {
        el.textContent = el.dataset.originalText;
        el.disabled = false;
        delete el.dataset.originalText;
      }
      
      // Update auto-save indicator
      const indicator = el.parentElement?.querySelector('.auto-save-indicator');
      if (indicator) {
        if (e.detail.xhr.status >= 200 && e.detail.xhr.status < 300) {
          indicator.textContent = 'Gespeichert';
          setTimeout(() => indicator.classList.remove('show'), 2000);
        } else {
          indicator.textContent = 'Fehler beim Speichern';
          indicator.style.color = '#ef4444';
          setTimeout(() => {
            indicator.classList.remove('show');
            indicator.style.color = '';
          }, 3000);
        }
      }
    });
  }

  createAutoSaveIndicator(element) {
    const indicator = document.createElement('span');
    indicator.className = 'auto-save-indicator';
    element.parentElement.appendChild(indicator);
    return indicator;
  }
}

window.LoadingStates = LoadingStates;
/**
 * Keyboard Shortcuts Module
 * Handles global keyboard shortcuts and navigation
 */

class KeyboardShortcuts {
  constructor(modalDialogs) {
    this.modalDialogs = modalDialogs;
    this.init();
  }

  init() {
    this.bindGlobalShortcuts();
    this.bindUIKeyboardSupport();
  }

  bindGlobalShortcuts() {
    document.addEventListener('keydown', (e) => {
      // Show shortcuts help
      if (e.key === '?' && !e.target.matches('input, textarea')) {
        e.preventDefault();
        this.modalDialogs.showShortcutsHelp();
        return;
      }
      
      // Ctrl+L: Add link to focused row
      if (e.ctrlKey && e.key === 'l' && !e.target.matches('input, textarea')) {
        e.preventDefault();
        const row = e.target.closest('tr');
        const addBtn = row?.querySelector('.add-link');
        if (addBtn) addBtn.click();
      }
      
      // Ctrl+T: Add tag to focused row
      if (e.ctrlKey && e.key === 't' && !e.target.matches('input, textarea')) {
        e.preventDefault();
        const row = e.target.closest('tr');
        const addBtn = row?.querySelector('.add-tag-btn');
        if (addBtn) addBtn.click();
      }
    });
  }

  bindUIKeyboardSupport() {
    // Status & Priority: Keyboard-Support (kombiniert)
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      
      const statusBadge = e.target.closest('.status-badge');
      if (statusBadge) {
        e.preventDefault();
        statusBadge.click();
        return;
      }
      
      const prioBadge = e.target.closest('.prio-badge');
      if (prioBadge) {
        e.preventDefault();
        prioBadge.click();
        return;
      }
    });
  }
}

window.KeyboardShortcuts = KeyboardShortcuts;
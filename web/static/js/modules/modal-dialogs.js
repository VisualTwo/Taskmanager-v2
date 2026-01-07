/**
 * Modal Dialogs Module
 * Handles confirmation dialogs and keyboard shortcuts help
 */

class ModalDialogs {
  constructor() {
    this.init();
  }

  init() {
    this.bindDeleteConfirmation();
  }

  showConfirmDialog(message, onConfirm, onCancel) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    
    const dialog = document.createElement('div');
    dialog.className = 'modal-dialog';
    
    dialog.innerHTML = `
      <h3 class="modal-title">Bestätigung</h3>
      <p>${message}</p>
      <div class="modal-buttons">
        <button type="button" class="btn btn-secondary cancel-btn">Abbrechen</button>
        <button type="button" class="btn btn-danger confirm-btn">Bestätigen</button>
      </div>
    `;
    
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
    
    const confirmBtn = dialog.querySelector('.confirm-btn');
    const cancelBtn = dialog.querySelector('.cancel-btn');
    
    confirmBtn.focus();
    
    const cleanup = () => {
      overlay.style.opacity = '0';
      setTimeout(() => overlay.remove(), 200);
    };
    
    confirmBtn.addEventListener('click', () => {
      cleanup();
      if (onConfirm) onConfirm();
    });
    
    cancelBtn.addEventListener('click', () => {
      cleanup();
      if (onCancel) onCancel();
    });
    
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        cleanup();
        if (onCancel) onCancel();
      }
    });
    
    document.addEventListener('keydown', function escapeHandler(e) {
      if (e.key === 'Escape') {
        cleanup();
        if (onCancel) onCancel();
        document.removeEventListener('keydown', escapeHandler);
      }
    });
  }

  showShortcutsHelp() {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    
    const dialog = document.createElement('div');
    dialog.className = 'shortcuts-help';
    
    dialog.innerHTML = `
      <h3>Keyboard Shortcuts</h3>
      <div class="shortcuts-grid">
        <span class="shortcut-key">Ctrl+L</span><span>Link hinzufügen</span>
        <span class="shortcut-key">Ctrl+T</span><span>Tag hinzufügen</span>
        <span class="shortcut-key">Enter/Space</span><span>Status/Priorität ändern</span>
        <span class="shortcut-key">Esc</span><span>Bearbeitung abbrechen</span>
        <span class="shortcut-key">?</span><span>Diese Hilfe anzeigen</span>
      </div>
      <div style="text-align: right; margin-top: 1rem;">
        <button type="button" class="btn btn-primary close-help">Schließen</button>
      </div>
    `;
    
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
    
    const closeBtn = dialog.querySelector('.close-help');
    closeBtn.focus();
    
    const cleanup = () => {
      overlay.style.opacity = '0';
      setTimeout(() => overlay.remove(), 200);
    };
    
    closeBtn.addEventListener('click', cleanup);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) cleanup();
    });
    
    document.addEventListener('keydown', function escapeHandler(e) {
      if (e.key === 'Escape') {
        cleanup();
        document.removeEventListener('keydown', escapeHandler);
      }
    });
  }

  bindDeleteConfirmation() {
    document.addEventListener('click', (e) => {
      const trigger = e.target.closest('.delete-trigger');
      if (trigger) {
        e.preventDefault();
        const wrap = trigger.closest('.delete-wrap');
        const itemName = wrap.closest('tr').querySelector('.name-link')?.textContent || 'diesen Eintrag';
        
        this.showConfirmDialog(
          `Möchten Sie "${itemName}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`,
          () => {
            const deleteBtn = wrap.querySelector('.do-delete');
            if (deleteBtn) deleteBtn.click();
          }
        );
        return;
      }
    });
  }
}

window.ModalDialogs = ModalDialogs;
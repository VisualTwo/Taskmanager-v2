/**
 * Main Application Module
 * Coordinates all UI modules and initializes the application
 */

class TaskManagerApp {
  constructor() {
    this.modules = {};
    this.init();
  }

  init() {
    // Initialize all modules
    this.modules.toastNotifications = new ToastNotifications();
    this.modules.modalDialogs = new ModalDialogs();
    this.modules.loadingStates = new LoadingStates();
    this.modules.uiInteractions = new UIInteractions();
    this.modules.tagsLinks = new TagsLinks();
    this.modules.keyboardShortcuts = new KeyboardShortcuts(this.modules.modalDialogs);

    // Global initialization
    this.initializeGlobalElements();
    
    console.log('Task Manager App initialized with modules:', Object.keys(this.modules));
  }

  initializeGlobalElements() {
    // Batch-Aktionen: "Alle auswählen" Checkbox
    const masterCheck = document.getElementById('select-all-items');
    if (masterCheck) {
      const itemChecks = Array.from(document.querySelectorAll('input[name="selected_items"]'));
      
      masterCheck.addEventListener('change', () => {
        itemChecks.forEach(cb => cb.checked = masterCheck.checked);
      });
      
      itemChecks.forEach(cb => {
        cb.addEventListener('change', () => {
          masterCheck.checked = itemChecks.every(c => c.checked);
          masterCheck.indeterminate = itemChecks.some(c => c.checked) && !itemChecks.every(c => c.checked);
        });
      });
    }

    // Sortierung: Click-Handler
    document.querySelectorAll('.sortable').forEach(th => {
      th.addEventListener('click', (e) => {
        e.preventDefault();
        const url = new URL(window.location);
        const col = th.dataset.sort;
        const currentSort = url.searchParams.get('sort_by');
        const currentDir = url.searchParams.get('sort_dir') || 'asc';
        
        if (currentSort === col && currentDir === 'asc') {
          url.searchParams.set('sort_dir', 'desc');
        } else {
          url.searchParams.set('sort_dir', 'asc');
        }
        url.searchParams.set('sort_by', col);
        
        window.location.href = url.toString();
      });
    });
  }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  window.taskManagerApp = new TaskManagerApp();
});
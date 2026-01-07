/**
 * UI Interactions Module
 * Handles status/priority toggles, inline editing, and form interactions
 */

class UIInteractions {
  constructor() {
    this.init();
  }

  init() {
    this.bindStatusToggle();
    this.bindPriorityToggle();
    this.bindInlineEdit();
    this.bindTimeEditing();
  }

  bindStatusToggle() {
    // Status: Badge -> Select
    document.addEventListener('click', (e) => {
      const badge = e.target.closest('.status-badge');
      if (!badge) return;
      e.preventDefault();
      const wrap = badge.closest('.status-wrap');
      const sel = wrap?.querySelector('.status-select');
      if (!sel) return;
      badge.classList.add('hidden');
      sel.classList.remove('hidden');
      sel.style.display = 'inline-block';
      sel.focus();
    });

    // Status: Select -> Badge (blur)
    document.addEventListener('blur', (e) => {
      const sel = e.target;
      if (!(sel.classList && sel.classList.contains('status-select'))) return;
      setTimeout(() => {
        if (document.activeElement === sel) return;
        const wrap = sel.closest('.status-wrap');
        const badge = wrap?.querySelector('.status-badge');
        sel.classList.add('hidden');
        sel.style.display = 'none';
        if (badge) badge.classList.remove('hidden');
      }, 0);
    }, true);
  }

  bindPriorityToggle() {
    // Priority: Badge -> Select
    document.addEventListener('click', (e) => {
      const badge = e.target.closest('.prio-badge');
      if (!badge) return;
      e.preventDefault();
      const wrap = badge.closest('.prio-wrap');
      const sel = wrap?.querySelector('.prio-select');
      if (!sel) return;
      badge.classList.add('hidden');
      sel.classList.remove('hidden');
      sel.style.display = 'inline-block';
      sel.focus();
    });

    // Priority: Select -> Badge (blur)
    document.addEventListener('blur', (e) => {
      const sel = e.target;
      if (!(sel.classList && sel.classList.contains('prio-select'))) return;
      setTimeout(() => {
        if (document.activeElement === sel) return;
        const wrap = sel.closest('.prio-wrap');
        const badge = wrap?.querySelector('.prio-badge');
        sel.classList.add('hidden');
        sel.style.display = 'none';
        if (badge) badge.classList.remove('hidden');
      }, 0);
    }, true);
  }

  bindInlineEdit() {
    // Inline-Edit Button Handler
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.inline-edit-btn');
      if (!btn) return;
      
      e.preventDefault();
      e.stopPropagation();
      
      const id = btn.getAttribute('data-for');
      const wrap = btn.closest('.name-wrap');
      const link = wrap.querySelector('.name-link');
      const input = document.getElementById(`name-${id}`);
      
      if (!input) return;
      
      link.style.display = 'none';
      btn.style.display = 'none';
      
      input.classList.remove('hidden');
      setTimeout(() => {
        input.focus();
        input.select();
      }, 0);
    });

    // Name Input Blur Handler
    document.addEventListener('blur', async (e) => {
      const input = e.target;
      if (!(input.classList && input.classList.contains('name-input'))) return;
      
      const val = input.value.trim();
      const wrap = input.closest('.name-wrap');
      const link = wrap?.querySelector('.name-link');
      const btn = wrap?.querySelector('.inline-edit-btn');
      
      if (!val) {
        input.value = input.getAttribute('data-current') || '';
        input.classList.add('hidden');
        if (link) link.style.display = '';
        if (btn) btn.style.display = '';
        return;
      }
      
      try {
        await htmx.ajax('POST', input.getAttribute('hx-post'), { 
          values: { name: val }, 
          swap: 'none' 
        });
        
        input.setAttribute('data-current', val);
        if (link) link.textContent = val;
      } catch (err) {
        console.error('Fehler beim Umbenennen:', err);
      } finally {
        input.classList.add('hidden');
        if (link) link.style.display = '';
        if (btn) btn.style.display = '';
      }
    }, true);

    // ESC-Taste schließt Inline-Edit ohne Speichern
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      
      const input = e.target;
      if (!(input.classList && input.classList.contains('name-input'))) return;
      
      input.value = input.getAttribute('data-current') || '';
      
      const wrap = input.closest('.name-wrap');
      const link = wrap?.querySelector('.name-link');
      const btn = wrap?.querySelector('.inline-edit-btn');
      
      input.classList.add('hidden');
      if (link) link.style.display = '';
      if (btn) btn.style.display = '';
    });
  }

  bindTimeEditing() {
    // Zeit-Inputs: Label->Input
    document.addEventListener('click', (e) => {
      const lab = e.target.closest('.time-label-inline');
      if (!lab) return;

      const wrap = lab.closest('.time-edit-wrap');
      if (!wrap) return;

      const input = wrap.querySelector('input.time-input');
      if (!input) return;

      lab.classList.add('hidden');
      input.classList.remove('hidden');

      this.initializeFlatpickr(input, lab, wrap);
    });

    // ESC schließt Zeit-Input
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      
      const inp = e.target;
      if (!(inp.classList && inp.classList.contains('time-input'))) return;
      
      if (inp._fp) inp._fp.close();
      
      const wrap = inp.closest('.time-edit-wrap');
      const lab = wrap?.querySelector('.time-label-inline');
      
      inp.classList.add('hidden');
      if (lab) lab.classList.remove('hidden');
    });
  }

  initializeFlatpickr(input, lab, wrap) {
    if (!window.flatpickr) return;

    if (input._fp) input._fp.destroy();
    
    const endpoint = input.getAttribute('data-endpoint');
    const paramName = input.getAttribute('data-param-name') || input.getAttribute('name');
    const targetSel = input.getAttribute('data-target');

    input._fp = flatpickr(input, {
      enableTime: true,
      time_24hr: true,
      dateFormat: "d.m.Y H:i",
      locale: "de",
      clickOpens: true,
      
      onClose: async function(selectedDates, dateStr, instance) {
        const val = dateStr.trim();
        if (!val) {
          input.classList.add('hidden');
          lab.classList.remove('hidden');
          return;
        }

        const isAppointmentOrEvent = wrap.closest('.time-inline-pair') !== null;
        
        try {
          if (isAppointmentOrEvent) {
            const pair = wrap.closest('.time-inline-pair');
            const startInput = pair.querySelector('input[data-param-name="start_local"]');
            const endInput = pair.querySelector('input[data-param-name="end_local"]');
            
            const values = {
              start_local: startInput?.value || '',
              end_local: endInput?.value || ''
            };
            
            await htmx.ajax('POST', endpoint, {
              values: values,
              target: targetSel || null,
              swap: targetSel ? 'innerHTML' : 'none'
            });
          } else {
            const values = {};
            values[paramName] = val;
            
            await htmx.ajax('POST', endpoint, {
              values: values,
              target: targetSel || null,
              swap: targetSel ? 'innerHTML' : 'none'
            });
          }

          lab.textContent = val;
          input.value = val;
        } catch (err) {
          console.error('Fehler beim Speichern:', err);
        } finally {
          input.classList.add('hidden');
          lab.classList.remove('hidden');
        }
      }
    });

    if (input._fp) {
      setTimeout(() => input._fp.open(), 10);
    } else {
      setTimeout(() => input.focus(), 0);
    }
  }

  // Status & Priority: Keyboard-Support
  bindKeyboardSupport() {
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

// Export for use in main app
window.UIInteractions = UIInteractions;
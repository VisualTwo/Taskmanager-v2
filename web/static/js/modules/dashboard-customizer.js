/**
 * Dashboard Customizer
 * Handles dashboard personalization and layout customization
 */

export class DashboardCustomizer {
    constructor() {
        this.isOpen = false;
        this.settings = {
            layout: 'default',
            widgets: {},
            theme: 'light'
        };
        this.loadSettings();
    }

    init() {
        this.bindEvents();
        this.applySettings();
    }

    bindEvents() {
        // Layout options
        document.addEventListener('click', (e) => {
            if (e.target.matches('.layout-option')) {
                this.handleLayoutChange(e.target);
            }
        });

        // Widget toggles
        document.addEventListener('change', (e) => {
            if (e.target.matches('.widget-toggle input[type="checkbox"]')) {
                this.handleWidgetToggle(e.target);
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
            
            // Ctrl/Cmd + D to open customizer
            if ((e.ctrlKey || e.metaKey) && e.key === 'd' && !this.isOpen) {
                e.preventDefault();
                this.open();
            }
        });

        // Close when clicking overlay
        document.getElementById('dashboard-overlay')?.addEventListener('click', () => {
            this.close();
        });
    }

    open() {
        const customizer = document.getElementById('dashboard-customizer');
        const overlay = document.getElementById('dashboard-overlay');
        
        if (customizer && overlay) {
            customizer.classList.add('open');
            overlay.classList.add('active');
            this.isOpen = true;
            
            // Focus management
            const firstInput = customizer.querySelector('input, button');
            if (firstInput) firstInput.focus();
            
            // Prevent body scroll
            document.body.style.overflow = 'hidden';
        }
    }

    close() {
        const customizer = document.getElementById('dashboard-customizer');
        const overlay = document.getElementById('dashboard-overlay');
        
        if (customizer && overlay) {
            customizer.classList.remove('open');
            overlay.classList.remove('active');
            this.isOpen = false;
            
            // Restore body scroll
            document.body.style.overflow = '';
            
            // Save settings when closing
            this.saveSettings();
        }
    }

    handleLayoutChange(button) {
        // Update active state
        document.querySelectorAll('.layout-option').forEach(opt => {
            opt.classList.remove('active');
        });
        button.classList.add('active');
        
        // Apply layout
        const layout = button.dataset.layout;
        this.setLayout(layout);
        
        // Animate change
        this.animateLayoutChange();
    }

    setLayout(layout) {
        this.settings.layout = layout;
        document.documentElement.setAttribute('data-layout', layout);
        
        // Trigger layout recalculation
        this.recalculateLayout();
    }

    recalculateLayout() {
        // Force browser to recalculate grid layout
        const container = document.getElementById('dashboard-grid');
        if (container) {
            const display = container.style.display;
            container.style.display = 'none';
            container.offsetHeight; // Trigger reflow
            container.style.display = display;
        }
    }

    animateLayoutChange() {
        const widgets = document.querySelectorAll('.dashboard-widget');
        widgets.forEach((widget, index) => {
            widget.style.transition = 'all 0.3s ease-in-out';
            widget.style.transform = 'scale(0.95)';
            
            setTimeout(() => {
                widget.style.transform = 'scale(1)';
            }, index * 50);
        });
    }

    handleWidgetToggle(checkbox) {
        const widgetId = checkbox.dataset.widget;
        const isVisible = checkbox.checked;
        
        this.settings.widgets[widgetId] = {
            ...this.settings.widgets[widgetId],
            visible: isVisible
        };
        
        // Toggle widget visibility
        this.toggleWidget(widgetId, isVisible);
    }

    toggleWidget(widgetId, show) {
        const widget = document.querySelector(`[data-widget="${widgetId}"]`);
        if (!widget) return;

        if (show) {
            widget.style.display = '';
            widget.classList.remove('widget-hidden');
            // Animate in
            widget.style.opacity = '0';
            widget.style.transform = 'translateY(-20px)';
            
            requestAnimationFrame(() => {
                widget.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                widget.style.opacity = '1';
                widget.style.transform = 'translateY(0)';
            });
        } else {
            widget.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            widget.style.opacity = '0';
            widget.style.transform = 'translateY(-20px)';
            
            setTimeout(() => {
                widget.style.display = 'none';
                widget.classList.add('widget-hidden');
            }, 300);
        }
    }

    // Theme management
    setTheme(theme) {
        this.settings.theme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        
        // Animate theme transition
        document.body.style.transition = 'background-color 0.3s ease, color 0.3s ease';
        setTimeout(() => {
            document.body.style.transition = '';
        }, 300);
    }

    // Widget positioning
    enableWidgetReordering() {
        const container = document.getElementById('dashboard-grid');
        if (!container) return;

        // Use modern drag and drop API
        let draggedWidget = null;
        let placeholder = null;

        container.addEventListener('dragstart', (e) => {
            if (e.target.matches('.dashboard-widget')) {
                draggedWidget = e.target;
                e.target.style.opacity = '0.5';
                
                // Create placeholder
                placeholder = this.createPlaceholder();
                
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/html', e.target.outerHTML);
            }
        });

        container.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';

            const afterElement = this.getDragAfterElement(container, e.clientY);
            if (afterElement == null) {
                container.appendChild(placeholder);
            } else {
                container.insertBefore(placeholder, afterElement);
            }
        });

        container.addEventListener('drop', (e) => {
            e.preventDefault();
            
            if (draggedWidget && placeholder) {
                container.insertBefore(draggedWidget, placeholder);
                container.removeChild(placeholder);
                
                // Save new order
                this.saveWidgetOrder();
            }
        });

        container.addEventListener('dragend', (e) => {
            if (e.target.matches('.dashboard-widget')) {
                e.target.style.opacity = '';
                if (placeholder && placeholder.parentNode) {
                    placeholder.parentNode.removeChild(placeholder);
                }
                draggedWidget = null;
                placeholder = null;
            }
        });
    }

    createPlaceholder() {
        const placeholder = document.createElement('div');
        placeholder.className = 'widget-placeholder';
        placeholder.style.cssText = `
            border: 2px dashed var(--color-border);
            border-radius: var(--radius-md);
            background: var(--color-bg-alt);
            min-height: 200px;
            opacity: 0.7;
        `;
        return placeholder;
    }

    getDragAfterElement(container, y) {
        const draggableElements = [...container.querySelectorAll('.dashboard-widget:not(.dragging)')];
        
        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            
            if (offset < 0 && offset > closest.offset) {
                return { offset: offset, element: child };
            } else {
                return closest;
            }
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }

    saveWidgetOrder() {
        const widgets = Array.from(document.querySelectorAll('[data-widget]'));
        const order = widgets.map((widget, index) => ({
            id: widget.dataset.widget,
            order: index
        }));

        this.settings.widgetOrder = order;
        this.saveSettings();
    }

    restoreWidgetOrder() {
        if (!this.settings.widgetOrder) return;

        const container = document.getElementById('dashboard-grid');
        if (!container) return;

        // Sort widgets according to saved order
        const sortedWidgets = this.settings.widgetOrder
            .map(item => document.querySelector(`[data-widget="${item.id}"]`))
            .filter(Boolean);

        sortedWidgets.forEach(widget => {
            container.appendChild(widget);
        });
    }

    // Settings persistence
    loadSettings() {
        try {
            const saved = localStorage.getItem('dashboard-customizer-settings');
            if (saved) {
                this.settings = { ...this.settings, ...JSON.parse(saved) };
            }
        } catch (error) {
            console.error('Failed to load customizer settings:', error);
        }
    }

    saveSettings() {
        try {
            localStorage.setItem('dashboard-customizer-settings', JSON.stringify(this.settings));
        } catch (error) {
            console.error('Failed to save customizer settings:', error);
        }
    }

    applySettings() {
        // Apply layout
        if (this.settings.layout) {
            document.documentElement.setAttribute('data-layout', this.settings.layout);
            const layoutBtn = document.querySelector(`[data-layout="${this.settings.layout}"]`);
            if (layoutBtn) {
                document.querySelectorAll('.layout-option').forEach(opt => opt.classList.remove('active'));
                layoutBtn.classList.add('active');
            }
        }

        // Apply theme
        if (this.settings.theme) {
            document.documentElement.setAttribute('data-theme', this.settings.theme);
        }

        // Apply widget settings
        Object.entries(this.settings.widgets).forEach(([widgetId, config]) => {
            const checkbox = document.querySelector(`input[data-widget="${widgetId}"]`);
            if (checkbox) {
                checkbox.checked = config.visible !== false;
            }
            
            if (config.visible === false) {
                this.toggleWidget(widgetId, false);
            }
        });

        // Restore widget order
        this.restoreWidgetOrder();
    }

    // Export/Import settings
    exportSettings() {
        const settings = {
            ...this.settings,
            exportDate: new Date().toISOString(),
            version: '1.0'
        };
        
        const blob = new Blob([JSON.stringify(settings, null, 2)], {
            type: 'application/json'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'dashboard-settings.json';
        a.click();
        
        URL.revokeObjectURL(url);
    }

    async importSettings(file) {
        try {
            const text = await file.text();
            const settings = JSON.parse(text);
            
            // Validate settings structure
            if (this.validateSettings(settings)) {
                this.settings = { ...this.settings, ...settings };
                this.saveSettings();
                this.applySettings();
                return true;
            }
        } catch (error) {
            console.error('Failed to import settings:', error);
        }
        return false;
    }

    validateSettings(settings) {
        // Basic validation
        if (typeof settings !== 'object') return false;
        if (settings.layout && !['compact', 'default', 'spacious'].includes(settings.layout)) return false;
        if (settings.theme && !['light', 'dark'].includes(settings.theme)) return false;
        
        return true;
    }

    // Reset to defaults
    resetToDefaults() {
        this.settings = {
            layout: 'default',
            widgets: {},
            theme: 'light'
        };
        
        this.saveSettings();
        this.applySettings();
        
        // Reset UI
        document.querySelectorAll('.widget-toggle input[type="checkbox"]').forEach(cb => {
            cb.checked = true;
        });
        
        document.querySelectorAll('.dashboard-widget').forEach(widget => {
            widget.style.display = '';
            widget.classList.remove('widget-hidden');
        });
    }

    // Accessibility helpers
    announceChange(message) {
        // Create screen reader announcement
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.style.cssText = 'position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden;';
        announcement.textContent = message;
        
        document.body.appendChild(announcement);
        
        setTimeout(() => {
            document.body.removeChild(announcement);
        }, 1000);
    }

    // Performance optimization
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Get current configuration
    getCurrentConfig() {
        return {
            ...this.settings,
            isOpen: this.isOpen,
            activeWidgets: Array.from(document.querySelectorAll('[data-widget]:not(.widget-hidden)'))
                .map(el => el.dataset.widget)
        };
    }
}
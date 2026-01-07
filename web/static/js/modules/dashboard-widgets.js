/**
 * Dashboard Widgets Manager
 * Handles widget functionality, refreshing, and state management
 */

export class DashboardWidgets {
    constructor() {
        this.widgets = new Map();
        this.currentMonth = new Date();
    }

    init() {
        this.initializeWidgets();
        this.initMiniCalendar();
        this.bindEvents();
    }

    initializeWidgets() {
        // Register all widgets
        document.querySelectorAll('[data-widget]').forEach(widget => {
            const widgetId = widget.dataset.widget;
            this.widgets.set(widgetId, {
                element: widget,
                config: this.getWidgetConfig(widgetId),
                lastUpdate: null
            });
        });
    }

    getWidgetConfig(widgetId) {
        const configs = {
            stats: {
                refreshInterval: 30000, // 30 seconds
                autoRefresh: true
            },
            priority: {
                refreshInterval: 60000, // 1 minute
                autoRefresh: true
            },
            schedule: {
                refreshInterval: 60000,
                autoRefresh: true
            },
            events: {
                refreshInterval: 300000, // 5 minutes
                autoRefresh: true
            },
            actions: {
                refreshInterval: null,
                autoRefresh: false
            },
            calendar: {
                refreshInterval: null,
                autoRefresh: false
            }
        };

        return configs[widgetId] || { refreshInterval: null, autoRefresh: false };
    }

    bindEvents() {
        // Auto-refresh widgets
        this.widgets.forEach((widget, widgetId) => {
            if (widget.config.autoRefresh && widget.config.refreshInterval) {
                setInterval(() => {
                    this.refreshWidget(widgetId);
                }, widget.config.refreshInterval);
            }
        });

        // Widget drag and drop (simplified)
        this.initDragAndDrop();
    }

    initDragAndDrop() {
        const widgets = document.querySelectorAll('.dashboard-widget');
        
        widgets.forEach(widget => {
            widget.draggable = true;
            
            widget.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', widget.dataset.widget);
                widget.classList.add('dragging');
            });
            
            widget.addEventListener('dragend', () => {
                widget.classList.remove('dragging');
            });
            
            widget.addEventListener('dragover', (e) => {
                e.preventDefault();
                const afterElement = this.getDragAfterElement(widget.parentElement, e.clientY);
                const dragging = document.querySelector('.dragging');
                
                if (afterElement == null) {
                    widget.parentElement.appendChild(dragging);
                } else {
                    widget.parentElement.insertBefore(dragging, afterElement);
                }
            });
        });
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

    async refreshWidget(widgetId) {
        const widget = this.widgets.get(widgetId);
        if (!widget) return;

        try {
            // Add loading state
            widget.element.classList.add('widget-loading');
            
            // Simulate API call - in real implementation, this would fetch fresh data
            await this.simulateApiCall();
            
            // Update timestamp
            widget.lastUpdate = new Date();
            
            // Remove loading state
            widget.element.classList.remove('widget-loading');
            
            // Trigger refresh event
            widget.element.dispatchEvent(new CustomEvent('widget-refreshed', {
                detail: { widgetId, timestamp: widget.lastUpdate }
            }));
            
        } catch (error) {
            console.error(`Failed to refresh widget ${widgetId}:`, error);
            widget.element.classList.add('widget-error');
            setTimeout(() => {
                widget.element.classList.remove('widget-error');
            }, 3000);
        }
    }

    async simulateApiCall() {
        return new Promise(resolve => {
            setTimeout(resolve, 500 + Math.random() * 1000);
        });
    }

    toggleWidget(widgetId, show) {
        const widget = this.widgets.get(widgetId);
        if (!widget) return;

        if (show) {
            widget.element.classList.remove('widget-hidden');
        } else {
            widget.element.classList.add('widget-hidden');
        }

        // Save preference
        this.saveWidgetPreferences();
    }

    saveWidgetPreferences() {
        const preferences = {};
        this.widgets.forEach((widget, widgetId) => {
            preferences[widgetId] = {
                visible: !widget.element.classList.contains('widget-hidden'),
                order: Array.from(widget.element.parentElement.children).indexOf(widget.element)
            };
        });
        
        localStorage.setItem('dashboard-widgets', JSON.stringify(preferences));
    }

    loadWidgetPreferences() {
        try {
            const preferences = JSON.parse(localStorage.getItem('dashboard-widgets') || '{}');
            
            Object.entries(preferences).forEach(([widgetId, config]) => {
                if (config.visible === false) {
                    this.toggleWidget(widgetId, false);
                }
            });
        } catch (error) {
            console.error('Failed to load widget preferences:', error);
        }
    }

    // Mini Calendar functionality
    initMiniCalendar() {
        this.renderMiniCalendar();
    }

    changeMonth(delta) {
        this.currentMonth.setMonth(this.currentMonth.getMonth() + delta);
        this.renderMiniCalendar();
    }

    renderMiniCalendar() {
        const calendarEl = document.getElementById('mini-calendar');
        if (!calendarEl) return;

        const year = this.currentMonth.getFullYear();
        const month = this.currentMonth.getMonth();
        const today = new Date();
        
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const firstDayWeek = firstDay.getDay();
        const daysInMonth = lastDay.getDate();

        let html = '<table><thead><tr>';
        const weekdays = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
        weekdays.forEach(day => {
            html += `<th>${day}</th>`;
        });
        html += '</tr></thead><tbody>';

        let date = 1;
        for (let week = 0; week < 6; week++) {
            html += '<tr>';
            
            for (let day = 0; day < 7; day++) {
                if (week === 0 && day < firstDayWeek) {
                    // Previous month days
                    const prevMonthDay = new Date(year, month, -(firstDayWeek - day - 1));
                    html += `<td class="other-month">${prevMonthDay.getDate()}</td>`;
                } else if (date > daysInMonth) {
                    // Next month days
                    html += `<td class="other-month">${date - daysInMonth}</td>`;
                    date++;
                } else {
                    // Current month days
                    const isToday = year === today.getFullYear() && 
                                   month === today.getMonth() && 
                                   date === today.getDate();
                    
                    const hasEvents = this.hasEventsOnDate(year, month, date);
                    
                    const classes = [];
                    if (isToday) classes.push('today');
                    if (hasEvents) classes.push('has-events');
                    
                    html += `<td class="${classes.join(' ')}">${date}</td>`;
                    date++;
                }
            }
            
            html += '</tr>';
            if (date > daysInMonth) break;
        }

        html += '</tbody></table>';
        calendarEl.innerHTML = html;
    }

    hasEventsOnDate(year, month, date) {
        // In real implementation, this would check against actual event data
        // For now, simulate some events
        return Math.random() > 0.8;
    }

    // Widget-specific methods
    updateStats(stats) {
        const widget = this.widgets.get('stats');
        if (!widget) return;

        const statCards = widget.element.querySelectorAll('.stat-number');
        if (statCards.length >= 4) {
            statCards[0].textContent = stats.overdue || 0;
            statCards[1].textContent = stats.today || 0;
            statCards[2].textContent = stats.undated || 0;
            statCards[3].textContent = stats.events || 0;
        }
    }

    addPriorityItem(item) {
        const widget = this.widgets.get('priority');
        if (!widget) return;

        const list = widget.element.querySelector('.priority-list');
        if (list) {
            const itemEl = this.createPriorityItemElement(item);
            list.appendChild(itemEl);
        }
    }

    createPriorityItemElement(item) {
        const div = document.createElement('div');
        div.className = 'priority-item priority-item--overdue';
        div.innerHTML = `
            <div class="priority-indicator"></div>
            <div class="priority-content">
                <div class="priority-title">
                    <img src="/static/icons/${item.type}.svg" class="item-icon" alt="">
                    <span>${item.name}</span>
                </div>
                <div class="priority-meta">
                    <span class="priority-time">${item.time || 'Kein Termin'}</span>
                    <span class="priority-badge priority-badge--danger">Überfällig</span>
                </div>
            </div>
            <button class="priority-action" onclick="dashboard.editItem(${item.id})">
                <svg class="icon"><use href="#icon-edit"></use></svg>
            </button>
        `;
        return div;
    }

    // Animation helpers
    animateWidget(widgetId, animation = 'pulse') {
        const widget = this.widgets.get(widgetId);
        if (!widget) return;

        widget.element.style.animation = `${animation} 0.5s ease-in-out`;
        setTimeout(() => {
            widget.element.style.animation = '';
        }, 500);
    }

    // Performance monitoring
    getPerformanceMetrics() {
        return {
            totalWidgets: this.widgets.size,
            visibleWidgets: Array.from(this.widgets.values()).filter(w => 
                !w.element.classList.contains('widget-hidden')
            ).length,
            lastUpdates: Object.fromEntries(
                Array.from(this.widgets.entries()).map(([id, widget]) => 
                    [id, widget.lastUpdate]
                )
            )
        };
    }
}
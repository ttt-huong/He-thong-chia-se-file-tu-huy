/**
 * Main Application Controller
 * Initializes all components and manages global application state
 */

class Application {
    constructor() {
        this.components = {};
        this.isInitialized = false;
    }

    /**
     * Initialize application
     */
    async init() {
        console.log('🚀 Initializing Distributed File Sharing System Frontend...');
        console.log('API Base URL:', CONFIG.API_BASE_URL);

        try {
            // Wait for DOM to be ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.setupApplication());
            } else {
                this.setupApplication();
            }
        } catch (error) {
            console.error('Fatal error during initialization:', error);
            this.showFatalError(error);
        }
    }

    /**
     * Setup application after DOM is ready
     */
    setupApplication() {
        console.log('📦 Components loaded successfully');

        // Store references to components
        this.components = {
            upload: window.uploadComponent,
            health: window.healthCheckComponent,
            nodes: window.nodesStatusComponent,
            fileList: window.fileListComponent,
        };

        // Log component status
        Object.entries(this.components).forEach(([name, component]) => {
            if (component) {
                console.log(`✅ ${name} component initialized`);
            } else {
                console.warn(`⚠️ ${name} component not initialized`);
            }
        });

        this.isInitialized = true;

        // Setup keyboard shortcuts (future feature)
        this.setupKeyboardShortcuts();

        // Setup error boundary
        this.setupErrorBoundary();

        console.log('✅ Application ready');
    }

    /**
     * Setup keyboard shortcuts
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl+U for upload (future)
            // Ctrl+R for refresh
            if (e.ctrlKey && e.key === 'r') {
                e.preventDefault();
                this.refreshAll();
            }
        });
    }

    /**
     * Setup global error boundary
     */
    setupErrorBoundary() {
        window.addEventListener('error', (e) => {
            console.error('Global error:', e.error);
        });

        window.addEventListener('unhandledrejection', (e) => {
            console.error('Unhandled promise rejection:', e.reason);
        });
    }

    /**
     * Refresh all components
     */
    refreshAll() {
        console.log('🔄 Refreshing all components...');

        Object.values(this.components).forEach(component => {
            if (component && typeof component.refresh === 'function') {
                component.refresh();
            }
        });
    }

    /**
     * Show fatal error
     */
    showFatalError(error) {
        const container = document.querySelector('.container') || document.body;
        container.innerHTML = `
            <div style="
                background: #fff5f5;
                border: 2px solid #dc3545;
                border-radius: 8px;
                padding: 30px;
                margin: 20px;
                text-align: center;
            ">
                <h1 style="color: #dc3545; margin-bottom: 10px;">❌ Application Error</h1>
                <p style="color: #666; margin-bottom: 15px;">
                    An error occurred while initializing the application.
                </p>
                <p style="
                    background: #f5f5f5;
                    padding: 15px;
                    border-radius: 4px;
                    font-family: monospace;
                    font-size: 12px;
                    color: #333;
                    text-align: left;
                    overflow-x: auto;
                ">
                    ${error.message}
                </p>
                <p style="color: #999; font-size: 12px; margin-top: 15px;">
                    Please check the console for more details.
                </p>
            </div>
        `;
    }

    /**
     * Cleanup on page unload
     */
    cleanup() {
        console.log('🛑 Cleaning up...');

        Object.values(this.components).forEach(component => {
            if (component && typeof component.stopPolling === 'function') {
                component.stopPolling();
            }
        });
    }
}

// Global application instance
let app = null;

// Initialize when DOM is ready or immediately if already loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        app = new Application();
        app.init();
    });
} else {
    app = new Application();
    app.init();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (app) {
        app.cleanup();
    }
});

// Console greeting
console.log('%c📦 File Sharing System v2.0', 'font-size: 20px; font-weight: bold; color: #667eea;');
console.log('%cDistributed Architecture with Auto-Replication & Failover', 'font-size: 14px; color: #764ba2;');
console.log('%cChapters 4-8: REST APIs, URIs, Caching, Replication, Load Balancing', 'font-size: 12px; color: #666;');

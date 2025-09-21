// Enhanced UI JavaScript for AI Career Advisor
(function() {
    'use strict';

    // Theme Management
    class ThemeManager {
        constructor() {
            this.currentTheme = localStorage.getItem('theme') || 'light';
            this.init();
        }

        init() {
            this.applyTheme(this.currentTheme);
            this.createToggleButton();
            this.bindEvents();
        }

        applyTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            this.currentTheme = theme;
            localStorage.setItem('theme', theme);
            this.updateToggleButton();
        }

        toggleTheme() {
            const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
            this.applyTheme(newTheme);
            
            // Add a subtle animation to indicate theme change
            document.body.style.transition = 'all 0.3s ease';
            setTimeout(() => {
                document.body.style.transition = '';
            }, 300);
        }

        createToggleButton() {
            const navbar = document.querySelector('.navbar-nav:last-child');
            if (!navbar) return;

            const toggleContainer = document.createElement('li');
            toggleContainer.className = 'nav-item';
            
            const toggleButton = document.createElement('button');
            toggleButton.className = 'theme-toggle nav-link';
            toggleButton.setAttribute('aria-label', 'Toggle dark mode');
            toggleButton.innerHTML = `
                <span class="theme-toggle-icon">🌙</span>
                <span class="theme-toggle-text">Dark</span>
            `;
            
            toggleContainer.appendChild(toggleButton);
            navbar.insertBefore(toggleContainer, navbar.firstChild);
            
            this.toggleButton = toggleButton;
            this.updateToggleButton();
        }

        updateToggleButton() {
            if (!this.toggleButton) return;
            
            const icon = this.toggleButton.querySelector('.theme-toggle-icon');
            const text = this.toggleButton.querySelector('.theme-toggle-text');
            
            if (this.currentTheme === 'dark') {
                icon.textContent = '☀️';
                text.textContent = 'Light';
            } else {
                icon.textContent = '🌙';
                text.textContent = 'Dark';
            }
        }

        bindEvents() {
            if (this.toggleButton) {
                this.toggleButton.addEventListener('click', () => this.toggleTheme());
            }
        }
    }

    // Animation Manager
    class AnimationManager {
        constructor() {
            this.init();
        }

        init() {
            this.setupIntersectionObserver();
            this.setupScrollAnimations();
            this.setupHoverEffects();
            this.setupFormAnimations();
        }

        setupIntersectionObserver() {
            const observerOptions = {
                threshold: 0.1,
                rootMargin: '0px 0px -50px 0px'
            };

            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('fade-in');
                        observer.unobserve(entry.target);
                    }
                });
            }, observerOptions);

            // Observe elements for animation
            const animateElements = document.querySelectorAll('.card-feature, .content-section, .tracker-container');
            animateElements.forEach(el => {
                observer.observe(el);
            });
        }

        setupScrollAnimations() {
            let ticking = false;

            function updateScrollAnimations() {
                const scrolled = window.pageYOffset;
                const parallaxElements = document.querySelectorAll('.hero-section');
                
                parallaxElements.forEach(el => {
                    const speed = 0.5;
                    el.style.transform = `translateY(${scrolled * speed}px)`;
                });

                ticking = false;
            }

            function requestScrollUpdate() {
                if (!ticking) {
                    requestAnimationFrame(updateScrollAnimations);
                    ticking = true;
                }
            }

            window.addEventListener('scroll', requestScrollUpdate);
        }

        setupHoverEffects() {
            // Add ripple effect to buttons
            const buttons = document.querySelectorAll('.btn');
            buttons.forEach(button => {
                button.addEventListener('click', this.createRipple);
            });

            // Add hover sound effect (optional)
            const hoverElements = document.querySelectorAll('.card-feature, .btn, .nav-link');
            hoverElements.forEach(el => {
                el.addEventListener('mouseenter', () => {
                    el.style.transform = el.style.transform || '';
                });
            });
        }

        setupFormAnimations() {
            const formInputs = document.querySelectorAll('.form-control');
            formInputs.forEach(input => {
                // Floating label effect
                input.addEventListener('focus', () => {
                    input.parentElement.classList.add('focused');
                });

                input.addEventListener('blur', () => {
                    if (!input.value) {
                        input.parentElement.classList.remove('focused');
                    }
                });

                // Auto-resize textarea
                if (input.tagName === 'TEXTAREA') {
                    input.addEventListener('input', this.autoResize);
                }
            });
        }

        createRipple(event) {
            const button = event.currentTarget;
            const ripple = document.createElement('span');
            const rect = button.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = event.clientX - rect.left - size / 2;
            const y = event.clientY - rect.top - size / 2;

            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple');

            button.appendChild(ripple);

            setTimeout(() => {
                ripple.remove();
            }, 600);
        }

        autoResize(event) {
            const textarea = event.target;
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        }
    }

    // Chat Enhancements
    class ChatEnhancements {
        constructor() {
            this.init();
        }

        init() {
            this.setupTypingIndicator();
            this.setupMessageAnimations();
            this.setupAutoScroll();
            this.setupVoiceIndicators();
        }

        setupTypingIndicator() {
            const typingIndicator = document.getElementById('typing-indicator');
            if (!typingIndicator) return;

            // Create animated dots
            const dotsContainer = document.createElement('div');
            dotsContainer.className = 'typing-dots';
            dotsContainer.innerHTML = `
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            `;

            const existingText = typingIndicator.querySelector('small');
            if (existingText) {
                existingText.appendChild(dotsContainer);
            }
        }

        setupMessageAnimations() {
            // Animate new messages as they appear
            const chatMessages = document.getElementById('chat-messages');
            if (!chatMessages) return;

            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType === 1 && node.classList.contains('d-flex')) {
                            node.style.opacity = '0';
                            node.style.transform = 'translateY(20px)';
                            
                            setTimeout(() => {
                                node.style.transition = 'all 0.3s ease';
                                node.style.opacity = '1';
                                node.style.transform = 'translateY(0)';
                            }, 50);
                        }
                    });
                });
            });

            observer.observe(chatMessages, { childList: true });
        }

        setupAutoScroll() {
            const chatMessages = document.getElementById('chat-messages');
            if (!chatMessages) return;

            // Smooth scroll to bottom when new messages arrive
            const scrollToBottom = () => {
                chatMessages.scrollTo({
                    top: chatMessages.scrollHeight,
                    behavior: 'smooth'
                });
            };

            // Override the existing scroll behavior
            const originalScrollTop = chatMessages.scrollTop;
            Object.defineProperty(chatMessages, 'scrollTop', {
                set: function(value) {
                    if (value === this.scrollHeight) {
                        scrollToBottom();
                    } else {
                        originalScrollTop.call(this, value);
                    }
                },
                get: function() {
                    return originalScrollTop.call(this);
                }
            });
        }

        setupVoiceIndicators() {
            const voiceButtons = document.querySelectorAll('#toggle-tts, #start-voice');
            voiceButtons.forEach(button => {
                button.addEventListener('click', () => {
                    button.classList.toggle('active');
                    
                    // Add visual feedback
                    if (button.classList.contains('active')) {
                        button.style.background = 'rgba(66, 153, 225, 0.2)';
                        button.style.color = '#4299e1';
                    } else {
                        button.style.background = '';
                        button.style.color = '';
                    }
                });
            });
        }
    }

    // Loading States Manager
    class LoadingManager {
        static showLoading(element) {
            element.classList.add('loading');
            element.style.pointerEvents = 'none';
        }

        static hideLoading(element) {
            element.classList.remove('loading');
            element.style.pointerEvents = '';
        }

        static showSuccess(element) {
            const checkmark = document.createElement('div');
            checkmark.className = 'success-checkmark';
            element.appendChild(checkmark);

            setTimeout(() => {
                checkmark.remove();
            }, 2000);
        }
    }

    // Performance Optimizations
    class PerformanceOptimizer {
        constructor() {
            this.init();
        }

        init() {
            this.setupLazyLoading();
            this.setupDebouncing();
            this.setupPreloading();
        }

        setupLazyLoading() {
            const images = document.querySelectorAll('img[data-src]');
            const imageObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                        imageObserver.unobserve(img);
                    }
                });
            });

            images.forEach(img => imageObserver.observe(img));
        }

        setupDebouncing() {
            // Debounce scroll events
            let scrollTimeout;
            const originalScrollHandler = window.onscroll;
            
            window.onscroll = function(event) {
                clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(() => {
                    if (originalScrollHandler) {
                        originalScrollHandler.call(this, event);
                    }
                }, 16); // ~60fps
            };
        }

        setupPreloading() {
            // Preload critical images
            const criticalImages = [
                '/static/img/hero-bg-modern.jpg',
                '/static/img/hero-bg-dark.jpg'
            ];

            criticalImages.forEach(src => {
                const link = document.createElement('link');
                link.rel = 'preload';
                link.as = 'image';
                link.href = src;
                document.head.appendChild(link);
            });
        }
    }

    // Accessibility Enhancements
    class AccessibilityManager {
        constructor() {
            this.init();
        }

        init() {
            this.setupKeyboardNavigation();
            this.setupScreenReaderSupport();
            this.setupReducedMotion();
        }

        setupKeyboardNavigation() {
            // Enhanced keyboard navigation for chat
            const chatInput = document.getElementById('user-input');
            if (chatInput) {
                chatInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape') {
                        chatInput.blur();
                    }
                });
            }

            // Focus management for modals and dropdowns
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Tab') {
                    // Ensure focus stays within modal if open
                    const modal = document.querySelector('.modal.show');
                    if (modal) {
                        this.trapFocus(modal, e);
                    }
                }
            });
        }

        setupScreenReaderSupport() {
            // Add ARIA labels and descriptions
            const chatMessages = document.getElementById('chat-messages');
            if (chatMessages) {
                chatMessages.setAttribute('aria-live', 'polite');
                chatMessages.setAttribute('aria-label', 'Chat conversation');
            }

            // Announce theme changes
            const themeToggle = document.querySelector('.theme-toggle');
            if (themeToggle) {
                themeToggle.addEventListener('click', () => {
                    const theme = document.documentElement.getAttribute('data-theme');
                    this.announceToScreenReader(`Switched to ${theme} mode`);
                });
            }
        }

        setupReducedMotion() {
            // Respect user's motion preferences
            const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
            
            if (prefersReducedMotion.matches) {
                document.documentElement.style.setProperty('--transition-fast', '0.01ms');
                document.documentElement.style.setProperty('--transition-medium', '0.01ms');
                document.documentElement.style.setProperty('--transition-slow', '0.01ms');
            }
        }

        trapFocus(element, event) {
            const focusableElements = element.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];

            if (event.shiftKey && document.activeElement === firstElement) {
                lastElement.focus();
                event.preventDefault();
            } else if (!event.shiftKey && document.activeElement === lastElement) {
                firstElement.focus();
                event.preventDefault();
            }
        }

        announceToScreenReader(message) {
            const announcement = document.createElement('div');
            announcement.setAttribute('aria-live', 'assertive');
            announcement.setAttribute('aria-atomic', 'true');
            announcement.className = 'sr-only';
            announcement.textContent = message;
            
            document.body.appendChild(announcement);
            setTimeout(() => announcement.remove(), 1000);
        }
    }

    // Initialize all managers when DOM is ready
    function initializeEnhancedUI() {
        new ThemeManager();
        new AnimationManager();
        new ChatEnhancements();
        new PerformanceOptimizer();
        new AccessibilityManager();

        // Add global utility functions
        window.LoadingManager = LoadingManager;
        
        // Add CSS for ripple effect
        const rippleCSS = `
            .ripple {
                position: absolute;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.6);
                transform: scale(0);
                animation: ripple-animation 0.6s linear;
                pointer-events: none;
            }
            
            @keyframes ripple-animation {
                to {
                    transform: scale(4);
                    opacity: 0;
                }
            }
            
            .sr-only {
                position: absolute;
                width: 1px;
                height: 1px;
                padding: 0;
                margin: -1px;
                overflow: hidden;
                clip: rect(0, 0, 0, 0);
                white-space: nowrap;
                border: 0;
            }
        `;
        
        const style = document.createElement('style');
        style.textContent = rippleCSS;
        document.head.appendChild(style);

        console.log('Enhanced UI initialized successfully');
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeEnhancedUI);
    } else {
        initializeEnhancedUI();
    }

})();


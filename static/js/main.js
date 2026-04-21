// Mobile Menu Toggle
document.addEventListener('DOMContentLoaded', function() {
    const hamburger = document.querySelector('.hamburger');
    const navMenu = document.querySelector('.nav-menu');

    if (hamburger) {
        hamburger.addEventListener('click', function() {
            navMenu.classList.toggle('active');
            hamburger.classList.toggle('active');
        });
    }

    // Close menu when clicking outside
    document.addEventListener('click', function(event) {
        if (!hamburger.contains(event.target) && !navMenu.contains(event.target)) {
            navMenu.classList.remove('active');
            hamburger.classList.remove('active');
        }
    });

    // Dropdown toggle for services (mobile and desktop)
    const navDropdown = document.querySelector('.nav-dropdown');
    
    if (navDropdown) {
        const dropdownTrigger = navDropdown.querySelector('.dropdown-trigger') || navDropdown.querySelector('.nav-link');
        const dropdownMenu = navDropdown.querySelector('.dropdown-menu');
        
        if (dropdownTrigger && dropdownMenu) {
            // Function to check if mobile
            function isMobile() {
                return window.innerWidth <= 768;
            }
            
            // Handle click on dropdown trigger
            dropdownTrigger.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                // Toggle dropdown
                const isActive = navDropdown.classList.contains('active');
                if (isActive) {
                    navDropdown.classList.remove('active');
                } else {
                    navDropdown.classList.add('active');
                }
            });
            
            // Prevent dropdown from closing when clicking inside it
            dropdownMenu.addEventListener('click', function(e) {
                e.stopPropagation();
            });
            
            // Close dropdown when clicking outside (but not immediately to allow menu click)
            document.addEventListener('click', function(e) {
                if (navDropdown && !navDropdown.contains(e.target)) {
                    navDropdown.classList.remove('active');
                }
            });
            
            // Handle window resize - close dropdown if switching between mobile/desktop
            let resizeTimer;
            window.addEventListener('resize', function() {
                clearTimeout(resizeTimer);
                resizeTimer = setTimeout(function() {
                    navDropdown.classList.remove('active');
                }, 250);
            });
        }
    }

    // Close flash messages
    const flashCloseButtons = document.querySelectorAll('.flash-close');
    flashCloseButtons.forEach(button => {
        button.addEventListener('click', function() {
            const flashMessage = this.closest('.flash-message');
            flashMessage.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                flashMessage.remove();
            }, 300);
        });
    });

    // Auto-close flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                message.remove();
            }, 300);
        }, 5000);
    });

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href !== '#' && href.length > 1) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });

    // Navbar scroll effect
    let lastScroll = 0;
    const navbar = document.querySelector('.navbar');
    
    window.addEventListener('scroll', function() {
        const currentScroll = window.pageYOffset;
        
        if (currentScroll > 100) {
            navbar.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
        } else {
            navbar.style.boxShadow = '0 1px 2px 0 rgba(0, 0, 0, 0.05)';
        }
        
        lastScroll = currentScroll;
    });

    // Form validation
    const contactForm = document.querySelector('.contact-form');
    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            const inputs = contactForm.querySelectorAll('input[required], select[required], textarea[required]');
            let isValid = true;

            inputs.forEach(input => {
                if (!input.value.trim()) {
                    isValid = false;
                    input.style.borderColor = 'var(--error-color)';
                } else {
                    input.style.borderColor = 'var(--border-color)';
                }
            });

            if (!isValid) {
                e.preventDefault();
                alert('Por favor, preencha todos os campos obrigatórios.');
            }
        });
    }

    // Animate on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe elements
    document.querySelectorAll('.service-card, .feature-item, .value-card, .service-item').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
});

// Add slideOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Hero Slider Functionality
(function() {
    'use strict';
    
    let currentSlide = 0;
    let slideInterval;
    const slides = document.querySelectorAll('.slide');
    const indicators = document.querySelectorAll('.indicator');
    
    if (slides.length === 0) return;
    
    function showSlide(index) {
        // Remove active class from all slides and indicators
        slides.forEach(slide => {
            slide.classList.remove('active');
        });
        indicators.forEach(indicator => {
            indicator.classList.remove('active');
        });
        
        // Add active class to current slide and indicator
        slides[index].classList.add('active');
        if (indicators[index]) {
            indicators[index].classList.add('active');
        }
        
        currentSlide = index;
    }
    
    function nextSlide() {
        const next = (currentSlide + 1) % slides.length;
        showSlide(next);
    }
    
    function prevSlide() {
        const prev = (currentSlide - 1 + slides.length) % slides.length;
        showSlide(prev);
    }
    
    function startAutoSlide() {
        slideInterval = setInterval(nextSlide, 5000); // Muda slide a cada 5 segundos
    }
    
    function stopAutoSlide() {
        clearInterval(slideInterval);
    }
    
    // Indicator clicks
    indicators.forEach((indicator, index) => {
        indicator.addEventListener('click', () => {
            stopAutoSlide();
            showSlide(index);
            startAutoSlide();
        });
    });
    
    // Pause on hover
    const sliderContainer = document.querySelector('.slider-container');
    if (sliderContainer) {
        sliderContainer.addEventListener('mouseenter', stopAutoSlide);
        sliderContainer.addEventListener('mouseleave', startAutoSlide);
    }
    
    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft') {
            stopAutoSlide();
            prevSlide();
            startAutoSlide();
        } else if (e.key === 'ArrowRight') {
            stopAutoSlide();
            nextSlide();
            startAutoSlide();
        }
    });
    
    // Alinhar slide com a borda inferior da navbar (DESATIVADO para evitar espaço preto)
    function alignSliderWithNavbar() {
        // O slide agora começa do topo (Y=0) para um visual mais limpo
        const slider = document.querySelector('.hero-slider');
        if (slider) {
            slider.style.marginTop = '0';
        }
    }
    
    // Initialize
    showSlide(0);
    startAutoSlide();
    alignSliderWithNavbar();
    
    window.addEventListener('resize', alignSliderWithNavbar);
    window.addEventListener('load', alignSliderWithNavbar);
})();

// Image fallback handler
(function() {
    'use strict';
    
    // Função para tratar erro de carregamento de imagens
    function handleImageError(img) {
        const fallback = img.getAttribute('data-fallback');
        if (fallback && img.src !== fallback) {
            img.src = fallback;
        }
    }
    
    // Aplicar handler para todas as imagens com data-fallback
    document.addEventListener('DOMContentLoaded', function() {
        const images = document.querySelectorAll('img[data-fallback]');
        images.forEach(function(img) {
            img.addEventListener('error', function() {
                handleImageError(this);
            });
        });
    });
})();


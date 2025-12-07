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
    const dropdownTrigger = navDropdown ? navDropdown.querySelector('.dropdown-trigger, .nav-link') : null;
    const dropdownMenu = navDropdown ? navDropdown.querySelector('.dropdown-menu') : null;
    
    if (dropdownTrigger && dropdownMenu) {
        // Function to check if mobile
        function isMobile() {
            return window.innerWidth <= 768;
        }
        
        // Handle click on dropdown trigger
        dropdownTrigger.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (isMobile()) {
                // On mobile, toggle dropdown
                navDropdown.classList.toggle('active');
            } else {
                // On desktop, toggle dropdown (alternative to hover)
                navDropdown.classList.toggle('active');
            }
        });
        
        // Prevent dropdown from closing when clicking inside it
        dropdownMenu.addEventListener('click', function(e) {
            e.stopPropagation();
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (navDropdown && !navDropdown.contains(e.target)) {
                navDropdown.classList.remove('active');
            }
        });
        
        // Handle window resize - close dropdown if switching between mobile/desktop
        window.addEventListener('resize', function() {
            navDropdown.classList.remove('active');
        });
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
    const heroSlider = document.querySelector('.hero-slider');
    
    if (slides.length === 0) return;
    
    // Função para ajustar altura do slider baseada nas imagens
    function adjustSliderHeight() {
        if (!heroSlider) return;
        
        const slideImages = document.querySelectorAll('.slide-image[data-bg-image]');
        if (slideImages.length === 0) return;
        
        const sliderWidth = heroSlider.offsetWidth || window.innerWidth;
        const isMobile = window.innerWidth <= 768;
        let maxHeight = isMobile ? 250 : 300; // altura mínima
        
        // Carregar todas as imagens para obter suas dimensões
        const imagePromises = Array.from(slideImages).map(function(imgElement) {
            return new Promise(function(resolve) {
                const bgImage = imgElement.getAttribute('data-bg-image');
                if (!bgImage) {
                    resolve(null);
                    return;
                }
                
                // Verificar se há tag img dentro
                const imgTag = imgElement.querySelector('img');
                const imageSrc = imgTag ? imgTag.src : bgImage;
                
                // Criar imagem temporária para obter dimensões
                const img = new Image();
                img.onload = function() {
                    const naturalWidth = this.naturalWidth;
                    const naturalHeight = this.naturalHeight;
                    if (naturalWidth > 0 && naturalHeight > 0) {
                        const aspectRatio = naturalHeight / naturalWidth;
                        let calculatedHeight;
                        
                        if (isMobile) {
                            // No mobile com contain, calcular altura baseada na largura
                            calculatedHeight = sliderWidth * aspectRatio;
                            // Limitar altura máxima no mobile
                            if (calculatedHeight > 400) {
                                calculatedHeight = 400;
                            }
                        } else {
                            // No desktop com cover, usar altura calculada
                            calculatedHeight = sliderWidth * aspectRatio;
                        }
                        
                        if (calculatedHeight > maxHeight) {
                            maxHeight = calculatedHeight;
                        }
                    }
                    resolve(maxHeight);
                };
                img.onerror = function() {
                    resolve(maxHeight);
                };
                img.src = imageSrc;
            });
        });
        
        // Quando todas as imagens carregarem, ajustar altura
        Promise.all(imagePromises).then(function() {
            const minHeight = isMobile ? 250 : 300;
            if (maxHeight > minHeight) {
                heroSlider.style.height = maxHeight + 'px';
            } else {
                heroSlider.style.height = minHeight + 'px';
            }
        }).catch(function() {
            heroSlider.style.height = (isMobile ? 250 : 300) + 'px';
        });
    }
    
    // Aplicar background-image usando atributos data IMEDIATAMENTE
    // Isso garante que as imagens apareçam mesmo antes do JavaScript completo carregar
    (function applyBackgroundImages() {
        const slideImages = document.querySelectorAll('.slide-image[data-bg-image]');
        const isMobile = window.innerWidth <= 768;
        
        slideImages.forEach(function(imgElement) {
            const bgImage = imgElement.getAttribute('data-bg-image');
            if (bgImage) {
                // Garantir que a tag img dentro também seja visível no mobile
                const imgTag = imgElement.querySelector('img');
                if (imgTag) {
                    // No mobile, priorizar a tag img com contain
                    if (isMobile) {
                        imgTag.style.display = 'block';
                        imgTag.style.objectFit = 'contain';
                        imgTag.style.objectPosition = 'center';
                        imgElement.style.backgroundImage = 'none';
                        imgElement.style.backgroundSize = 'contain';
                    } else {
                        // No desktop, usar background-image com cover e esconder img
                        imgTag.style.display = 'none';
                        imgElement.style.backgroundImage = "url('" + bgImage + "')";
                        imgElement.style.backgroundSize = 'cover';
                    }
                } else {
                    // Se não houver tag img, aplicar background-image
                    imgElement.style.backgroundImage = "url('" + bgImage + "')";
                    if (isMobile) {
                        imgElement.style.backgroundSize = 'contain';
                    } else {
                        imgElement.style.backgroundSize = 'cover';
                    }
                }
            }
        });
        
        // Reaplicar ao redimensionar
        window.addEventListener('resize', function() {
            const newIsMobile = window.innerWidth <= 768;
            slideImages.forEach(function(imgElement) {
                const imgTag = imgElement.querySelector('img');
                if (imgTag) {
                    if (newIsMobile) {
                        imgTag.style.display = 'block';
                        imgTag.style.objectFit = 'contain';
                        imgTag.style.objectPosition = 'center';
                        imgElement.style.backgroundImage = 'none';
                        imgElement.style.backgroundSize = 'contain';
                    } else {
                        imgTag.style.display = 'none';
                        const bgImage = imgElement.getAttribute('data-bg-image');
                        imgElement.style.backgroundImage = bgImage ? "url('" + bgImage + "')" : 'none';
                        imgElement.style.backgroundSize = 'cover';
                    }
                } else {
                    imgElement.style.backgroundSize = newIsMobile ? 'contain' : 'cover';
                }
            });
        });
    })();
    
    function showSlide(index) {
        // Remove active class from all slides and indicators
        slides.forEach(slide => {
            slide.classList.remove('active', 'prev');
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
    
    // Initialize
    showSlide(0);
    startAutoSlide();
    
    // Alinhar slide com a borda inferior da navbar
    function alignSliderWithNavbar() {
        const navbar = document.querySelector('.navbar');
        const slider = document.querySelector('.hero-slider');
        if (navbar && slider) {
            const navbarHeight = navbar.offsetHeight;
            slider.style.marginTop = navbarHeight + 'px';
        }
    }
    
    // Executar ao carregar e ao redimensionar
    alignSliderWithNavbar();
    window.addEventListener('resize', function() {
        alignSliderWithNavbar();
        adjustSliderHeight();
    });
    window.addEventListener('load', function() {
        alignSliderWithNavbar();
        adjustSliderHeight();
    });
    
    // Ajustar altura quando as imagens carregarem
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', adjustSliderHeight);
    } else {
        adjustSliderHeight();
    }
    
    // No mobile, recalcular altura quando cada imagem carregar
    if (window.innerWidth <= 768) {
        const slideImages = document.querySelectorAll('.slide-image img');
        slideImages.forEach(function(img) {
            if (!img.complete) {
                img.addEventListener('load', function() {
                    setTimeout(adjustSliderHeight, 50);
                });
            } else {
                // Imagem já carregada, recalcular imediatamente
                setTimeout(adjustSliderHeight, 50);
            }
        });
    }
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


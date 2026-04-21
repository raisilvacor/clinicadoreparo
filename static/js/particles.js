// Particle effect for hero section
document.addEventListener('DOMContentLoaded', function() {
    const particlesContainer = document.querySelector('.particles');
    
    if (!particlesContainer) return;

    // Create particles
    const particleCount = 50;
    const particles = [];

    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.cssText = `
            position: absolute;
            width: ${Math.random() * 4 + 2}px;
            height: ${Math.random() * 4 + 2}px;
            background: rgba(255, 255, 255, ${Math.random() * 0.5 + 0.2});
            border-radius: 50%;
            left: ${Math.random() * 100}%;
            top: ${Math.random() * 100}%;
            pointer-events: none;
            animation: float-particle ${Math.random() * 10 + 10}s infinite ease-in-out;
            animation-delay: ${Math.random() * 5}s;
        `;
        particlesContainer.appendChild(particle);
        particles.push(particle);
    }

    // Add animation keyframes
    const style = document.createElement('style');
    style.textContent = `
        @keyframes float-particle {
            0%, 100% {
                transform: translate(0, 0) scale(1);
                opacity: 0.3;
            }
            25% {
                transform: translate(${Math.random() * 100 - 50}px, ${Math.random() * 100 - 50}px) scale(1.2);
                opacity: 0.6;
            }
            50% {
                transform: translate(${Math.random() * 100 - 50}px, ${Math.random() * 100 - 50}px) scale(0.8);
                opacity: 0.4;
            }
            75% {
                transform: translate(${Math.random() * 100 - 50}px, ${Math.random() * 100 - 50}px) scale(1.1);
                opacity: 0.5;
            }
        }
    `;
    document.head.appendChild(style);
});


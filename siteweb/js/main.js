/* ========================================
   DELIVERY RUSH — Main JS
   ======================================== */

'use strict';

/* ---- Navbar scroll effect ---- */
(function initNavbar() {
  const navbar = document.getElementById('navbar');
  if (!navbar) return;

  let ticking = false;

  function onScroll() {
    if (!ticking) {
      requestAnimationFrame(() => {
        navbar.classList.toggle('scrolled', window.scrollY > 40);
        ticking = false;
      });
      ticking = true;
    }
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll(); // run once on load
})();


/* ---- Smooth scrolling for anchor links ---- */
(function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', e => {
      const targetId = link.getAttribute('href');
      const target = document.querySelector(targetId);
      if (!target) return;
      e.preventDefault();

      const navbarHeight = document.getElementById('navbar')?.offsetHeight ?? 70;
      const y = target.getBoundingClientRect().top + window.scrollY - navbarHeight;

      window.scrollTo({ top: y, behavior: 'smooth' });

      // Close mobile menu if open
      document.getElementById('nav-links')?.classList.remove('open');
      const hamburger = document.getElementById('hamburger');
      if (hamburger) {
        hamburger.classList.remove('open');
        hamburger.setAttribute('aria-expanded', 'false');
      }
    });
  });
})();


/* ---- Hamburger / mobile menu ---- */
(function initMobileMenu() {
  const hamburger = document.getElementById('hamburger');
  const navLinks  = document.getElementById('nav-links');
  if (!hamburger || !navLinks) return;

  hamburger.addEventListener('click', () => {
    const isOpen = navLinks.classList.toggle('open');
    hamburger.classList.toggle('open', isOpen);
    hamburger.setAttribute('aria-expanded', String(isOpen));
  });

  // Close on outside click
  document.addEventListener('click', e => {
    if (!hamburger.contains(e.target) && !navLinks.contains(e.target)) {
      navLinks.classList.remove('open');
      hamburger.classList.remove('open');
      hamburger.setAttribute('aria-expanded', 'false');
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      navLinks.classList.remove('open');
      hamburger.classList.remove('open');
      hamburger.setAttribute('aria-expanded', 'false');
    }
  });
})();


/* ---- Scroll-triggered animations (IntersectionObserver) ---- */
(function initScrollAnimations() {
  const elements = document.querySelectorAll('.animate-on-scroll');
  if (!elements.length) return;

  // Stagger delay for feature cards, about cards, etc.
  function getDelay(el) {
    const parent = el.closest('.features-grid, .about-cards, .requirements-grid, .steps-grid, .controls-grid, .team-grid, .resources-grid');
    if (!parent) return 0;
    const siblings = Array.from(parent.querySelectorAll('.animate-on-scroll'));
    const index    = siblings.indexOf(el);
    return index * 80; // ms
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const delay = getDelay(entry.target);
          setTimeout(() => {
            entry.target.classList.add('visible');
          }, delay);
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
  );

  elements.forEach(el => observer.observe(el));
})();


/* ---- Parallax on hero section ---- */
(function initParallax() {
  const heroContent = document.querySelector('.hero-content');
  const heroBg      = document.querySelector('.hero-gradient');
  if (!heroContent || !heroBg) return;

  // Skip parallax on mobile / reduced-motion
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReduced || window.innerWidth < 768) return;

  let ticking = false;

  function onScroll() {
    if (!ticking) {
      requestAnimationFrame(() => {
        const scrolled = window.scrollY;
        if (scrolled < window.innerHeight) {
          heroContent.style.transform = `translateY(${scrolled * 0.25}px)`;
          heroBg.style.transform      = `translateY(${scrolled * 0.12}px)`;
        }
        ticking = false;
      });
      ticking = true;
    }
  }

  window.addEventListener('scroll', onScroll, { passive: true });
})();


/* ---- Animated particles in hero ---- */
(function initParticles() {
  const container = document.getElementById('particles');
  if (!container) return;

  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReduced) return;

  const PARTICLE_COUNT = 55;
  const particles      = [];

  // Create SVG canvas
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', '100%');
  svg.style.cssText = 'position:absolute;inset:0;pointer-events:none;';
  container.appendChild(svg);

  function randomBetween(a, b) {
    return a + Math.random() * (b - a);
  }

  function createParticle() {
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    const isAccent = Math.random() > 0.7;
    const r = randomBetween(1, 2.5);

    circle.setAttribute('r', r);
    circle.setAttribute('fill', isAccent ? '#f9a825' : '#4a6478');
    circle.setAttribute('opacity', randomBetween(0.15, 0.5));
    svg.appendChild(circle);

    return {
      el:  circle,
      x:   randomBetween(0, 100),
      y:   randomBetween(0, 100),
      vx:  randomBetween(-0.012, 0.012),
      vy:  randomBetween(-0.018, -0.006),
      opacity: randomBetween(0.15, 0.5),
    };
  }

  for (let i = 0; i < PARTICLE_COUNT; i++) {
    particles.push(createParticle());
  }

  let animId;
  function animate() {
    particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;

      // Wrap around
      if (p.x < -2)  p.x = 102;
      if (p.x > 102) p.x = -2;
      if (p.y < -2)  { p.y = 102; p.x = randomBetween(0, 100); }
      if (p.y > 102) p.y = -2;

      p.el.setAttribute('cx', p.x + '%');
      p.el.setAttribute('cy', p.y + '%');
    });
    animId = requestAnimationFrame(animate);
  }
  animate();

  // Pause when tab not visible
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      cancelAnimationFrame(animId);
    } else {
      animate();
    }
  });
})();


/* ---- Copy-to-clipboard for code blocks ---- */
(function initCopyButtons() {
  document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const code = btn.getAttribute('data-code');
      if (!code) return;

      navigator.clipboard.writeText(code).then(() => {
        const original = btn.textContent;
        btn.textContent = '✓ Copié';
        btn.classList.add('copied');
        setTimeout(() => {
          btn.textContent = original;
          btn.classList.remove('copied');
        }, 2000);
      }).catch(() => {
        // Fallback for older browsers
        const ta = document.createElement('textarea');
        ta.value = code;
        ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0;';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);

        const original = btn.textContent;
        btn.textContent = '✓ Copié';
        btn.classList.add('copied');
        setTimeout(() => {
          btn.textContent = original;
          btn.classList.remove('copied');
        }, 2000);
      });
    });
  });
})();
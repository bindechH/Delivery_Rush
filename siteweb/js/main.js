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


/* ---- Language toggle (FR / EN) ---- */
(function initLangToggle() {
  const translations = {
    fr: {
      // About section
      'about-p1':         '<strong>Delivery Rush</strong> est un jeu vidéo de livraison se déroulant dans une grande ville ouverte, développé en Python avec Pygame par une équipe de 4 étudiants de L3.1 G4 à l\'EPITA (Promo 2026). Le joueur contrôle un véhicule et doit accomplir différentes missions de livraison dans un temps limité, en naviguant à travers plus de 40 lieux et quartiers distincts.',
      'about-p2':         'Le jeu propose une physique de conduite réaliste avec gestion du drift et du frein à main, un catalogue de 17 véhicules déblocables (de la citadine économique à la supercar ultime), 3 types de missions (Standard, Express, Chaîne) et un mode multijoueur optionnel via UDP. Le style graphique pixel art cartoon en vue aérienne garantit une accessibilité immédiate.',
      'tag-aerial':       '🏎️ Vue aérienne',
      'tag-missions':     '📦 3 types de missions',
      'tag-vehicles':     '🚗 17 véhicules',
      'acard1-title':     '40+ lieux sur la carte',
      'acard1-desc':      'Une grande ville organisée en plusieurs quartiers : zone universitaire (Campus Epita), centre commercial, hôpitaux, banques, stade, zones résidentielles, logistique et bien plus.',
      'acard2-title':     'Physique de conduite avancée',
      'acard2-desc':      'Drift dynamique, frein à main, gestion de l\'inertie hors-route et collisions réalistes. Chaque véhicule a ses propres caractéristiques de vitesse, accélération et maniabilité.',
      'acard3-title':     'Multijoueur optionnel',
      'acard3-desc':      'Mode multijoueur client/serveur UDP permettant de jouer avec d\'autres joueurs. La sauvegarde et le mode solo fonctionnent de façon totalement indépendante.',
      // Features
      'feat1-title':      'Physique de conduite réaliste',
      'feat1-desc':       'Vue aérienne avec physique avancée : gestion du drift, frein à main, inertie hors-route et collisions. Chaque véhicule possède ses propres paramètres de vitesse, accélération, maniabilité et adhérence.',
      'feat2-title':      '3 types de missions dynamiques',
      'feat2-desc':       'Missions <strong>Standard</strong> (2–4 min, 100–250 €), <strong>Express</strong> (45 s–1,5 min, 200–500 €) et en <strong>Chaîne</strong> (1,5–2,5 min, 150–350 €), générées aléatoirement sur 40+ points d\'intérêt de la ville.',
      'feat3-title':      'Ville ouverte par quartiers',
      'feat3-desc':       'Carte construite avec Tiled : campus universitaire, centre commercial, hôpitaux, commissariat, tribunal, stade, zones résidentielles, banques, quartier d\'affaires et entrepôts de livraison.',
      'feat4-title':      'Multijoueur UDP',
      'feat4-desc':       'Architecture client/serveur UDP (Python socket) avec authentification. Partagez la carte avec d\'autres joueurs en temps réel. Le mode solo fonctionne de manière totalement indépendante.',
      'feat5-title':      '17 véhicules déblocables',
      'feat5-desc':       'Du MICRO (gratuit) à la SUPERCAR (15 000 €), chaque véhicule est disponible en 8 couleurs. Achetez de nouveaux véhicules grâce à l\'argent gagné lors de vos livraisons et gérez votre garage.',
      'feat6-title':      'Sauvegarde &amp; progression',
      'feat6-desc':       'Votre progression (argent, véhicules, missions accomplies, position, distance totale) est sauvegardée automatiquement dans <code>solo_save.json</code>. Reprenez là où vous vous êtes arrêté à chaque session.',
      // Resources
      'res-cat-libs':     'Langages &amp; Bibliothèques',
      'res-python-desc':  'Langage principal du projet. Utilisé pour toute la logique du jeu, le réseau et le serveur. Requis sur Windows pour lancer le jeu.',
      'res-pygame-desc':  'Bibliothèque principale pour les graphiques 2D, la gestion des événements, le son et la boucle de jeu. Installée via pip.',
      'res-pytmx-desc':   'Chargement des fichiers de carte .tmx produits par l\'éditeur Tiled. Permet d\'intégrer la carte complète de la ville dans le jeu.',
      'res-pyscroll-desc':'Rendu efficace de grandes cartes en tiles avec scrolling. Gère l\'affichage de la carte ouverte centrée sur le joueur.',
      'res-socket-desc':  'Bibliothèque standard Python pour la communication réseau UDP. Utilisée pour le mode multijoueur entre le serveur et les clients.',
      'res-cat-tools':    'Outils de développement',
      'res-tiled-desc':   'Éditeur de cartes en tiles utilisé pour concevoir toute la carte de la ville (fichier deliveryrush_map.tmx). Format .tmx / .tsx.',
      'res-github-desc':  'Gestion de version et collaboration. Hébergement du code source du projet, suivi des issues et CI. Dépôt public.',
      'res-cat-assets':   'Ressources graphiques &amp; sonores',
      'res-sprites-name': 'Sprites de véhicules pixel art',
      'res-sprites-desc': '17 modèles de véhicules en vue aérienne (MICRO, SEDAN, SUV, SUPERCAR, BOX TRUCK…) chacun disponible en 8 couleurs avec animations de rotation par frames.',
      'res-tilesets-name':'Tilesets de la carte urbaine',
      'res-tilesets-desc':'Tilesets personnalisés pour la carte de la ville : routes, bâtiments, quartiers résidentiels, zones commerciales et industrielles. Fichiers .tsx / .tmx.',
      'res-sounds-name':  'Musique &amp; effets sonores',
      'res-sounds-desc':  'Musique d\'ambiance pour le menu et le jeu, effets sonores de moteur et interface. Gérés par le module SoundManager avec contrôle du volume.',
      'res-included':     'Inclus dans le projet',
      'res-cat-web':      'Ressources de ce site web',
      'res-fonts-desc':   'Polices utilisées sur ce site : <em>Orbitron</em> (titres), <em>Rajdhani</em> (navigation &amp; textes), <em>Inter</em> (corps de texte).',
      // Requirements
      'req1-title':       'Python',
      'req1-version':     '3.8 ou supérieur (Windows)',
      'req1-desc':        'Requis pour exécuter le jeu. Le projet est conçu pour Windows. Téléchargez Python sur <a href="https://python.org" target="_blank" rel="noopener noreferrer">python.org</a>',
      'req2-desc':        'Bibliothèque principale pour les graphiques, la physique, les collisions et la boucle de jeu. Installée automatiquement via pip.',
      'req3-desc':        'Chargement des cartes Tiled (.tmx) et rendu efficient de la grande carte urbaine avec scrolling centré sur le joueur.',
      'req4-title':       'Réseau (socket)',
      'req4-desc':        'Bibliothèque standard <code>socket</code> de Python pour la communication UDP entre serveur et clients. Connexion requise pour le multijoueur uniquement.',
      'req-note':         'Toutes les dépendances Python sont listées dans <code>requirements.txt</code>. Le code source est géré via GitHub pour le travail collaboratif. Installez tout en une commande : <code>pip install -r requirements.txt</code>',
      // Download
      'btn-source2':      'Voir le code source',
      // Footer bottom
      'footer-bottom':    'Fait avec ❤️ en Python &amp; Pygame · L3.1 G4 · EPITA Promo 2026 · <a href="https://github.com/bindechH/Delivery_Rush" target="_blank" rel="noopener noreferrer">GitHub</a>',
      'footer-tech-net':  '🌐 Réseau UDP (socket)',
      // Nav
      'nav-about':        'À propos',
      'nav-features':     'Fonctionnalités',
      'nav-team':         'Équipe',
      'nav-resources':    'Ressources',
      'nav-howtoplay':    'Comment jouer',
      'nav-requirements': 'Configuration',
      'nav-download':     'Télécharger',
      'hero-badge':       '🎮 Disponible gratuitement',
      'hero-tagline':     'Un jeu vidéo de livraison dans une grande ville ouverte',
      'hero-sub':         'Conduisez. Livrez. Progressez.',
      'btn-download':     'Télécharger',
      'btn-source':       'Voir le code source',
      'stat-vehicles':    'Véhicules',
      'stat-missions':    'Types de missions',
      'stat-locations':   'Lieux sur la carte',
      'stat-multiplayer': 'Multijoueur',
      'scroll-hint':      'Défiler',
      'about-tag':        'À propos du jeu',
      'about-title':      'Un jeu de livraison dans une grande ville ouverte',
      'features-tag':     'Fonctionnalités',
      'features-title':   "Tout ce qu'il faut pour une livraison réussie",
      'team-tag':         'Notre équipe',
      'team-sub':         "Un projet réalisé par 4 étudiants passionnés à l'EPITA dans le cadre du cours de programmation avancée en Python.",
      'team-role':        'Développeur Python / Pygame',
      'team-school':      'Étudiant L3.1 — EPITA G4',
      'team-note':        "Projet réalisé dans le cadre du cours de L3 à l'<strong>EPITA</strong> (École Pour l'Informatique et les Techniques Avancées), Lyon. Groupe G4 — Promotion 2026.",
      'resources-tag':    'Ressources & Références',
      'resources-title':  'Bibliothèques, outils & ressources utilisés',
      'resources-sub':    'Toutes les ressources externes et bibliothèques utilisées dans le projet Delivery Rush.',
      'howtoplay-tag':    'Comment jouer',
      'howtoplay-title':  'Prêt à démarrer en 3 étapes',
      'step1-title':      'Installer les dépendances',
      'step1-desc':       "Assurez-vous d'avoir <strong>Python 3.8+</strong> installé sur Windows, puis installez les dépendances du projet via pip :",
      'step2-title':      'Lancer le serveur',
      'step2-desc':       'Démarrez le serveur UDP qui gérera les connexions multijoueurs. Le jeu reste entièrement jouable en mode solo sans cette étape :',
      'step3-title':      'Lancer le jeu',
      'step3-desc':       'Lancez le client principal, choisissez votre véhicule et commencez à accomplir vos missions de livraison :',
      'controls-title':   'Contrôles',
      'ctrl-accel':       'Accélérer',
      'ctrl-brake':       'Freiner / Reculer',
      'ctrl-turn':        'Tourner',
      'ctrl-handbrake':   'Frein à main',
      'ctrl-aim':         'Viser et tirer',
      'req-tag':          'Configuration système',
      'req-title':        'Ce dont vous avez besoin',
      'dl-title':         'Prêt à livrer ?',
      'dl-desc':          'Delivery Rush est entièrement <strong>gratuit et open source</strong>, réalisé par une équipe de 4 étudiants (L3.1 G4 — EPITA). Téléchargez le projet ou le rapport de soutenance ci-dessous.',
      'dl-btn-zip':       'Télécharger le projet (.zip)',
      'report-title':     'Rapport de soutenance',
      'report-desc':      'Rapport complet du projet : conception, architecture logicielle, choix techniques, analyse des résultats et perspectives.',
      'report-btn':       'Télécharger le rapport PDF',
      'footer-tagline':   'Un jeu vidéo de livraison open source — L3.1 G4 EPITA',
      'footer-nav':       'Navigation',
      'footer-downloads': 'Téléchargements',
      'footer-ext':       'Liens externes',
      'footer-repo':      'Repository GitHub',
      'footer-dl':        'Télécharger le projet',
      'footer-bug':       'Signaler un bug',
      'footer-tech':      'Technologies',
    },
    en: {
      // About section
      'about-p1':         '<strong>Delivery Rush</strong> is a delivery video game set in a large open city, developed in Python with Pygame by a team of 4 L3.1 G4 students at EPITA (Class of 2026). The player controls a vehicle and must complete various delivery missions within a time limit, navigating through more than 40 distinct locations and districts.',
      'about-p2':         'The game features realistic driving physics with drift and handbrake mechanics, a catalogue of 17 unlockable vehicles (from the budget city car to the ultimate supercar), 3 mission types (Standard, Express, Chain) and an optional UDP multiplayer mode. The top-down pixel art cartoon art style ensures immediate accessibility.',
      'tag-aerial':       '🏎️ Top-down view',
      'tag-missions':     '📦 3 mission types',
      'tag-vehicles':     '🚗 17 vehicles',
      'acard1-title':     '40+ map locations',
      'acard1-desc':      'A large city organised into several districts: university area (Campus Epita), shopping centre, hospitals, banks, stadium, residential areas, logistics hubs and much more.',
      'acard2-title':     'Advanced driving physics',
      'acard2-desc':      'Dynamic drift, handbrake, off-road inertia management and realistic collisions. Each vehicle has its own speed, acceleration and handling characteristics.',
      'acard3-title':     'Optional multiplayer',
      'acard3-desc':      'UDP client/server multiplayer mode allowing you to play with other players. Saves and solo mode work in a completely independent way.',
      // Features
      'feat1-title':      'Realistic driving physics',
      'feat1-desc':       'Top-down view with advanced physics: drift management, handbrake, off-road inertia and collisions. Each vehicle has its own speed, acceleration, handling and grip parameters.',
      'feat2-title':      '3 dynamic mission types',
      'feat2-desc':       '<strong>Standard</strong> missions (2–4 min, €100–250), <strong>Express</strong> (45 s–1.5 min, €200–500) and <strong>Chain</strong> (1.5–2.5 min, €150–350), randomly generated across 40+ points of interest in the city.',
      'feat3-title':      'Open city by districts',
      'feat3-desc':       'Map built with Tiled: university campus, shopping centre, hospitals, police station, courthouse, stadium, residential areas, banks, business district and delivery warehouses.',
      'feat4-title':      'UDP Multiplayer',
      'feat4-desc':       'UDP client/server architecture (Python socket) with authentication. Share the map with other players in real time. Solo mode works in a completely independent way.',
      'feat5-title':      '17 unlockable vehicles',
      'feat5-desc':       'From the MICRO (free) to the SUPERCAR (€15,000), each vehicle is available in 8 colours. Buy new vehicles with money earned from your deliveries and manage your garage.',
      'feat6-title':      'Save &amp; progression',
      'feat6-desc':       'Your progress (money, vehicles, completed missions, position, total distance) is saved automatically in <code>solo_save.json</code>. Pick up where you left off each session.',
      // Resources
      'res-cat-libs':     'Languages &amp; Libraries',
      'res-python-desc':  'Main language of the project. Used for all game logic, networking and the server. Required on Windows to run the game.',
      'res-pygame-desc':  'Main library for 2D graphics, event handling, sound and the game loop. Installed via pip.',
      'res-pytmx-desc':   'Loading .tmx map files produced by the Tiled editor. Allows the full city map to be integrated into the game.',
      'res-pyscroll-desc':'Efficient rendering of large tile maps with scrolling. Handles the display of the open map centred on the player.',
      'res-socket-desc':  'Python standard library for UDP network communication. Used for the multiplayer mode between server and clients.',
      'res-cat-tools':    'Development tools',
      'res-tiled-desc':   'Tile map editor used to design the entire city map (deliveryrush_map.tmx file). .tmx / .tsx format.',
      'res-github-desc':  'Version control and collaboration. Hosting of the project source code, issue tracking and CI. Public repository.',
      'res-cat-assets':   'Graphic &amp; audio assets',
      'res-sprites-name': 'Pixel art vehicle sprites',
      'res-sprites-desc': '17 vehicle models in top-down view (MICRO, SEDAN, SUV, SUPERCAR, BOX TRUCK…) each available in 8 colours with frame-by-frame rotation animations.',
      'res-tilesets-name':'Urban map tilesets',
      'res-tilesets-desc':'Custom tilesets for the city map: roads, buildings, residential districts, commercial and industrial zones. .tsx / .tmx files.',
      'res-sounds-name':  'Music &amp; sound effects',
      'res-sounds-desc':  'Ambient music for the menu and game, engine and interface sound effects. Managed by the SoundManager module with volume control.',
      'res-included':     'Included in the project',
      'res-cat-web':      'Website resources',
      'res-fonts-desc':   'Fonts used on this site: <em>Orbitron</em> (headings), <em>Rajdhani</em> (navigation &amp; text), <em>Inter</em> (body text).',
      // Requirements
      'req1-title':       'Python',
      'req1-version':     '3.8 or higher (Windows)',
      'req1-desc':        'Required to run the game. The project is designed for Windows. Download Python at <a href="https://python.org" target="_blank" rel="noopener noreferrer">python.org</a>',
      'req2-desc':        'Main library for graphics, physics, collisions and the game loop. Installed automatically via pip.',
      'req3-desc':        'Loading Tiled maps (.tmx) and efficient rendering of the large urban map with scrolling centred on the player.',
      'req4-title':       'Network (socket)',
      'req4-desc':        'Python standard <code>socket</code> library for UDP communication between server and clients. Connection required for multiplayer only.',
      'req-note':         'All Python dependencies are listed in <code>requirements.txt</code>. The source code is managed via GitHub for collaborative work. Install everything in one command: <code>pip install -r requirements.txt</code>',
      // Download
      'btn-source2':      'View source code',
      // Footer bottom
      'footer-bottom':    'Made with ❤️ in Python &amp; Pygame · L3.1 G4 · EPITA Class of 2026 · <a href="https://github.com/bindechH/Delivery_Rush" target="_blank" rel="noopener noreferrer">GitHub</a>',
      'footer-tech-net':  '🌐 UDP Network (socket)',
      // Nav
      'nav-about':        'About',
      'nav-features':     'Features',
      'nav-team':         'Team',
      'nav-resources':    'Resources',
      'nav-howtoplay':    'How to Play',
      'nav-requirements': 'Requirements',
      'nav-download':     'Download',
      'hero-badge':       '🎮 Free to play',
      'hero-tagline':     'A delivery video game set in a large open city',
      'hero-sub':         'Drive. Deliver. Progress.',
      'btn-download':     'Download',
      'btn-source':       'View source code',
      'stat-vehicles':    'Vehicles',
      'stat-missions':    'Mission types',
      'stat-locations':   'Map locations',
      'stat-multiplayer': 'Multiplayer',
      'scroll-hint':      'Scroll',
      'about-tag':        'About the game',
      'about-title':      'A delivery game in a large open city',
      'features-tag':     'Features',
      'features-title':   'Everything you need for a successful delivery',
      'team-tag':         'Our team',
      'team-sub':         'A project built by 4 passionate students at EPITA as part of the advanced Python programming course.',
      'team-role':        'Python / Pygame Developer',
      'team-school':      'L3.1 Student — EPITA G4',
      'team-note':        'Project built as part of the L3 course at <strong>EPITA</strong> (École Pour l\'Informatique et les Techniques Avancées), Lyon. Group G4 — Class of 2026.',
      'resources-tag':    'Resources & References',
      'resources-title':  'Libraries, tools & resources used',
      'resources-sub':    'All external resources and libraries used in the Delivery Rush project.',
      'howtoplay-tag':    'How to play',
      'howtoplay-title':  'Ready to start in 3 steps',
      'step1-title':      'Install dependencies',
      'step1-desc':       'Make sure you have <strong>Python 3.8+</strong> installed on Windows, then install the project dependencies via pip:',
      'step2-title':      'Start the server',
      'step2-desc':       'Launch the UDP server that will handle multiplayer connections. The game is fully playable in solo mode without this step:',
      'step3-title':      'Launch the game',
      'step3-desc':       'Run the main client, choose your vehicle and start completing your delivery missions:',
      'controls-title':   'Controls',
      'ctrl-accel':       'Accelerate',
      'ctrl-brake':       'Brake / Reverse',
      'ctrl-turn':        'Steer',
      'ctrl-handbrake':   'Handbrake',
      'ctrl-aim':         'Aim and shoot',
      'req-tag':          'System requirements',
      'req-title':        'What you need',
      'dl-title':         'Ready to deliver?',
      'dl-desc':          'Delivery Rush is entirely <strong>free and open source</strong>, built by a team of 4 students (L3.1 G4 — EPITA). Download the project or the project report below.',
      'dl-btn-zip':       'Download the project (.zip)',
      'report-title':     'Project report',
      'report-desc':      'Full project report: design, software architecture, technical choices, results analysis and perspectives.',
      'report-btn':       'Download PDF report',
      'footer-tagline':   'An open source delivery video game — L3.1 G4 EPITA',
      'footer-nav':       'Navigation',
      'footer-downloads': 'Downloads',
      'footer-ext':       'External links',
      'footer-repo':      'GitHub Repository',
      'footer-dl':        'Download the project',
      'footer-bug':       'Report a bug',
      'footer-tech':      'Technologies',
    }
  };

  let currentLang = 'fr';

  function applyLang(lang) {
    const t = translations[lang];
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (t[key] !== undefined) {
        el.innerHTML = t[key];
      }
    });
    document.documentElement.lang = lang;
    const btn = document.getElementById('lang-toggle');
    if (btn) btn.textContent = lang === 'fr' ? '🌐 EN' : '🌐 FR';
  }

  const btn = document.getElementById('lang-toggle');
  if (!btn) return;

  btn.addEventListener('click', () => {
    currentLang = currentLang === 'fr' ? 'en' : 'fr';
    applyLang(currentLang);
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
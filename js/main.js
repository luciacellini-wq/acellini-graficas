document.addEventListener('DOMContentLoaded', function () {

  // AOS (Animate On Scroll) — reemplaza el viejo sistema custom de .reveal
  if (window.AOS) {
    AOS.init({
      duration: 650,
      easing: 'ease-out-cubic',
      once: true,
      offset: 60
    });
  }

  // El toggle del menú y los dropdowns ahora los maneja el JS bundle de Bootstrap
  // (data-bs-toggle="collapse" / "dropdown"), no hace falta JS propio para eso.

  var slides = document.querySelectorAll('.hero-slide');
  var currentEl = document.getElementById('carouselCurrent');
  var totalEl = document.getElementById('carouselTotal');
  var barEl = document.getElementById('carouselBar');
  if (slides.length) {
    var idx = 0;
    if (totalEl) totalEl.textContent = String(slides.length).padStart(2, '0');
    function showSlide(i) {
      slides.forEach(function (s, si) { s.classList.toggle('is-active', si === i); });
      if (currentEl) currentEl.textContent = String(i + 1).padStart(2, '0');
      if (barEl) barEl.style.width = ((i + 1) / slides.length * 100) + '%';
    }
    showSlide(0);
    setInterval(function () {
      idx = (idx + 1) % slides.length;
      showSlide(idx);
    }, 4500);
  }

  var statNumbers = document.querySelectorAll('.stat-number');
  if (statNumbers.length && 'IntersectionObserver' in window) {
    var counted = new WeakSet();
    var statIo = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && !counted.has(entry.target)) {
          counted.add(entry.target);
          var target = parseInt(entry.target.getAttribute('data-count'), 10) || 0;
          var start = 0;
          var duration = 900;
          var startTime = null;
          function step(ts) {
            if (!startTime) startTime = ts;
            var progress = Math.min((ts - startTime) / duration, 1);
            entry.target.textContent = Math.round(start + (target - start) * progress);
            if (progress < 1) requestAnimationFrame(step);
          }
          requestAnimationFrame(step);
          statIo.unobserve(entry.target);
        }
      });
    }, { threshold: 0.4 });
    statNumbers.forEach(function (el) { statIo.observe(el); });
  }

  var contactForm = document.getElementById('contactForm');
  if (contactForm) {
    contactForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var valid = true;
      ['name', 'email', 'machine', 'message'].forEach(function (field) {
        var input = document.getElementById(field);
        var errorEl = contactForm.querySelector('[data-error-for="' + field + '"]');
        if (errorEl) errorEl.textContent = '';
        if (input && !input.value.trim()) {
          valid = false;
          if (errorEl) errorEl.textContent = 'Este campo es obligatorio.';
        }
      });
      var successEl = document.getElementById('formSuccess');
      if (valid) {
        if (successEl) successEl.classList.add('is-visible');
        contactForm.reset();
      } else if (successEl) {
        successEl.classList.remove('is-visible');
      }
    });
  }

  var toTop = document.getElementById('toTop');
  if (toTop) {
    toTop.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  var yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // Filtro de categorías en el catálogo de máquinas (pages/maquinas.html)
  var chipRow = document.querySelector('.chip-row');
  var machineCards = document.querySelectorAll('.machine-grid .product-card');
  var noResults = document.getElementById('noResults');
  if (chipRow && machineCards.length) {
    var chips = chipRow.querySelectorAll('.chip');
    var validCats = Array.prototype.map.call(chips, function (c) {
      return c.getAttribute('data-filter');
    });

    function applyFilter(cat) {
      var any = false;
      machineCards.forEach(function (card) {
        var match = cat === 'todas' || card.getAttribute('data-category') === cat;
        card.style.display = match ? '' : 'none';
        if (match) any = true;
      });
      if (noResults) noResults.classList.toggle('is-visible', !any);
      chips.forEach(function (chip) {
        chip.classList.toggle('active', chip.getAttribute('data-filter') === cat);
      });
    }

    chips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        var cat = chip.getAttribute('data-filter');
        var newHash = cat === 'todas' ? '' : '#' + cat;
        history.replaceState(null, '', location.pathname + newHash);
        applyFilter(cat);
      });
    });

    function catFromHash() {
      var cat = (location.hash || '').replace('#', '');
      return validCats.indexOf(cat) === -1 ? 'todas' : cat;
    }

    applyFilter(catFromHash());

    window.addEventListener('hashchange', function () {
      applyFilter(catFromHash());
    });
  }

});

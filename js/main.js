/* Mobile nav toggle + footer year */
(function () {
  const toggle = document.querySelector('.nav__toggle');
  const menu = document.getElementById('primary-nav');
  if (toggle && menu) {
    toggle.addEventListener('click', () => {
      const open = menu.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    menu.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => {
        menu.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  const yearEl = document.getElementById('copyright-year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  /* --- E-mail obfuscation: decode `<a class="eml" data-u="…" data-d="…">` --- */
  document.querySelectorAll('a.eml[data-u][data-d]').forEach((a) => {
    const u = a.dataset.u.split('').reverse().join('');
    const d = a.dataset.d.split('').reverse().join('');
    const addr = `${u}@${d}`;
    a.href = `mailto:${addr}`;
    /* Replace placeholder text only if it isn't already a real address. */
    if (!a.textContent.includes('@')) a.textContent = addr;
  });

  /* --- Share: copy link to clipboard --- */
  const copyBtn = document.querySelector('.footer-share__copy');
  if (copyBtn) {
    copyBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      const url = window.location.href;
      try {
        await navigator.clipboard.writeText(url);
      } catch {
        /* Fallback for older browsers */
        const tmp = document.createElement('input');
        tmp.value = url;
        document.body.appendChild(tmp);
        tmp.select();
        document.execCommand('copy');
        document.body.removeChild(tmp);
      }
      const msg = copyBtn.dataset.copied || 'Link copied!';
      showToast(msg);
    });
  }

  /* --- DKB library search: live-filter the file list --- */
  const dkbSearch = document.getElementById('dkb-search');
  if (dkbSearch) {
    const clearBtn = document.getElementById('dkb-search-clear');
    const status   = document.getElementById('dkb-search-status');
    const categories = Array.from(document.querySelectorAll('.dkb-cat'));
    const stripDiacritics = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '');
    const norm = (s) => stripDiacritics((s || '').toLowerCase());

    /* Remember initial open/closed state to restore on clear */
    const initialOpen = new Map();
    categories.forEach(cat => initialOpen.set(cat, cat.open));

    const lang = document.documentElement.lang || 'de';
    const T = lang.startsWith('en')
      ? { noResults: 'No matches for', matches: 'matches' }
      : { noResults: 'Keine Treffer für', matches: 'Treffer' };

    let raf;
    const applyFilter = () => {
      const query = norm(dkbSearch.value.trim());
      clearBtn.hidden = query.length === 0;

      if (!query) {
        /* Restore original state */
        categories.forEach(cat => {
          cat.hidden = false;
          cat.open = initialOpen.get(cat);
          Array.from(cat.querySelectorAll('.dkb-list li')).forEach(li => li.hidden = false);
        });
        status.hidden = true;
        return;
      }

      let totalMatches = 0;
      categories.forEach(cat => {
        let catMatches = 0;
        Array.from(cat.querySelectorAll('.dkb-list li')).forEach(li => {
          const name = norm(li.querySelector('.dkb-item__name')?.textContent || '');
          const hit = name.includes(query);
          li.hidden = !hit;
          if (hit) catMatches++;
        });
        if (catMatches > 0) {
          cat.hidden = false;
          cat.open = true;
          /* Update count badge to reflect filtered results */
          const badge = cat.querySelector('.dkb-cat__count');
          if (badge && !badge.dataset.original) badge.dataset.original = badge.textContent;
          if (badge) badge.textContent = `${catMatches} / ${badge.dataset.original.split(' ')[0]}`;
          totalMatches += catMatches;
        } else {
          cat.hidden = true;
        }
      });

      /* Restore badge text if no filter */
      if (!query) {
        categories.forEach(cat => {
          const badge = cat.querySelector('.dkb-cat__count');
          if (badge && badge.dataset.original) badge.textContent = badge.dataset.original;
        });
      }

      status.hidden = false;
      if (totalMatches === 0) {
        status.textContent = `${T.noResults} „${dkbSearch.value.trim()}".`;
      } else {
        status.textContent = `${totalMatches} ${T.matches}.`;
      }
    };

    const debounced = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(applyFilter);
    };

    dkbSearch.addEventListener('input', debounced);
    clearBtn.addEventListener('click', () => {
      dkbSearch.value = '';
      /* Reset badges */
      categories.forEach(cat => {
        const badge = cat.querySelector('.dkb-cat__count');
        if (badge && badge.dataset.original) badge.textContent = badge.dataset.original;
      });
      applyFilter();
      dkbSearch.focus();
    });
  }

  /* --- Homepage finder widget: "Use my location" → bounce to finder with geo flag --- */
  document.querySelectorAll('a[data-locate]').forEach(link => {
    link.addEventListener('click', (e) => {
      if (!navigator.geolocation) return; /* fall through to plain href */
      e.preventDefault();
      navigator.geolocation.getCurrentPosition(
        (p) => {
          const base = link.getAttribute('href').split('#')[0];
          const q = `${p.coords.latitude.toFixed(4)},${p.coords.longitude.toFixed(4)}`;
          window.location.href = `${base}?q=${encodeURIComponent(q)}#finder`;
        },
        () => { window.location.href = link.href; },
        { enableHighAccuracy: false, timeout: 8000 }
      );
    });
  });

  /* --- Detail-page sub-nav: highlight active section while scrolling --- */
  const detailNav = document.querySelector('.detail-nav');
  if (detailNav) {
    const links = Array.from(detailNav.querySelectorAll('a[href^="#"]'));
    const sections = links
      .map(a => document.getElementById(a.getAttribute('href').slice(1)))
      .filter(Boolean);

    if (sections.length) {
      /* The header (72px) + this nav (~50px) cover the top — leave a bit of breathing room. */
      const NAV_OFFSET = 140;

      const setActive = (id) => {
        links.forEach(l => {
          const isActive = l.getAttribute('href') === '#' + id;
          l.classList.toggle('is-active', isActive);
          if (isActive) {
            l.setAttribute('aria-current', 'location');
          } else {
            l.removeAttribute('aria-current');
          }
        });
        /* Keep the active link visible in the horizontal sub-nav */
        const activeLink = links.find(l => l.classList.contains('is-active'));
        if (activeLink) {
          const navList = activeLink.parentElement.parentElement; /* ul */
          if (navList) {
            const linkRect = activeLink.getBoundingClientRect();
            const listRect = navList.getBoundingClientRect();
            const offset = linkRect.left - listRect.left - (listRect.width - linkRect.width) / 2;
            navList.scrollBy({ left: offset, behavior: 'smooth' });
          }
        }
      };

      /* Manual click handler — bypasses the buggy native anchor scroll with sticky elements */
      links.forEach(a => {
        a.addEventListener('click', (e) => {
          e.preventDefault();
          const id = a.getAttribute('href').slice(1);
          const sec = document.getElementById(id);
          if (!sec) return;
          const targetY = sec.getBoundingClientRect().top + window.scrollY - NAV_OFFSET;
          window.scrollTo({ top: targetY, behavior: 'smooth' });
          history.replaceState(null, '', '#' + id);
          setActive(id);
        });
      });

      /* On scroll: pick the section that contains the probe line below the navs */
      const updateActive = () => {
        const probe = NAV_OFFSET + 40;
        let current = null;
        for (const sec of sections) {
          const r = sec.getBoundingClientRect();
          if (r.top <= probe && r.bottom > probe) {
            current = sec;
            break;
          }
        }
        if (!current) {
          let best = Infinity;
          for (const sec of sections) {
            const r = sec.getBoundingClientRect();
            const center = (r.top + r.bottom) / 2;
            const d = Math.abs(center - probe);
            if (d < best) { best = d; current = sec; }
          }
        }
        if (current) setActive(current.id);
      };

      let rafId;
      const onScroll = () => {
        if (rafId) return;
        rafId = requestAnimationFrame(() => {
          updateActive();
          rafId = null;
        });
      };
      window.addEventListener('scroll', onScroll, { passive: true });
      window.addEventListener('resize', onScroll, { passive: true });

      /* Handle page load with an existing hash */
      if (location.hash) {
        const id = location.hash.slice(1);
        const sec = document.getElementById(id);
        if (sec) {
          requestAnimationFrame(() => {
            const targetY = sec.getBoundingClientRect().top + window.scrollY - NAV_OFFSET;
            window.scrollTo({ top: targetY });
            setActive(id);
          });
        }
      } else {
        updateActive(); /* initial */
      }
    }
  }

  function showToast(text) {
    let toast = document.querySelector('.footer-share__toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.className = 'footer-share__toast';
      toast.setAttribute('role', 'status');
      document.body.appendChild(toast);
    }
    toast.textContent = text;
    requestAnimationFrame(() => toast.classList.add('is-visible'));
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => toast.classList.remove('is-visible'), 2200);
  }
})();

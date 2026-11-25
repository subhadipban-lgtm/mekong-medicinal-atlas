/* Shared helpers for the Mekong Medicinal Plant Atlas. */
(function (global) {
  'use strict';

  const GRADE_LABEL = { A: 'dark green', B: 'amber', C: 'grey', D: 'red (not mapped)' };
  const COUNTRY_NAMES = { CN: 'China', TH: 'Thailand', VN: 'Vietnam', LA: 'Laos', KH: 'Cambodia', MM: 'Myanmar' };

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, c => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function fold(text) {
    return String(text == null ? '' : text).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }
  function fmt(n) {
    return Number(n || 0).toLocaleString('en-US');
  }
  /* Fuzzy match: every character of the query appears in order, allowing gaps and typos of spacing. */
  function fuzzy(haystack, query) {
    const h = fold(haystack), q = fold(query).replace(/\s+/g, ' ').trim();
    if (!q) return true;
    if (h.includes(q)) return true;
    let hi = 0;
    for (const ch of q) {
      if (ch === ' ') continue;
      const found = h.indexOf(ch, hi);
      if (found < 0) return false;
      hi = found + 1;
    }
    return true;
  }
  function photoLarge(url) {
    return String(url || '').replace(/\/(square|small|medium|large|original)\./, '/large.');
  }
  function markActiveNav() {
    const page = document.body.dataset.page;
    document.querySelectorAll('.navbar-atlas .nav-link').forEach(a => a.classList.toggle('active', a.dataset.page === page));
  }
  function gradeBadge(g) {
    return `<span class="badge badge-grade ${esc(g)}" title="Evidence grade ${esc(g)}">${esc(g)}</span>`;
  }
  function iucnBadge(code) {
    const c = String(code || '').split('/')[0];
    return c ? `<span class="badge badge-iucn ${esc(c)}" title="IUCN category ${esc(c)}">${esc(c)}</span>`
             : '<span class="text-muted">–</span>';
  }

  document.addEventListener('DOMContentLoaded', markActiveNav);
  global.Atlas = { GRADE_LABEL, COUNTRY_NAMES, esc, fold, fmt, fuzzy, photoLarge, gradeBadge, iucnBadge };
})(window);

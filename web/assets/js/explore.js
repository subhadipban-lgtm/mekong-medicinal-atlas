/* Explore page: one filter state drives both the clustered map and the species table. */
(function () {
  'use strict';
  const A = window.Atlas, M = window.AtlasMap;
  const { esc, fmt, fuzzy, gradeBadge, iucnBadge, COUNTRY_NAMES } = A;
  const OUTSIDE_NAME = 'Records outside the basin (generalised to half-degree cells)';
  const INSIDE_NAME = 'Records inside the basin (every record)';

  const state = { q: '', species: '', countries: [], grades: [], family: '', lifeForm: '', iucn: '', cites: '' };
  let SPECIES = [], byId = {}, inLayer = null, outLayer = null, outsideLoading = null, mapState = null, table = null;

  const speciesHref = id => 'species/' + id.replace(/^sp_/, '') + '.html';
  const resolver = id => { const s = byId[id]; return s ? { name: s.name, family: s.family, href: speciesHref(id) } : null; };

  function speciesPasses(s) {
    if (state.species && s.id !== state.species) return false;
    if (state.family && s.family !== state.family) return false;
    if (state.lifeForm && s.life_form !== state.lifeForm) return false;
    if (state.iucn && s.iucn !== state.iucn) return false;
    if (state.cites && s.cites_appendix !== state.cites) return false;
    if (state.q) {
      const hay = [s.name, s.authorship, s.family, (s.synonyms || []).join(' '),
        Object.values(s.local_names || {}).join(' ')].join(' ');
      if (!fuzzy(hay, state.q)) return false;
    }
    return true;
  }
  function countryPasses(s) {
    if (!state.countries.length) return true;
    const cs = new Set([...(s.countries || []), ...(s.occ_countries || [])]);
    return state.countries.some(c => cs.has(c));
  }
  const gradePasses = s => !state.grades.length || state.grades.includes(s.grade);

  function apply(updateAddress) {
    const allowed = new Set(SPECIES.filter(s => speciesPasses(s) && gradePasses(s)).map(s => s.id));
    const countries = state.countries.length ? new Set(state.countries) : null;
    const pick = m => allowed.has(m.feature.properties.id) && (!countries || countries.has(m.feature.properties.c));
    const shown = inLayer.markers.filter(pick);
    inLayer.show(shown);
    let records = shown.reduce((a, m) => a + m.feature.properties.n, 0);
    const ids = new Set(shown.map(m => m.feature.properties.id));
    if (outLayer && mapState.map.hasLayer(outLayer.group)) {
      const outer = outLayer.markers.filter(pick);
      outLayer.show(outer);
      outer.forEach(m => { records += m.feature.properties.n; ids.add(m.feature.properties.id); });
    } else if (outLayer) {
      outLayer.show([]);
    }
    const el = document.getElementById('mapStatus');
    const grades = [...new Set([...shown, ...(outLayer && mapState.map.hasLayer(outLayer.group) ? outLayer.markers.filter(pick) : [])]
      .map(m => m.feature.properties.g || 'C'))].sort().join('/');
    if (el) el.textContent = `${fmt(records)} records shown · ${fmt(ids.size)} species · evidence grade${grades.length > 1 ? 's' : ''} ${grades}`;
    if (table) table.draw();
    const n = document.getElementById('nSpeciesShown');
    if (n) n.textContent = fmt(ids.size);
    if (updateAddress) {
      const p = new URLSearchParams();
      if (state.species) p.set('taxon', byId[state.species].name);
      if (state.countries.length) p.set('country', state.countries.join(','));
      if (state.family) p.set('family', state.family);
      if (state.grades.length) p.set('grade', state.grades.join(','));
      if (state.q) p.set('q', state.q);
      history.replaceState(null, '', location.pathname + (p.toString() ? '?' + p : ''));
    }
  }

  function readControls() {
    state.q = document.getElementById('q').value.trim();
    state.species = document.getElementById('fSpecies').value;
    state.countries = [...document.getElementById('fCountry').selectedOptions].map(o => o.value);
    state.grades = [...document.querySelectorAll('#gradeBoxes input:checked')].map(b => b.value);
    state.family = document.getElementById('fFamily').value;
    state.lifeForm = document.getElementById('fLifeForm').value;
    state.iucn = document.getElementById('fIucn').value;
    state.cites = document.getElementById('fCites').value;
  }

  function fillSelect(id, items, allLabel) {
    const el = document.getElementById(id);
    el.innerHTML = `<option value="">${esc(allLabel)}</option>` + items.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('');
  }

  function loadOutside() {
    if (!outsideLoading) {
      outsideLoading = M.getJSON('data/geo/occurrences_outside_basin.geojson', 30000).then(gj => {
        outLayer = M.occurrenceLayer(mapState, gj, { light: true, species: resolver });
        return outLayer;
      });
    }
    return outsideLoading;
  }

  function initTable() {
    const rows = SPECIES.map(s => [
      `<a class="taxon" href="${speciesHref(s.id)}">${esc(s.name)}</a> <span class="text-muted small">${esc(s.authorship || '')}</span>`,
      esc(s.family || '–'),
      (s.occ_countries || []).map(c => COUNTRY_NAMES[c] || c).join(', ') || '–',
      gradeBadge(s.grade),
      iucnBadge(s.iucn),
      fmt(s.n_in_basin),
      fmt(s.n_records),
      `<a class="btn btn-sm btn-outline-success" href="${speciesHref(s.id)}">Open</a>`]);
    $.fn.dataTable.ext.search.push((settings, data, index) => {
      const s = SPECIES[index];
      return speciesPasses(s) && gradePasses(s) && countryPasses(s);
    });
    table = $('#speciesTable').DataTable({
      data: rows, pageLength: 25, lengthMenu: [[25, 50, 100], [25, 50, 100]], order: [[0, 'asc']],
      autoWidth: false, searching: false, dom: "<'row'<'col-sm-5'l><'col-sm-7'f>>" + "<'row'<'col-12'tr>>" + "<'row'<'col-sm-5'i><'col-sm-7'p>>",
      language: { info: '_START_–_END_ of _TOTAL_ species', lengthMenu: 'Show _MENU_ species' },
      columnDefs: [{ targets: [3, 4, 5, 6, 7], className: 'text-nowrap' }]
    });
  }

  function exportVisible() {
    const lines = [['accepted_name', 'family', 'countries_in_basin', 'evidence_grade', 'iucn_category', 'cites_appendix',
      'records_in_basin', 'records_in_countries', 'species_page'].join(',')];
    table.rows({ search: 'applied' }).every(function () {
      const s = SPECIES[this.index()];
      lines.push([s.name, s.family, (s.occ_countries || []).join(';'), s.grade, s.iucn, s.cites_appendix,
        s.n_in_basin, s.n_records, speciesHref(s.id)].map(v => `"${String(v).replace(/"/g, '""')}"`).join(','));
    });
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'mekong_medicinal_plant_atlas_selection.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function init() {
    Promise.all([M.getJSON('data/species.json'), M.create(document.getElementById('map'), { countries: true }),
      M.getJSON('data/geo/occurrences.geojson', 30000)]).then(([species, ms, gj]) => {
      SPECIES = species; byId = Object.fromEntries(SPECIES.map(s => [s.id, s]));
      mapState = ms;
      inLayer = M.occurrenceLayer(ms, gj, { species: resolver });
      inLayer.group.addTo(ms.map);

      fillSelect('fSpecies', SPECIES.map(s => [s.id, s.name]), `All species (${SPECIES.length})`);
      fillSelect('fFamily', [...new Set(SPECIES.map(s => s.family).filter(Boolean))].sort().map(f => [f, f]), 'All families');
      fillSelect('fLifeForm', [...new Set(SPECIES.map(s => s.life_form).filter(Boolean))].sort().map(f => [f, f]), 'All life forms');
      fillSelect('fIucn', [['CR', 'CR - Critically Endangered'], ['EN', 'EN - Endangered'], ['VU', 'VU - Vulnerable'],
        ['NT', 'NT - Near Threatened'], ['LC', 'LC - Least Concern'], ['DD', 'DD - Data Deficient']], 'Any IUCN status');
      fillSelect('fCites', [['I', 'CITES Appendix I'], ['II', 'CITES Appendix II'], ['III', 'CITES Appendix III'],
        ['not listed', 'Not listed in CITES']], 'Any CITES status');
      const countrySelect = document.getElementById('fCountry');
      countrySelect.innerHTML = Object.keys(COUNTRY_NAMES).sort((a, b) => COUNTRY_NAMES[a].localeCompare(COUNTRY_NAMES[b]))
        .map(c => `<option value="${c}">${esc(COUNTRY_NAMES[c])}</option>`).join('');

      // Address parameters link here from species pages and from the home page.
      const p = new URLSearchParams(location.search);
      const taxon = p.get('taxon');
      if (taxon) {
        const key = A.fold(taxon);
        const hit = SPECIES.find(s => A.fold(s.name) === key) ||
          SPECIES.find(s => (s.synonyms || []).some(x => A.fold(x).includes(key))) || SPECIES.find(s => A.fold(s.name).startsWith(key));
        if (hit) state.species = hit.id;
      }
      if (p.get('country')) state.countries = p.get('country').split(',').filter(c => COUNTRY_NAMES[c]);
      if (p.get('family')) state.family = p.get('family');
      if (p.get('grade')) state.grades = p.get('grade').split(',');
      if (p.get('q')) state.q = p.get('q');
      document.getElementById('q').value = state.q;
      document.getElementById('fSpecies').value = state.species;
      document.getElementById('fFamily').value = state.family;
      [...countrySelect.options].forEach(o => { o.selected = state.countries.includes(o.value); });
      document.querySelectorAll('#gradeBoxes input').forEach(b => { b.checked = state.grades.includes(b.value); });

      const overlays = M.addOverlays(ms, true);
      const outsidePlaceholder = L.featureGroup();
      overlays[INSIDE_NAME] = inLayer.group;
      overlays[OUTSIDE_NAME] = outsidePlaceholder;
      L.control.layers({ 'CartoDB Positron': ms.base }, overlays, { collapsed: true, position: 'topleft' }).addTo(ms.map);
      ms.map.on('overlayadd', e => {
        if (e.name !== OUTSIDE_NAME) return;
        ms.map.removeLayer(outsidePlaceholder);
        loadOutside().then(layer => { layer.group.addTo(ms.map); apply(false); });
      });
      ms.map.on('overlayremove', e => { if (e.name === OUTSIDE_NAME && outLayer) ms.map.removeLayer(outLayer.group); });

      initTable();
      apply(false);
      // Test handles (harmless in normal use): the browser checks read these.
      window.__atlasExplore = { map: ms.map, inLayer, outLayer: () => outLayer, apply, state, SPECIES };
      if (state.species) {
        const own = inLayer.markers.filter(m => m.feature.properties.id === state.species);
        if (own.length) ms.map.fitBounds(L.latLngBounds(own.map(m => m.getLatLng())).pad(0.5));
      }
      document.querySelectorAll('#filterPanel input, #filterPanel select').forEach(el => {
        el.addEventListener('change', () => { readControls(); apply(true); });
      });
      let timer;
      document.getElementById('q').addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => { readControls(); apply(true); }, 250);
      });
      document.getElementById('resetFilters').addEventListener('click', () => {
        document.getElementById('filterPanel').reset();
        document.querySelectorAll('#gradeBoxes input').forEach(b => { b.checked = true; });
        readControls(); apply(true);
      });
      document.getElementById('exportVisible').addEventListener('click', exportVisible);

      /* ---- bioeconomy priority overlay (off by default, loads lazily) ---- */
      const bioChk = document.getElementById('bioeconLayer');
      const bioNote = document.getElementById('bioeconNote');
      let bioLayer = null, bioLoading = false;
      if (bioChk) bioChk.addEventListener('change', () => {
        if (!bioChk.checked) {
          if (bioLayer) ms.map.removeLayer(bioLayer);
          if (bioNote) bioNote.textContent = 'Overlay off. Enable it to count high-priority bioeconomy taxa per 5 km cell.';
          return;
        }
        if (bioLoading) return;
        bioLoading = true;
        if (bioNote) bioNote.textContent = 'Loading the bioeconomy overlay…';
        M.getJSON('data/geo/bioeconomy_priority_cells.geojson', 20000).then(gj => {
          bioLayer = L.geoJSON(gj, {
            style: f => ({ color: '#8b1a1a', weight: 0.5, fillColor: '#b71c1c', fillOpacity: 0.45 }),
            onEachFeature: (f, l) => l.bindTooltip('5 km cell with ' + f.properties.count_high +
              ' high-priority bioeconomy taxa', { sticky: true })
          }).addTo(ms.map);
          bioLoading = false;
          const leg = document.getElementById('bioeconLegend');
          if (leg) leg.hidden = false;
          if (bioNote) bioNote.textContent = gj.features.length
            ? gj.features.length + ' cells with at least one high-priority bioeconomy taxon.'
            : 'No atlas taxon currently has a high-priority bioeconomy tier, so the layer is empty. See the Data tab for why.';
        }).catch(err => {
          bioLoading = false;
          bioChk.checked = false;
          if (bioNote) bioNote.textContent = 'The bioeconomy overlay could not be loaded: ' + err.message;
        });
      });
      document.getElementById('loading').remove();
    }).catch(err => {
      const el = document.getElementById('loading');
      if (el) el.textContent = 'The map data could not be loaded: ' + err.message;
    });
  }
  document.addEventListener('DOMContentLoaded', init);
})();

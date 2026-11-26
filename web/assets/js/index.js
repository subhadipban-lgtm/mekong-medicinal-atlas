/* Home page: the basin map with clustered in-basin records and a country filter.
   Record scope toggle (disabled until the in-basin layer is drawn): "In-basin" loads only
   data/geo/occurrences.geojson (default). "All records" lazily fetches
   data/geo/occurrences_outside_basin.geojson — the count comes from #mapScope[data-outside] —
   generalised to one point per species per half-degree cell — and adds it as a second
   marker-clustered layer (disableClusteringAtZoom = 6, the generalisation cell).
   Chosen approach (documented in the repo): a separate GeoJSON loaded lazily on toggle,
   with markercluster enabled, so the default load never touches the 6 MB out-of-basin file. */
(function () {
  'use strict';
  const A = window.Atlas, M = window.AtlasMap;
  const { fmt, fuzzy } = A;

  function init() {
    const el = document.getElementById('map');
    if (!el) return;
    /* Loading badge: count each of the three parts as it arrives (species list, base map,
       in-basin records) so a slow connection shows progress rather than a frozen message. */
    const stepEl = document.getElementById('homeLoadingStep');
    let ready = 0;
    const step = p => p.then(v => {
      ready += 1;
      if (stepEl) stepEl.textContent = `${ready} of 3 parts ready`;
      return v;
    });
    const scopeBox = document.getElementById('mapScope');
    const outsideN = Number(scopeBox && scopeBox.dataset.outside) || 0;
    const IN_NOTE = 'Showing in-basin records only; switch to all records to add the out-of-basin layer.';
    Promise.all([step(M.getJSON('data/species.json')), step(M.create(el, { countries: true })),
                 step(M.getJSON('data/geo/occurrences.geojson', 30000))])
      .then(([species, ms, gj]) => {
        const byId = Object.fromEntries(species.map(s => [s.id, s]));
        const speciesInfo = id => { const s = byId[id]; return s ? { name: s.name, family: s.family, href: 'species/' + id.replace(/^sp_/, '') + '.html' } : null; };
        const layer = M.occurrenceLayer(ms, gj, { species: speciesInfo });
        const overlays = M.addOverlays(ms, true);
        layer.group.addTo(ms.map);
        overlays['Occurrence records inside the basin'] = layer.group;
        L.control.layers({ 'CartoDB Positron': ms.base }, overlays, { collapsed: true, position: 'topleft' }).addTo(ms.map);

        const country = document.getElementById('homeCountry');
        const search = document.getElementById('homeSearch');
        const scopeNote = document.getElementById('scopeNote');
        let all = [];
        function draw() {
          const q = search.value.trim(), c = country.value;
          all = layer.markers.filter(m => {
            const p = m.feature.properties, s = byId[p.id];
            if (c && p.c !== c) return false;
            if (q && s && !fuzzy([s.name, s.family, (s.synonyms || []).join(' ')].join(' '), q)) return false;
            return true;
          });
          layer.show(all);
          const ids = new Set(all.map(m => m.feature.properties.id));
          document.getElementById('homeStatus').textContent = q || c
            ? `${fmt(all.length)} records · ${fmt(ids.size)} species`
            : `${fmt(all.length)} georeferenced records inside the basin boundary`;
        }
        country.addEventListener('change', draw);
        let timer;
        search.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(draw, 250); });
        draw();

        /* ---- scope toggle: lazily add the out-of-basin layer ------------------------ */
        let outside = null;   // { group, markers, show } once loaded
        let outsideLoading = false;
        const scopeIn = document.getElementById('scopeInBasin');
        const scopeAll = document.getElementById('scopeAll');

        function setScope(value) {
          if (value === 'all') {
            if (!outside && !outsideLoading) {
              outsideLoading = true;
              if (scopeNote) scopeNote.textContent = `Loading the out-of-basin layer (${fmt(outsideN)} records, generalised)…`;
              if (scopeNote) scopeNote.classList.add('is-loading');
              M.getJSON('data/geo/occurrences_outside_basin.geojson', 60000)
                .then(gj => {
                  outside = M.occurrenceLayer(ms, gj, {
                    light: true, species: speciesInfo, disableClusteringAtZoom: 6
                  });
                  overlays['Occurrence records outside the basin (generalised)'] = outside.group;
                  outside.group.addTo(ms.map);
                  outside.show(outside.markers);
                  outsideLoading = false;
                  if (scopeNote) scopeNote.classList.remove('is-loading');
                  if (scopeNote) scopeNote.textContent = 'All records shown; out-of-basin points are generalised to one point per species per half-degree cell.';
                })
                .catch(err => {
                  outsideLoading = false;
                  if (scopeNote) scopeNote.classList.remove('is-loading');
                  if (scopeNote) scopeNote.textContent = 'The out-of-basin layer could not be loaded: ' + err.message;
                  if (scopeIn) scopeIn.checked = true;
                  if (scopeAll) scopeAll.checked = false;
                });
            } else if (outside) {
              outside.show(outside.markers);
              if (scopeNote) scopeNote.textContent = 'All records shown; out-of-basin points are generalised to one point per species per half-degree cell.';
            }
          } else {
            if (outside) outside.show([]);
            if (scopeNote) scopeNote.textContent = IN_NOTE;
          }
        }
        if (scopeIn) scopeIn.addEventListener('change', () => setScope('in'));
        if (scopeAll) scopeAll.addEventListener('change', () => setScope('all'));
        [scopeIn, scopeAll].forEach(r => { if (r) r.disabled = false; });
        if (scopeNote) scopeNote.textContent = IN_NOTE;
        const loading = document.getElementById('homeLoading');
        if (loading) loading.remove();
        window.__atlasHomeReady = true;
      })
      .catch(err => {
        const loading = document.getElementById('homeLoading');
        if (loading) {
          loading.classList.add('is-error');
          loading.textContent = 'The map data could not be loaded: ' + err.message;
        }
        const note = document.getElementById('scopeNote');
        if (note) note.textContent = 'The record scope is unavailable because the map data did not load.';
      });
  }
  document.addEventListener('DOMContentLoaded', init);
})();

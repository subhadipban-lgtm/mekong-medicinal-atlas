/* Home page: the basin map with clustered in-basin records and a country filter. */
(function () {
  'use strict';
  const A = window.Atlas, M = window.AtlasMap;
  const { esc, fmt, fuzzy, COUNTRY_NAMES } = A;

  function init() {
    const el = document.getElementById('map');
    if (!el) return;
    Promise.all([M.getJSON('data/species.json'), M.create(el, { countries: true }), M.getJSON('data/geo/occurrences.geojson', 30000)])
      .then(([species, ms, gj]) => {
        const byId = Object.fromEntries(species.map(s => [s.id, s]));
        const layer = M.occurrenceLayer(ms, gj, {
          species: id => { const s = byId[id]; return s ? { name: s.name, family: s.family, href: 'species/' + id.replace(/^sp_/, '') + '.html' } : null; }
        });
        const overlays = M.addOverlays(ms, true);
        layer.group.addTo(ms.map);
        overlays['Occurrence records inside the basin'] = layer.group;
        L.control.layers({ 'CartoDB Positron': ms.base }, overlays, { collapsed: true, position: 'topleft' }).addTo(ms.map);

        const country = document.getElementById('homeCountry');
        const search = document.getElementById('homeSearch');
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
        const loading = document.getElementById('homeLoading');
        if (loading) loading.remove();
      })
      .catch(err => {
        const loading = document.getElementById('homeLoading');
        if (loading) loading.textContent = 'The map data could not be loaded: ' + err.message;
      });
  }
  document.addEventListener('DOMContentLoaded', init);
})();

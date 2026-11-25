/* Species page: a map of one species' records, without clustering. */
(function () {
  'use strict';
  const A = window.Atlas, M = window.AtlasMap;
  const { esc, COUNTRY_NAMES } = A;

  function init() {
    const el = document.getElementById('map');
    if (!el) return;
    Promise.all([M.create(el, { fit: 'none', scrollWheelZoom: false }), M.getJSON('data/' + el.dataset.file + '.geojson')])
      .then(([ms, gj]) => {
        const overlays = M.addOverlays(ms, false);
        const points = L.featureGroup();
        gj.features.forEach(f => {
          const p = f.properties;
          const marker = L.circleMarker([f.geometry.coordinates[1], f.geometry.coordinates[0]], {
            radius: p.n > 1 ? 6 : 5, weight: p.s ? 1.5 : 2, color: M.GRADE_FILL.C, opacity: 0.95,
            fillColor: p.s ? M.GRADE_FILL.C : '#ffffff', fillOpacity: p.n > 1 ? 0.5 : 0.95
          });
          marker.bindPopup(M.recordPopup(Object.assign({ gen: p.gen }, p), { name: el.dataset.name, family: el.dataset.family, href: null }));
          marker.addTo(points);
        });
        points.addTo(ms.map);
        if (gj.features.length) ms.map.fitBounds(points.getBounds().pad(0.45));
        else ms.map.fitBounds(ms.basin.getBounds());
        const empty = document.getElementById('mapEmpty');
        if (empty) empty.remove();
      })
      .catch(err => {
        const empty = document.getElementById('mapEmpty');
        if (empty) empty.textContent = 'The map data could not be loaded: ' + err.message;
      });
  }
  document.addEventListener('DOMContentLoaded', init);
})();

/* Sustainability page map: harvest-pressure tiers, major dams and their 10 km buffers. */
(function () {
  'use strict';
  const M = window.AtlasMap;

  function init() {
    const el = document.getElementById('map');
    if (!el) return;
    M.create(el, { countries: true }).then(ms => {
      const overlays = M.addOverlays(ms, false);
      const failures = [];
      const promises = [
        M.getJSON('data/geo/harvest_pressure_tiers.geojson').then(gj => {
          const layer = L.geoJSON(gj, { style: f => ({ color: f.properties.fill, weight: 0.5, fillColor: f.properties.fill, fillOpacity: 0.55 }),
            onEachFeature: (f, l) => l.bindTooltip('Harvest-pressure tier: ' + f.properties.tier, { sticky: true }) });
          overlays['Harvest-pressure proxy (tiers)'] = layer;
          layer.addTo(ms.map);
          return layer;
        }).catch(() => failures.push("Harvest-pressure layer unavailable")),
        M.getJSON('data/geo/mekong_dams.geojson').then(gj => {
          const major = L.featureGroup();
          const buffers = L.featureGroup();
          gj.features.forEach(f => {
            const p = f.properties;
            const num = v => { const x = parseFloat(v); return isNaN(x) ? null : x; };
            const h = num(p.height_m), cap = num(p.capacity_mw);
            if (!(h !== null && h >= 15) && !(cap !== null && cap >= 15)) return;
            const ll = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
            L.circleMarker(ll, { radius: 4, color: '#1f5f8b', weight: 1.5, fillColor: '#1f5f8b', fillOpacity: 0.9 })
              .bindTooltip('<strong>' + (p.name || p.alternate_name || 'dam') + '</strong><br>' + (p.country || '') + ' · ' + (p.river || ''))
              .addTo(major);
            L.circle(ll, { radius: 10000, color: '#1f5f8b', weight: 1, fill: false, opacity: 0.6, dashArray: '4 4' }).addTo(buffers);
          });
          overlays['Major dams (' + major.getLayers().length + ')'] = major;
          major.addTo(ms.map);
          overlays['Dam influence buffer (10 km)'] = buffers;
        }).catch(() => failures.push("Dam and buffer layers unavailable")),
      ];
      Promise.all(promises).then(() => {
        L.control.layers({ 'CartoDB Positron': ms.base }, overlays, { collapsed: false, position: 'topleft' }).addTo(ms.map);
        document.getElementById('sustStatus').textContent = failures.length ? failures.join('; ') : 'Toggle the layers with the control (top left).';
      });
    }).catch(err => {
      const el = document.getElementById('sustStatus');
      if (el) el.textContent = 'The sustainability map could not be loaded: ' + err.message;
    });
  }
  document.addEventListener('DOMContentLoaded', init);
})();

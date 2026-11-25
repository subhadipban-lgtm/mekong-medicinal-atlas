/* Map building blocks shared by the home, explore and species pages.
   Layer order is fixed with custom panes: basemap < basin boundary < river < occurrence records,
   so the order in which remote layers arrive cannot change the visual hierarchy. */
(function (global) {
  'use strict';

  const CARTO_KEY = 'cb1_5f90_1_2200dcf519089dbbd5552a5c';
  const BASEMAP_STYLE = 'light_all'; // CartoDB Positron; also valid: voyager, dark_all
  const WWF_RIVER_URL = ('https://services1.arcgis.com/RTK5Unh1Z71JKIiR/ArcGIS/rest/services/Mekong_River_/FeatureServer/0/' +
                         'query?where=1%3D1&outFields=*&f=geojson');
  const RIVER_TIMEOUT_MS = 9000;
  const GRADE_FILL = { A: '#1b5e20', B: '#b36b00', C: '#66707a', D: '#a23b3b' };
  const ATTRIBUTION = ('© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> ' +
    'contributors © <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a> · ' +
    'Basin: <a href="https://doi.org/10.5281/zenodo.7622998" target="_blank" rel="noopener">Tiwari et al. (Zenodo, CC-BY 4.0)</a> · ' +
    'River: WWF-Laos / Natural Earth · Records: <a href="https://www.gbif.org" target="_blank" rel="noopener">GBIF</a>');

  const { esc, fmt, COUNTRY_NAMES } = global.Atlas;

  function getJSON(url, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs || 20000);
    return fetch(url, { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .finally(() => clearTimeout(timer));
  }

  function riverStyle() {
    return { color: '#1f5f8b', weight: 3.5, opacity: 0.92 };
  }

  function create(el, options) {
    const opts = Object.assign({ fit: 'basin', minZoom: 4, maxZoom: 12, countries: false }, options || {});
    const map = L.map(el, { attributionControl: false, minZoom: opts.minZoom, maxZoom: opts.maxZoom,
      scrollWheelZoom: opts.scrollWheelZoom !== false });
    map.createPane('basinPane').style.zIndex = 350;
    map.createPane('riverPane').style.zIndex = 360;
    L.control.attribution({ position: 'bottomright', prefix: false }).addAttribution(ATTRIBUTION).addTo(map);
    L.control.scale({ imperial: false, position: 'bottomright' }).addTo(map);
    const base = L.tileLayer(`https://basemaps.cartocdn.com/rastertiles/${BASEMAP_STYLE}/{z}/{x}/{y}.png?key=${CARTO_KEY}`, {
      maxZoom: opts.maxZoom }).addTo(map);

    // A map without a view loads no tiles, so pages that fit to their own data later still start
    // from a sensible view.
    if (opts.fit === 'none') map.setView([17.5, 103], 5);
    const state = { map, base, basin: null, river: null, riverSource: null, countries: null };

    const basin = getJSON('data/geo/mekong_basin_display.geojson').then(gj => {
      state.basin = L.geoJSON(gj, {
        pane: 'basinPane', interactive: false,
        style: () => ({ color: '#166a4f', weight: 1.5, dashArray: '6 5', fillColor: '#166a4f', fillOpacity: 0.12 })
      }).addTo(map);
      if (opts.fit === 'basin') {
        map.fitBounds(state.basin.getBounds().pad(0.03));
        // Fitting the basin's full north-south extent floors the zoom one level too far; step in
        // when the map is tall enough to hold it, so the atlas opens on the basin itself.
        if (map.getZoom() < 5 && map.getSize().y >= 620) map.setZoom(5);
      }
      return state.basin;
    });
    /* The WWF centreline carries no stated licence, so it is rendered from the publisher's service
       and never redistributed; Natural Earth (public domain) is the committed fallback. */
    const river = getJSON(WWF_RIVER_URL, opts.riverTimeoutMs || RIVER_TIMEOUT_MS).then(gj => {
      state.river = L.geoJSON(gj, { pane: 'riverPane', style: riverStyle, interactive: false });
      state.riverSource = 'WWF-Laos (ArcGIS Online)';
    }).catch(() => getJSON('data/geo/mekong_river_naturalearth.geojson').then(gj => {
      state.river = L.geoJSON(gj, { pane: 'riverPane', style: riverStyle, interactive: false });
      state.riverSource = 'Natural Earth';
    })).catch(() => { state.riverSource = null; });
    const countries = opts.countries ? getJSON('data/geo/countries_outline.geojson').then(gj => {
      state.countries = L.geoJSON(gj, { pane: 'basinPane', interactive: false,
        style: () => ({ color: '#5b6962', weight: 0.8, fill: false, opacity: 0.65 }) });
      return state.countries;
    }).catch(() => null) : Promise.resolve(null);
    return Promise.all([basin, river, countries]).then(() => state);
  }

  /* Adds the river and basin overlays to the map in display order and returns them for a layer control. */
  function addOverlays(state, withCountries) {
    if (state.countries && withCountries) state.countries.addTo(state.map);
    state.basin.addTo(state.map);
    if (state.river) state.river.addTo(state.map);
    const overlays = { 'Mekong basin boundary': state.basin, 'Mekong River': state.river || L.featureGroup() };
    if (state.countries && withCountries) overlays['Country outlines'] = state.countries;
    return overlays;
  }

  function markerOptions(p, light) {
    const grade = GRADE_FILL[p.g] ? p.g : 'C';
    return {
      radius: light ? 4 : (p.n > 1 ? 6 : 5),
      color: GRADE_FILL[grade], weight: light ? 1.2 : (p.s ? 1.5 : 2), opacity: light ? 0.7 : 0.95,
      fillColor: p.s ? GRADE_FILL[grade] : '#ffffff', fillOpacity: (light ? 0.45 : 0.95) * (p.q === 'low' ? 0.6 : 1),
      className: p.q === 'low' ? 'occ-low' : ''
    };
  }

  function recordPopup(p, sp) {
    const countries = COUNTRY_NAMES[p.c] || p.c || '–';
    const quality = { high: 'high', medium: 'medium', low: 'low' }[p.q] || p.q || '–';
    return `<div class="occ-popup"><strong class="taxon">${esc(sp ? sp.name : p.id)}</strong><br>
      <span class="text-muted">${esc(sp ? sp.family : '')}</span>
      <table>
        ${p.n === 1
          ? `<tr><td>Basis</td><td>${p.s ? 'specimen (herbarium or living voucher)' : 'observation'}</td></tr>`
          : `<tr><td><strong>${fmt(p.n)}</strong></td><td>records at this location (evidence grade ${esc(p.g || 'C')})</td></tr>
             <tr><td colspan="2" class="text-muted">Location generalised to a half-degree cell</td></tr>`}
      </table>
      Country: ${esc(countries)}${p.gen ? ' · <span class="badge badge-sens">generalised locality</span>' : ''}<br>
      Coordinate quality: ${esc(quality)}${p.q === 'low' ? ' (rendered hollow)' : ''}<br>
      ${p.k ? `<a href="https://www.gbif.org/occurrence/${esc(p.k)}" target="_blank" rel="noopener">Example record in GBIF</a> · ` : ''}
      ${sp && sp.href ? `<a href="${esc(sp.href)}">Species page</a>` : ''}</div>`;
  }

  /* Builds one marker per feature once; filtering then swaps subsets in and out of the cluster group. */
  function occurrenceLayer(state, geojson, opts) {
    const o = Object.assign({ light: false, species: () => null }, opts || {});
    const group = L.markerClusterGroup({
      disableClusteringAtZoom: 12, maxClusterRadius: 55, spiderfyOnMaxZoom: true,
      showCoverageOnHover: false, zoomToBoundsOnClick: false, animate: false
    });

    group.options.iconCreateFunction = cluster => {
      const tally = { A: 0, B: 0, C: 0 };
      let records = 0;
      cluster.getAllChildMarkers().forEach(m => { tally[m.feature.properties.g] += m.feature.properties.n; records += m.feature.properties.n; });
      // The dominant evidence grade of a cluster is the grade with the most records behind it.
      const dominant = ['A', 'B', 'C'].reduce((best, g) => tally[g] > tally[best] ? g : best, 'C');
      const size = records > 9999 ? 'l' : records > 199 ? 'm' : 's';
      return L.divIcon({ html: `<div class="cluster ${size} ${dominant}" title="${fmt(records)} records">${records > 9999 ? Math.round(records / 1000) + 'k' : fmt(records)}</div>`,
        className: 'cluster-wrap', iconSize: size === 'l' ? [50, 50] : size === 'm' ? [38, 38] : [28, 28] });
    };

    const markers = geojson.features.filter(f => f.geometry && f.geometry.type === 'Point').map(f => {
      const p = f.properties;
      const marker = L.circleMarker([f.geometry.coordinates[1], f.geometry.coordinates[0]], markerOptions(p, o.light));
      marker.feature = f;
      marker.bindPopup(() => recordPopup(p, o.species(p.id)));
      return marker;
    });

    /* MarkerCluster (pinned 1.5.3) spiderfies a cluster itself when all its markers stay together at
       the lowest clustering zoom; the composition popup must not compete with that. */
    function pluginSpiderfies(cluster) {
      let bottom = cluster;
      while (bottom._childClusters && bottom._childClusters.length === 1) bottom = bottom._childClusters[0];
      return bottom._zoom === group._maxZoom && bottom._childCount === cluster._childCount && group.options.spiderfyOnMaxZoom;
    }

    // Species composition of a cluster: the species with the most records behind it, most first.
    function composition(cluster) {
      const species = new Map();
      let records = 0;
      cluster.getAllChildMarkers().forEach(m => {
        const p = m.feature.properties;
        records += p.n;
        const entry = species.get(p.id) || Object.assign({ n: 0 }, o.species(p.id) || { name: p.id, href: null });
        entry.n += p.n;
        species.set(p.id, entry);
      });
      return { species: [...species.values()].sort((x, y) => y.n - x.n), records, nSpecies: species.size };
    }

    group.on('clusterclick', a => {
      if (pluginSpiderfies(a.layer)) return;
      const { species, records, nSpecies } = composition(a.layer);
      // Species composition of the cluster: the five species with the most records behind it.
      const top = species.slice(0, 5);
      const rows = top.map(s => `<tr><td><strong>${fmt(s.n)}</strong></td><td>${s.href ? `<a href="${esc(s.href)}" class="taxon">${esc(s.name)}</a>` : `<span class="taxon">${esc(s.name)}</span>`}</td></tr>`).join('');
      L.popup({ maxWidth: 320 }).setLatLng(a.latlng).setContent(
        `<div class="occ-popup"><strong>${fmt(nSpecies)}</strong> species · <strong>${fmt(records)}</strong> records in this cluster
         <table>${rows}</table>${nSpecies > 5 ? `<span class="text-muted">and ${nSpecies - 5} more species</span><br>` : ''}
         <button class="btn btn-sm btn-outline-success" id="zoomCluster">Zoom in</button></div>`)
        .openOn(state.map);
      const btn = document.getElementById('zoomCluster');
      if (btn) btn.addEventListener('click', () => { state.map.closePopup(); state.map.fitBounds(a.layer.getBounds().pad(0.2)); });
    });

    let current = [];
    function show(which) {
      if (current.length) group.removeLayers(current);
      current = which;
      if (which.length) group.addLayers(which);
      return which.length;
    }
    return { group, markers, show, composition, pluginSpiderfies };
  }

  global.AtlasMap = { create, addOverlays, occurrenceLayer, getJSON, GRADE_FILL, recordPopup, WWF_RIVER_URL };
})(window);

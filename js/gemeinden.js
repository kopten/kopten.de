/* ============================================================
   Gemeindefinder — koptische Gemeinden in Deutschland
   Daten: data/kopten_gemeinden.xml
   Karte: Google Maps JS API
   ============================================================ */

let gMap = null;
let gGeocoder = null;
let gemeindenData = []; /* parsed XML items, with lat/lng once geocoded */
let markers = [];
let activeInfoWindow = null;
let userMarker = null;

const MAP_CENTER_DE = { lat: 51.1657, lng: 10.4515 };

/* i18n strings — controlled via <script data-lang="en"> attribute */
const FINDER_SCRIPT = document.currentScript;
const LANG = (FINDER_SCRIPT && FINDER_SCRIPT.dataset.lang) || "de";
const BASE = (FINDER_SCRIPT && FINDER_SCRIPT.dataset.base) || "";

const I18N = {
  de: {
    loading: "Lade Gemeinden …",
    countAll: (n) => `${n} Gemeinden in Deutschland`,
    countSorted: (n) => `${n} Gemeinden — nach Entfernung sortiert`,
    detail: "Mehr erfahren →",
    iwDetail: "Detailseite →",
    iwWebsite: "Website →",
    iwRoute: "Route planen",
    iwRouteCar: "Auto",
    iwRouteTransit: "ÖPNV",
    iwRouteWalk: "Zu Fuß",
    mapUnavailable: "Karte derzeit nicht verfügbar",
    mapHint: "Die vollständige Gemeindeliste steht rechts zur Verfügung.",
    addressNotFound:
      "Adresse konnte nicht gefunden werden. Bitte prüfen Sie Ihre Eingabe.",
    geolocationUnsupported:
      "Geolocation wird von Ihrem Browser nicht unterstützt.",
    geolocationDenied:
      "Standort konnte nicht ermittelt werden. Bitte erlauben Sie den Zugriff auf Ihren Standort.",
    yourLocation: "Ihr Standort",
    gemeindenPath: "gemeinden",
    xmlPath: "data/kopten_gemeinden.xml",
    coordsPath: "data/gemeinden-coords.json",
  },
  en: {
    loading: "Loading parishes …",
    countAll: (n) => `${n} parishes in Germany`,
    countSorted: (n) => `${n} parishes — sorted by distance`,
    detail: "Learn more →",
    iwDetail: "Details →",
    iwWebsite: "Website →",
    iwRoute: "Get directions",
    iwRouteCar: "Drive",
    iwRouteTransit: "Transit",
    iwRouteWalk: "Walk",
    mapUnavailable: "Map currently unavailable",
    mapHint: "The full list of parishes is available on the right.",
    addressNotFound: "Address could not be found. Please check your input.",
    geolocationUnsupported: "Geolocation is not supported by your browser.",
    geolocationDenied:
      "Could not determine your location. Please allow access to your location.",
    yourLocation: "Your location",
    gemeindenPath: "communities",
    xmlPath: "../data/kopten_gemeinden.xml",
    coordsPath: "../data/gemeinden-coords.json",
  },
};

const T = I18N[LANG] || I18N.de;

/* --------------------- Build-time geocode cache ---------------------- */
async function loadCoordsCache() {
  try {
    const res = await fetch(T.coordsPath);
    if (!res.ok) return {};
    return await res.json();
  } catch (e) {
    console.warn("Coords cache not available, will fall back to runtime geocoding", e);
    return {};
  }
}

/* --------------------- XML parsing ---------------------- */
async function loadGemeinden() {
  try {
    const res = await fetch(T.xmlPath);
    const text = await res.text();
    const xml = new DOMParser().parseFromString(text, "text/xml");
    const items = xml.getElementsByTagName("gemeinde");
    const out = [];
    for (const g of items) {
      const get = (tag) => {
        const el = g.getElementsByTagName(tag)[0];
        return el ? el.textContent.trim() : "";
      };
      const addr = g.getElementsByTagName("adresse")[0];
      const a = (tag) => {
        if (!addr) return "";
        const el = addr.getElementsByTagName(tag)[0];
        return el ? el.textContent.trim() : "";
      };
      const priesterNode = g.getElementsByTagName("priester")[0];
      const priesterName = priesterNode
        ? priesterNode.getElementsByTagName("name")[0]?.textContent.trim() || ""
        : "";

      const zeitenNodes = g.getElementsByTagName("zeit");
      const zeiten = Array.from(zeitenNodes).map((z) => z.textContent.trim());

      // Read links from <links> sub-element (new schema) or fall back to top-level
      const linksNode = g.getElementsByTagName("links")[0] || g;
      const lk = (tag) => {
        const el = linksNode.getElementsByTagName(tag)[0];
        return el ? el.textContent.trim() : "";
      };

      out.push({
        id: g.getAttribute("id"),
        typ: g.getAttribute("typ"),
        bistum: g.getAttribute("bistum"),
        name: get("name"),
        gemeindeort: get("gemeindeort"),
        url: get("url"),
        strasse: a("strasse"),
        plz: a("plz"),
        ort: a("ort"),
        priester: priesterName,
        zeiten: zeiten,
        website: lk("website"),
        facebook: lk("facebook"),
        instagram: lk("instagram"),
        youtube: lk("youtube"),
        lat: null,
        lng: null,
      });
    }
    return out;
  } catch (err) {
    console.error("Fehler beim Laden der Gemeinden:", err);
    return [];
  }
}

/* --------------------- Geocoding ---------------------- */
function geocodeAddress(item) {
  return new Promise((resolve) => {
    const query = `${item.strasse}, ${item.plz} ${item.ort}, Deutschland`;
    gGeocoder.geocode({ address: query, region: "de" }, (results, status) => {
      if (status === "OK" && results[0]) {
        const loc = results[0].geometry.location;
        item.lat = loc.lat();
        item.lng = loc.lng();
        resolve(item);
      } else {
        /* Fallback: try ORT only */
        gGeocoder.geocode(
          { address: `${item.plz} ${item.ort}, Deutschland`, region: "de" },
          (r2, s2) => {
            if (s2 === "OK" && r2[0]) {
              const loc = r2[0].geometry.location;
              item.lat = loc.lat();
              item.lng = loc.lng();
            }
            resolve(item);
          },
        );
      }
    });
  });
}

/* Fülle Lat/Lng aus dem Build-Time-Cache; nur Fehlende kommen ggf. zur
   Google-Geocoding-API. Spart 99% der API-Calls im Normalbetrieb. */
function applyCachedCoords(items, cache) {
  let filled = 0;
  items.forEach((i) => {
    const c = cache[i.id];
    if (c && typeof c.lat === "number" && typeof c.lng === "number") {
      i.lat = c.lat;
      i.lng = c.lng;
      filled++;
    }
  });
  return filled;
}

/* Throttle: geocode in small batches to respect API limits.
   Aufgerufen nur für Einträge ohne Cache-Hit. */
async function geocodeAll(items) {
  const remaining = items.filter((i) => i.lat == null || i.lng == null);
  if (remaining.length === 0) return;
  const BATCH = 6;
  for (let i = 0; i < remaining.length; i += BATCH) {
    const slice = remaining.slice(i, i + BATCH);
    await Promise.all(slice.map(geocodeAddress));
    await new Promise((r) => setTimeout(r, 150));
    renderResults(gemeindenData);
    renderMarkers(gemeindenData);
  }
}

/* --------------------- Rendering ---------------------- */
function bistumClass(b) {
  if (!b) return "";
  const t = b.toLowerCase();
  if (t.includes("nord")) return "gemeinde-item__bistum--nord";
  if (t.includes("süd") || t.includes("sued"))
    return "gemeinde-item__bistum--sued";
  return "";
}

function escapeHtml(s) {
  return (s || "").replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[c],
  );
}

function renderResults(items, userPos) {
  const list = document.getElementById("finder-list");
  const count = document.getElementById("finder-count");
  if (!list || !count) return;

  /* If we already have coords, sort by distance/name; otherwise show everything alphabetically as a fallback */
  const withCoords = items.filter((i) => i.lat && i.lng);
  let display;
  if (withCoords.length > 0) {
    display = withCoords;
    if (userPos) {
      display.forEach(
        (i) => (i._dist = distanceKm(userPos.lat, userPos.lng, i.lat, i.lng)),
      );
      display.sort((a, b) => a._dist - b._dist);
    } else {
      display.sort((a, b) => (a.gemeindeort || a.name).localeCompare(b.gemeindeort || b.name, "de"));
    }
  } else {
    /* Fallback: Maps/Geocoder not (yet) available — show full list without distance */
    display = [...items].sort((a, b) => (a.gemeindeort || a.name).localeCompare(b.gemeindeort || b.name, "de"));
  }

  count.textContent = userPos
    ? T.countSorted(display.length)
    : T.countAll(display.length);

  list.innerHTML = display
    .map((i) => {
      /* derive the slug from the url field */
      const slug = detailSlug(i.url);
      const detailLink = slug
        ? `<a class="gemeinde-item__detail" href="${T.gemeindenPath}/${slug}/">${T.detail}</a>`
        : "";
      return `
    <div class="gemeinde-item" data-id="${escapeHtml(i.id)}">
      ${i.gemeindeort ? `<p class="gemeinde-item__ort">${escapeHtml(i.gemeindeort)}</p>` : ""}
      <h4 class="gemeinde-item__name">${escapeHtml(i.name)}</h4>
      <p class="gemeinde-item__address">${escapeHtml([i.strasse, `${i.plz} ${i.ort}`].filter(Boolean).join(", "))}</p>
      <span class="gemeinde-item__bistum ${bistumClass(i.bistum)}">${escapeHtml(i.typ)} · ${escapeHtml(i.bistum || "")}</span>
      ${i._dist != null ? `<span class="gemeinde-item__distance">${i._dist.toFixed(1)} km</span>` : ""}
      ${detailLink}
    </div>`;
    })
    .join("");

  /* Click to focus marker */
  list.querySelectorAll(".gemeinde-item").forEach((el) => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-id");
      const item = gemeindenData.find((g) => g.id === id);
      if (!item || !item.lat) return;
      gMap.panTo({ lat: item.lat, lng: item.lng });
      gMap.setZoom(11);
      const marker = markers.find((m) => m._id === id);
      if (marker && marker._openIw) marker._openIw();
      list
        .querySelectorAll(".gemeinde-item")
        .forEach((e) => e.classList.remove("is-active"));
      el.classList.add("is-active");
    });
  });
}

/* Farb-Palette pro Bistum */
const BISTUM_COLORS = {
  nord: { bg: "#7a1f1f", cross: "#c9a961" }, /* Burgunder + Gold */
  sued: { bg: "#1f5a8a", cross: "#f0e0a8" }, /* Petrol-Blau + Hellgold */
};

function colorsFor(bistum) {
  const b = (bistum || "").toLowerCase();
  if (b.includes("nord")) return BISTUM_COLORS.nord;
  if (b.includes("süd") || b.includes("sued")) return BISTUM_COLORS.sued;
  return BISTUM_COLORS.nord; /* Fallback */
}

/* DOM-Element für AdvancedMarkerElement statt SVG-Data-URL.
   Klöster: 52×64 mit Goldring; Gemeinden: 36×44. */
function makeKirchenpinElement(bistum, isKloster) {
  const { bg, cross } = colorsFor(bistum);
  const wrapper = document.createElement("div");
  wrapper.className = "gemeinde-pin" + (isKloster ? " gemeinde-pin--kloster" : "");
  // translateY(-50%) zentriert den Anker am unteren Spitze des Pins
  wrapper.style.transform = "translateY(-50%)";
  wrapper.style.cursor = "pointer";

  if (isKloster) {
    wrapper.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="52" height="64" viewBox="0 0 52 64" style="display:block">
  <circle cx="26" cy="26" r="24" fill="#c9a961" stroke="#fff" stroke-width="2"/>
  <circle cx="26" cy="26" r="20" fill="${bg}"/>
  <g transform="translate(16.55,13.05) scale(0.148)" fill="${cross}">
    <polygon points="63.9,-38.34 80.94,-8.52 115.02,-8.52 89.46,21.3 89.46,59.64 127.8,59.64 157.62,34.08 157.62,68.16 187.44,85.2 157.62,102.24 157.62,136.32 127.8,110.76 89.46,110.76 89.46,149.1 115.02,178.92 80.94,178.92 63.9,208.74 46.86,178.92 12.78,178.92 38.34,149.1 38.34,110.76 0,110.76 -29.82,136.32 -29.82,102.24 -59.64,85.2 -29.82,68.16 -29.82,34.08 0,59.64 38.34,59.64 38.34,21.3 12.78,-8.52 46.86,-8.52"/>
  </g>
  <polygon points="14,48 26,64 38,48" fill="#c9a961"/>
</svg>`;
  } else {
    wrapper.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="44" viewBox="0 0 36 44" style="display:block">
  <circle cx="18" cy="18" r="17" fill="${bg}" stroke="#fff" stroke-width="1.5"/>
  <g transform="translate(11.28,9.04) scale(0.1052)" fill="${cross}">
    <polygon points="63.9,-38.34 80.94,-8.52 115.02,-8.52 89.46,21.3 89.46,59.64 127.8,59.64 157.62,34.08 157.62,68.16 187.44,85.2 157.62,102.24 157.62,136.32 127.8,110.76 89.46,110.76 89.46,149.1 115.02,178.92 80.94,178.92 63.9,208.74 46.86,178.92 12.78,178.92 38.34,149.1 38.34,110.76 0,110.76 -29.82,136.32 -29.82,102.24 -59.64,85.2 -29.82,68.16 -29.82,34.08 0,59.64 38.34,59.64 38.34,21.3 12.78,-8.52 46.86,-8.52"/>
  </g>
  <polygon points="10,33 18,44 26,33" fill="${bg}"/>
</svg>`;
  }
  return wrapper;
}

function makeUserMarkerElement() {
  const wrapper = document.createElement("div");
  wrapper.style.transform = "translate(-50%, -50%)";
  wrapper.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 22 22" style="display:block">
    <circle cx="11" cy="11" r="9" fill="#1c1c1c" stroke="#fff" stroke-width="3"/>
  </svg>`;
  return wrapper;
}

function renderMarkers(items) {
  /* remove old markers */
  markers.forEach((m) => { m.map = null; });
  markers = [];

  const AdvancedMarker = google.maps.marker?.AdvancedMarkerElement;
  if (!AdvancedMarker) {
    console.warn("AdvancedMarkerElement not available — libraries=marker missing?");
    return;
  }

  items
    .filter((i) => i.lat && i.lng)
    .forEach((i) => {
      const isKloster = i.typ === "Kloster";
      const marker = new AdvancedMarker({
        position: { lat: i.lat, lng: i.lng },
        map: gMap,
        title: i.name,
        zIndex: isKloster ? 1000 : 1,  /* Klöster immer oben */
        content: makeKirchenpinElement(i.bistum, isKloster),
        gmpClickable: true,
      });
      marker._id = i.id;

      const website =
        i.website ||
        (i.url && !i.url.startsWith("https://kopten.de/gemeinden/")
          ? i.url
          : "");
      const slug = detailSlug(i.url);
      const detailHref = slug ? `${T.gemeindenPath}/${slug}/` : "";

      /* Route-Planung: bevorzugt lat,lng (eindeutig), Fallback Adresse */
      const destParam = (i.lat && i.lng)
        ? `${i.lat},${i.lng}`
        : `${i.strasse}, ${i.plz} ${i.ort}, Deutschland`;
      const dest = encodeURIComponent(destParam);
      const routeHref = (mode) =>
        `https://www.google.com/maps/dir/?api=1&destination=${dest}&travelmode=${mode}`;

      const content = `
      <div class="gm-info">
        ${i.gemeindeort ? `<p class="gm-info__ort">${escapeHtml(i.gemeindeort)}</p>` : ""}
        <h4>${escapeHtml(i.name)}</h4>
        <p>${escapeHtml([i.strasse, `${i.plz} ${i.ort}`].filter(Boolean).join(", "))}</p>
        <div class="gm-info__route">
          <span class="gm-info__route-label">${T.iwRoute}:</span>
          <a class="gm-info__route-btn" href="${routeHref('driving')}" target="_blank" rel="noopener" title="${T.iwRouteCar}" aria-label="${T.iwRouteCar}">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 17h14l-1.5-7H6.5L5 17zM7 17v2M17 17v2M9 11V7h6v4"/><circle cx="7.5" cy="17.5" r="1"/><circle cx="16.5" cy="17.5" r="1"/></svg>
          </a>
          <a class="gm-info__route-btn" href="${routeHref('transit')}" target="_blank" rel="noopener" title="${T.iwRouteTransit}" aria-label="${T.iwRouteTransit}">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="3" width="12" height="14" rx="2"/><path d="M8 17v3M16 17v3M6 10h12"/><circle cx="9" cy="13.5" r="0.6" fill="currentColor"/><circle cx="15" cy="13.5" r="0.6" fill="currentColor"/></svg>
          </a>
          <a class="gm-info__route-btn" href="${routeHref('walking')}" target="_blank" rel="noopener" title="${T.iwRouteWalk}" aria-label="${T.iwRouteWalk}">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="13" cy="4" r="2"/><path d="M9 22l2.5-7-2-3 1-5 5 2 1 3M14 12l3 2"/></svg>
          </a>
        </div>
        ${detailHref ? `<p style="margin-top:0.5rem;"><a href="${escapeHtml(detailHref)}">${T.iwDetail}</a></p>` : ""}
        ${website ? `<p style="margin-top:0.3rem;"><a href="${escapeHtml(website)}" target="_blank" rel="noopener">${T.iwWebsite}</a></p>` : ""}
      </div>`;
      const iw = new google.maps.InfoWindow({ content });
      const openIw = () => {
        if (activeInfoWindow) activeInfoWindow.close();
        iw.open({ map: gMap, anchor: marker });
        activeInfoWindow = iw;
      };
      marker.addListener("gmp-click", openIw);
      marker._openIw = openIw;
      markers.push(marker);
    });
}

/* derive detail-page slug from the <url> field */
function detailSlug(url) {
  if (!url) return "";
  const m = url.match(/\/gemeinden\/([^/]+)\/?$/);
  return m ? m[1] : "";
}

/* --------------------- Helpers ---------------------- */
function distanceKm(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const toRad = (x) => (x * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function setUserMarker(pos, label) {
  if (userMarker) userMarker.map = null;
  const AdvancedMarker = google.maps.marker?.AdvancedMarkerElement;
  if (!AdvancedMarker) return;
  userMarker = new AdvancedMarker({
    position: pos,
    map: gMap,
    title: label || T.yourLocation,
    content: makeUserMarkerElement(),
    zIndex: 2000,
  });
}

/* --------------------- Search / Locate ---------------------- */
function handleSearch(query) {
  if (!query.trim() || !gGeocoder) return;
  gGeocoder.geocode(
    { address: `${query}, Deutschland`, region: "de" },
    (results, status) => {
      if (status === "OK" && results[0]) {
        const loc = results[0].geometry.location;
        const pos = { lat: loc.lat(), lng: loc.lng() };
        gMap.panTo(pos);
        gMap.setZoom(10);
        setUserMarker(pos, query);
        renderResults(gemeindenData, pos);
      } else {
        alert(T.addressNotFound);
      }
    },
  );
}

function handleLocate() {
  if (!navigator.geolocation) {
    alert(T.geolocationUnsupported);
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (p) => {
      const pos = { lat: p.coords.latitude, lng: p.coords.longitude };
      gMap.panTo(pos);
      gMap.setZoom(10);
      setUserMarker(pos, T.yourLocation);
      renderResults(gemeindenData, pos);
    },
    () => {
      alert(T.geolocationDenied);
    },
    { enableHighAccuracy: false, timeout: 8000 },
  );
}

function handleReset() {
  document.getElementById("finder-search").value = "";
  if (userMarker) {
    userMarker.map = null;
    userMarker = null;
  }
  gMap.panTo(MAP_CENTER_DE);
  gMap.setZoom(6);
  renderResults(gemeindenData);
}

/* --------------------- Bootstrap ---------------------- */
async function initGemeindenMap() {
  const mapEl = document.getElementById("finder-map");
  if (!mapEl) return;

  /* mapId ist Pflicht für AdvancedMarkerElement.
     "DEMO_MAP_ID" ist Googles öffentlicher Default und funktioniert sofort.
     Für eigenes Map-Styling: Cloud Console → Map Styles → Map ID erstellen
     und hier eintragen (dann sind die `styles` per Cloud konfigurierbar). */
  gMap = new google.maps.Map(mapEl, {
    center: MAP_CENTER_DE,
    zoom: 6,
    mapId: "DEMO_MAP_ID",
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: true,
  });
  gGeocoder = new google.maps.Geocoder();

  gemeindenData = await loadGemeinden();

  /* Build-time Cache laden und sofort verwenden — keine API-Calls */
  const coordsCache = await loadCoordsCache();
  const filled = applyCachedCoords(gemeindenData, coordsCache);
  if (filled > 0) {
    renderResults(gemeindenData);
    renderMarkers(gemeindenData);
  } else {
    renderResults(gemeindenData);
  }

  /* Wire up controls */
  const search = document.getElementById("finder-search");
  const btnLocate = document.getElementById("finder-locate");
  const btnReset = document.getElementById("finder-reset");

  if (search) {
    let typingTimer;
    search.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleSearch(search.value);
      }
    });
    search.addEventListener("input", () => {
      clearTimeout(typingTimer);
      typingTimer = setTimeout(() => {
        if (search.value.trim().length >= 3) handleSearch(search.value);
      }, 600);
    });
  }
  if (btnLocate) btnLocate.addEventListener("click", handleLocate);
  if (btnReset) btnReset.addEventListener("click", handleReset);

  initDirectPicker();

  /* Auto-search from ?q=… (e.g. from the homepage finder widget) */
  const params = new URLSearchParams(window.location.search);
  const q = params.get("q");
  if (q && q.trim()) {
    /* If q looks like "lat,lng" coordinates → treat as user location */
    const coords = q.match(/^(-?\d+\.?\d*),(-?\d+\.?\d*)$/);
    if (coords) {
      const pos = { lat: parseFloat(coords[1]), lng: parseFloat(coords[2]) };
      setTimeout(() => {
        gMap.panTo(pos);
        gMap.setZoom(10);
        setUserMarker(pos, T.yourLocation);
        renderResults(gemeindenData, pos);
      }, 250);
    } else {
      if (search) search.value = q;
      setTimeout(() => handleSearch(q), 250);
    }
  }

  /* Now geocode everything progressively */
  geocodeAll(gemeindenData);
}

/* --------------------- Direct parish picker (combobox) ---------------------- */
let directPickerWired = false;

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightMatch(text, query) {
  if (!query) return text;
  const re = new RegExp(`(${escapeRegex(query)})`, "ig");
  return text.replace(re, "<mark>$1</mark>");
}

/* Loose normaliser so „Köln" matches "koln" and vice versa */
function norm(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/ß/g, "ss");
}

function pickerLabel(g) {
  /* Prefer gemeindeort (place name in church terms), fall back to <ort>, then <name> */
  return g.gemeindeort || g.ort || g.name || "";
}

function pickerSub(g) {
  const bits = [];
  if (g.plz) bits.push(g.plz);
  if (g.ort && g.ort !== pickerLabel(g)) bits.push(g.ort);
  if (g.typ === "kloster") bits.unshift("Kloster");
  return bits.join(" · ");
}

function buildPickerEntries(list) {
  return list
    .map((g) => ({
      raw: g,
      slug: detailSlug(g.url),
      label: pickerLabel(g),
      sub: pickerSub(g),
    }))
    .filter((e) => e.slug && e.label)
    .sort((a, b) => a.label.localeCompare(b.label, LANG === "en" ? "en" : "de"));
}

function initDirectPicker() {
  if (directPickerWired) return;
  const input = document.getElementById("finder-direct-input");
  const listEl = document.getElementById("finder-direct-list");
  const clearBtn = document.getElementById("finder-direct-clear");
  const field = input ? input.closest(".finder__direct-field") : null;
  if (!input || !listEl) return;

  directPickerWired = true;

  const entries = buildPickerEntries(gemeindenData);
  let highlightedIdx = -1;
  let currentMatches = [];

  const detailHref = (slug) => `${T.gemeindenPath}/${slug}/`;

  function close() {
    listEl.hidden = true;
    input.setAttribute("aria-expanded", "false");
    highlightedIdx = -1;
  }

  function render(matches, query) {
    listEl.innerHTML = "";
    if (!matches.length) {
      const empty = document.createElement("li");
      empty.className = "finder__direct-empty";
      empty.textContent = LANG === "en" ? "No matching parish." : "Keine Gemeinde gefunden.";
      listEl.appendChild(empty);
      listEl.hidden = false;
      input.setAttribute("aria-expanded", "true");
      return;
    }
    matches.forEach((m, i) => {
      const li = document.createElement("li");
      li.className = "finder__direct-item";
      li.setAttribute("role", "option");
      li.dataset.idx = i;
      li.dataset.href = detailHref(m.slug);
      li.innerHTML = `
        <span class="finder__direct-item__name">${highlightMatch(m.label, query)}</span>
        ${m.sub ? `<span class="finder__direct-item__sub">${m.sub}</span>` : ""}
      `;
      li.addEventListener("mousedown", (e) => {
        /* mousedown beats blur → keeps the click usable */
        e.preventDefault();
        window.location.href = li.dataset.href;
      });
      li.addEventListener("mouseenter", () => setHighlight(i));
      listEl.appendChild(li);
    });
    listEl.hidden = false;
    input.setAttribute("aria-expanded", "true");
    setHighlight(matches.length ? 0 : -1);
  }

  function setHighlight(i) {
    highlightedIdx = i;
    Array.from(listEl.children).forEach((el, idx) => {
      el.classList.toggle("is-highlighted", idx === i);
      if (idx === i && el.scrollIntoView) {
        el.scrollIntoView({ block: "nearest" });
      }
    });
  }

  function update() {
    const raw = input.value.trim();
    if (clearBtn) clearBtn.hidden = raw.length === 0;
    const q = norm(raw);
    if (!q) {
      currentMatches = entries.slice(0, 30);
    } else {
      currentMatches = entries
        .filter((e) => norm(e.label).includes(q) || norm(e.sub).includes(q))
        .slice(0, 30);
    }
    render(currentMatches, raw);
  }

  input.addEventListener("focus", update);
  input.addEventListener("input", update);
  input.addEventListener("keydown", (e) => {
    if (listEl.hidden && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      update();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight(Math.min(highlightedIdx + 1, currentMatches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight(Math.max(highlightedIdx - 1, 0));
    } else if (e.key === "Enter") {
      if (highlightedIdx >= 0 && currentMatches[highlightedIdx]) {
        e.preventDefault();
        window.location.href = detailHref(currentMatches[highlightedIdx].slug);
      }
    } else if (e.key === "Escape") {
      close();
      input.blur();
    }
  });

  input.addEventListener("blur", () => {
    /* Delay so mousedown on an item can still fire */
    setTimeout(close, 120);
  });

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      input.value = "";
      clearBtn.hidden = true;
      input.focus();
      update();
    });
  }

  /* Close when clicking outside the field */
  document.addEventListener("click", (e) => {
    if (!field) return;
    const root = field.closest(".finder__direct");
    if (root && !root.contains(e.target)) close();
  });
}

/* Expose for the Maps API callback */
window.initGemeindenMap = initGemeindenMap;

/* Fallback bootstrap: load gemeinde list immediately so users always see something,
   even if the Google Maps API fails to load (referrer error, network, etc.). */
document.addEventListener("DOMContentLoaded", async () => {
  if (!document.getElementById("finder-list")) return;
  /* If Maps already loaded, the callback handles it */
  if (window.google && window.google.maps) return;

  if (!gemeindenData.length) {
    gemeindenData = await loadGemeinden();
    const cache = await loadCoordsCache();
    applyCachedCoords(gemeindenData, cache);
  }
  renderResults(gemeindenData);
  initDirectPicker();

  /* Show a hint that the map could not be loaded */
  const mapEl = document.getElementById("finder-map");
  if (mapEl && !mapEl.firstChild) {
    setTimeout(() => {
      if (!window.google || !window.google.maps) {
        mapEl.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;padding:2rem;text-align:center;color:var(--color-ink-soft);background:var(--color-bg-alt);">
          <div>
            <p style="margin-bottom:0.5rem;font-weight:500">${T.mapUnavailable}</p>
            <p style="font-size:0.875rem;margin:0">${T.mapHint}</p>
          </div>
        </div>`;
      }
    }, 3000);
  }
});

/* ============================================================
   Coptic Calendar — Feasts and Fasting Periods
   Dynamic calculation from data/koptische_feste.json
   Bilingual (de/en) via <html lang="…">.
   ============================================================ */

const LANG = document.documentElement.lang === 'en' ? 'eng' : 'deu';
const IS_EN_SUBDIR = window.location.pathname.includes('/en/');
const DATA_BASE = IS_EN_SUBDIR ? '../data/' : 'data/';
const DATA_URL = `${DATA_BASE}koptische_feste.json`;
const LORD_FEASTS_URL = `${DATA_BASE}herrenfeste.json`;
const YEAR_RANGE_FORWARD = 10;

const STRINGS = {
  deu: {
    months: ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
    monthsShort: ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'],
    weekdays: ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'],
    sectionTitle: year => `Fastenzeiten und Feste ${year}`,
    unnamedEvent: 'Unbenanntes Ereignis',
    fetchError: status => `Kalenderdaten konnten nicht geladen werden (HTTP ${status}).`,
    fetchErrorGeneric: 'Kalenderdaten konnten nicht geladen werden.',
    fmtLong: date => `${date.getUTCDate()}. ${STRINGS.deu.months[date.getUTCMonth()]} ${date.getUTCFullYear()}`
  },
  eng: {
    months: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    monthsShort: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    weekdays: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
    sectionTitle: year => `Fasting Periods and Feasts ${year}`,
    unnamedEvent: 'Unnamed event',
    fetchError: status => `Calendar data could not be loaded (HTTP ${status}).`,
    fetchErrorGeneric: 'Calendar data could not be loaded.',
    fmtLong: date => `${STRINGS.eng.months[date.getUTCMonth()]} ${date.getUTCDate()}, ${date.getUTCFullYear()}`
  }
};

const T = STRINGS[LANG];

const appState = {
  items: [],
  lordFeasts: null,
  selectedYear: new Date().getFullYear()
};

function isGregorianLeapYear(year) {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

function addDaysUTC(date, days) {
  return new Date(date.getTime() + days * 86400000);
}

function toISODateUTC(date) {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function parseISODateUTC(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

function getCopticNewYearGregorian(amYear) {
  const gregorianStartYear = amYear + 283;
  const day = isGregorianLeapYear(gregorianStartYear + 1) ? 12 : 11;
  return new Date(Date.UTC(gregorianStartYear, 8, day));
}

function copticToGregorian(amYear, month, day) {
  const copticNewYear = getCopticNewYearGregorian(amYear);
  const offsetDays = (month - 1) * 30 + (day - 1);
  return addDaysUTC(copticNewYear, offsetDays);
}

function getOrthodoxEasterGregorian(year) {
  const a = year % 4;
  const b = year % 7;
  const c = year % 19;
  const d = (19 * c + 15) % 30;
  const e = (2 * a + 4 * b - d + 34) % 7;

  const julianMonth = Math.floor((d + e + 114) / 31);
  const julianDay = ((d + e + 114) % 31) + 1;
  const gregorianShift = Math.floor(year / 100) - Math.floor(year / 400) - 2;

  return new Date(Date.UTC(year, julianMonth - 1, julianDay + gregorianShift));
}

function fmtDay(date) { return date.getUTCDate(); }
function fmtMonth(date) { return T.monthsShort[date.getUTCMonth()]; }
function fmtLong(date) { return T.fmtLong(date); }

function getEventType(item) {
  return item.is_fasting_day || item.season_type === 'fasting' ? 'fast' : 'feast';
}

function getEventName(item) {
  return item.titleDisplay?.[LANG]
    || item.titleDisplay?.deu
    || item.key
    || T.unnamedEvent;
}

function buildNonMovableEvent(item, amYear) {
  const times = item.times;
  if (!times || !times.monthStart || !times.dayStart) return null;

  const start = copticToGregorian(amYear, times.monthStart, times.dayStart);
  const end = (times.monthEnd && times.dayEnd)
    ? copticToGregorian(amYear, times.monthEnd, times.dayEnd)
    : start;

  return {
    name: getEventName(item),
    type: getEventType(item),
    date: toISODateUTC(start),
    end: toISODateUTC(end)
  };
}

function buildMovableEvent(item, easterDate) {
  const times = item.times;
  if (!times || typeof times.daysToEasternStart !== 'number') return null;

  const daysToStart = times.daysToEasternStart;
  const daysToEnd = typeof times.daysToEasternEnd === 'number'
    ? times.daysToEasternEnd
    : daysToStart;

  const start = addDaysUTC(easterDate, -daysToStart);
  const end = addDaysUTC(easterDate, -daysToEnd);

  return {
    name: getEventName(item),
    type: getEventType(item),
    date: toISODateUTC(start),
    end: toISODateUTC(end)
  };
}

function intersectsGregorianYear(event, year) {
  const start = parseISODateUTC(event.date);
  const end = parseISODateUTC(event.end || event.date);
  return start.getUTCFullYear() === year || end.getUTCFullYear() === year;
}

function normalizeRange(event) {
  const start = parseISODateUTC(event.date);
  const end = parseISODateUTC(event.end || event.date);
  if (start <= end) return event;
  return { ...event, date: toISODateUTC(end), end: toISODateUTC(start) };
}

function dedupeEvents(events) {
  const seen = new Set();
  return events.filter(event => {
    const key = `${event.name}|${event.type}|${event.date}|${event.end}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function buildEventsForYear(year, items) {
  const easter = getOrthodoxEasterGregorian(year);
  const copticYears = [year - 284, year - 283];
  const events = [];

  items.forEach(item => {
    if (item.disabled || !item.times || !item.time_type) return;

    if (item.time_type === 'non-movable') {
      copticYears.forEach(amYear => {
        const event = buildNonMovableEvent(item, amYear);
        if (event) events.push(normalizeRange(event));
      });
      return;
    }

    if (item.time_type === 'movable') {
      const event = buildMovableEvent(item, easter);
      if (event) events.push(normalizeRange(event));
    }
  });

  return dedupeEvents(events.filter(ev => intersectsGregorianYear(ev, year)))
    .sort((a, b) => {
      if (a.date !== b.date) return a.date.localeCompare(b.date);
      if (a.end !== b.end) return a.end.localeCompare(b.end);
      return a.name.localeCompare(b.name, LANG === 'eng' ? 'en' : 'de');
    });
}

function updateMeta(year) {
  const copticEl = document.getElementById('coptic-year');
  if (copticEl) {
    copticEl.textContent = `${year - 284} / ${year - 283} A.M.`;
  }

  const gregEl = document.getElementById('gregorian-year');
  if (gregEl) gregEl.textContent = String(year);

  const titleEl = document.getElementById('calendar-section-title');
  if (titleEl) titleEl.textContent = T.sectionTitle(year);

  const navLink = document.getElementById('calendar-section-nav-feasts');
  if (navLink) navLink.textContent = T.sectionTitle(year);
}

function renderCalendar(year) {
  const list = document.getElementById('calendar-list');
  if (!list) return;

  const events = buildEventsForYear(year, appState.items);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const isCurrentYear = today.getFullYear() === year;

  let currentMonth = -1;
  const fragment = document.createDocumentFragment();

  events.forEach(event => {
    const start = parseISODateUTC(event.date);
    const end = parseISODateUTC(event.end || event.date);
    const month = start.getUTCMonth();

    if (month !== currentMonth) {
      currentMonth = month;
      const divider = document.createElement('li');
      divider.className = 'calendar-month-divider';
      divider.textContent = `${T.months[month]} ${start.getUTCFullYear()}`;
      fragment.appendChild(divider);
    }

    const item = document.createElement('li');
    item.className = `calendar-item calendar-item--${event.type === 'fast' ? 'fast' : 'feast'}`;

    const isPast = isCurrentYear && end.getTime() < today.getTime();
    const isUpcoming = isCurrentYear && !isPast && start.getTime() <= (today.getTime() + 30 * 86400000);
    if (isPast) item.classList.add('calendar-item--past');
    if (isUpcoming) item.classList.add('calendar-item--upcoming');

    const dateBlock = document.createElement('div');
    dateBlock.className = 'calendar-item__date';
    dateBlock.innerHTML = `<span class="calendar-item__day">${fmtDay(start)}</span><span class="calendar-item__month">${fmtMonth(start)}</span>`;

    const body = document.createElement('div');
    body.className = 'calendar-item__body';

    const name = document.createElement('h3');
    name.className = 'calendar-item__name';
    name.textContent = event.name;
    body.appendChild(name);

    const meta = document.createElement('p');
    meta.className = 'calendar-item__meta';
    meta.textContent = (event.end && event.end !== event.date)
      ? `${fmtLong(start)} — ${fmtLong(end)}`
      : fmtLong(start);
    body.appendChild(meta);

    item.appendChild(dateBlock);
    item.appendChild(body);
    fragment.appendChild(item);
  });

  list.innerHTML = '';
  list.appendChild(fragment);
  updateMeta(year);
  renderLordFeasts(year);
}

function buildItemDateForYear(item, year) {
  const easter = getOrthodoxEasterGregorian(year);
  const candidates = [];

  if (item.time_type === 'movable') {
    const ev = buildMovableEvent(item, easter);
    if (ev) candidates.push(ev);
  } else if (item.time_type === 'non-movable') {
    [year - 284, year - 283].forEach(amYear => {
      const ev = buildNonMovableEvent(item, amYear);
      if (ev) candidates.push(normalizeRange(ev));
    });
  }

  return candidates.find(ev => intersectsGregorianYear(ev, year)) || null;
}

function formatLordFeastDate(event) {
  if (!event) return '—';
  const start = parseISODateUTC(event.date);
  const end = parseISODateUTC(event.end || event.date);
  const weekday = T.weekdays[start.getUTCDay()];
  if (event.end && event.end !== event.date) {
    return `${fmtLong(start)} — ${fmtLong(end)}`;
  }
  return `${weekday}, ${fmtLong(start)}`;
}

function renderLordFeasts(year) {
  const container = document.getElementById('lord-feasts');
  if (!container || !appState.lordFeasts) return;

  const itemsByKey = new Map();
  appState.items.forEach(item => {
    if (item.key && !itemsByKey.has(item.key)) itemsByKey.set(item.key, item);
  });

  const fragment = document.createDocumentFragment();

  appState.lordFeasts.groups.forEach(group => {
    const section = document.createElement('section');
    section.className = 'lord-feasts__group';

    const heading = document.createElement('h2');
    heading.className = 'lord-feasts__title';
    heading.textContent = group.title?.[LANG] || group.title?.deu || group.id;
    section.appendChild(heading);

    const ul = document.createElement('ul');
    ul.className = 'lord-feasts__list';

    group.keys.forEach(key => {
      const item = itemsByKey.get(key);
      if (!item) return;
      const event = buildItemDateForYear(item, year);
      const li = document.createElement('li');
      li.className = 'lord-feasts__item';

      const name = document.createElement('span');
      name.className = 'lord-feasts__name';
      name.textContent = getEventName(item);

      const date = document.createElement('span');
      date.className = 'lord-feasts__date';
      date.textContent = formatLordFeastDate(event);

      li.appendChild(name);
      li.appendChild(date);
      ul.appendChild(li);
    });

    section.appendChild(ul);
    fragment.appendChild(section);
  });

  container.innerHTML = '';
  container.appendChild(fragment);
}

function setupYearSelect() {
  const select = document.getElementById('calendar-year-select');
  if (!select) return;

  const currentYear = new Date().getFullYear();
  const endYear = currentYear + YEAR_RANGE_FORWARD;

  select.innerHTML = '';
  for (let year = currentYear; year <= endYear; year += 1) {
    const option = document.createElement('option');
    option.value = String(year);
    option.textContent = String(year);
    if (year === appState.selectedYear) option.selected = true;
    select.appendChild(option);
  }

  select.addEventListener('change', event => {
    const selectedYear = Number(event.target.value);
    if (!Number.isNaN(selectedYear)) {
      appState.selectedYear = selectedYear;
      renderCalendar(appState.selectedYear);
    }
  });
}

async function initCalendar() {
  const list = document.getElementById('calendar-list');
  if (!list) return;

  try {
    const response = await fetch(DATA_URL, { cache: 'no-store' });
    if (!response.ok) throw new Error(T.fetchError(response.status));

    appState.items = await response.json();

    try {
      const lordRes = await fetch(LORD_FEASTS_URL, { cache: 'no-store' });
      if (lordRes.ok) appState.lordFeasts = await lordRes.json();
    } catch (_) { /* optional resource */ }

    setupYearSelect();
    renderCalendar(appState.selectedYear);
  } catch (error) {
    list.innerHTML = '';
    const item = document.createElement('li');
    item.className = 'calendar-item';
    item.textContent = error instanceof Error ? error.message : T.fetchErrorGeneric;
    list.appendChild(item);
  }
}

document.addEventListener('DOMContentLoaded', initCalendar);

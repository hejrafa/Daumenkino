const cards = [...document.querySelectorAll('.review-card')];
const filters = [...document.querySelectorAll('[data-filter]')];
const more = document.querySelector('#load-more');
const status = document.querySelector('#filter-status');
const languageButtons = [...document.querySelectorAll('[data-language]')];
const translations = [...document.querySelectorAll('[data-en], [data-en-aria-label], [data-en-content]')].map(element => ({
  element,
  text: element.hasAttribute('data-en') ? element.textContent : null,
  label: element.getAttribute('aria-label'),
  content: element.getAttribute('content'),
}));
let active = 'all';
let limit = 5;
let language = 'de';

function updateStatus(matching) {
  const shown = Math.min(limit, matching.length);
  status.textContent = language === 'en'
    ? `${shown} of ${matching.length} film reviews shown.`
    : `${shown} von ${matching.length} Filmkritiken angezeigt.`;
}

function render() {
  const matching = cards.filter(card => active === 'all' || card.dataset.author === active);
  cards.forEach(card => { card.hidden = true; card.classList.remove('feature'); });
  matching.slice(0, limit).forEach((card, i) => { card.hidden = false; card.classList.toggle('feature', i === 0); });
  more.hidden = matching.length <= limit;
  updateStatus(matching);
}

function setLanguage(next, remember = false) {
  language = next === 'en' ? 'en' : 'de';
  document.documentElement.lang = language;
  translations.forEach(({ element, text, label, content }) => {
    if (text !== null) element.textContent = language === 'en' ? element.dataset.en : text;
    if (element.hasAttribute('data-en-aria-label')) element.setAttribute('aria-label', language === 'en' ? element.dataset.enAriaLabel : label);
    if (element.hasAttribute('data-en-content')) element.setAttribute('content', language === 'en' ? element.dataset.enContent : content);
    if (element.hasAttribute('data-language-text')) element.lang = language;
  });
  document.querySelectorAll('time[data-date]').forEach(element => {
    if (!element.dataset.date) return;
    const date = new Date(`${element.dataset.date}T12:00:00Z`);
    if (Number.isNaN(date.getTime())) return;
    element.dateTime = element.dataset.date;
    element.textContent = new Intl.DateTimeFormat(language === 'en' ? 'en-GB' : 'de-DE', {
      day: '2-digit', month: language === 'en' ? 'short' : '2-digit', year: 'numeric', timeZone: 'UTC',
    }).format(date);
  });
  languageButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.language === language)));
  updateStatus(cards.filter(card => active === 'all' || card.dataset.author === active));
  if (remember) {
    try { localStorage.setItem('daumenkino-language', language); } catch { /* Switching still works when storage is unavailable. */ }
  }
}

filters.forEach(button => button.addEventListener('click', () => {
  active = button.dataset.filter;
  limit = 5;
  filters.forEach(filter => filter.setAttribute('aria-pressed', String(filter === button)));
  render();
}));
more.addEventListener('click', () => {
  const matching = cards.filter(card => active === 'all' || card.dataset.author === active);
  const firstNew = matching[limit];
  limit += 4;
  render();
  firstNew?.querySelector('a')?.focus({ preventScroll: true });
});
languageButtons.forEach(button => button.addEventListener('click', () => setLanguage(button.dataset.language, true)));
let preferredLanguage = navigator.language?.toLowerCase().startsWith('de') ? 'de' : 'en';
try {
  const saved = localStorage.getItem('daumenkino-language');
  if (saved === 'de' || saved === 'en') preferredLanguage = saved;
} catch { /* Browser language is enough when storage is unavailable. */ }
setLanguage(preferredLanguage);
document.querySelector('.language-toggle').hidden = false;
render();
// A missing remote image leaves a deliberate, readable solid-color card.
document.querySelectorAll('img').forEach(img => img.addEventListener('error', () => {
  if (img.classList.contains('film-still')) img.style.display = 'none';
}));

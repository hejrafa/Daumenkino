const cards = [...document.querySelectorAll('.review-card')];
const filters = [...document.querySelectorAll('[data-filter]')];
const more = document.querySelector('#load-more');
const status = document.querySelector('#filter-status');
const language = document.documentElement.lang === 'en' ? 'en' : 'de';
const params = new URLSearchParams(location.search);
let active = ['hejrafa', 'annso'].includes(params.get('author')) ? params.get('author') : 'all';
let limit = Math.max(5, Math.min(cards.length, Number(params.get('count')) || 5));
filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === active)));

function render(announce = true) {
  const matching = cards.filter(card => active === 'all' || card.dataset.author === active);
  cards.forEach(card => { card.hidden = true; card.classList.remove('feature'); });
  matching.slice(0, limit).forEach((card, i) => {
    card.hidden = false;
    card.classList.toggle('feature', i === 0);
  });
  more.hidden = matching.length <= limit;
  if (announce) status.textContent = language === 'en'
    ? `${Math.min(limit, matching.length)} of ${matching.length} film reviews shown.`
    : `${Math.min(limit, matching.length)} von ${matching.length} Filmkritiken angezeigt.`;
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
  firstNew?.querySelector('h3')?.focus();
});
function revealLinkedReview() {
  const linked = cards.find(card => '#' + card.id === location.hash);
  if (!linked) return;
  active = 'all';
  limit = Math.max(limit, cards.indexOf(linked) + 1);
  filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === 'all')));
  render(false);
  linked.scrollIntoView();
}
document.querySelector('.filters').hidden = false;
render(false);
revealLinkedReview();
window.addEventListener('hashchange', revealLinkedReview);
// Language links remain ordinary crawlable URLs, and retain the current section.
document.querySelectorAll('[data-language]').forEach(link => link.addEventListener('click', () => {
  const destination = new URL(link.href);
  if (active !== 'all') destination.searchParams.set('author', active);
  if (limit > 5) destination.searchParams.set('count', String(limit));
  destination.hash = location.hash;
  link.href = destination.href;
}));
document.querySelectorAll('time[data-date]').forEach(element => {
  if (!element.dataset.date) return;
  const date = new Date(`${element.dataset.date}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return;
  element.dateTime = element.dataset.date;
  element.textContent = new Intl.DateTimeFormat(language === 'en' ? 'en-GB' : 'de-DE', {
    day: '2-digit', month: language === 'en' ? 'short' : '2-digit', year: 'numeric', timeZone: 'UTC',
  }).format(date);
});
document.querySelectorAll('img').forEach(img => img.addEventListener('error', () => {
  if (img.classList.contains('film-still')) img.style.display = 'none';
}));

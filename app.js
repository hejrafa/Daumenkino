const cards = [...document.querySelectorAll('.review-card')];
const filters = [...document.querySelectorAll('[data-filter]')];
const more = document.querySelector('#load-more');
const status = document.querySelector('#filter-status');
let active = 'all';
let limit = 5;
function render() {
  const matching = cards.filter(card => active === 'all' || card.dataset.author === active);
  cards.forEach(card => { card.hidden = true; card.classList.remove('feature'); });
  matching.slice(0, limit).forEach((card, i) => { card.hidden = false; card.classList.toggle('feature', i === 0); });
  more.hidden = matching.length <= limit;
  status.textContent = `${Math.min(limit, matching.length)} von ${matching.length} Filmkritiken angezeigt.`;
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
render();
// A missing remote image leaves a deliberate, readable solid-color card.
document.querySelectorAll('img').forEach(img => img.addEventListener('error', () => {
  if (img.classList.contains('film-still')) img.style.display = 'none';
}));

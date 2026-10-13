// Without JavaScript every year is listed in full; with it, the year links switch between lists.
const years = [...document.querySelectorAll('.top20-year')];
const yearLinks = [...document.querySelectorAll('.year-nav a')];

function showYear(id, focus = false) {
  const selected = years.find(year => year.id === id) || years[0];
  if (!selected) return;
  years.forEach(year => { year.hidden = year !== selected; });
  yearLinks.forEach(link => {
    if (link.hash === '#' + selected.id) link.setAttribute('aria-current', 'true');
    else link.removeAttribute('aria-current');
  });
  if (focus) selected.querySelector('h2')?.focus({ preventScroll: true });
}
yearLinks.forEach(link => link.addEventListener('click', event => {
  event.preventDefault();
  // Switching years keeps the page where it is; the URL still points at the chosen year.
  history.replaceState(null, '', link.hash);
  showYear(link.hash.slice(1), true);
}));
years.forEach(year => year.querySelector('h2')?.setAttribute('tabindex', '-1'));
showYear(location.hash.slice(1));
// Hiding the other years moves a linked year (e.g. from a review's rank badge), so scroll to it again.
document.getElementById(location.hash.slice(1))?.scrollIntoView({ behavior: 'instant' });
window.addEventListener('hashchange', () => showYear(location.hash.slice(1)));

// Language links keep the year that is showing.
document.querySelectorAll('[data-language]').forEach(link => link.addEventListener('click', () => {
  const destination = new URL(link.href);
  destination.hash = location.hash;
  link.href = destination.href;
}));
document.querySelectorAll('img').forEach(img => img.addEventListener('error', () => { img.style.display = 'none'; }));

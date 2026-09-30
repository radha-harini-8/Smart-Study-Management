document.addEventListener('DOMContentLoaded', () => {
  const feed = document.querySelector('[data-live-feed]');
  if (!feed) return;
  let after = 0;
  async function refresh() {
    try {
      const response = await fetch(`/api/live-activity?after=${after}`);
      if (!response.ok) return;
      const data = await response.json();
      after = data.latest_id || after;
      if (!data.items?.length) return;
      feed.querySelector('.live-list').innerHTML = data.items.reverse().map(item =>
        `<a href="/resource/${item.resource_id}"><b>${item.text}</b><span>${item.at}</span></a>`
      ).join('');
    } catch (_) { /* Retry automatically on the next cycle. */ }
  }
  refresh();
  window.setInterval(refresh, 8000);
});

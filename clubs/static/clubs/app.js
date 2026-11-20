document.querySelector('[data-menu]')?.addEventListener('click', () => {
  const nav = document.getElementById('sidebar');
  nav.classList.toggle('open');
  document.querySelector('[data-menu]').setAttribute('aria-expanded', String(nav.classList.contains('open')));
});
document.addEventListener('click', (event) => {
  if (!event.target.closest('.sidebar') && !event.target.closest('[data-menu]')) {
    document.getElementById('sidebar')?.classList.remove('open');
  }
});


(() => {
  const form = document.getElementById('squad-form');
  if (!form) return;
  const boxes = [...form.querySelectorAll('input[name="players"]')];
  let timer, controller, revision = 0;
  const note = (message) => {
    const target = document.querySelector('[data-preview-state]');
    if (target) target.textContent = message;
  };
  const changed = () => {
    document.querySelector('[data-selected-count]').textContent = boxes.filter(box => box.checked).length;
    revision += 1;
    const current = revision;
    clearTimeout(timer);
    controller?.abort();
    note('Seçim değişti; kontrol güncelleniyor. Henüz kaydedilmedi.');
    timer = setTimeout(async () => {
      controller = new AbortController();
      const data = new FormData(form);
      data.set('action', 'preview');
      try {
        const response = await fetch(form.action, {method:'POST', body:data, signal:controller.signal,
          headers:{'X-Requested-With':'XMLHttpRequest'}, credentials:'same-origin'});
        if (!response.ok || response.redirected) throw new Error('preview failed');
        const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
        const panel = doc.getElementById('squad-result');
        if (!panel) throw new Error('panel missing');
        if (current !== revision) return;
        document.getElementById('squad-result').replaceWith(panel);
        note('Seçimin kontrolü güncel. Saklamak için Taslağı kaydet düğmesine bas.');
      } catch (error) {
        if (error.name !== 'AbortError' && current === revision) note('Canlı kontrol yenilenemedi. Sonuç önceki seçime ait; Kaydetmeden kontrol et düğmesini kullan.');
      }
    }, 200);
  };
  form.querySelectorAll('[data-squad-select]').forEach(button => button.addEventListener('click', () => {
    const choice = button.dataset.squadSelect;
    boxes.forEach(box => { if (!box.disabled) box.checked = choice === 'all' || box.dataset.status === choice; });
    changed();
  }));
  form.addEventListener('change', changed);
  form.addEventListener('submit', () => {clearTimeout(timer); revision += 1; controller?.abort();});
})();

/**
 * Tags and Links Management Module
 * Handles adding/removing tags and links
 */

class TagsLinks {
  constructor() {
    this.init();
  }

  init() {
    this.bindTagOperations();
    this.bindLinkOperations();
    this.bindLazyFavicons();
  }

  bindTagOperations() {
    // Tag hinzufügen per Button mit Prompt
    document.addEventListener('click', async (e) => {
      if (!(e.target && e.target.classList.contains('add-tag-btn'))) return;
      const btn = e.target;
      const wrap = btn.closest('.tags');
      let tag = prompt('Bitte Tag eingeben');
      if (!tag) return;
      tag = tag.trim();
      if (!tag) {
        showToast('Tag darf nicht leer sein', 'error');
        return;
      }
      if (Array.from(wrap.querySelectorAll('.tag-chip')).some(c => c.getAttribute('data-tag') === tag)) {
        showToast('Tag bereits vorhanden', 'error');
        return;
      }
      btn.disabled = true;
      try {
        await htmx.ajax('POST', `/items/${wrap.dataset.id}/tags/add`, {values: {tag}, target: null, swap: 'none'});
        const chip = this.appendTagChip(wrap, tag);
        if (window.htmx && chip) htmx.process(chip);
        showToast('Tag hinzugefügt', 'success');
      } catch (err) {
        showToast('Fehler beim Hinzufügen des Tags', 'error');
      } finally {
        btn.disabled = false;
      }
    });

    // Tag-Suggest
    document.addEventListener('htmx:afterOnLoad', (e) => {
      const tgt = e.target;
      if (!(tgt.classList && tgt.classList.contains('tag-suggest'))) return;
      try {
        const data = JSON.parse(e.detail.xhr.responseText);
        tgt.innerHTML = '';
        data.forEach(tag => {
          const item = document.createElement('div');
          item.className = 'tag-sugg-item';
          item.tabIndex = 0;
          item.textContent = tag;
          item.addEventListener('mousedown', (ev) => {
            ev.preventDefault();
            this.addTagFromSuggest(tgt, tag);
          });
          item.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter') { ev.preventDefault(); this.addTagFromSuggest(tgt, tag); }
          });
          tgt.appendChild(item);
        });
      } catch(_) {}
    });

    let clickedSuggest = false;
    document.addEventListener('mousedown', (e) => {
      if (e.target && e.target.classList && e.target.classList.contains('tag-sugg-item')) {
        clickedSuggest = true;
      }
    });

    document.addEventListener('blur', (e) => {
      const el = e.target;
      if (!(el.classList && el.classList.contains('tag-input'))) return;
      setTimeout(() => {
        const wrap = el.closest('.tags');
        const sugg = wrap?.querySelector('.tag-suggest');
        if (!sugg) return;
        if (clickedSuggest) {
          clickedSuggest = false;
        } else {
          sugg.innerHTML = '';
        }
      }, 0);
    }, true);
  }

  bindLinkOperations() {
    // Link hinzufügen
    document.addEventListener('click', async (e) => {
      if (!(e.target && e.target.classList.contains('add-link'))) return;
      const btn = e.target;
      const wrap = btn.closest('.links');
      const id = wrap.dataset.id;
      let url = prompt('Bitte Link-URL eingeben (https://...)');
      if (!url) return;
      url = url.trim();
      if (!url) {
        showToast('URL darf nicht leer sein', 'error');
        return;
      }
      if (!/^https?:\/\//i.test(url)) {
        showToast('Bitte eine gültige URL mit https:// oder http:// angeben', 'error');
        return;
      }
      const exists = Array.from(wrap.querySelectorAll('.links-list .link-anchor'))
        .some(a => (a.getAttribute('href') || '') === url);
      if (exists) {
        showToast('Link bereits vorhanden', 'error');
        return;
      }
      btn.disabled = true;
      try {
        await htmx.ajax('POST', `/items/${id}/links/add`, {values: {url}, swap:'none'});
        this.appendLinkAnchor(wrap, url);
        showToast('Link hinzugefügt', 'success');
      } catch (err) {
        showToast('Fehler beim Hinzufügen des Links', 'error');
      } finally {
        btn.disabled = false;
      }
    });

    document.addEventListener('keydown', (e) => {
      const el = e.target;
      if (el.classList && el.classList.contains('link-input') && e.key === 'Enter') {
        e.preventDefault();
        const btn = el.closest('.links').querySelector('.add-link');
        if (btn) btn.click();
      }
    });
  }

  appendTagChip(wrap, tag) {
    if (Array.from(wrap.querySelectorAll('.tag-chip')).some(c => c.getAttribute('data-tag') === tag)) return null;
    const chip = document.createElement('span');
    chip.className = 'tag-chip';
    chip.setAttribute('data-tag', tag);

    const text = document.createElement('span');
    text.className = 'tag-text';
    text.textContent = tag;

    const hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.name = 'tag';
    hidden.value = tag;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'tag-x';
    btn.title = 'Entfernen';
    btn.setAttribute('aria-label', 'Tag entfernen');
    btn.textContent = '×';
    btn.setAttribute('hx-post', `/items/${wrap.dataset.id}/tags/remove`);
    btn.setAttribute('hx-params', '*');
    btn.setAttribute('hx-include', 'closest .tag-chip');
    btn.setAttribute('hx-swap', 'none');

    chip.appendChild(text);
    chip.appendChild(hidden);
    chip.appendChild(btn);

    const list = wrap.querySelector('.tag-list') || wrap;
    list.appendChild(chip);

    if (window.htmx) { htmx.process(chip); }
    return chip;
  }

  appendLinkAnchor(wrap, url) {
    const list = wrap.querySelector('.links-list');
    if (Array.from(list.querySelectorAll('.link-row')).some(r => (r.dataset.url||'') === url)) return;

    const row = document.createElement('span');
    row.className = 'link-row';
    row.dataset.url = url;

    const a = document.createElement('a');
    a.className = 'link-anchor';
    a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.title = url;

    const img = document.createElement('img');
    img.className = 'link-favicon'; img.alt = ''; img.loading = 'lazy';
    const domain = (()=>{
      try { return new URL(url).hostname; } catch(_){ return ''; }
    })();
    img.src = domain ? `https://www.google.com/s2/favicons?domain=${domain}` : '/static/icons/link.svg';

    const text = document.createElement('span');
    text.className = 'link-text';
    text.textContent = url;

    const hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.name = 'url';
    hidden.value = url;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'link-del';
    btn.title = 'Entfernen';
    btn.setAttribute('aria-label', 'Link entfernen');
    btn.setAttribute('hx-post', `/items/${wrap.dataset.id}/links/remove`);
    btn.setAttribute('hx-params', '*');
    btn.setAttribute('hx-include', 'closest .link-row');
    btn.setAttribute('hx-target', `#links-${wrap.dataset.id}`);
    btn.setAttribute('hx-swap', 'outerHTML');
    btn.style.padding = '0 .3em';
    btn.style.background = 'none';
    btn.style.border = 'none';
    btn.style.cursor = 'pointer';
    btn.textContent = '×';

    a.appendChild(img);
    a.appendChild(text);
    row.appendChild(a);
    row.appendChild(btn);
    row.appendChild(hidden);
    list.appendChild(row);
    
    // htmx für den neuen Button aktivieren
    if (window.htmx) {
      htmx.process(btn);
    }
  }

  addTagFromSuggest(tgt, tag) {
    const wrap = tgt.closest('.tags');
    const input = wrap.querySelector('.tag-input');
    const sugg = wrap.querySelector('.tag-suggest');
    if (sugg) sugg.innerHTML = '';
    input.value = tag;
    htmx.ajax('POST', `/items/${wrap.dataset.id}/tags/add`, {values: {tag}, target: null, swap: 'none'})
      .then(()=>{
        const chip = this.appendTagChip(wrap, tag);
        if (window.htmx && chip) htmx.process(chip);
        input.value='';
      });
  }

  bindLazyFavicons() {
    function setFavicon(img, url){
      try {
        const domain = new URL(url).hostname;
        img.src = domain ? `https://www.google.com/s2/favicons?domain=${domain}` : '/static/icons/link.svg';
      } catch(_){
        img.src = '/static/icons/link.svg';
      }
    }
    
    const imgs = Array.from(document.querySelectorAll('img.link-favicon[data-url]'));
    if (!('IntersectionObserver' in window)) {
      imgs.forEach(img => setFavicon(img, img.dataset.url));
    } else {
      const io = new IntersectionObserver((entries, obs)=>{
        entries.forEach(ent=>{
          if (ent.isIntersecting) {
            const img = ent.target;
            setFavicon(img, img.dataset.url);
            obs.unobserve(img);
          }
        });
      }, {rootMargin: '200px 0px'});
      imgs.forEach(img => io.observe(img));
    }
  }
}

window.TagsLinks = TagsLinks;
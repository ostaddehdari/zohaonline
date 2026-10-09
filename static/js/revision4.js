(function(){
  'use strict';
  const form=document.getElementById('fishForm');
  if(!form)return;
  const storageKey='zoha:unfinished:'+location.pathname;
  const fields=()=>Array.from(form.querySelectorAll('input:not([type=password]):not([type=file]),textarea,select'));
  function snapshot(){
    const data={savedAt:new Date().toISOString(),values:{}};
    fields().forEach(el=>{if(!el.name||['csrfmiddlewaretoken','save_mode'].includes(el.name))return;data.values[el.name]=el.type==='checkbox'||el.type==='radio'?{checked:el.checked,value:el.value}:$(el).val()});
    const editor=document.getElementById('id_body');
    if(editor?.zohaHtmlEditor)data.values.body=editor.zohaHtmlEditor.getHTML();
    localStorage.setItem(storageKey,JSON.stringify(data));
  }
  function restore(data){
    Object.entries(data.values||{}).forEach(([name,value])=>{form.querySelectorAll(`[name="${CSS.escape(name)}"]`).forEach(el=>{if(value&&typeof value==='object'&&'checked'in value){if(el.value===value.value)el.checked=value.checked}else{$(el).val(value).trigger('change')}})});
    const editor=document.getElementById('id_body');if(editor&&data.values?.body){editor.value=data.values.body;if(editor.zohaHtmlEditor){editor.zohaHtmlEditor.root.innerHTML=data.values.body;editor.zohaHtmlEditor.sync()}}
  }
  const saved=JSON.parse(localStorage.getItem(storageKey)||'null');
  if(saved?.values){const bar=document.createElement('div');bar.className='draft-restore-bar';bar.innerHTML='<i class="fa-solid fa-clock-rotate-left"></i><span>یک پیش‌نویس ذخیره‌نشده در این مرورگر وجود دارد.</span><button type="button">بازیابی آخرین پیش‌نویس ناتمام</button><button type="button" class="discard">حذف</button>';form.prepend(bar);bar.querySelector('button:not(.discard)').onclick=()=>{restore(saved);bar.remove()};bar.querySelector('.discard').onclick=()=>{localStorage.removeItem(storageKey);bar.remove()}}
  setInterval(snapshot,30000);
  form.addEventListener('submit',()=>localStorage.removeItem(storageKey));
  window.addEventListener('pagehide',snapshot);

  const body=document.getElementById('id_body');
  const reading=document.createElement('div');reading.className='reading-estimate';body?.closest('.form-field-block')?.append(reading);
  function count(){const html=body?.zohaHtmlEditor?.getHTML?.()||body?.value||'';const tmp=document.createElement('div');tmp.innerHTML=html;const words=(tmp.innerText.trim().match(/\S+/gu)||[]).length;reading.innerHTML=`<i class="fa-regular fa-clock"></i> ${words.toLocaleString('fa-IR')} واژه · زمان تقریبی ارائه ${Math.max(1,Math.ceil(words/120)).toLocaleString('fa-IR')} دقیقه`}
  setInterval(count,1500);count();

  function initHelp(root=document){root.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el=>{if(!bootstrap.Tooltip.getInstance(el))new bootstrap.Tooltip(el,{trigger:'hover focus click',container:'body'})});}
  function polishLabels(root=document){root.querySelectorAll('.topic-analysis-card').forEach(card=>card.querySelectorAll('label,.analysis-picker-help,option,button,input').forEach(el=>{el.childNodes.forEach(n=>{if(n.nodeType===3)n.textContent=n.textContent.replace(/محمول/g,'ریز موضوع')});['placeholder','title','aria-label'].forEach(a=>{if(el.hasAttribute(a))el.setAttribute(a,el.getAttribute(a).replace(/محمول/g,'ریز موضوع'))})}));initHelp(root)}
  new MutationObserver(m=>m.forEach(x=>x.addedNodes.forEach(n=>{if(n.nodeType===1)polishLabels(n)}))).observe(form,{childList:true,subtree:true});polishLabels();
  $(form).on('select2:select',function(e){const el=e.target;if(el.classList.contains('topic-select')||el.classList.contains('select2-tags'))setTimeout(()=>{$(el).select2('close');const search=document.querySelector('.select2-container--open .select2-search__field');if(search)search.value=''},0)});
  document.addEventListener('hidden.bs.modal',()=>{document.querySelectorAll('.modal-backdrop').forEach(x=>x.remove());document.body.classList.remove('modal-open');document.body.style.removeProperty('padding-right');document.body.style.removeProperty('overflow')});
})();

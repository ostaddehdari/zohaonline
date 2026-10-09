(()=>{'use strict';
  const cleanup=()=>{if(document.querySelector('.modal.show'))return;document.querySelectorAll('.modal-backdrop').forEach(x=>x.remove());document.body.classList.remove('modal-open');document.body.style.removeProperty('overflow');document.body.style.removeProperty('padding-right');};
  const moveModals=()=>document.querySelectorAll('.modal').forEach(modal=>{if(modal.parentElement!==document.body)document.body.appendChild(modal);});
  document.addEventListener('DOMContentLoaded',()=>{moveModals();cleanup();document.querySelectorAll('.audience-regions').forEach(x=>x.closest('.col-12')?.remove());const title=document.querySelector('[name=title]');if(title){title.required=true;title.addEventListener('input',()=>{title.setCustomValidity(title.value.trim()?'':'عنوان فیش الزامی است.');});}new MutationObserver(()=>{moveModals();document.querySelectorAll('.audience-regions').forEach(x=>x.closest('.col-12')?.remove());}).observe(document.body,{childList:true,subtree:true});});
  document.addEventListener('show.bs.modal',e=>{const modal=e.target;if(modal.parentElement!==document.body)document.body.appendChild(modal);modal.style.zIndex='1080';setTimeout(()=>document.querySelectorAll('.modal-backdrop').forEach(x=>x.style.zIndex='1070'),0);});
  document.addEventListener('shown.bs.modal',e=>{e.target.removeAttribute('aria-hidden');e.target.querySelector('input:not([type=hidden]),select,textarea,button')?.focus();});
  document.addEventListener('hidden.bs.modal',cleanup);window.addEventListener('pageshow',cleanup);window.setInterval(cleanup,2500);
})();

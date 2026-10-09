(function(){
  'use strict';

  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function button(icon, title, command, value=''){
    return `<button type="button" class="zhe-btn" title="${esc(title)}" data-command="${esc(command)}" data-value="${esc(value)}"><i class="fa-solid ${icon}"></i></button>`;
  }

  function select(title, command, options){
    return `<label class="zhe-select-wrap" title="${esc(title)}"><select class="zhe-select" data-command="${esc(command)}">${options.map(x=>`<option value="${esc(x[0])}">${esc(x[1])}</option>`).join('')}</select></label>`;
  }

  function normalizeUrl(value){
    const url=(value||'').trim();
    if(!url)return '';
    if(/^(https?:|mailto:|data:image\/)/i.test(url))return url;
    return `https://${url}`;
  }

  function createEditor(textarea, options={}){
    if(!textarea || textarea.dataset.zohaEditorReady==='1')return null;
    textarea.dataset.zohaEditorReady='1';

    const shell=document.createElement('section');
    shell.className='zoha-html-editor';
    shell.dataset.release='ZOHA-EDITOR-260';
    shell.innerHTML=`
      <div class="zhe-release-badge"><i class="fa-solid fa-wand-magic-sparkles"></i> ویرایشگر حرفه‌ای فعال · ۲.۵</div><div class="zhe-toolbar" role="toolbar" aria-label="ابزارهای ویرایش متن">
        <div class="zhe-group">${button('fa-rotate-left','بازگشت','undo')}${button('fa-rotate-right','تکرار','redo')}</div>
        <div class="zhe-group">${select('ساختار متن','formatBlock', [['p','پاراگراف'],['h1','عنوان ۱'],['h2','عنوان ۲'],['h3','عنوان ۳'],['h4','عنوان ۴'],['blockquote','نقل‌قول'],['pre','کد/متن قالب‌بندی‌شده']])}</div>
        <div class="zhe-group">${select('فونت','fontName', [['Vazirmatn','وزیرمتن'],['Tahoma','Tahoma'],['Arial','Arial'],['serif','سریف'],['monospace','تک‌فاصله']])}${select('اندازه','fontSize', [['3','عادی'],['1','ریز'],['2','کوچک'],['4','بزرگ'],['5','خیلی بزرگ'],['6','درشت']])}</div>
        <div class="zhe-group">${button('fa-bold','ضخیم','bold')}${button('fa-italic','مورب','italic')}${button('fa-underline','زیرخط','underline')}${button('fa-strikethrough','خط‌خورده','strikeThrough')}${button('fa-subscript','زیرنویس','subscript')}${button('fa-superscript','بالانویس','superscript')}</div>
        <div class="zhe-group zhe-colors"><label title="رنگ متن"><i class="fa-solid fa-font"></i><input type="color" data-color-command="foreColor" value="#17324d"></label><label title="رنگ پس‌زمینه متن"><i class="fa-solid fa-highlighter"></i><input type="color" data-color-command="hiliteColor" value="#fff2a8"></label></div>
        <div class="zhe-group">${button('fa-align-right','راست‌چین','justifyRight')}${button('fa-align-center','وسط‌چین','justifyCenter')}${button('fa-align-left','چپ‌چین','justifyLeft')}${button('fa-align-justify','تراز کامل','justifyFull')}${button('fa-right-long','راست‌به‌چپ','directionRTL')}${button('fa-left-long','چپ‌به‌راست','directionLTR')}</div>
        <div class="zhe-group">${button('fa-list-ol','فهرست شماره‌دار','insertOrderedList')}${button('fa-list-ul','فهرست نشانه‌دار','insertUnorderedList')}${button('fa-indent','افزایش تورفتگی','indent')}${button('fa-outdent','کاهش تورفتگی','outdent')}</div>
        <div class="zhe-group">${button('fa-link','افزودن پیوند','createLink')}${button('fa-link-slash','حذف پیوند','unlink')}${button('fa-image','افزودن تصویر','insertImage')}${button('fa-table-cells','افزودن جدول','insertTable')}${button('fa-minus','خط جداکننده','insertHorizontalRule')}</div>
        <div class="zhe-group">${button('fa-eraser','پاک‌کردن قالب‌بندی','removeFormat')}${button('fa-code','ویرایش HTML','sourceMode')}${button('fa-expand','تمام‌صفحه','fullscreen')}${button('fa-print','چاپ متن','print')}</div>
      </div>
      <div class="zhe-editor" contenteditable="true" dir="rtl" spellcheck="true" data-placeholder="متن اصلی تحقیق را اینجا بنویسید…"></div>
      <textarea class="zhe-source" spellcheck="false" aria-label="کد HTML"></textarea>
      <footer class="zhe-status"><span class="zhe-mode"><i class="fa-solid fa-pen-nib"></i> حالت دیداری</span><span class="zhe-count">۰ واژه · ۰ نویسه</span><span class="zhe-save-state"><i class="fa-solid fa-circle-check"></i> آماده ذخیره</span></footer>
    `;
    textarea.insertAdjacentElement('afterend', shell);
    textarea.classList.add('d-none');

    const editor=shell.querySelector('.zhe-editor');
    const source=shell.querySelector('.zhe-source');
    const modeLabel=shell.querySelector('.zhe-mode');
    const countLabel=shell.querySelector('.zhe-count');
    const saveLabel=shell.querySelector('.zhe-save-state');
    let sourceMode=false;
    const listeners=[];

    editor.innerHTML=textarea.value || '<p><br></p>';
    source.value=editor.innerHTML;

    function selectionInside(){
      const sel=window.getSelection();
      return sel && sel.rangeCount && editor.contains(sel.anchorNode);
    }
    function focusEditor(){
      if(sourceMode)return;
      editor.focus({preventScroll:true});
    }
    function exec(command,value=null){
      focusEditor();
      document.execCommand('styleWithCSS', false, true);
      document.execCommand(command, false, value);
      sync();
    }
    function html(){return sourceMode ? source.value : editor.innerHTML;}
    function text(){
      const temp=document.createElement('div');
      temp.innerHTML=html();
      return (temp.innerText||temp.textContent||'').trim();
    }
    function updateCount(){
      const plain=text();
      const words=plain ? plain.split(/\s+/u).filter(Boolean).length : 0;
      countLabel.textContent=`${words.toLocaleString('fa-IR')} واژه · ${plain.length.toLocaleString('fa-IR')} نویسه`;
    }
    function sync(){
      textarea.value=html();
      saveLabel.innerHTML='<i class="fa-solid fa-circle-dot"></i> دارای تغییر';
      updateCount();
      listeners.forEach(fn=>fn());
    }
    function toggleSource(){
      sourceMode=!sourceMode;
      if(sourceMode){
        source.value=editor.innerHTML;
        editor.style.display='none';source.style.display='block';
        modeLabel.innerHTML='<i class="fa-solid fa-code"></i> حالت HTML';
        source.focus();
      }else{
        editor.innerHTML=source.value || '<p><br></p>';
        source.style.display='none';editor.style.display='block';
        modeLabel.innerHTML='<i class="fa-solid fa-pen-nib"></i> حالت دیداری';
        editor.focus();
      }
      sync();
    }
    function createLink(){
      const url=normalizeUrl(prompt('نشانی پیوند را وارد کنید:','https://'));
      if(url)exec('createLink',url);
    }
    function insertImage(){
      const url=normalizeUrl(prompt('نشانی تصویر را وارد کنید:','https://'));
      if(!url)return;
      const alt=prompt('متن جایگزین تصویر:','')||'';
      exec('insertHTML',`<figure class="zoha-editor-image"><img src="${esc(url)}" alt="${esc(alt)}" style="max-width:100%;height:auto"><figcaption>${esc(alt)}</figcaption></figure><p><br></p>`);
    }
    function insertTable(){
      const rows=Math.min(12,Math.max(1,parseInt(prompt('تعداد ردیف:','3'),10)||3));
      const cols=Math.min(8,Math.max(1,parseInt(prompt('تعداد ستون:','3'),10)||3));
      let table='<table class="zoha-content-table" style="width:100%;border-collapse:collapse"><tbody>';
      for(let r=0;r<rows;r++){
        table+='<tr>';
        for(let c=0;c<cols;c++)table+=`<${r===0?'th':'td'} style="border:1px solid #cbd5e1;padding:8px">${r===0?`عنوان ${c+1}`:'متن'}</${r===0?'th':'td'}>`;
        table+='</tr>';
      }
      table+='</tbody></table><p><br></p>';
      exec('insertHTML',table);
    }
    function printEditor(){
      const win=window.open('','_blank','width=900,height=700');
      if(!win)return;
      win.document.write(`<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>چاپ متن تحقیق</title><style>body{font-family:Tahoma,sans-serif;line-height:2;padding:40px;direction:rtl}img{max-width:100%}table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbb;padding:8px}</style></head><body>${html()}</body></html>`);
      win.document.close();win.focus();win.print();
    }

    shell.querySelector('.zhe-toolbar')?.addEventListener('mousedown',event=>{
      const control=event.target.closest('button[data-command]');
      if(control)event.preventDefault();
    });
    shell.querySelectorAll('[data-command]').forEach(control=>{
      const event=control.tagName==='SELECT'?'change':'click';
      control.addEventListener(event,e=>{
        e.preventDefault();
        const command=control.dataset.command;
        const value=control.value || control.dataset.value || null;
        if(command==='sourceMode')return toggleSource();
        if(command==='fullscreen'){shell.classList.toggle('is-fullscreen');document.body.classList.toggle('editor-fullscreen-open',shell.classList.contains('is-fullscreen'));return;}
        if(command==='createLink')return createLink();
        if(command==='insertImage')return insertImage();
        if(command==='insertTable')return insertTable();
        if(command==='directionRTL'){focusEditor();document.execCommand('justifyRight');document.execCommand('formatBlock',false,'p');const node=window.getSelection()?.anchorNode?.parentElement;node?.setAttribute('dir','rtl');return sync();}
        if(command==='directionLTR'){focusEditor();document.execCommand('justifyLeft');const node=window.getSelection()?.anchorNode?.parentElement;node?.setAttribute('dir','ltr');return sync();}
        if(command==='print')return printEditor();
        exec(command,value);
        if(control.tagName==='SELECT')control.selectedIndex=0;
      });
    });
    shell.querySelectorAll('[data-color-command]').forEach(input=>input.addEventListener('input',()=>exec(input.dataset.colorCommand,input.value)));
    editor.addEventListener('input',sync);
    source.addEventListener('input',sync);
    editor.addEventListener('paste',()=>setTimeout(sync,0));
    editor.addEventListener('keydown',e=>{
      if(e.key==='Tab'){e.preventDefault();exec(e.shiftKey?'outdent':'indent');}
      if(e.key==='s'&&(e.ctrlKey||e.metaKey)){e.preventDefault();textarea.form?.requestSubmit();}
    });
    document.addEventListener('keydown',e=>{
      if(e.key==='Escape'&&shell.classList.contains('is-fullscreen')){shell.classList.remove('is-fullscreen');document.body.classList.remove('editor-fullscreen-open');}
    });
    textarea.form?.addEventListener('submit',()=>{textarea.value=html();saveLabel.innerHTML='<i class="fa-solid fa-spinner fa-spin"></i> در حال ذخیره';});

    updateCount();
    const api={
      root:editor,
      getText:text,
      getHTML:html,
      sync,
      on(event,callback){if(event==='text-change'&&typeof callback==='function')listeners.push(callback);},
      focus:focusEditor,
    };
    textarea.zohaHtmlEditor=api;
    return api;
  }

  window.ZohaHtmlEditor={create:createEditor};
})();

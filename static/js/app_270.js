(function ($) {
  'use strict';

  // Select2 یک بهبود رابط است؛ در صورت قطع CDN، فرم‌ها با select بومی همچنان کار می‌کنند.
  const select2Available = typeof $.fn.select2 === 'function';
  window.ZOHA_SELECT2_AVAILABLE = select2Available;
  if (!select2Available) {
    $.fn.select2 = function (command) {
      if (typeof command === 'string') return this;
      return this;
    };
  }

  function cookie(name) {
    return document.cookie.split('; ').find(x => x.startsWith(name + '='))?.split('=')[1] || '';
  }
  function csrf() { return decodeURIComponent(cookie(window.ZOHA?.csrfCookie || 'csrftoken')); }
  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  }
  function debounce(fn, wait) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); }; }
  function formEncode(data) {
    const params = new URLSearchParams();
    Object.entries(data).forEach(([k,v]) => params.append(k, v ?? ''));
    return params;
  }
  async function api(url, options={}) {
    const headers = {...(options.headers || {})};
    if ((options.method || 'GET').toUpperCase() !== 'GET') headers['X-CSRFToken'] = csrf();
    const response = await fetch(url, {...options, headers});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) { const error = new Error(data.error || 'خطا در ارتباط با سامانه'); error.data=data; error.status=response.status; throw error; }
    return data;
  }
  function toast(message, tone='success') {
    const id='toast-'+Date.now();
    const icon=tone==='success'?'fa-circle-check':tone==='danger'?'fa-triangle-exclamation':'fa-circle-info';
    $('#toastContainer').append(`<div id="${id}" class="toast align-items-center border-0 shadow" role="alert"><div class="d-flex"><div class="toast-body"><i class="fa-solid ${icon} ms-2 text-${tone}"></i>${escapeHtml(message)}</div><button class="btn-close m-auto ms-2" data-bs-dismiss="toast"></button></div></div>`);
    const el=document.getElementById(id); new bootstrap.Toast(el,{delay:3500}).show(); el.addEventListener('hidden.bs.toast',()=>el.remove());
  }
  window.ZohaUI={toast,api,escapeHtml};

  document.querySelectorAll('[data-sidebar-open]').forEach(btn=>btn.addEventListener('click',()=>{
    document.getElementById('appSidebar')?.classList.add('open'); document.querySelector('.sidebar-backdrop')?.classList.add('show');
  }));
  document.querySelectorAll('[data-sidebar-close]').forEach(btn=>btn.addEventListener('click',()=>{
    document.getElementById('appSidebar')?.classList.remove('open'); document.querySelector('.sidebar-backdrop')?.classList.remove('show');
  }));
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el=>new bootstrap.Tooltip(el));
  $('.select2').each(function(){ if(!$(this).hasClass('select2-hidden-accessible')) $(this).select2({theme:'bootstrap-5',dir:'rtl',width:'100%',placeholder:$(this).data('placeholder')||'انتخاب کنید',allowClear:!this.required}); });

  /* Legacy supplementary index panel */
  window.refreshIndexPanel=function(url){
    $('#indexPanelBody').html('<div class="loading-state"><div class="spinner-border"></div><span>در حال بارگذاری…</span></div>').load(url,function(){
      $('.select2-panel').select2({theme:'bootstrap-5',dropdownParent:$('#indexOffcanvas'),dir:'rtl',width:'100%'});
    });
  };
  $(document).on('click','.open-index-panel',function(){ const url=$(this).data('url'); refreshIndexPanel(url); bootstrap.Offcanvas.getOrCreateInstance(document.getElementById('indexOffcanvas')).show(); });
  $(document).on('submit','.ajax-index-form',function(e){ e.preventDefault(); const form=$(this), panel=form.closest('[data-panel-url]'); $.ajax({url:form.attr('action'),method:'POST',data:form.serialize(),success:()=>refreshIndexPanel(panel.data('panel-url')),error:x=>toast(x.responseJSON?.error||'خطا در ثبت نمایه','danger')}); });
  $(document).on('click','.ajax-remove,.ajax-delete-value',function(){ if(!confirm('این مورد حذف یا غیرفعال شود؟'))return; const btn=$(this),panel=btn.closest('[data-panel-url]'); $.ajax({url:btn.data('url'),method:'POST',headers:{'X-CSRFToken':csrf()},success:()=>refreshIndexPanel(panel.data('panel-url')),error:x=>toast(x.responseJSON?.error||'حذف ممکن نیست','danger')}); });

  window.ZohaCharts={
    dashboard(data){
      if(typeof Chart==='undefined') return;
      Chart.defaults.font.family='Vazirmatn'; Chart.defaults.color='#64808f'; Chart.defaults.borderColor='rgba(171,205,213,.42)';
      const palette=['#12bfc2','#7457f5','#ffb547','#20b989','#d94fd5','#2985d8','#ef6f6c','#123b58'];
      const common={responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{usePointStyle:true,boxWidth:8,padding:16}}}};
      const monthly=document.getElementById('monthlyChart'); if(monthly)new Chart(monthly,{type:'line',data:{labels:data.monthly.labels,datasets:[{label:'تعداد فیش',data:data.monthly.values,borderColor:'#12aeb4',backgroundColor:'rgba(18,191,194,.12)',fill:true,tension:.42,pointRadius:4,pointBackgroundColor:'#fff',pointBorderWidth:3}]},options:{...common,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{precision:0}},x:{grid:{display:false}}}}});
      const status=document.getElementById('statusChart'); if(status)new Chart(status,{type:'doughnut',data:{labels:data.status.labels,datasets:[{data:data.status.values,backgroundColor:palette,borderWidth:4,borderColor:'#fff'}]},options:{...common,cutout:'68%',plugins:{legend:{position:'bottom',labels:{usePointStyle:true,boxWidth:7,font:{size:10}}}}}});
      const topic=document.getElementById('topicChart'); if(topic)new Chart(topic,{type:'bar',data:{labels:data.topic.labels,datasets:[{label:'تعداد',data:data.topic.values,backgroundColor:'rgba(116,87,245,.78)',borderRadius:8}]},options:{...common,indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,ticks:{precision:0}},y:{grid:{display:false}}}}});
      const content=document.getElementById('contentChart'); if(content)new Chart(content,{type:'polarArea',data:{labels:data.content.labels,datasets:[{data:data.content.values,backgroundColor:palette.map(x=>x+'cc'),borderColor:'#fff',borderWidth:2}]},options:{...common,plugins:{legend:{position:'bottom',labels:{usePointStyle:true,boxWidth:7,font:{size:10}}}},scales:{r:{ticks:{display:false}}}}});
    }
  };

  window.ZohaFishForm={
    init(config){
      const form=document.getElementById(config.formId); if(!form)return;
      const state={config,analyses:Array.isArray(config.analyses)?config.analyses:[],audiences:Array.isArray(config.audiences)?config.audiences:[],dirty:false,currentOptionTarget:null,currentOptionType:null,currentOptionParent:null,currentSourceTarget:null,quill:null};
      const $form=$(form);

      // ویرایشگر HTML داخلی و حرفه‌ای؛ در صورت نبود آن، Quill یا textarea بومی استفاده می‌شود.
      const textarea=form.querySelector('textarea.rich-editor');
      if(textarea && textarea.zohaHtmlEditor){
        state.quill=textarea.zohaHtmlEditor;
        state.quill.on('text-change',()=>{state.dirty=true;updateProgress();});
      }else if(textarea && window.ZohaHtmlEditor){
        state.quill=window.ZohaHtmlEditor.create(textarea,{placeholder:'متن اصلی تحقیق را با ساختار مناسب وارد کنید…'});
        state.quill?.on('text-change',()=>{state.dirty=true;updateProgress();});
      }else if(textarea && typeof Quill!=='undefined'){
        const editor=document.createElement('div'); editor.id='fish-body-editor'; textarea.insertAdjacentElement('afterend',editor); textarea.style.display='none';
        state.quill=new Quill(editor,{theme:'snow',placeholder:'متن اصلی فیش را با ساختار مناسب وارد کنید…',modules:{toolbar:[[{header:[1,2,3,4,5,6,false]}],[{font:[]}],[{size:['small',false,'large','huge']}],['bold','italic','underline','strike'],[{color:[]},{background:[]}],[{script:'sub'},{script:'super'}],[{list:'ordered'},{list:'bullet'}],[{indent:'-1'},{indent:'+1'}],[{align:[]}],[{direction:'rtl'}],['blockquote','code-block'],['link','image','video'],['clean']]}});
        state.quill.root.innerHTML=textarea.value||''; state.quill.on('text-change',()=>{state.dirty=true;updateProgress();});
      }

      // Select2
      $form.find('.select2').each(function(){ if($(this).hasClass('select2-hidden-accessible'))$(this).select2('destroy'); $(this).select2({theme:'bootstrap-5',dir:'rtl',width:'100%',placeholder:$(this).data('placeholder')||'جست‌وجو و انتخاب کنید',allowClear:!this.required}); });

      // title count and similar titles
      const title=form.querySelector('#id_title'); const counter=form.querySelector('[data-counter-for="id_title"]');
      function countTitle(){if(counter)counter.textContent=`${title?.value.length||0}/۱۶۰`;}
      const titleLookup=debounce(async()=>{
        const box=document.getElementById('similarTitles'); if(!box||!title||title.value.trim().length<2){box?.classList.add('d-none');return;}
        try{const data=await api(`${window.ZOHA.urls.titleSimilar}?q=${encodeURIComponent(title.value.trim())}`);if(!data.results.length){box.classList.add('d-none');return;}
          const hasExact=data.results.some(x=>x.exact); box.innerHTML=`<h6><i class="fa-solid fa-triangle-exclamation ms-2"></i>${hasExact?'عنوان کاملاً مشابه وجود دارد':'عنوان‌های نزدیک پیدا شد'}</h6>${data.results.map(x=>`<div class="similar-title-item"><div><a target="_blank" href="${x.url}">${escapeHtml(x.title)}</a><small class="d-block text-muted">شناسه ${escapeHtml(String(x.id).slice(0,8))} · ${escapeHtml(x.kind)} · ${escapeHtml(x.status)} · شباهت ${x.score}٪</small></div><i class="fa-solid fa-arrow-up-right-from-square"></i></div>`).join('')}<label class="duplicate-confirm"><input type="checkbox" class="form-check-input" id="duplicateOverrideCheck" ${form.querySelector('#id_duplicate_override').value==='True'||form.querySelector('#id_duplicate_override').value==='1'?'checked':''}><span>موارد را بررسی کردم و می‌خواهم با وجود هشدار ادامه دهم.</span></label>`;box.classList.remove('d-none');document.getElementById('duplicateOverrideCheck')?.addEventListener('change',e=>form.querySelector('#id_duplicate_override').value=e.target.checked?'1':'0');
        }catch(e){console.warn(e);}
      },400);
      title?.addEventListener('input',()=>{countTitle();state.dirty=true;titleLookup();updateProgress();});countTitle();if(title?.value)titleLookup();

      // dependent subformat
      const main=$('#id_main_format'),sub=$('#id_sub_format'); let previousMain=main.val();
      async function loadSubformats(parentId,keepValue=true){
        const current=keepValue?sub.val():null; sub.prop('disabled',true);
        if(!parentId){sub.empty().append(new Option('ابتدا قالب اصلی را انتخاب کنید',''));sub.trigger('change');sub.prop('disabled',false);return;}
        try{const data=await api(`${window.ZOHA.urls.options}?type=content-subformat&parent=${parentId}`);sub.empty().append(new Option('ریزقالب را انتخاب کنید',''));data.results.forEach(x=>sub.append(new Option(x.text,x.id,false,String(x.id)===String(current))));if(current&&!data.results.some(x=>String(x.id)===String(current)))sub.val(null);sub.trigger('change');}finally{sub.prop('disabled',false);}
      }
      main.on('change',async function(){const currentSub=sub.val();if(currentSub&&previousMain&&String(previousMain)!==String(this.value)){if(!confirm('با تغییر قالب اصلی، ریزقالب قبلی نامعتبر می‌شود. ادامه می‌دهید؟')){main.val(previousMain).trigger('change.select2');return;}}previousMain=this.value;await loadSubformats(this.value,false);state.dirty=true;updateProgress();});
      if(main.val())loadSubformats(main.val(),true);

      // Generic option modal
      const optionModal=bootstrap.Modal.getOrCreateInstance(document.getElementById('optionModal'));
      $(document).on('click','[data-add-option]',function(){
        state.currentOptionType=$(this).data('add-option');state.currentOptionTarget=$(this).data('target');state.currentOptionParent=$(this).data('parent-select')?$($(this).data('parent-select')).val():($(this).data('parent')||'');
        const modalForm=document.getElementById('optionModalForm');modalForm.reset();if(modalForm.elements.force)modalForm.elements.force.value='0';modalForm.elements.type.value=state.currentOptionType;modalForm.elements.parent.value=state.currentOptionParent||'';if(modalForm.elements.edit_id)modalForm.elements.edit_id.value='';document.getElementById('occasionDateFields')?.classList.toggle('d-none',state.currentOptionType!=='occasion');modalForm.closest('.modal-content')?.querySelector('.modal-title')?.replaceChildren(document.createTextNode('افزودن مورد جدید'));document.getElementById('optionSimilarWarning').classList.add('d-none');optionModal.show();setTimeout(()=>modalForm.elements.title.focus(),300);
      });
      document.getElementById('optionModalForm')?.addEventListener('submit',async function(e){e.preventDefault();const btn=this.querySelector('button[type=submit]');btn.disabled=true;const editId=this.elements.edit_id?.value||'';try{const url=editId?window.ZOHA.urls.optionEditPattern.replace('/0/','/'+editId+'/'):window.ZOHA.urls.addOption;const data=await api(url,{method:'POST',body:new URLSearchParams(new FormData(this))});const option=data.option;/* ZOHA-W1.3-W1.4-CREATE-FLOW:START */appendConfigOption(state.currentOptionType,option,true);selectCreatedOption(state.currentOptionTarget,option);if(this.elements.force)this.elements.force.value='0';/* ZOHA-W1.3-W1.4-CREATE-FLOW:END */optionModal.hide();toast(editId?'گزینه ویرایش شد.':'گزینه جدید در فهرست شخصی شما ایجاد و انتخاب شد.');}catch(err){if(editId)toast(err.message,'danger');else handleSimilar(err,this,document.getElementById('optionSimilarWarning'),state.currentOptionTarget,optionModal);}finally{btn.disabled=false;}});
      function selectCreatedOption(targetSelector,option){const target=$(targetSelector);if(!target.length)return;const multiple=target.prop('multiple');target.append(new Option(`${option.text}${option.private?' (شخصی)':''}`,option.id,true,true));if(!multiple)target.val(String(option.id));target.trigger('change');state.dirty=true;}
      function handleSimilar(err,modalForm,warning,target,modalInstance){
        if(err.status!==409){toast(err.message,'danger');return;} const data=err.data;const items=data.similar||([data.existing].filter(Boolean));warning.innerHTML=`<strong>${escapeHtml(data.error)}</strong><div class="mt-2">${items.map(x=>`<button type="button" class="btn btn-sm btn-light ms-1 mb-1 use-similar" data-id="${x.id}" data-text="${escapeHtml(x.text||x.title)}">${escapeHtml(x.text||x.title)}${x.score?' · '+x.score+'٪':''}</button>`).join('')}</div><button type="button" class="btn btn-sm btn-warning mt-2 force-create">با وجود شباهت، مورد جدید ساخته شود</button>`;warning.classList.remove('d-none');warning.querySelectorAll('.use-similar').forEach(btn=>btn.addEventListener('click',()=>{selectCreatedOption(target,{id:btn.dataset.id,text:btn.dataset.text});modalInstance.hide();}));warning.querySelector('.force-create')?.addEventListener('click',e=>{const forceButton=e.currentTarget;if(forceButton.disabled)return;forceButton.disabled=true;modalForm.elements.force.value='1';modalForm.requestSubmit();});
      }
      function appendConfigOption(type,option,replace=false){const map={'subject':'topics','processing-key':'processing','predicate':'predicates','audience-job':'jobs','audience-country':'countries','audience-city':'cities'};const key=map[type];if(key){state.config[key]=state.config[key]||[];const found=state.config[key].find(x=>String(x.id)===String(option.id));if(found){found.title=option.text||option.title;found.visibility=option.visibility||found.visibility;}else state.config[key].push({id:option.id,title:option.text||option.title,visibility:option.visibility||'private'});if(['subject','processing-key','predicate'].includes(type))renderAnalyses();if(['audience-job','audience-country','audience-city'].includes(type))renderAudiences();}if(['promotional-usage','presentation-style'].includes(type))window.Zoha270AppendSpecialOption?.(type,option);}

      // Source modal
      const sourceModal=bootstrap.Modal.getOrCreateInstance(document.getElementById('sourceModal'));
      $(document).on('click','[data-add-source]',function(){state.currentSourceTarget=$(this).data('target');const sourceForm=document.getElementById('sourceModalForm');sourceForm.reset();if(sourceForm.elements.edit_id)sourceForm.elements.edit_id.value='';sourceForm.closest('.modal-content')?.querySelector('.modal-title')?.replaceChildren(document.createTextNode('افزودن منبع جدید'));document.getElementById('sourceSimilarWarning').classList.add('d-none');sourceModal.show();});
      document.getElementById('sourceModalForm')?.addEventListener('submit',async function(e){e.preventDefault();const btn=this.querySelector('button[type=submit],button:not([type])');btn.disabled=true;const editId=this.elements.edit_id?.value||'';try{const url=editId?window.ZOHA.urls.sourceEditPattern.replace('/0/','/'+editId+'/'):window.ZOHA.urls.addSource;const data=await api(url,{method:'POST',body:new URLSearchParams(new FormData(this))});const target=$(state.currentSourceTarget);const source=data.source;target.find(`option[value="${source.id}"]`).remove();target.append(new Option(source.text,source.id,true,true)).trigger('change');sourceModal.hide();toast(editId?'منبع ویرایش شد.':'منبع جدید ایجاد و انتخاب شد.');state.dirty=true;}catch(err){if(editId)toast(err.message,'danger');else handleSimilar(err,this,document.getElementById('sourceSimilarWarning'),state.currentSourceTarget,sourceModal);}finally{btn.disabled=false;}});

      // Topic analyses builder
      const topicContainer=document.getElementById('topicAnalyses');
      function optionHtml(items,selected,multiple=false){const selectedSet=new Set((multiple?(selected||[]):[selected]).filter(Boolean).map(String));return items.map(x=>`<option value="${x.id}" ${selectedSet.has(String(x.id))?'selected':''}>${escapeHtml(x.title||x.text)}${x.visibility==='private'?' (شخصی)':''}</option>`).join('');}
      function processingChecksHtml(items,selected){const selectedSet=new Set((selected||[]).filter(Boolean).map(String));return items.map(x=>`<label class="analysis-check-option" data-search-text="${escapeHtml((x.title||x.text).toLowerCase())}"><input type="checkbox" value="${x.id}" ${selectedSet.has(String(x.id))?'checked':''}><span><i class="fa-solid fa-check"></i>${escapeHtml(x.title||x.text)}${x.visibility==='private'?'<small>شخصی</small>':''}</span></label>`).join('');}
      function addAnalysis(row={}){state.analyses.push({id:row.id||null,topic:row.topic||'',processing_keys:row.processing_keys||[],predicate:row.predicate||'',predicate_text:row.predicate_text||'',interpretation:row.interpretation||'',review_status:row.review_status||'unchecked'});renderAnalyses();state.dirty=true;}
      function renderAnalyses(){
        topicContainer.innerHTML='';
        if(!state.analyses.length){topicContainer.innerHTML='<div class="empty-filter-message"><i class="fa-solid fa-diagram-project"></i><p>موضوع اختیاری است؛ در صورت نیاز یک موضوع اضافه کنید.</p></div>';syncAnalyses();updateProgress();return;}
        state.analyses.forEach((row,index)=>{
          const card=document.createElement('article');card.className='topic-analysis-card animate__animated animate__fadeIn';card.dataset.index=index;
          card.innerHTML=`<div class="topic-card-head"><i class="fa-solid fa-grip-vertical drag-handle"></i><div class="topic-card-title">تحلیل موضوعی ${index+1}<small>${row.topic?escapeHtml(state.config.topics.find(x=>String(x.id)===String(row.topic))?.title||'موضوع انتخاب‌شده'):'موضوع هنوز انتخاب نشده'}</small></div><div class="analysis-status"><i class="fa-solid fa-circle-check"></i><span>اطلاعات محفوظ است</span></div><div class="topic-card-actions"><button type="button" class="toggle" title="جمع‌کردن"><i class="fa-solid fa-chevron-up"></i></button><button type="button" class="remove" title="حذف"><i class="fa-solid fa-trash"></i></button></div></div><div class="topic-card-body"><div class="row g-3"><div class="col-lg-6"><div class="d-flex justify-content-between"><label class="form-label">موضوع</label><span class="inline-option-actions"><button type="button" class="btn btn-add-inline" data-edit-selected data-target="#topic-${index}" title="ویرایش گزینه انتخاب‌شده"><i class="fa-solid fa-pen"></i> ویرایش</button><button type="button" class="btn btn-add-inline" data-add-option="subject" data-target="#topic-${index}"><i class="fa-solid fa-plus"></i> موضوع شخصی</button></span></div><select id="topic-${index}" class="form-select topic-select" data-field="topic"><option value="">جست‌وجو و انتخاب موضوع</option>${optionHtml(state.config.topics,row.topic)}</select></div><div class="col-lg-6"><div class="d-flex justify-content-between align-items-center"><label class="form-label">کلیدهای پردازش <small class="text-muted">اختیاری</small></label><span class="inline-option-actions"><button type="button" class="btn btn-add-inline" data-edit-selected data-target="#processing-${index}" title="ویرایش گزینه انتخاب‌شده"><i class="fa-solid fa-pen"></i> ویرایش</button><button type="button" class="btn btn-add-inline" data-add-option="processing-key" data-target="#processing-${index}"><i class="fa-solid fa-plus"></i> کلید جدید</button></span></div><div class="analysis-picker"><div class="analysis-picker-search"><i class="fa-solid fa-magnifying-glass"></i><input type="search" class="form-control processing-filter" placeholder="جست‌وجو میان کلیدهای پردازش"></div><div class="analysis-check-grid">${processingChecksHtml(state.config.processing,row.processing_keys)}</div><select id="processing-${index}" class="d-none processing-select" multiple data-field="processing_keys">${optionHtml(state.config.processing,row.processing_keys,true)}</select><small class="analysis-picker-help"><i class="fa-solid fa-circle-info"></i> هر تعداد کلید لازم است با یک کلیک انتخاب کنید.</small></div></div><div class="col-lg-6"><div class="d-flex justify-content-between align-items-center"><label class="form-label">محمول استاندارد <small class="text-muted">اختیاری</small></label><span class="inline-option-actions"><button type="button" class="btn btn-add-inline" data-edit-selected data-target="#predicate-${index}" title="ویرایش گزینه انتخاب‌شده"><i class="fa-solid fa-pen"></i> ویرایش</button><button type="button" class="btn btn-add-inline" data-add-option="predicate" data-target="#predicate-${index}"><i class="fa-solid fa-plus"></i> محمول جدید</button></span></div><div class="analysis-picker"><div class="analysis-picker-search"><i class="fa-solid fa-magnifying-glass"></i><input type="search" class="form-control predicate-filter" placeholder="نام محمول را تایپ کنید"></div><select id="predicate-${index}" class="form-select predicate-select native-analysis-select" size="7" data-field="predicate"><option value="">بدون محمول استاندارد</option>${optionHtml(state.config.predicates,row.predicate)}</select><small class="analysis-picker-help"><i class="fa-solid fa-hand-pointer"></i> روی محمول مورد نظر کلیک کنید.</small></div></div><div class="col-lg-6"><label class="form-label">یا محمول پیشنهادی</label><input class="form-control" data-field="predicate_text" value="${escapeHtml(row.predicate_text)}" placeholder="در صورت نبود گزینه مناسب"></div><div class="col-12"><label class="form-label">برداشت نویسنده از این موضوع <small class="text-muted">اختیاری</small></label><textarea class="form-control" rows="4" data-field="interpretation" placeholder="تحلیل و برداشت اختصاصی مرتبط با همین موضوع">${escapeHtml(row.interpretation)}</textarea></div></div></div>`;
          topicContainer.appendChild(card);
          /* ZOHA-W1.2-TOPIC-SELECTION:START */
          const topicSelect=$(card).find('.topic-select');

          topicSelect.select2({
            theme:'bootstrap-5',
            dir:'rtl',
            width:'100%',
            placeholder:'جست‌وجو و انتخاب موضوع',
            allowClear:true
          });

          /*
           * انتخاب موضوع باید هم‌زمان در چهار محل ثابت شود:
           * 1) select واقعی
           * 2) state.analyses
           * 3) topic_analyses_json
           * 4) عنوان کارت موضوع
           */
          function persistTopicSelection(value){
            const normalized=(value===null||value===undefined)?'':String(value);

            row.topic=normalized;
            state.analyses[index].topic=normalized;

            /*
             * Select2 گاهی UI را از select اصلی جدا نگه می‌دارد.
             * change.select2 فقط ظاهر Select2 را sync می‌کند و
             * handler عمومی change را دوباره وارد حلقه نمی‌کند.
             */
            if(normalized){
              topicSelect.val(normalized);
            }else{
              topicSelect.val(null);
            }

            topicSelect.trigger('change.select2');

            syncAnalyses();
            updateTopicHeader(card,index);
            updateProgress();

            state.dirty=true;
          }

          topicSelect.on('select2:select.zohaTopic',function(e){
            const selectedId=
              e?.params?.data?.id ??
              $(this).val() ??
              '';

            persistTopicSelection(selectedId);
          });

          topicSelect.on('select2:clear.zohaTopic',function(){
            persistTopicSelection('');
          });

          /*
           * fallback برای مرورگر یا حالتی که Select2 event اختصاصی
           * اجرا نشود.
           */
          topicSelect.on('change.zohaTopic',function(){
            const selected=$(this).val()||'';

            if(String(state.analyses[index].topic||'') !== String(selected)){
              persistTopicSelection(selected);
            }else{
              /*
               * حتی اگر state از قبل مقدار داشته باشد،
               * hidden JSON و header باید sync شوند.
               */
              syncAnalyses();
              updateTopicHeader(card,index);
            }
          });

          /*
           * هنگام Edit نیز انتخاب قبلی باید بعد از initialize شدن
           * Select2 داخل فیلد قابل مشاهده بماند.
           */
          if(row.topic){
            topicSelect
              .val(String(row.topic))
              .trigger('change.select2');

            syncAnalyses();
            updateTopicHeader(card,index);
          }
          /* ZOHA-W1.2-TOPIC-SELECTION:END */
          const processingSelect=$(card).find('.processing-select');
          card.querySelectorAll('.analysis-check-option input').forEach(input=>input.addEventListener('change',()=>{const values=Array.from(card.querySelectorAll('.analysis-check-option input:checked')).map(x=>x.value);processingSelect.val(values).trigger('change');}));
          card.querySelector('.processing-filter')?.addEventListener('input',e=>{const q=e.target.value.trim().toLowerCase();card.querySelectorAll('.analysis-check-option').forEach(label=>label.classList.toggle('d-none',q&&!label.dataset.searchText.includes(q)));});
          /* ZOHA-W1.5-W1.6-PREDICATE:START */
          const predicateSelect=card.querySelector('.predicate-select');
          const predicateFilter=card.querySelector('.predicate-filter');

          function cleanPredicateLabel(value){
            return String(value||'')
              .replace(/\s*\(شخصی\)\s*$/,'')
              .trim();
          }

          function selectedPredicateLabel(){
            if(!predicateSelect)return '';

            const option=predicateSelect.selectedOptions?.[0];

            if(!option || !option.value)return '';

            return cleanPredicateLabel(option.textContent);
          }

          function persistPredicateSelection(value){
            const normalized=
              value===null || value===undefined
                ? ''
                : String(value);

            row.predicate=normalized;
            state.analyses[index].predicate=normalized;

            if(predicateSelect){
              predicateSelect.value=normalized;
            }

            if(predicateFilter){
              predicateFilter.value=selectedPredicateLabel();
            }

            syncAnalyses();
            updateTopicHeader(card,index);
            updateProgress();

            state.dirty=true;
          }

          predicateSelect?.addEventListener('change',function(){
            persistPredicateSelection(this.value||'');
          });

          predicateFilter?.addEventListener('input',function(e){
            const q=e.target.value.trim().toLowerCase();

            if(!predicateSelect)return;

            Array.from(predicateSelect.options).forEach((opt,i)=>{
              if(i===0)return;

              opt.hidden=
                !!q &&
                !cleanPredicateLabel(opt.textContent)
                  .toLowerCase()
                  .includes(q);
            });
          });

          predicateFilter?.addEventListener('search',function(){
            if(this.value)return;

            if(predicateSelect){
              Array.from(predicateSelect.options)
                .forEach(opt=>opt.hidden=false);
            }
          });

          /*
           * Restore predicate when editing an existing fish.
           */
          if(row.predicate && predicateSelect){
            predicateSelect.value=String(row.predicate);

            if(predicateFilter){
              predicateFilter.value=selectedPredicateLabel();
            }

            syncAnalyses();
          }
          /* ZOHA-W1.5-W1.6-PREDICATE:END */
          card.querySelector('.remove').addEventListener('click',()=>{if(confirm('این تحلیل موضوعی حذف شود؟')){state.analyses.splice(index,1);renderAnalyses();state.dirty=true;}});
          card.querySelector('.toggle').addEventListener('click',e=>{const body=card.querySelector('.topic-card-body'),closing=!body.classList.contains('collapsed');if(closing&&!isAnalysisComplete(state.analyses[index])&&!confirm('اطلاعات این تحلیل موضوعی هنوز کامل نیست. بخش جمع شود؟'))return;body.classList.toggle('collapsed');e.currentTarget.querySelector('i').classList.toggle('fa-chevron-down');e.currentTarget.querySelector('i').classList.toggle('fa-chevron-up');updateTopicHeader(card,index);});
          $(card).on('change input','[data-field]',function(){const field=$(this).data('field');state.analyses[index][field]=$(this).prop('multiple')?($(this).val()||[]):$(this).val();syncAnalyses();updateTopicHeader(card,index);updateProgress();state.dirty=true;});
          updateTopicHeader(card,index);
        });syncAnalyses();updateProgress();
      }
      function isAnalysisComplete(row){return !!row.topic;}
      function updateTopicHeader(card,index){const row=state.analyses[index],name=state.config.topics.find(x=>String(x.id)===String(row.topic))?.title,complete=isAnalysisComplete(row),status=card.querySelector('.analysis-status');card.querySelector('.topic-card-title small').textContent=name||'موضوع هنوز انتخاب نشده';if(status){status.classList.toggle('incomplete',!complete);status.querySelector('i').className=`fa-solid ${complete?'fa-circle-check':'fa-circle-exclamation'}`;status.querySelector('span').textContent=complete?'موضوع ثبت‌شده':'موضوع را انتخاب کنید';}}
      function syncAnalyses(){form.querySelector('#id_topic_analyses_json').value=JSON.stringify(state.analyses);}
      document.getElementById('addTopicAnalysis')?.addEventListener('click',()=>addAnalysis());
      renderAnalyses();

      // Audience builder
      const audienceContainer=document.getElementById('audienceProfiles');
      const genderOpts=['زن','مرد'],ageOpts=['کودک','نوجوان','جوان','میانسال','کهنسال'];
      function audienceOptionIds(items,values){return (values||[]).map(v=>{const found=(items||[]).find(x=>String(x.id)===String(v)||String(x.title||x.text).trim()===String(v).trim());return found?String(found.id):String(v);});}
      const regionOptions=(()=>{const seen=new Set();return [...(state.config.countries||[]),...(state.config.cities||[])].filter(x=>{const key=String(x.title||x.text||'').trim();if(!key||seen.has(key))return false;seen.add(key);return true;});})();
      function addAudience(row={}){const legacy=[...(row.countries||[]),...(row.cities||[]),...([row.country,row.city].filter(Boolean))];state.audiences.push({is_primary:row.is_primary??state.audiences.length===0,general:row.general||false,genders:row.genders||[],ages:row.ages||[],jobs:audienceOptionIds(state.config.jobs,row.jobs||[]),regions:audienceOptionIds(regionOptions,row.regions||legacy)});renderAudiences();state.dirty=true;}
      function toggles(values,selected,field,index){return values.map(v=>`<label class="audience-toggle"><input type="checkbox" data-field="${field}" value="${escapeHtml(v)}" ${(selected||[]).includes(v)?'checked':''}><span>${escapeHtml(v)}</span></label>`).join('');}
      function renderAudiences(){
        audienceContainer.innerHTML='';if(!state.audiences.length){audienceContainer.innerHTML='<div class="empty-filter-message"><i class="fa-solid fa-users-viewfinder"></i><p>در صورت نیاز، مخاطب اصلی یا تکمیلی اضافه کنید.</p></div>';syncAudiences();return;}
        state.audiences.forEach((row,index)=>{const card=document.createElement('article');card.className='audience-card animate__animated animate__fadeIn';card.innerHTML=`<div class="audience-card-head"><i class="fa-solid fa-user-group"></i><strong class="flex-grow-1">مخاطب ${index+1}</strong><label class="form-check form-switch mb-0"><input class="form-check-input primary-audience" type="radio" name="primaryAudience" ${row.is_primary?'checked':''}><span class="small">اصلی</span></label><button type="button" class="btn btn-sm btn-outline-danger remove-audience"><i class="fa-solid fa-trash"></i></button></div><div class="audience-card-body"><label class="form-check mb-3"><input class="form-check-input general-audience" type="checkbox" ${row.general?'checked':''}><span class="form-check-label fw-bold">عموم مردم</span></label><div class="audience-specific ${row.general?'d-none':''}"><div class="row g-3"><div class="col-md-6"><label class="form-label">جنسیت</label><div class="audience-toggle-row">${toggles(genderOpts,row.genders,'genders',index)}</div></div><div class="col-md-6"><label class="form-label">گروه سنی</label><div class="audience-toggle-row">${toggles(ageOpts,row.ages,'ages',index)}</div></div><div class="col-12"><div class="d-flex justify-content-between"><label class="form-label">صنف یا نقش اجتماعی</label><span class="inline-option-actions"><button type="button" class="btn btn-add-inline" data-edit-selected data-target="#audience-jobs-${index}" title="ویرایش صنف انتخاب‌شده"><i class="fa-solid fa-pen"></i> ویرایش</button><button type="button" class="btn btn-add-inline" data-add-option="audience-job" data-target="#audience-jobs-${index}"><i class="fa-solid fa-plus"></i> افزودن صنف</button></span></div><select id="audience-jobs-${index}" class="form-select audience-jobs" multiple>${optionHtml(state.config.jobs,row.jobs,true)}</select></div><div class="col-12"><label class="form-label">اقلیم <button type="button" class="field-help" data-bs-toggle="tooltip" title="نام شهر یا کشور مرتبط با متن"><i class="fa-regular fa-circle-question"></i></button></label><select id="audience-regions-${index}" class="form-select audience-regions" multiple>${optionHtml(regionOptions,row.regions,true)}</select><small class="form-help">نام شهر یا کشور مرتبط با متن؛ امکان انتخاب چند شهر و کشور وجود دارد.</small></div></div></div></div>`;audienceContainer.appendChild(card);
          $(card).find('.audience-jobs').select2({theme:'bootstrap-5',dir:'rtl',width:'100%',placeholder:'یک یا چند نقش اجتماعی'});$(card).find('.audience-regions').select2({theme:'bootstrap-5',dir:'rtl',width:'100%',tags:true,placeholder:'نام شهر یا کشور مرتبط با متن'});
          card.querySelector('.remove-audience').addEventListener('click',()=>{state.audiences.splice(index,1);if(state.audiences.length&&!state.audiences.some(x=>x.is_primary))state.audiences[0].is_primary=true;renderAudiences();state.dirty=true;});
          card.querySelector('.primary-audience').addEventListener('change',()=>{state.audiences.forEach((x,i)=>x.is_primary=i===index);syncAudiences();});
          card.querySelector('.general-audience').addEventListener('change',e=>{row.general=e.target.checked;card.querySelector('.audience-specific').classList.toggle('d-none',row.general);syncAudiences();state.dirty=true;});
          card.querySelectorAll('input[data-field]').forEach(input=>input.addEventListener('change',()=>{const field=input.dataset.field;row[field]=Array.from(card.querySelectorAll(`input[data-field="${field}"]:checked`)).map(x=>x.value);syncAudiences();state.dirty=true;}));
          $(card).find('.audience-jobs').on('change',function(){row.jobs=$(this).val()||[];syncAudiences();state.dirty=true;});
          $(card).find('.audience-regions').on('change',function(){row.regions=$(this).val()||[];syncAudiences();state.dirty=true;});
        });syncAudiences();
      }
      function syncAudiences(){form.querySelector('#id_audiences_json').value=JSON.stringify(state.audiences);}
      document.getElementById('addAudience')?.addEventListener('click',()=>addAudience());renderAudiences();

      // Progress and dirty guard
      function updateProgress(){
        const bodyReady=(state.quill?state.quill.getText().trim().length>0:!!textarea?.value.trim());const indexReady=!!$('#id_content_kind').val()||!!$('#id_content_category').val()||!!main.val()||!!sub.val()||state.analyses.some(x=>x.topic)||state.audiences.length>0||!!$('#id_source_type').val()||!!$('#id_source').val()||($('#id_characters').val()||[]).length>0||($('#id_occasions').val()||[]).length>0;const checks={title:!!title?.value.trim(),body:bodyReady,format:indexReady,topics:state.analyses.some(x=>x.topic),access:!!$('#id_access_level').val()};
        const complete=Object.values(checks).filter(Boolean).length,pct=Math.round(complete*100/Object.keys(checks).length);const ring=form.querySelector('[data-form-progress]');if(ring){ring.style.setProperty('--progress',pct+'%');ring.querySelector('strong').textContent=pct+'٪';}
        Object.entries(checks).forEach(([key,val])=>{const item=form.querySelector(`[data-check="${key}"]`);item?.classList.toggle('done',val);});
      }
      $form.on('change input','input,textarea,select',()=>{state.dirty=true;updateProgress();});updateProgress();
      window.addEventListener('beforeunload',e=>{if(state.dirty){e.preventDefault();e.returnValue='';}});
      form.addEventListener('submit',()=>{if(state.quill)textarea.value=state.quill.getHTML?state.quill.getHTML():state.quill.root.innerHTML;syncAnalyses();syncAudiences();state.dirty=false;});
      document.querySelectorAll('[data-no-dirty-guard]').forEach(el=>el.addEventListener('submit',()=>state.dirty=false));
    }
  };

  window.ZohaSearch={
    init(config){
      const container=document.getElementById('indexFilterRows'),empty=document.getElementById('emptyFilterMessage');if(!container)return;
      function addRow(initial={}){
        const row=document.createElement('div');row.className='index-filter-row animate__animated animate__fadeIn';
        row.innerHTML=`<div><label class="form-label">نوع نمایه</label><select class="form-select filter-type" name="filter_type"><option value="">انتخاب نوع نمایه</option>${config.types.map(x=>`<option value="${x.id}" data-slug="${escapeHtml(x.slug)}" ${String(x.id)===String(initial.type_id)?'selected':''}>${escapeHtml(x.text)}</option>`).join('')}</select></div><div><label class="form-label">مقدار مورد نظر</label><select class="form-select filter-value" name="filter_value"></select></div><button type="button" class="remove-filter" title="حذف شرط"><i class="fa-solid fa-trash"></i></button>`;
        container.appendChild(row);const type=$(row).find('.filter-type'),value=$(row).find('.filter-value');type.select2({theme:'bootstrap-5',dir:'rtl',width:'100%',placeholder:'نوع نمایه'});
        async function initValue(selected){
          if(value.hasClass('select2-hidden-accessible'))value.select2('destroy');
          value.empty();
          if(selected)value.append(new Option(selected.value,selected.value_id,true,true));
          const slug=type.find(':selected').data('slug')||'';
          if(!select2Available){
            value.append(new Option('انتخاب مقدار',''));
            if(!slug)return;
            try{
              const params=new URLSearchParams({type:slug,q:''});
              const data=await api(`${window.ZOHA.urls.options}?${params.toString()}`);
              data.results.forEach(x=>{if(!value.find(`option[value="${x.id}"]`).length)value.append(new Option(x.text+(x.private?' (شخصی)':''),x.id));});
              if(selected)value.val(String(selected.value_id));
            }catch(err){toast('بارگذاری مقادیر نمایه انجام نشد.','danger');}
            return;
          }
          value.select2({theme:'bootstrap-5',dir:'rtl',width:'100%',placeholder:'تایپ برای جست‌وجو',allowClear:true,minimumInputLength:0,ajax:{url:window.ZOHA.urls.options,dataType:'json',delay:250,data:params=>({type:slug,q:params.term||''}),processResults:data=>({results:data.results.map(x=>({id:x.id,text:x.text+(x.private?' (شخصی)':'' )}))}),cache:true}});
        }
        initValue(initial.value_id?initial:null);type.on('change',()=>{initValue(null);});row.querySelector('.remove-filter').addEventListener('click',()=>{value.select2('destroy');type.select2('destroy');row.remove();toggleEmpty();});toggleEmpty();
      }
      function toggleEmpty(){empty.classList.toggle('d-none',container.children.length>0);}
      document.getElementById('addIndexFilter')?.addEventListener('click',()=>addRow());document.querySelector('[data-add-first-filter]')?.addEventListener('click',()=>addRow());
      (config.filters||[]).forEach(addRow);toggleEmpty();
      document.querySelectorAll('[data-view]').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('[data-view]').forEach(x=>x.classList.remove('active'));btn.classList.add('active');document.getElementById('searchResults')?.classList.toggle('list-view',btn.dataset.view==='list');}));
    }
  };

  window.ZohaOptionManagement={
    init(){
      $('.merge-option-select').each(async function(){
        const select=$(this),type=select.data('type');
        if(select2Available){
          select.select2({theme:'bootstrap-5',dir:'rtl',width:'100%',placeholder:'گزینه مقصد',minimumInputLength:1,ajax:{url:window.ZOHA.urls.options,dataType:'json',delay:250,data:p=>({type,q:p.term||''}),processResults:d=>({results:d.results.map(x=>({id:x.id,text:x.text}))})}});
          return;
        }
        try{
          const params=new URLSearchParams({type,q:''});
          const data=await api(`${window.ZOHA.urls.options}?${params.toString()}`);
          select.append(new Option('گزینه مقصد',''));
          data.results.forEach(x=>select.append(new Option(x.text,x.id)));
        }catch(err){toast('بارگذاری گزینه‌های ادغام انجام نشد.','danger');}
      });
    }
  };
})(jQuery);

/* Zoha 2.6 — approved public/workbench interaction layer */
(function($){
  'use strict';
  const ui=window.ZohaUI||{};
  const api=ui.api||((...args)=>fetch(...args));
  const toast=ui.toast||((m)=>console.log(m));
  const esc=ui.escapeHtml||((v)=>String(v??''));

  function editorHtml(){
    const textarea=document.getElementById('id_body');
    if(!textarea)return '';
    try{return textarea.zohaHtmlEditor?.getHTML?.() ?? textarea.value ?? '';}catch(_){return textarea.value||'';}
  }
  function plain(html){const d=document.createElement('div');d.innerHTML=html||'';d.querySelectorAll('script,style,iframe,object,embed').forEach(x=>x.remove());return (d.textContent||'').trim();}
  function safePreview(html){
    const d=document.createElement('div');d.innerHTML=html||'';
    d.querySelectorAll('script,style,iframe,object,embed').forEach(x=>x.remove());
    d.querySelectorAll('*').forEach(el=>{[...el.attributes].forEach(a=>{if(/^on/i.test(a.name)||(/^(href|src)$/i.test(a.name)&&/^javascript:/i.test(a.value)))el.removeAttribute(a.name);});});
    return d.innerHTML;
  }
  function splitSelected(select){return Array.from(select?.selectedOptions||[]).map(x=>x.text.replace(/\s*\(شخصی\)\s*$/,'').trim()).filter(Boolean);}

  window.Zoha270Form={
    init(config={}){
      const form=document.getElementById('fishForm'); if(!form)return;
      const specialInput=document.getElementById('id_special_indexes_json');
      const specials=config.specials&&typeof config.specials==='object'?config.specials:{};
      let stage=1,localDirty=false,submitting=false,autosaveTimer=null;

      // 4-stage navigation
      const stages=[...form.querySelectorAll('.form-stage')],steps=[...form.querySelectorAll('.fish-step')];
      const next=form.querySelector('[data-stage-next]'),prev=form.querySelector('[data-stage-prev]'),submit=form.querySelector('[data-final-submit]');
      function showStage(n,scroll=true){
        stage=Math.min(4,Math.max(1,Number(n)||1));
        stages.forEach(x=>x.classList.toggle('active',Number(x.dataset.stage)===stage));
        steps.forEach(x=>{const value=Number(x.dataset.stageGo);x.classList.toggle('active',value===stage);x.classList.toggle('done',value<stage);});
        form.querySelectorAll('.guide-dots i').forEach((x,i)=>x.classList.toggle('active',i===stage-1));
        const label=document.getElementById('mobileStageLabel');if(label)label.textContent=`مرحله ${stage} از ۴`;
        prev?.classList.toggle('d-none',stage===1);next?.classList.toggle('d-none',stage===4);submit?.classList.toggle('d-none',stage!==4);
        if(next){const texts=['ادامه و تکمیل نمایه‌ها','ادامه به دسترسی و پیوست','بازبینی نهایی'];next.innerHTML=`${texts[stage-1]||'ادامه'} <i class="fa-solid fa-angle-left"></i>`;}
        if(stage===4)refreshReview();
        if(scroll)document.querySelector('.fish-form-main')?.scrollIntoView({behavior:'smooth',block:'start'});
      }
      steps.forEach(x=>x.addEventListener('click',()=>showStage(x.dataset.stageGo)));
      next?.addEventListener('click',()=>showStage(stage+1));prev?.addEventListener('click',()=>showStage(stage-1));
      const firstError=form.querySelector('.errorlist');if(firstError){const bad=firstError.closest('.form-stage');showStage(bad?.dataset.stage||1,false);}else showStage(1,false);

      // Content-kind pills and dependent content field
      const kind=document.getElementById('id_content_kind'),category=$('#id_content_category');
      function syncKindPills(){
        const wrap=document.getElementById('contentKindPills');if(!wrap||!kind)return;
        wrap.querySelectorAll('[data-kind-id]').forEach(b=>b.classList.toggle('selected',String(b.dataset.kindId)===String(kind.value)));
        if(kind.value&&!wrap.querySelector(`[data-kind-id="${CSS.escape(String(kind.value))}"]`)){
          const opt=kind.selectedOptions[0];if(opt){const b=document.createElement('button');b.type='button';b.dataset.kindId=kind.value;b.className='selected';b.innerHTML=`<i class="fa-regular fa-file-lines"></i>${esc(opt.text.replace(/\s*\(شخصی\)\s*$/,''))}`;wrap.appendChild(b);b.addEventListener('click',()=>setKind(b.dataset.kindId));}
        }
      }
      async function loadCategories(keep=true){
        if(!category.length)return;const current=keep?category.val():'';
        if(!kind?.value){category.prop('disabled',true).empty().append(new Option('ابتدا جنس محتوا را انتخاب کنید','')).trigger('change');return;}
        try{const data=await api(`${window.ZOHA.urls.options}?type=content-category&parent=${encodeURIComponent(kind.value)}`);category.prop('disabled',false).empty().append(new Option('محتوا را انتخاب کنید (اختیاری)',''));data.results.forEach(x=>category.append(new Option(x.text,x.id,false,String(x.id)===String(current))));if(current&&!data.results.some(x=>String(x.id)===String(current)))category.val(null);category.trigger('change');}catch(_){category.prop('disabled',false);}
      }
      function setKind(id){if(!kind)return;$(kind).val(String(id)).trigger('change');}
      document.querySelectorAll('[data-kind-id]').forEach(b=>b.addEventListener('click',()=>setKind(b.dataset.kindId)));
      $(kind).on('change',()=>{syncKindPills();loadCategories(false);markDirty();});syncKindPills();loadCategories(true);

      // Special indexes: usage + presentation, with primary/supplemental distinction
      function normalizeSpecial(slug){const row=specials[slug]||{};return {items:(row.items||[]).map(String),primary:row.primary?String(row.primary):null};}
      ['promotional-usage','presentation-style'].forEach(slug=>{specials[slug]=normalizeSpecial(slug);const row=specials[slug];form.querySelectorAll(`[data-special-item="${slug}"]`).forEach(cb=>cb.checked=row.items.includes(String(cb.value)));form.querySelectorAll(`[data-special-primary="${slug}"]`).forEach(r=>r.checked=String(r.value)===String(row.primary));});
      function syncSpecial(slug){
        const checks=[...form.querySelectorAll(`[data-special-item="${slug}"]:checked`)];let items=checks.map(x=>String(x.value));let primary=form.querySelector(`[data-special-primary="${slug}"]:checked`)?.value||null;
        if(primary&&!items.includes(String(primary)))items.push(String(primary));
        if(items.length&&!primary){primary=items[0];const radio=form.querySelector(`[data-special-primary="${slug}"][value="${CSS.escape(String(primary))}"]`);if(radio)radio.checked=true;}
        if(!items.length){primary=null;form.querySelectorAll(`[data-special-primary="${slug}"]`).forEach(x=>x.checked=false);}
        specials[slug]={items,primary};if(specialInput)specialInput.value=JSON.stringify(specials);markDirty(false);refreshReview();
      }
      form.querySelectorAll('[data-special-item]').forEach(cb=>cb.addEventListener('change',()=>{const slug=cb.dataset.specialItem;if(!cb.checked){const r=form.querySelector(`[data-special-primary="${slug}"][value="${CSS.escape(cb.value)}"]`);if(r)r.checked=false;}syncSpecial(slug);}));
      form.querySelectorAll('[data-special-primary]').forEach(r=>r.addEventListener('change',()=>{const slug=r.dataset.specialPrimary;const cb=form.querySelector(`[data-special-item="${slug}"][value="${CSS.escape(r.value)}"]`);if(cb)cb.checked=true;syncSpecial(slug);}));
      function bindSpecialControls(root){root.querySelectorAll('[data-special-item]').forEach(cb=>cb.addEventListener('change',()=>{const slug=cb.dataset.specialItem;if(!cb.checked){const r=form.querySelector(`[data-special-primary="${slug}"][value="${CSS.escape(cb.value)}"]`);if(r)r.checked=false;}syncSpecial(slug);}));root.querySelectorAll('[data-special-primary]').forEach(r=>r.addEventListener('change',()=>{const slug=r.dataset.specialPrimary;const cb=form.querySelector(`[data-special-item="${slug}"][value="${CSS.escape(r.value)}"]`);if(cb)cb.checked=true;syncSpecial(slug);}));}
      window.Zoha270AppendSpecialOption=(slug,option)=>{const id=String(option.id),title=esc(option.text||option.title||'گزینه جدید');if(form.querySelector(`[data-special-item="${slug}"][value="${CSS.escape(id)}"]`))return;let root=null;if(slug==='presentation-style'){const grid=form.querySelector('[data-special-group="presentation-style"] .presentation-chip-grid');if(!grid)return;root=document.createElement('div');root.innerHTML=`<label><input type="checkbox" data-special-item="presentation-style" value="${id}" checked><span>${title}</span></label><label class="primary-choice"><input type="radio" name="primary-presentation-style" data-special-primary="presentation-style" value="${id}"> اصلی</label><button type="button" data-edit-special="${id}"><i class="fa-regular fa-pen-to-square"></i></button>`;grid.appendChild(root);}else{const box=form.querySelector('[data-special-group="promotional-usage"]');if(!box)return;root=document.createElement('div');root.className='usage-group';root.innerHTML=`<div class="usage-group-title"><label><input type="checkbox" data-special-item="promotional-usage" value="${id}" checked><b>${title}</b></label><label class="primary-choice"><input type="radio" name="primary-promotional-usage" data-special-primary="promotional-usage" value="${id}"> اصلی</label><button type="button" data-edit-special="${id}"><i class="fa-regular fa-pen-to-square"></i></button></div><div class="usage-children"></div>`;box.appendChild(root);}bindSpecialControls(root);syncSpecial(slug);};
      if(specialInput)specialInput.value=JSON.stringify(specials);

      // Access cards mirror the real Django field
      const access=document.getElementById('id_access_level'),teamWrap=document.getElementById('teamAccessField'),team=document.getElementById('id_team');
      function syncAccess(){const value=access?.value||'private';form.querySelectorAll('[data-access]').forEach(x=>{x.classList.toggle('selected',x.dataset.access===value);const radio=x.querySelector('input');if(radio)radio.checked=x.dataset.access===value;});teamWrap?.classList.toggle('d-none',value!=='team');if(team)team.required=value==='team';refreshReview();}
      form.querySelectorAll('[data-access] input').forEach(r=>r.addEventListener('change',()=>{$(access).val(r.value).trigger('change');syncAccess();markDirty();}));$(access).on('change',syncAccess);syncAccess();

      // Edit the selected personal taxonomy option using the same modal.
      function selectedId(target){const el=document.querySelector(target);if(!el)return null;const vals=$(el).val();if(Array.isArray(vals)){if(vals.length!==1){toast(vals.length?'برای ویرایش فقط یک گزینه را انتخاب کنید.':'ابتدا یک گزینه را انتخاب کنید.','info');return null;}return vals[0];}if(!vals){toast('ابتدا یک گزینه را انتخاب کنید.','info');return null;}return vals;}
      document.addEventListener('click',e=>{
        const btn=e.target.closest('[data-edit-selected]');if(!btn)return;e.preventDefault();
        const target=btn.dataset.target,id=selectedId(target);if(!id)return;const add=btn.parentElement?.querySelector('[data-add-option]')||document.querySelector(`[data-add-option][data-target="${target}"]`);if(!add)return;add.click();setTimeout(()=>{const f=document.getElementById('optionModalForm'),sel=document.querySelector(target);if(!f||!sel)return;f.elements.edit_id.value=id;f.elements.title.value=Array.from(sel.options).find(o=>String(o.value)===String(id))?.text.replace(/\s*\(شخصی\)\s*$/,'')||'';f.closest('.modal-content').querySelector('.modal-title').textContent='ویرایش گزینه';f.elements.title.focus();},30);
      });
      document.querySelectorAll('[data-edit-source-selected]').forEach(btn=>btn.addEventListener('click',()=>{const target=btn.dataset.target,id=selectedId(target);if(!id)return;const add=btn.parentElement?.querySelector('[data-add-source]');add?.click();setTimeout(()=>{const f=document.getElementById('sourceModalForm'),sel=document.querySelector(target);if(!f||!sel)return;f.elements.edit_id.value=id;f.elements.title.value=Array.from(sel.options).find(o=>String(o.value)===String(id))?.text||'';f.closest('.modal-content').querySelector('.modal-title').textContent='ویرایش منبع';f.elements.title.focus();},30);}));
      document.addEventListener('click',async e=>{const btn=e.target.closest('[data-edit-special]');if(!btn)return;e.preventDefault();const id=btn.dataset.editSpecial;const holder=btn.closest('.usage-group-title')||btn.parentElement;const label=holder?.querySelector('label')?.textContent.trim()||'';const title=prompt('عنوان جدید گزینه شخصی را وارد کنید:',label);if(!title||title===label)return;try{const data=await api(window.ZOHA.urls.optionEditPattern.replace('/0/','/'+id+'/'),{method:'POST',body:new URLSearchParams({title})});const text=data.option?.text||title;const target=holder?.querySelector('b, label span');if(target)target.textContent=text;toast('گزینه شخصی ویرایش شد.');}catch(err){toast(err.message||'ویرایش ممکن نیست.','danger');}});

      // Attachment deletion without leaving the form
      document.querySelectorAll('[data-delete-attachment]').forEach(btn=>btn.addEventListener('click',async()=>{if(!confirm('این پیوست حذف شود؟'))return;try{await api(btn.dataset.deleteAttachment,{method:'POST'});btn.closest('[data-attachment-row]')?.remove();toast('پیوست حذف شد.');markDirty(false);}catch(e){toast(e.message||'حذف پیوست انجام نشد.','danger');}}));

      // Live review / preview
      function selectedText(id){const el=document.getElementById(id);return el?.selectedOptions?.[0]?.text?.replace(/\s*\(شخصی\)\s*$/,'').trim()||'';}
      function specialNames(slug){return [...form.querySelectorAll(`[data-special-item="${slug}"]:checked`)].map(x=>x.closest('label')?.textContent.trim()).filter(Boolean);}
      function refreshReview(){
        const title=(document.getElementById('id_title')?.value||'').trim()||'فیش بدون عنوان';const kindText=selectedText('id_content_kind')||'فیش تبلیغی';const html=editorHtml();
        const t=document.getElementById('reviewTitle'),k=document.getElementById('reviewKind'),b=document.getElementById('reviewBody'),a=document.getElementById('reviewAbstract'),src=document.getElementById('reviewSource'),idx=document.getElementById('reviewIndexes'),acc=document.getElementById('reviewAccess');
        if(t)t.textContent=title;if(k)k.textContent=kindText;if(b)b.textContent=plain(html).slice(0,700)||'متن اصلی اینجا پیش‌نمایش داده می‌شود.';if(a)a.textContent=(document.getElementById('id_abstract')?.value||'').trim()||'—';if(src)src.textContent=selectedText('id_source')||selectedText('id_source_type')||'—';
        const indexes=[...splitSelected(document.getElementById('id_characters')),...splitSelected(document.getElementById('id_occasions')),...specialNames('promotional-usage'),...specialNames('presentation-style')];if(idx)idx.textContent=indexes.slice(0,12).join('، ')||'نمایه‌های موضوعی/مخاطب پس از ذخیره ثبت می‌شوند.';if(acc)acc.textContent=selectedText('id_access_level')||'فقط خودم';
      }
      document.querySelector('[data-preview-open]')?.addEventListener('click',()=>{refreshReview();const box=document.getElementById('liveFishPreview');if(box){box.innerHTML=`<article class="live-preview-paper"><span>${esc(selectedText('id_content_kind')||'فیش تبلیغی')}</span><h2>${esc((document.getElementById('id_title')?.value||'').trim()||'فیش بدون عنوان')}</h2>${document.getElementById('id_abstract')?.value?`<p class="preview-summary">${esc(document.getElementById('id_abstract').value)}</p>`:''}<div class="preview-content">${safePreview(editorHtml())}</div></article>`;}bootstrap.Modal.getOrCreateInstance(document.getElementById('fishPreviewModal')).show();});

      // Save status + autosave for existing records
      const indicator=document.getElementById('saveIndicator');
      function saveState(kind,text){if(!indicator)return;indicator.className=`save-indicator ${kind||''}`;indicator.innerHTML=`<i class="fa-solid ${kind==='saving'?'fa-spinner fa-spin':kind==='error'?'fa-triangle-exclamation':'fa-circle-check'}"></i><span>${esc(text)}</span>`;}
      function markDirty(schedule=true){localDirty=true;if(schedule&&form.dataset.autosaveUrl){clearTimeout(autosaveTimer);autosaveTimer=setTimeout(autoSave,8000);}}
      async function autoSave(){if(!localDirty||submitting||!form.dataset.autosaveUrl)return;const body=plain(editorHtml());if(!body)return;const hasIndex=!!kind?.value||!!category.val()||!!$('#id_main_format').val()||!!$('#id_source_type').val()||!!$('#id_source').val()||($('#id_characters').val()||[]).length||($('#id_occasions').val()||[]).length||[...form.querySelectorAll('[data-special-item]:checked')].length||JSON.parse(document.getElementById('id_topic_analyses_json')?.value||'[]').length||JSON.parse(document.getElementById('id_audiences_json')?.value||'[]').length;if(!hasIndex){saveState('','برای ذخیره خودکار، حداقل یک نمایه انتخاب کنید');return;}
        try{saveState('saving','در حال ذخیره…');const fd=new FormData(form);fd.delete('attachments');fd.delete('source_file');fd.set('body',editorHtml());fd.set('special_indexes_json',JSON.stringify(specials));const response=await fetch(form.dataset.autosaveUrl,{method:'POST',headers:{'X-CSRFToken':decodeURIComponent(document.cookie.split('; ').find(x=>x.startsWith((window.ZOHA.csrfCookie||'csrftoken')+'='))?.split('=')[1]||'')},body:fd});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||'ذخیره خودکار فعلاً ممکن نیست');localDirty=false;saveState('success',`ذخیره شد · ${data.saved_at||''}`);}catch(e){saveState('error','ذخیره خودکار انجام نشد؛ از «ذخیره پیش‌نویس» استفاده کنید');}
      }
      form.addEventListener('input',()=>{markDirty();refreshReview();});form.addEventListener('change',()=>{markDirty();refreshReview();});
      form.addEventListener('submit',()=>{submitting=true;clearTimeout(autosaveTimer);if(specialInput)specialInput.value=JSON.stringify(specials);const textarea=document.getElementById('id_body');if(textarea&&textarea.zohaHtmlEditor?.getHTML)textarea.value=textarea.zohaHtmlEditor.getHTML();saveState('saving','در حال ذخیره…');});
      document.querySelector('[data-form-cancel]')?.addEventListener('click',e=>{if(localDirty&&!confirm('برخی تغییرات ذخیره نشده‌اند. از صفحه خارج می‌شوید؟'))e.preventDefault();});

      // Submission confirmation and review freshness
      submit?.addEventListener('click',e=>{refreshReview();if(!confirm('آیا می‌خواهید این فیش برای بررسی ارسال شود؟'))e.preventDefault();});
      refreshReview();
    }
  };
})(jQuery);

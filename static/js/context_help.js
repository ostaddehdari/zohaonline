(function(){
  'use strict';
  const guides={
    'داشبورد':'نمای کلی وضعیت فیش‌ها، آمار شخصی و موارد نیازمند اقدام.',
    'فیش‌های اخیر':'آخرین فیش‌هایی که ایجاد یا ویرایش شده‌اند.',
    'آمار شخصی':'توزیع فیش‌های شما بر اساس وضعیت گردش کار.',
    'اطلاعات پایه':'مشخصات اصلی و دسته‌بندی اولیه فیش را وارد کنید.',
    'متن اصلی':'متن کامل فیش را وارد کنید؛ در نسخه پنجم فقط عنوان برای ادامه الزامی است.',
    'تحلیل موضوعی':'موضوع، کلید پردازش و ریز موضوع مرتبط با متن را ثبت کنید.',
    'مخاطب':'می‌توانید چند مخاطب بسازید و یکی را مخاطب اصلی قرار دهید.',
    'منبع':'اطلاعات کتاب، رسانه، راوی، جلد، صفحه یا پیوند منبع.',
    'دسترسی':'مشخص می‌کند فیش خصوصی، گروهی یا عمومی باشد.',
    'پیوست':'فایل‌های تصویری، صوتی، متنی یا اسناد مرتبط را اضافه کنید.',
    'نمایه':'نمایه‌ها بازیابی و جست‌وجوی دقیق‌تر محتوا را ممکن می‌کنند.',
    'جست‌وجو':'عبارت و فیلترها را ترکیب کنید تا نتیجه دقیق‌تر شود.',
    'گزارش':'آمار سامانه و وضعیت تولید و ارزیابی محتوا.',
    'پروژه':'فیش‌ها و نمایه‌های مرتبط را در یک مجموعه هدفمند نگهداری کنید.',
    'اعلان':'رویدادهای ارزیابی، اصلاح و فعالیت‌های مرتبط با حساب شما.',
    'ارزیابی':'محتوا و نمایه‌ها را بررسی و نتیجه یا یادداشت اصلاحی ثبت کنید.',
    'کاربران':'حساب‌ها، نقش‌ها و وضعیت دسترسی کاربران را مدیریت کنید.',
    'گروه':'اعضا و دسترسی مشترک فیش‌های گروه کاری را مدیریت کنید.',
    'ریز جنس محتوا':'زیرگونه‌ای که به جنس محتوای انتخاب‌شده وابسته است.',
    'ریز موضوع':'مفهوم یا گزاره جزئی وابسته به موضوع اصلی.'
  };
  function helpFor(text){text=(text||'').replace(/\s+/g,' ').trim();for(const [key,value] of Object.entries(guides))if(text.includes(key))return value;return text?`راهنمای بخش «${text.slice(0,70)}»`:'راهنمای این بخش';}
  function addHelp(el){if(!el||el.querySelector(':scope > .section-help'))return;const text=el.innerText;const button=document.createElement('button');button.type='button';button.className='section-help field-help';button.setAttribute('aria-label','راهنمای این بخش');button.setAttribute('data-bs-toggle','tooltip');button.title=helpFor(text);button.innerHTML='<i class="fa-regular fa-circle-question"></i>';el.append(button);if(window.bootstrap?.Tooltip)new bootstrap.Tooltip(button,{trigger:'hover focus click',container:'body'});}
  function normalizeLabels(root=document.body){const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;while((node=walker.nextNode())){if(node.parentElement?.closest('script,style'))continue;const trimmed=node.nodeValue.trim();if(trimmed==='محمول')node.nodeValue=node.nodeValue.replace('محمول','ریز موضوع');if(trimmed==='محمول استاندارد')node.nodeValue=node.nodeValue.replace('محمول استاندارد','ریز موضوع استاندارد');if(trimmed==='یا محمول پیشنهادی')node.nodeValue=node.nodeValue.replace('یا محمول پیشنهادی','یا ریز موضوع پیشنهادی')}}
  normalizeLabels();
  document.querySelectorAll('.panel-heading h3,.dash-panel-head h2,.form-section h2,.form-section h3,.form-field-block>.form-label,.fish-form-intro h1,.detail-hero h2,.docs-content h2').forEach(addHelp);
  new MutationObserver(items=>items.forEach(item=>item.addedNodes.forEach(node=>{if(node.nodeType!==1)return;if(node.matches?.('.form-label,h2,h3'))addHelp(node);node.querySelectorAll?.('.form-label,h2,h3').forEach(addHelp)}))).observe(document.body,{childList:true,subtree:true});
})();

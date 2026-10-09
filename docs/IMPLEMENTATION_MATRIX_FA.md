# ماتریس پیاده‌سازی ZohaOnline 2.6.0 — کارگاه محتوای ضحی

| حوزه | وضعیت | محل اصلی پیاده‌سازی |
|---|---|---|
| ویترین عمومی جست‌وجومحور، RTL و واکنش‌گرا | انجام‌شده | `templates/public/*`, `static/css/app_260.css` |
| هدر، Hero، دسته‌های سریع، موضوعات پرکاربرد و فوتر | انجام‌شده | `public/home.html`, `public/base_public.html` |
| فیش منتخب مدیریتی، جدیدترین و پربازدیدترین | انجام‌شده | `Research.is_featured`, `featured_order`, `public_home` |
| CTA ورود/ثبت‌نام و ذخیره فیش عمومی | انجام‌شده | `public/home.html`, `ResearchBookmark` |
| جست‌وجوی عمومی FTS/Trigram + Pagination | انجام‌شده | `public_search` |
| فیلتر عمومی: نوع، موضوع، مناسبت، مخاطب، کاربرد، شیوه ارائه و کلمه کلیدی | انجام‌شده | `public/search.html`, `public_search` |
| Drawer فیلتر موبایل | انجام‌شده | `public/search.html`, `app_260.css` |
| صفحه جزئیات عمومی + اشتراک + ذخیره + مرتبط | انجام‌شده | `public/fish_detail.html` |
| داشبورد فیش‌بردار مطابق طراحی سرمه‌ای/طلایی | انجام‌شده | `research/dashboard.html` |
| فهرست فیش‌های من و فیلترهای کامل | انجام‌شده | `research_list`, `research/research_list.html` |
| Lifecycle واحد فیش و Team access واقعی | انجام‌شده | Baseline 2.5 + models/services |
| فرم ۴ مرحله‌ای ثبت/ویرایش | انجام‌شده | `research/research_form.html`, `app_260.js` |
| ذخیره پیش‌نویس، Autosave، Preview و ارسال | انجام‌شده | form views + `research_autosave` |
| «جنس محتوا» و «محتوا» وابسته | انجام‌شده | Seed, `ResearchForm`, JS |
| ساختار منبع: نوع، نام، فایل + توضیحات منبع | انجام‌شده | Model/Form/Template |
| موضوعات اختیاری با کارت‌های جدا، ویرایش/حذف | انجام‌شده | `TopicAnalysis`, JS Topic Builder |
| کلید پردازش و محمول اختیاری | انجام‌شده | `TopicAnalysis`, Form/JS |
| کاربردهای تبلیغی اقناعی/احساسی/رفتاری و زیرگروه‌ها | انجام‌شده | Seed + `ResearchIndex` special workflow |
| کاربرد اصلی/تکمیلی | انجام‌شده | `ResearchIndex.is_primary`, detail templates |
| پیشنهاد شیوه ارائه اختیاری و قابل جست‌وجو | انجام‌شده | Seed + special indexes + search |
| مخاطب عمومی/اختصاصی ترکیبی | انجام‌شده | `audience_profiles`, Audience Builder |
| افزودن/ویرایش صنف، کشور و شهر | انجام‌شده | Option API + Select2 Audience Builder |
| کلمات کلیدی فقط از متن و غیرتکراری با نمایه | انجام‌شده | `ResearchForm.clean` |
| شخصیت/موضوع/محمول/منبع/... افزودن و ویرایش شخصی | انجام‌شده | Option/Source APIs + form modals |
| مناسبت با روز و ماه شمسی و چند مناسبت در روز | انجام‌شده | `IndexValue.metadata`, option modal |
| توضیحات نویسنده | انجام‌شده | `author_explanation` |
| فیش‌برداری اختصاصی | انجام‌شده | `CustomCollection`, `custom_collections` |
| پیوست تصویر/صوت/سند | انجام‌شده | `ResearchAttachment` |
| نمایش خلاصه و کلمات کلیدی پیش از متن اصلی | انجام‌شده | internal/public detail templates |
| AI-assisted indexing workflow | انجام‌شده | Baseline 2.5 AI models/views |
| Sermon Artifact و Revision | انجام‌شده | Baseline 2.5 |
| Upgrade بدون حذف داده | انجام‌شده | migrations + installer |

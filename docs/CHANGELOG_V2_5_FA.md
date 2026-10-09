# Changelog — ZohaOnline 2.5.0

## Release Baseline

- Version: `2.5.0`
- Marker: `ZOHA-AURORA-250`
- Codename: `Aurora Knowledge Studio / استودیوی دانش شفق`

## 1. Release Consolidation

هسته ۲.۴.۰ و Hotfixهای ۲.۴.۲ و ۲.۴.۳ در یک Baseline واحد ادغام شدند. نسخه، نام انتشار، Marker و Codename از `zoha/release.py` خوانده می‌شوند و Template/API از عددهای ثابت مستقل شده‌اند.

## 2. Research Lifecycle

`Research.status` تنها Lifecycle مرجع فیش است. فیلدهای موازی `validation_status`، `publication_status` و `is_public` پس از Migration داده حذف می‌شوند.

Lifecycle اصلی:

`draft → in_review → changes_requested / approved / rejected → published`

حالت `submitted` برای سازگاری داده‌های تاریخی حفظ شده و هنگام شروع ارزیابی به `in_review` منتقل می‌شود.

انتشار عمومی فقط وقتی معتبر است که هم‌زمان `status=published` و `access_level=public` باشد.

## 3. Team Access Domain

مدل‌های `Team` و `TeamMembership` اضافه شدند. دسترسی `access_level=team` اکنون به عضویت فعال یا مالکیت Team وابسته است. در Migration، رکوردهای تاریخی `team` به `private` تبدیل می‌شوند چون در نسخه قبلی هیچ رابطه عضویتی قابل اتکایی وجود نداشت.

## 4. Disabled Account Hardening

`User.is_enabled` منبع محصولی وضعیت حساب است و برای کاربران غیر Superuser هنگام ذخیره با Django `is_active` همگام می‌شود. Middleware نیز نشست کاربر غیرفعال را قطع می‌کند.

## 5. Search 2.5

در PostgreSQL:

- Full-Text Search با وزن‌دهی عنوان، کلیدواژه، منبع، خلاصه، متن و تحلیل موضوعی
- `pg_trgm` برای شباهت عنوان
- مرتب‌سازی بر اساس Rank/Similarity
- Pagination با ۲۴ نتیجه در هر صفحه
- Facet موضوع و جنس محتوا روی کل Query فیلترشده، بدون سقف ۱۰۰۰ نتیجه

برای SQLite یک fallback مبتنی بر `icontains` نگه داشته شده است.

## 6. AI Indexing Workflow

هر اجرای نمایه‌زنی AI در `AIIndexingRun` ذخیره و به `AIIndexSuggestion`های مستقل تبدیل می‌شود. پیشنهادها با واژگان موجود Match می‌شوند و پژوهشگر باید هر پیشنهاد را بپذیرد یا رد کند. فقط پیشنهادهای پذیرفته‌شده و دارای تطبیق کافی اعمال می‌شوند؛ واژگان حساس به‌صورت خودکار ساخته نمی‌شوند.

## 7. Sermon Artifact Versioning

خروجی موفق منبرساز در `SermonArtifact` ذخیره می‌شود و نسخه نخست در `SermonRevision` ثبت می‌شود. هر ویرایش محتوایی Revision جدید با شماره نسخه مستقل ایجاد می‌کند. وضعیت Artifact می‌تواند `draft`، `final` یا `archived` باشد.

## 8. Database Migrations

- `accounts/0003_team_access_domain.py`
- `research/0010_aurora_250_baseline.py`

Migration دوم `pg_trgm`، Team FK، نگاشت Lifecycle و مدل‌های Workflow هوش مصنوعی را اعمال می‌کند.

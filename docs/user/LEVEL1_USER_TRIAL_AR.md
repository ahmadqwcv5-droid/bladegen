# دليل تشغيل تجربة BladeGen Level 1

## الحالة الحالية

**النسخة الحالية جاهزة لتجربة المستخدم (`FP02_READY_FOR_USER_TRIAL`).** نجحت مصفوفة FP02-C1 المنقحة في 8/8 حالات، ونجح اختبار المتصفح الكامل في 16/16 من دون إعادة محاولة أو تخطي. أُصلح مرجع التحقق الوسيط في Q02/Q03، ونجحت Q04.R1 ذات الدوران Reverse في 26/26 مقطعاً. ملف Q04 الأصلي ما زال مرفوضاً عمداً قبل تشغيل CAD لأنه إدخال متعارض.

شغّل التجربة بملف 900 ثانية الموضح أدناه. الإعداد العادي 300 ثانية لم يُؤهّل لحالة X-57. أكّد المستخدم بنفسه نجاح إنشاء شفرة بسيطة وتعديل Twist وإعادة التوليد، وكذلك استيراد شفرة X-57 المشتقة وتوليدها. قبول تجميع المروحة من المستخدم مؤجل، والمطابقة الخارجية لسطح NASA غير متحققة.

## بدء وإيقاف البرنامج

من مجلد المستودع `bladegen` شغّل:

```bash
./scripts/start_level1_trial.sh
```

يجب أن ترى:

- `BladeGen profile: level1-trial`
- `Worker timeout: 900 seconds per design`
- `Generation runtime: READY`
- الواجهة: `http://127.0.0.1:5175`
- الخلفية: `http://127.0.0.1:8012`

افتح `http://127.0.0.1:5175` في المتصفح. للإيقاف اضغط `Ctrl+C` مرة واحدة في الطرفية؛ السكربت يوقف فقط عمليتي الخلفية والواجهة اللتين بدأهما.

الحد 900 ثانية هو حد أقصى لكل عملية توليد في ملف التشغيل `level1-trial`. الإعداد العادي ما زال 300 ثانية. لا تحتاج إلى إعادة بناء OpenVSP أو تعديل Python/C++ أو ضبط متغيرات مخفية.

## ملفات التجربة

لإعادة تشغيل **نفس الشفرة التي نجح فيها المستخدم** بعد تنظيف المستودع، افتح من زر `Open JSON` الملف
`fixtures/reference_user_x57/blade_spec_X57.json` ثم اضغط `Generate Blade` مرة واحدة.
مرجع هذه الحالة Job `3970dc6383f1425b9726d5a9a00f4202`، وملفا التحقق والمحرك الأصليان في المجلد نفسه.
هذا يختلف عن خطوات استيراد CSV أدناه: تلك الخطوات تشرح تأليف المدخلات، أما فتح JSON فيعيد تعريف المستخدم نفسه بلا إعادة كتابة يدوية.
راجع [حدود Level 1A](../releases/level1a/SCOPE_AND_STATUS.md) و[خريطة قراءة الكود](../developer/CODE_MAP_AR.md).

- مجلد الإدخالات: `qualification/fp02_c1/trial_inputs/`
- الحزمة: `qualification/fp02_c1/FP02_C1_LEVEL1_TRIAL_INPUTS.zip`
- الشفرة البسيطة: `trial_inputs/simple/FP02_C1_Q01_simple_blade.json`
- تعديل الالتواء: `trial_inputs/simple/FP02_C1_Q01_twist_edit.json`
- حالة PCHIP والحافة الخلفية: `trial_inputs/simple/FP02_C1_Q02_pchip_finite_te.json`
- حالة Reverse المنقحة: `trial_inputs/simple/FP02_C1_Q04_R1_reverse_imported.json`
- المروحة الثنائية: `trial_inputs/simple/FP02_C1_Q06_two_blade_propeller.json`
- ملف X-57 الهوائي: `trial_inputs/x57/x57_hlp_airfoil.csv`
- توزيعات X-57 الفيزيائية: `trial_inputs/x57/x57_hlp_control_points_mm.csv`
- فحوص X-57: `trial_inputs/x57/SHA256SUMS.txt`

للتحقق من ملفات X-57:

```bash
cd qualification/fp02_c1/trial_inputs/x57
sha256sum --check SHA256SUMS.txt
```

يجب أن تكون كل النتائج `OK`.

## 1. إنشاء الشفرة البسيطة ثم تعديلها

1. اضغط `New` واختر `Single Blade`.
2. أدخل `Name` = `FP02_Q01_simple_three_station`، و`Diameter` = `400`، و`Root radius` = `0.25`، و`Reference axis` = `0.25`، و`Rotation` = `Normal`.
3. اضغط `Set Up Airfoil Stations`، واجعل `Total airfoil stations` = `3` و`Common station trailing edge` = `0`، ثم اضغط `Apply Once`.
4. حدد المحطات الثلاث، واضغط `Apply Profile to Selected Stations`، واختر `NACA 0012`، وفعّل `Use constant thickness for selected common profile`، ثم اضغط `Apply to 3 Selected Stations`.
5. اضغط `Import Distributions` واختر `FP02_Q01_distributions.csv`. تحقق من ظهور `3 rows`، واجعل Interpolation لكل من Chord/Twist/Rake/Skew/Thickness هو `Linear`، ثم اضغط `Apply Once`.
6. انتظر رسالة `Canonical design preview is current`. هذه الخطوة لا يجب أن تبدأ CAD تلقائياً.
7. اضغط `Generate Blade`. النتيجة المتوقعة: `Build complete` وروابط تخص Job الحالي: `blade_solid.step` و`blade_spec.json` و`validation.json` و`engine_manifest.json`.
8. اضغط `Export JSON` واحفظ المشروع. افتح الملف من حقل فتح JSON وتأكد من رسالة `Opened and validated` ومن بقاء القيم نفسها.
9. غيّر `Twist value 2` من `18` إلى `21`. يجب أن تظهر `Inputs changed — regenerate` و`Last successful build — previous inputs` من دون توليد تلقائي.
10. اضغط `Generate Blade` مرة ثانية. يجب أن يكون Job ID جديداً، وأن ينجح `validation.json`، وأن يقيس المقطع عند `r/R = 0.625` قرابة 21° بدلاً من 18°.

مرجع آلي نهائي ناجح: Job أول `02b8bbe2a0884537ba99056fb636d2c4`، وإعادة التوليد `25a4f94715d34faeb459cb9904694085`. قاس الاختبار فرق الالتواء `3.000000000002°`.

## 2. استيراد X-57 دفعة واحدة وتوليد الشفرة

1. ابدأ مشروعاً نظيفاً واختر `Single Blade`.
2. أدخل الاسم `X57_HLP_manual_test`، القطر `575.9200184294399` mm، `Root radius` = `0.20238`، `Reference axis` = `0.5`، و`Rotation` = `Normal`.
3. اضغط `Set Up Airfoil Stations`، واجعل العدد `2` وسمك الحافة الخلفية المشترك `0`، ثم `Apply Once`. لا تفعل خيارات الاستبدال أو الحفظ الإضافية.
4. حدد المحطتين واضغط `Apply Profile to Selected Stations`.
5. في `Airfoil coordinate file` اختر `x57_hlp_airfoil.csv`. اترك خيار `Explicitly normalize using LE and mean TE chord` غير مفعّل، واضغط `Import and Preview`، ثم فعّل السماكة الثابتة واضغط `Apply to 2 Selected Stations`.
6. اضغط `Import Distributions` واختر `x57_hlp_control_points_mm.csv`. تحقق من `40 rows` ومن Diameter snapshot `575.9200184294399 mm`، وأن Interpolation هو `PCHIP` لكل Chord/Twist/Rake/Skew، ثم `Apply Once` مرة واحدة.
7. انتظر `Canonical design preview is current`. Apply يجب أن يحدّث المعاينة فقط ولا يولد CAD.
8. اضغط `Export JSON` واحتفظ بالمرشح، ثم اضغط `Generate Blade` مرة واحدة.
9. النتيجة المتوقعة في البيئة المقاسة: 41/41 محطة، Solid واحد، Shell واحدة مغلقة، صفر free edges، وBRep valid. العملية النهائية استغرقت 381.7 ثانية ضمن حد 900 ثانية.
10. نزّل ملفات Job نفسه: `blade_solid.step` و`blade_spec.json` و`validation.json` و`engine_manifest.json`.

الـ STEP الناتج من اختبار المتصفح النهائي موجود منفصلاً في `qualification/fp02_c1/artifacts/x57_hlp_final_browser.step`، وSHA-256 له:

`a50dfbff9da673bdabde10b48b33d5dbbf89b66b3435788b55c690d507cb5974`

هذا نجاح داخلي لإدخالات وهندسة CAD، وليس إثبات مطابقة سطح خارجي رسمي من NASA؛ المطابقة الخارجية ما زالت `UNVERIFIED`.

## 3. إنشاء مروحة بسيطة مدعومة

هذه تجربة مروحة ثنائية بسيطة، وليست إعادة إنتاج لمروحة NASA ذات خمس شفرات.

1. افتح `FP02_C1_Q06_two_blade_propeller.json` من حقل JSON.
2. تحقق من تفعيل `Full Propeller` ومن `Number of Blades` = `2`.
3. القيم المجمدة هي Hub قطره 90 mm وطوله 45 mm وثقب Shaft قطره 12 mm.
4. اضغط `Generate Propeller`.
5. النتيجة المتوقعة: `Build complete`، شفرتان مطلوبتان وشفرتان موضوعتان، Solid واحد مغلق وBRep valid بعد إعادة استيراد STEP.

مرجع آلي نهائي ناجح: Job `991f7d2e1b4c41e98e8169d7a9ae5b99`، زمن العامل 78.2 ثانية.

## 4. فحص حالتي الإغلاق Q02 وQ04.R1

1. افتح `FP02_C1_Q02_pchip_finite_te.json` واضغط `Generate Blade`. المتوقع PASS في 11/11 مقطعاً.
2. افتح `FP02_C1_Q04_R1_reverse_imported.json`. تحقق من `Rotation = Reverse` ومن وجود 8 محطات، ثم اضغط `Generate Blade`. المتوقع PASS في 26/26 مقطعاً.
3. لا تستخدم Q04 الأصلي كتجربة إيجابية؛ رفضه بسبب تعارض السماكة سلوك صحيح ومختبر.

مرجع المتصفح النهائي: Q02 Job `36f5f839a8e84340894fbd7f96d3828b`، وQ04.R1 Job `8d86b5cb2c3742b188ffa3dfddc8dc07`.

## عند حدوث مشكلة

- لا ترفع الحد فوق 900 ثانية ولا تغيّر السماحات أو بيانات X-57 للحصول على PASS.
- احتفظ بـ Job ID ورسالة الخطأ و`validation.json` و`engine_manifest.json` وملفات stdout/stderr.
- إذا فشل Job جديد، فالمعاينة القديمة يجب أن تبقى معنونة كـ `previous` أو `stale` ولا تعتبر نتيجة للعملية الفاشلة.
- بعد أي تغيير في كود/Runtime، أعد تشغيل `./scripts/start_level1_trial.sh` حتى يعيد فحص Runtime قبل التوليد.
- تقرير الإغلاق: `docs/sprints/FP02-C1/FP02_C1_REPORT.md`. مصفوفة القبول المنقحة: `docs/sprints/FP02-C1/FP02_C1_ACCEPTANCE_MATRIX.md`.

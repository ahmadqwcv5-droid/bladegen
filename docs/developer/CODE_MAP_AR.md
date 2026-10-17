# خريطة قراءة الكود — BladeGen

هذه خريطة للشفرة الحالية، وليست وصفاً لإعادة تصميمها. اتبع مسار الشفرة الواحدة أولاً؛ مسار المروحة موجود ومستقل عن قرار قبول المستخدم له.

| المحطة | الملف والرمز الحقيقي | السؤال عند القراءة |
| --- | --- | --- |
| 1 | `frontend/src/App.tsx` و`frontend/src/components/DistributionImportDialog.tsx` (`DistributionImportDialog`) | كيف يتحول فتح JSON/استيراد CSV إلى تصميم محرَّر، ومتى يضغط المستخدم Generate؟ |
| 2 | `backend/bladegen/models/blade_spec.py` (`BladeSpec`) | ما العقد المحايد عن الواجهة وOpenVSP؟ ما الوحدات والقيود؟ |
| 3 | `backend/bladegen/curves/resolver.py` (`resolve_blade_spec`, `resolve_airfoil_sections`) | كيف تُحضَّر المنحنيات والمقاطع والإحداثيات الأصلية قبل CAD؟ |
| 4 | `backend/bladegen/pipeline.py` (`build`) ثم `backend/bladegen/adapters/openvsp_adapter.py` (`build_and_export`) | أين يبدأ التوليد، وكيف تُرسل المقاطع الثابتة إلى OpenVSP؟ |
| 5 | `backend/bladegen/solid/ocp_solidify.py` (`solidify_step`) و`backend/bladegen/validation/measure_sections.py` (`measure_sections`) و`backend/api/services/jobs.py` (`JobManager`) | كيف يصبح STEP صلباً، ثم يُقاس ويُعاد استيراده، وكيف تصل النتيجة والملفات إلى الواجهة؟ |

`/api/design-preview` يعطي معاينة تصميم سريعة؛ مجسم العرض STL مشتق من OCP، ولا يحل محل `blade_solid.step` النهائي. **التوليد** في `pipeline.build` ينشئ CAD، أما **التحقق** في مسار `validation` فيقيس الناتج بمرجع الإدخال وقواعد القبول. منطق BladeSpec/resolver/validation الهندسي في `backend/bladegen/` قابل للاستدعاء من CLI والويب؛ `backend/api/main.py` و`frontend/src/App.tsx` واجهتان له، لا مصدران جديدان للهندسة.

التعديل الأصلي الثابت للمقاطع في `vendor/openvsp_fixed_plane/` مطلوب لأن بناء X-57 المؤهَّل يحتاج مواقع المقاطع الشعاعية المحددة دون دوران أضلاع OpenVSP التلقائي. مدير التشغيل في `backend/bladegen/runtime/manager.py` يختار النسخة المقيّدة ويتحقق من بصمتها؛ تعليمات التشغيل في [FIXED_PLANE_RUNTIME.md](FIXED_PLANE_RUNTIME.md). لا تُعدِّل النسخة المثبتة داخل `.tooling/` يدوياً.

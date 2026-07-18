# Hawaa Design System Guide

## الاستخدام

```python
from views.ui_kit import (
    page_header, data_card, primary_button, secondary_button,
    modern_field, PRIMARY, SUCCESS, DANGER, WARNING,
)
```

للشاشات الجديدة يفضّل الاستيراد المباشر من:

```python
from views.design_system.components import primary_action, metric_card
from views.design_system.responsive import responsive_grid, form_factor
from views.design_system.tokens import SPACE_4, RADIUS_CARD
```

## القواعد

1. لا تستخدم ألوانًا مباشرة للهوية؛ استخدم الرموز الدلالية.
2. الأخضر للنجاح/لنا، الأحمر للخطر، الكهرماني للانتظار، والأزرق للهوية والمعلومات.
3. لا تستخدم AlertDialog لنموذج يتجاوز ستة حقول.
4. لا تنشئ Scroll داخل Scroll.
5. استخدم `responsive_grid()` لبطاقات المؤشرات.
6. حافظ على أزرار اللمس بارتفاع 48 على الأقل.
7. استخدم `data_card()` و`page_header()` بدل بناء بطاقات وعناوين محلية.
8. يجب أن تبقى مبالغ العملات في سطر واحد باستخدام `money_text()`.

## النماذج المحاسبية المتدرجة — Phase 101

عند تجاوز النموذج ستة حقول أو احتوائه على أكثر من طرف مالي، استخدم:

```python
from views.design_system.workflow import (
    WorkflowController, WorkflowStep, adaptive_dialog_metrics,
    section_card, financial_summary, review_row,
)
```

قواعد التدفق:

1. قسّم النموذج حسب قرار المستخدم، لا حسب ترتيب أعمدة قاعدة البيانات.
2. تحقق من كل خطوة قبل الانتقال إلى التالية.
3. يجب أن تكون الخطوة الأخيرة «مراجعة وحفظ» وتعرض الأثر المالي المتوقع.
4. لا تُجرى كتابة قاعدة البيانات أثناء التنقل بين الخطوات.
5. زر الحفظ يظهر في الخطوة الأخيرة فقط.
6. على الهاتف يشغل التدفق معظم مساحة الشاشة، وعلى التابلت/سطح المكتب يبقى ضمن عرض مقروء.
7. لا تغير الـ Payload أو عقود المستودعات عند إعادة تصميم العرض.

# -*- coding: utf-8 -*-
from __future__ import annotations

COMMON_WEAK = {
    '123456', '12345678', 'password', 'admin', 'admin123', 'qwerty',
    '111111', '000000', 'hawaa', 'hawaa123', 'هوى', 'هوىالشام'
}


def evaluate_password(password: str) -> dict:
    pwd = password or ''
    score = 0
    problems = []
    if len(pwd) >= 8:
        score += 1
    else:
        problems.append('ثمانية أحرف على الأقل')
    if any(c.islower() for c in pwd) and any(c.isupper() for c in pwd):
        score += 1
    else:
        problems.append('أحرف كبيرة وصغيرة')
    if any(c.isdigit() for c in pwd):
        score += 1
    else:
        problems.append('رقم واحد على الأقل')
    if any(not c.isalnum() for c in pwd):
        score += 1
    else:
        problems.append('رمز خاص مثل @ أو #')
    if pwd.strip().lower() not in COMMON_WEAK and len(set(pwd)) >= 4:
        score += 1
    else:
        problems.append('تجنب كلمة مرور شائعة أو متكررة')
    label = 'ضعيفة'
    if score >= 4:
        label = 'قوية'
    elif score >= 3:
        label = 'متوسطة'
    return {'score': score, 'label': label, 'problems': problems, 'ok': score >= 3}

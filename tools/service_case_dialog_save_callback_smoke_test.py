# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / 'views' / 'dialogs' / 'service_case_dialog.py').read_text(encoding='utf-8')

assert 'self.error_box' in text, 'Service case dialog must show inline errors; snackbar alone can be hidden behind Android dialog surfaces.'
assert 'run_async_task(self._page, self._save_async, payload)' in text, 'Service case save must be scheduled non-blocking.'
assert 'async def _save_async' in text, 'Service case dialog must have async save path.'
assert 'asyncio.to_thread' in text, 'Repository/network write must run off the Flet event callback.'
assert 'validate_service_case_payload(payload)' in text, 'Dialog must validate before scheduling save.'
print('service_case_dialog_save_callback_smoke_test passed')

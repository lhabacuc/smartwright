from __future__ import annotations

import hashlib

from smartwright.core.store import KnowledgeStore


class FingerprintTracker:
    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store

    async def detect_change(self, page: object, page_key: str) -> bool:
        dom = await page.content()
        dom_hash = hashlib.md5(dom.encode("utf-8")).hexdigest()
        previous = self.store.get_fingerprint(page_key)
        self.store.save_fingerprint(page_key, dom_hash)
        return previous is not None and previous != dom_hash

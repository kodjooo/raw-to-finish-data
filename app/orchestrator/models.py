from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class SourceRow:
    row_index: int
    product_id: str
    product_content: str
    category: str
    image_path: Optional[str]
    claim_token: Optional[str]
    raw_values: Dict[str, Any]

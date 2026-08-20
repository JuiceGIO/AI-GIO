"""报销单存储层（Day9：先用 JSON 文件，Day12 换数据库）"""
import json
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "expense_forms.json"


class DuplicateInvoiceError(Exception):
    """发票号重复"""


def _load() -> list:
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _save(forms: list) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(forms, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def create_form(data: dict) -> dict:
    """创建报销单；发票号重复抛 DuplicateInvoiceError"""
    forms = _load()
    if any(f["invoice_no"] == data["invoice_no"] for f in forms):
        raise DuplicateInvoiceError(data["invoice_no"])

    form = {
        "id": max((f["id"] for f in forms), default=0) + 1,
        **data,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    forms.append(form)
    _save(forms)
    return form


def list_forms() -> list:
    return _load()
# ui/mappers.py
from domain.models import Occurrence
from domain.status_service import StatusService
from utils.datetime_helpers import format_display_datetime

def occ_to_row_vm(status: StatusService, name: str, status_key: str, occ: Occurrence):
    return {
        "id": occ.base_item_id,
        "type": occ.item_type,
        "name": name,
        "status_display": status.get_display_name(status_key),
        "start_local": format_display_datetime(occ.start_utc) if occ.start_utc else "",
        "end_local": format_display_datetime(occ.end_utc) if occ.end_utc else "",
        "due_local": format_display_datetime(occ.due_utc) if occ.due_utc and occ.item_type == 'task' else "",
        "is_all_day": occ.is_all_day,
    }

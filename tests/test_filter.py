from services.filter_service import filter_items
from domain.models import Task

def test_filter_text_and_type():
    items = [
        Task(id="1", type="task", name="Report fertig", status="TASK_OPEN", is_private=False),
        Task(id="2", type="task", name="Meeting vorbereiten", status="TASK_OPEN", is_private=False),
    ]
    out = filter_items(items, text="report", types=["task"])
    assert [x.id for x in out] == ["1"]

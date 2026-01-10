#!/usr/bin/env python3
"""
Test der Sortierungslogik für TaskManager V2
"""

from datetime import datetime, timezone, timedelta
import sys
sys.path.append('.')

def _aware(dt):
    return dt if dt and dt.tzinfo else (dt.replace(tzinfo=timezone.utc) if dt else datetime.max.replace(tzinfo=timezone.utc))

def sort_key_time(it):
    if getattr(it, "type", "") in ("appointment","event"):
        # Für appointments/events würde normalerweise next_or_display_occurrence aufgerufen
        # Hier vereinfacht nur start_utc/end_utc verwenden
        start = getattr(it, "start_utc", None)
        end = getattr(it, "end_utc", None)
        return _aware(start or end or datetime.max)
    else:
        return _aware(getattr(it, "due_utc", None) or getattr(it, "reminder_utc", None) or datetime.max)

class TestItem:
    def __init__(self, type, due_utc=None, start_utc=None, reminder_utc=None, name='Test'):
        self.type = type
        self.due_utc = due_utc
        self.start_utc = start_utc
        self.reminder_utc = reminder_utc
        self.name = name

def test_sorting():
    print("=== Test der chronologischen Sortierung ===")
    
    # Test 1: Tasks mit due_utc
    print("\n1. Test: Tasks mit due_utc (sollten 10:00 → 12:00 → 14:00 sortiert werden)")
    tasks = [
        TestItem('task', due_utc=datetime(2026, 1, 7, 14, 0, tzinfo=timezone.utc), name='Task 14:00'),
        TestItem('task', due_utc=datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc), name='Task 10:00'),
        TestItem('task', due_utc=datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc), name='Task 12:00'),
    ]

    print("Vor Sortierung:")
    for item in tasks:
        print(f"  {item.name}: {item.due_utc}")

    tasks.sort(key=sort_key_time)
    print("Nach Sortierung:")
    for item in tasks:
        print(f"  {item.name}: {item.due_utc}")
        
    # Test 2: Appointments mit start_utc  
    print("\n2. Test: Appointments mit start_utc (sollten 09:00 → 11:00 → 15:00 sortiert werden)")
    appointments = [
        TestItem('appointment', start_utc=datetime(2026, 1, 7, 15, 0, tzinfo=timezone.utc), name='Termin 15:00'),
        TestItem('appointment', start_utc=datetime(2026, 1, 7, 9, 0, tzinfo=timezone.utc), name='Termin 09:00'),
        TestItem('appointment', start_utc=datetime(2026, 1, 7, 11, 0, tzinfo=timezone.utc), name='Termin 11:00'),
    ]

    print("Vor Sortierung:")
    for item in appointments:
        print(f"  {item.name}: {item.start_utc}")

    appointments.sort(key=sort_key_time)
    print("Nach Sortierung:")
    for item in appointments:
        print(f"  {item.name}: {item.start_utc}")
        
    # Test 3: Gemischte Items
    print("\n3. Test: Gemischte Items (Tasks und Appointments)")
    mixed = [
        TestItem('task', due_utc=datetime(2026, 1, 7, 13, 0, tzinfo=timezone.utc), name='Task 13:00'),
        TestItem('appointment', start_utc=datetime(2026, 1, 7, 8, 0, tzinfo=timezone.utc), name='Termin 08:00'),
        TestItem('reminder', reminder_utc=datetime(2026, 1, 7, 16, 0, tzinfo=timezone.utc), name='Reminder 16:00'),
        TestItem('task', due_utc=datetime(2026, 1, 7, 11, 30, tzinfo=timezone.utc), name='Task 11:30'),
    ]

    print("Vor Sortierung:")
    for item in mixed:
        dt = item.due_utc or item.start_utc or item.reminder_utc
        print(f"  {item.name} ({item.type}): {dt}")

    mixed.sort(key=sort_key_time)
    print("Nach Sortierung (chronologisch aufsteigend):")
    for item in mixed:
        dt = item.due_utc or item.start_utc or item.reminder_utc
        print(f"  {item.name} ({item.type}): {dt}")

if __name__ == "__main__":
    test_sorting()

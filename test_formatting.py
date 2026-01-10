# Test der Zeitformatierungs-Funktionen
from datetime import datetime
import pytz
from web.routers.main import format_dashboard_time, format_local, format_local_weekday_de, format_local_short_weekday_de

# Test-Zeitpunkt
test_dt = datetime(2026, 1, 10, 15, 30, 0, tzinfo=pytz.UTC)
berlin_tz = pytz.timezone('Europe/Berlin')

print('=== Test der Zeitformatierungs-Funktionen ===')
print(f'Test-Zeit (UTC): {test_dt}')
print(f'Test-Zeit (Berlin): {test_dt.astimezone(berlin_tz)}')
print()

# Teste verschiedene Kontexte
contexts = ['series', 'next_events', 'calendar', 'today', 'next_48h', 'next_7_days', 'overdue', 'no_date']

for context in contexts:
    result = format_dashboard_time(test_dt, context, berlin_tz)
    print(f'{context:12}: {result}')

print()
print('=== Test der Wochentags-Funktionen ===')
print(f'Wochentag (lang): {format_local_weekday_de(test_dt)}')
print(f'Wochentag (kurz): {format_local_short_weekday_de(test_dt)}')
print()
print(f'Format local:     {format_local(test_dt)}')
print(f'Format local D:   {format_local(test_dt, "%d.%m.%Y")}')
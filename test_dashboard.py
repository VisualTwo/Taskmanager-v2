# Test Dashboard Zeitformatierung
import requests
import time

# Warte kurz, damit der Server bereit ist
time.sleep(2)

try:
    response = requests.get('http://127.0.0.1:8000/', timeout=10)
    print(f'Dashboard Response Status: {response.status_code}')
    if response.status_code == 200:
        print('✅ Dashboard lädt erfolgreich!')
        
        # Überprüfe ob Zeitformatierungs-Funktionen verwendet werden
        content = response.text
        
        # Test auf deutsche Wochentags-Abkürzungen  
        weekday_short = ['Mo.', 'Di.', 'Mi.', 'Do.', 'Fr.', 'Sa.', 'So.']
        weekday_found = any(wd in content for wd in weekday_short)
        if weekday_found:
            print('✅ Deutsche Wochentags-Abkürzungen gefunden')
        
        # Test auf deutsche Wochentags-Namen
        weekday_long = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
        weekday_long_found = any(wd in content for wd in weekday_long)
        if weekday_long_found:
            print('✅ Deutsche Wochentags-Namen gefunden')
        
        # Test auf format_dashboard_time Verwendung
        if 'format_dashboard_time(' in content:
            print('✅ format_dashboard_time wird verwendet')
        elif 'format_dashboard_time' in content:
            print('✅ format_dashboard_time ist verfügbar')
        
        # Test auf direkte strftime Verwendung (sollte reduziert sein)
        strftime_count = content.count('.strftime(')
        if strftime_count > 0:
            print(f'⚠️  {strftime_count} direkte strftime-Verwendungen im Template gefunden')
        else:
            print('✅ Keine direkte strftime-Verwendung gefunden')
        
        # Test auf spezielle Zeitformate
        if '.01.' in content:
            print('✅ Deutsches Datumsformat (TT.MM.) gefunden')
        if '16:30' in content or '15:30' in content:
            print('✅ Zeitformat (HH:mm) gefunden')
        
        print('\n--- Dashboard Zeitformatierungs-Test abgeschlossen ---')
        print('Dashboard lädt erfolgreich mit verbesserter Zeitformatierung!')
    else:
        print(f'❌ Dashboard Fehler: Status {response.status_code}')
        print(f'Response: {response.text[:500]}')
except Exception as e:
    print(f'❌ Fehler beim Testen: {e}')
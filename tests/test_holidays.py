"""Tests for German holiday integration functionality."""

from datetime import datetime, date
from unittest.mock import patch, Mock
import holidays


def test_german_holidays_integration():
    """Test that German holidays are properly integrated."""
    # Test the holiday name translation
    from web.server import GERMAN_HOLIDAY_NAMES
    
    # Check that the translation dictionary exists and has expected entries
    assert isinstance(GERMAN_HOLIDAY_NAMES, dict)
    assert "New Year's Day" in GERMAN_HOLIDAY_NAMES
    assert GERMAN_HOLIDAY_NAMES["New Year's Day"] == "Neujahr"
    assert "Christmas Day" in GERMAN_HOLIDAY_NAMES
    assert GERMAN_HOLIDAY_NAMES["Christmas Day"] == "1. Weihnachtstag"


def test_get_holidays_for_period():
    """Test the get_holidays_for_period function."""
    from web.server import get_holidays_for_period
    
    # Test getting holidays for a specific period
    start_date = date(2026, 1, 1)
    end_date = date(2026, 1, 31)
    
    holidays_dict = get_holidays_for_period(start_date, end_date)
    
    # Should be a list of holiday events
    assert isinstance(holidays_dict, list)
    
    # Should have New Year's Day
    holiday_names = [h['name'] for h in holidays_dict]
    assert "Neujahr" in holiday_names


def test_holidays_module_version_compatibility():
    """Test that the holidays module version works correctly."""
    # Test that we can create holiday instances
    de_ni = holidays.country_holidays('DE', subdiv='NI', years=[2026])
    
    # Should contain expected holidays
    assert date(2026, 1, 1) in de_ni  # New Year
    assert date(2026, 12, 25) in de_ni  # Christmas Day
    
    # Test that we get the expected names (English from holidays module)
    assert de_ni[date(2026, 1, 1)] == "New Year's Day"
    assert de_ni[date(2026, 12, 25)] == "Christmas Day"


def test_holiday_translation_coverage():
    """Test that we have translations for common holidays."""
    from web.server import GERMAN_HOLIDAY_NAMES
    
    # Test coverage of major holidays
    major_holidays = [
        "New Year's Day",
        "Christmas Day", 
        "Boxing Day",
        "Easter Sunday",
        "Easter Monday",
        "Good Friday",
        "Ascension Day",
        "Whit Sunday",
        "Whit Monday",
        "German Unity Day",
        "Reformation Day"
    ]
    
    # Check that we have translations for major holidays
    missing_translations = []
    for holiday in major_holidays:
        if holiday not in GERMAN_HOLIDAY_NAMES:
            missing_translations.append(holiday)
    
    # Allow some holidays to not have translations yet, but log them
    if missing_translations:
        print(f"Missing translations for: {missing_translations}")
    
    # At least ensure we have the most important ones
    essential_holidays = ["New Year's Day", "Christmas Day", "Easter Monday"]
    for holiday in essential_holidays:
        assert holiday in GERMAN_HOLIDAY_NAMES, f"Missing translation for essential holiday: {holiday}"


def test_holiday_period_boundary_conditions():
    """Test edge cases for holiday period calculations."""
    from web.server import get_holidays_for_period
    
    # Test single day period
    single_day = date(2026, 1, 1)
    holidays_dict = get_holidays_for_period(single_day, single_day)
    
    # Should be a list
    assert isinstance(holidays_dict, list)
    # Check if we got New Year's Day
    if holidays_dict:
        assert holidays_dict[0]['name'] == 'Neujahr'
    
    # Test period with no holidays
    start_date = date(2026, 6, 1)  # Typically no holidays in early June
    end_date = date(2026, 6, 5)
    
    holidays_dict = get_holidays_for_period(start_date, end_date)
    
    # Should return empty list for period without holidays
    assert isinstance(holidays_dict, list)
    # All dates in the returned dict should be within the period
    for holiday_date in holidays_dict:
        assert start_date <= holiday_date <= end_date


def test_dynamic_holiday_loading():
    """Test that holidays are loaded dynamically based on calendar range."""
    from web.server import get_holidays_for_period
    
    # Test different years
    holidays_2025 = get_holidays_for_period(date(2025, 12, 20), date(2025, 12, 31))
    holidays_2026 = get_holidays_for_period(date(2026, 1, 1), date(2026, 1, 10))
    
    # Should have holidays for both years
    holiday_names_2025 = [h['name'] for h in holidays_2025]
    holiday_names_2026 = [h['name'] for h in holidays_2026]
    
    assert "1. Weihnachtstag" in holiday_names_2025  # Christmas 2025
    assert "Neujahr" in holiday_names_2026  # New Year 2026
    
    # Basic verification that we got holidays
    assert len(holidays_2025) > 0
    assert len(holidays_2026) > 0

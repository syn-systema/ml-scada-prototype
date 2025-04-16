"""
Unit tests for the unit conversion module.
"""

import unittest
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path to import the app modules
sys.path.append(str(Path(__file__).parent.parent))

from app.utils.unit_conversion import (
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    bar_to_psi,
    psi_to_bar,
    cubic_meters_per_hour_to_mcf_per_day,
    mcf_per_day_to_cubic_meters_per_hour,
    convert_value,
    get_unit_system,
    get_equivalent_unit,
    UnitSystem
)

class TestUnitConversion(unittest.TestCase):
    """Test cases for unit conversion functions."""
    
    def test_temperature_conversion(self):
        """Test temperature conversion functions."""
        # Test Celsius to Fahrenheit
        self.assertAlmostEqual(celsius_to_fahrenheit(0), 32.0, places=2)
        self.assertAlmostEqual(celsius_to_fahrenheit(100), 212.0, places=2)
        self.assertAlmostEqual(celsius_to_fahrenheit(20), 68.0, places=2)
        
        # Test Fahrenheit to Celsius
        self.assertAlmostEqual(fahrenheit_to_celsius(32), 0.0, places=2)
        self.assertAlmostEqual(fahrenheit_to_celsius(212), 100.0, places=2)
        self.assertAlmostEqual(fahrenheit_to_celsius(68), 20.0, places=2)
        
        # Test round-trip conversion
        original_temp = 25.0
        converted_temp = fahrenheit_to_celsius(celsius_to_fahrenheit(original_temp))
        self.assertAlmostEqual(converted_temp, original_temp, places=2)
    
    def test_pressure_conversion(self):
        """Test pressure conversion functions."""
        # Test bar to PSI
        self.assertAlmostEqual(bar_to_psi(1), 14.5038, places=2)
        self.assertAlmostEqual(bar_to_psi(2), 29.0076, places=2)
        
        # Test PSI to bar
        self.assertAlmostEqual(psi_to_bar(14.5038), 1.0, places=2)
        self.assertAlmostEqual(psi_to_bar(29.0076), 2.0, places=2)
        
        # Test round-trip conversion
        original_pressure = 3.5
        converted_pressure = psi_to_bar(bar_to_psi(original_pressure))
        self.assertAlmostEqual(converted_pressure, original_pressure, places=2)
    
    def test_flow_conversion(self):
        """Test flow rate conversion functions."""
        # Test cubic meters per hour to MCF per day
        # 1 m³/h ≈ 0.847552 MCF/day
        self.assertAlmostEqual(cubic_meters_per_hour_to_mcf_per_day(1), 0.847552, places=2)
        self.assertAlmostEqual(cubic_meters_per_hour_to_mcf_per_day(10), 8.47552, places=2)
        
        # Test MCF per day to cubic meters per hour
        # 1 MCF/day ≈ 1.1798 m³/h
        self.assertAlmostEqual(mcf_per_day_to_cubic_meters_per_hour(1), 1.1798, places=2)
        self.assertAlmostEqual(mcf_per_day_to_cubic_meters_per_hour(10), 11.798, places=2)
        
        # Test round-trip conversion
        original_flow = 5.0
        converted_flow = mcf_per_day_to_cubic_meters_per_hour(cubic_meters_per_hour_to_mcf_per_day(original_flow))
        self.assertAlmostEqual(converted_flow, original_flow, places=2)
    
    def test_convert_value(self):
        """Test the convert_value function."""
        # Test temperature conversion
        self.assertAlmostEqual(convert_value(20, "°C", "°F"), 68.0, places=2)
        self.assertAlmostEqual(convert_value(68, "°F", "°C"), 20.0, places=2)
        
        # Test pressure conversion
        self.assertAlmostEqual(convert_value(1, "bar", "PSI"), 14.5038, places=2)
        self.assertAlmostEqual(convert_value(14.5038, "PSI", "bar"), 1.0, places=2)
        
        # Test flow rate conversion
        self.assertAlmostEqual(convert_value(1, "m3/h", "MCF/day"), 0.847552, places=2)
        self.assertAlmostEqual(convert_value(1, "MCF/day", "m3/h"), 1.1798, places=2)
        
        # Test same unit (no conversion)
        self.assertEqual(convert_value(10, "PSI", "PSI"), 10)
        
        # Test unsupported conversion
        with self.assertRaises(ValueError):
            convert_value(10, "PSI", "mm/s")
    
    def test_get_unit_system(self):
        """Test the get_unit_system function."""
        # Test metric units
        self.assertEqual(get_unit_system("°C"), UnitSystem.METRIC)
        self.assertEqual(get_unit_system("bar"), UnitSystem.METRIC)
        self.assertEqual(get_unit_system("m3/h"), UnitSystem.METRIC)
        self.assertEqual(get_unit_system("mm/s"), UnitSystem.METRIC)
        
        # Test imperial units
        self.assertEqual(get_unit_system("°F"), UnitSystem.IMPERIAL)
        self.assertEqual(get_unit_system("PSI"), UnitSystem.IMPERIAL)
        self.assertEqual(get_unit_system("MCF/day"), UnitSystem.IMPERIAL)
        
        # Test unknown unit
        self.assertIsNone(get_unit_system("unknown"))
    
    def test_get_equivalent_unit(self):
        """Test the get_equivalent_unit function."""
        # Test metric to imperial
        self.assertEqual(get_equivalent_unit("°C", UnitSystem.IMPERIAL), "°F")
        self.assertEqual(get_equivalent_unit("bar", UnitSystem.IMPERIAL), "PSI")
        self.assertEqual(get_equivalent_unit("m3/h", UnitSystem.IMPERIAL), "MCF/day")
        
        # Test imperial to metric
        self.assertEqual(get_equivalent_unit("°F", UnitSystem.METRIC), "°C")
        self.assertEqual(get_equivalent_unit("PSI", UnitSystem.METRIC), "bar")
        self.assertEqual(get_equivalent_unit("MCF/day", UnitSystem.METRIC), "m3/h")
        
        # Test unknown unit
        self.assertIsNone(get_equivalent_unit("unknown", UnitSystem.METRIC))
        
        # Test no equivalent in target system
        self.assertIsNone(get_equivalent_unit("mm/s", UnitSystem.IMPERIAL))

if __name__ == "__main__":
    unittest.main()

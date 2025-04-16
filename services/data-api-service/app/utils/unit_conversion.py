"""
Unit conversion utilities for the Data API Service.
Handles conversions between different unit systems for oil and gas industry measurements.
"""

from enum import Enum
from typing import Dict, Tuple, Optional, Union, Callable
import logging

# Configure logging
logger = logging.getLogger("data-api-service.unit_conversion")

class UnitSystem(Enum):
    """Enum for different unit systems."""
    METRIC = "metric"
    IMPERIAL = "imperial"

# Conversion functions
def celsius_to_fahrenheit(value: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return (value * 9/5) + 32

def fahrenheit_to_celsius(value: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (value - 32) * 5/9

def bar_to_psi(value: float) -> float:
    """Convert bar to PSI."""
    return value * 14.5038

def psi_to_bar(value: float) -> float:
    """Convert PSI to bar."""
    return value / 14.5038

def cubic_meters_per_hour_to_mcf_per_day(value: float) -> float:
    """Convert cubic meters per hour to thousand cubic feet per day."""
    # 1 cubic meter = 35.3147 cubic feet
    # Convert m³/h to ft³/h, then to ft³/day, then to MCF/day
    return value * 35.3147 * 24 / 1000

def mcf_per_day_to_cubic_meters_per_hour(value: float) -> float:
    """Convert thousand cubic feet per day to cubic meters per hour."""
    # 1 cubic foot = 0.0283168 cubic meters
    # Convert MCF/day to ft³/day, then to ft³/h, then to m³/h
    return value * 1000 * 0.0283168 / 24

# Unit conversion mapping
UNIT_CONVERSIONS = {
    # Temperature conversions
    ("°C", "°F"): celsius_to_fahrenheit,
    ("°F", "°C"): fahrenheit_to_celsius,
    
    # Pressure conversions
    ("bar", "PSI"): bar_to_psi,
    ("PSI", "bar"): psi_to_bar,
    
    # Flow rate conversions
    ("m3/h", "MCF/day"): cubic_meters_per_hour_to_mcf_per_day,
    ("MCF/day", "m3/h"): mcf_per_day_to_cubic_meters_per_hour,
}

def convert_value(value: float, from_unit: str, to_unit: str) -> float:
    """
    Convert a value from one unit to another.
    
    Args:
        value: The value to convert
        from_unit: The source unit
        to_unit: The target unit
        
    Returns:
        The converted value
        
    Raises:
        ValueError: If the conversion is not supported
    """
    if from_unit == to_unit:
        return value
    
    conversion_key = (from_unit, to_unit)
    if conversion_key not in UNIT_CONVERSIONS:
        raise ValueError(f"Conversion from {from_unit} to {to_unit} is not supported")
    
    conversion_func = UNIT_CONVERSIONS[conversion_key]
    return conversion_func(value)

def get_unit_system(unit: str) -> Optional[UnitSystem]:
    """
    Determine the unit system for a given unit.
    
    Args:
        unit: The unit string
        
    Returns:
        The unit system (METRIC or IMPERIAL) or None if unknown
    """
    metric_units = {"°C", "bar", "m3/h", "mm/s"}
    imperial_units = {"°F", "PSI", "MCF/day"}
    
    if unit in metric_units:
        return UnitSystem.METRIC
    elif unit in imperial_units:
        return UnitSystem.IMPERIAL
    else:
        return None

def get_equivalent_unit(unit: str, target_system: UnitSystem) -> Optional[str]:
    """
    Get the equivalent unit in the target unit system.
    
    Args:
        unit: The source unit
        target_system: The target unit system
        
    Returns:
        The equivalent unit in the target system, or None if not found
    """
    unit_mappings = {
        "°C": "°F",
        "°F": "°C",
        "bar": "PSI",
        "PSI": "bar",
        "m3/h": "MCF/day",
        "MCF/day": "m3/h"
    }
    
    if unit not in unit_mappings:
        return None
    
    equivalent_unit = unit_mappings[unit]
    equivalent_system = get_unit_system(equivalent_unit)
    
    if equivalent_system == target_system:
        return equivalent_unit
    else:
        return None

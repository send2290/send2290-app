"""Vehicle and tax calculation utilities"""

def group_vehicles_by_month(vehicles):
    """Group vehicles by their used month"""
    vehicles_by_month = {}
    for vehicle in vehicles:
        month = vehicle.get('used_month', '202507')  # Default to July 2025
        if month not in vehicles_by_month:
            vehicles_by_month[month] = []
        vehicles_by_month[month].append(vehicle)
    return vehicles_by_month

def calculate_vehicle_statistics(vehicles):
    """Calculate vehicle statistics for form fields"""
    total_reported = len(vehicles)
    total_suspended = len([v for v in vehicles if v.get("category") == "W"])
    total_taxable = total_reported - total_suspended
    
    # Count by logging status
    total_logging = len([v for v in vehicles if v.get("is_logging", False)])
    total_regular = total_reported - total_logging
    
    return {
        "total_reported_vehicles": str(total_reported),
        "total_suspended_vehicles": str(total_suspended),
        "total_taxable_vehicles": str(total_taxable),
        "total_logging_vehicles": str(total_logging),
        "total_regular_vehicles": str(total_regular)
    }

def add_dynamic_vin_fields(data, vehicles):
    """Add dynamic VIN fields to form data"""
    for i, vehicle in enumerate(vehicles, 1):
        if i <= 24:  # Support up to 24 VINs as defined in positions
            data[f"vin_{i}"] = vehicle.get("vin", "")
            data[f"vin_{i}_category"] = vehicle.get("category", "")

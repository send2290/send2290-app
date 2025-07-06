import { FormData, Vehicle, CategoryData, GrandTotals } from '../types/form';
import { weightCategories, loggingRates, partialPeriodTaxRegular, partialPeriodTaxLogging } from '../constants/formData';

export const validateBeforeSubmit = (
  formData: FormData, 
  totalTax: number, 
  captchaToken: string | null,
  totalDisposalCredits: number = 0
): string | null => {
  // CAPTCHA validation (skip on localhost for development)
  const isLocalhost = typeof window !== 'undefined' && 
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
  
  if (!isLocalhost && !captchaToken) {
    return 'Please complete the CAPTCHA verification';
  }
  
  if (!formData.business_name.trim()) return 'Business Name is required';
  if (!/^\d{2}-\d{7}$/.test(formData.ein)) return 'EIN must be 9 digits in format XX-XXXXXXX';
  
  // IRS Business Rule: EIN cannot be all 9s (R0000-021)
  const einDigitsOnly = formData.ein.replace(/-/g, '');
  if (einDigitsOnly === '999999999') return 'EIN cannot be all 9s';
  
  // Address length validation (IRS requirement: max 35 chars per line)
  if (formData.address.length > 35) return 'Address line 1 cannot exceed 35 characters';
  if (formData.address_line2 && formData.address_line2.length > 35) return 'Address line 2 cannot exceed 35 characters';
  
  // Business officer information validation
  if (!formData.officer_name.trim()) return 'Officer name is required for signing';
  if (!formData.officer_title.trim()) return 'Officer title is required (e.g., President, Owner, Manager)';
  if (!/^\d{3}-?\d{2}-?\d{4}$/.test(formData.officer_ssn)) return 'Officer SSN must be in format XXX-XX-XXXX or XXXXXXXXX';
  if (!/^\d{5}$/.test(formData.taxpayer_pin)) return 'Taxpayer PIN must be exactly 5 digits';
  
  // IRS Business Rule: Taxpayer PIN cannot be all zeros (R0000-031, R0000-084-01)
  if (formData.taxpayer_pin === '00000') return 'Taxpayer PIN cannot be all zeros';
  
  // Disposal credits validation (if provided)
  if (totalDisposalCredits < 0) return 'Disposal credits cannot be negative';
  
  // IRS Business Rule F2290-004-01: Credits cannot exceed total tax
  if (totalDisposalCredits > totalTax) return 'Disposal credits cannot exceed total tax amount';
  
  // IRS Business Rule: Disposal credits per month cannot exceed Line 4 tax for that month
  const monthlyTaxAndCredits = new Map<string, { tax: number, credits: number }>();
  
  // Group vehicles by month and calculate tax and credits per month
  formData.vehicles.forEach(vehicle => {
    if (!vehicle.used_month || !vehicle.category) return;
    
    const month = vehicle.used_month;
    if (!monthlyTaxAndCredits.has(month)) {
      monthlyTaxAndCredits.set(month, { tax: 0, credits: 0 });
    }
    
    const monthData = monthlyTaxAndCredits.get(month)!;
    
    // Calculate tax for this vehicle (only if not suspended/agricultural)
    if (vehicle.category !== 'W' && !vehicle.is_suspended && !vehicle.is_agricultural) {
      const catObj = weightCategories.find(w => w.value === vehicle.category);
      if (catObj) {
        const mon = parseInt(vehicle.used_month.slice(-2), 10) || 0;
        const isLogging = vehicle.is_logging;
        const isAnnualTax = mon === 7; // July = annual tax
        
        let taxAmount = 0;
        if (isAnnualTax) {
          // Annual tax (July only)
          taxAmount = isLogging ? (loggingRates[vehicle.category] || 0) : catObj.tax;
        } else {
          // Partial-period tax (all months except July) - use lookup tables
          if (isLogging) {
            taxAmount = partialPeriodTaxLogging[vehicle.category]?.[mon] || 0;
          } else {
            taxAmount = partialPeriodTaxRegular[vehicle.category]?.[mon] || 0;
          }
        }
        monthData.tax += taxAmount;
      }
    }
    
    // Add disposal credit for this vehicle (if any)
    if (vehicle.disposal_credit && vehicle.disposal_credit > 0) {
      monthData.credits += vehicle.disposal_credit;
    }
  });
  
  // Validate each month's credits don't exceed its tax
  for (const [month, data] of monthlyTaxAndCredits.entries()) {
    console.log(`🔍 Month ${formatMonth(month)}: Tax=$${data.tax.toFixed(2)}, Credits=$${data.credits.toFixed(2)}`);
    if (data.credits > data.tax) {
      const monthStr = formatMonth(month);
      return `Disposal credits for ${monthStr} ($${data.credits.toFixed(2)}) cannot exceed the total tax for that month ($${data.tax.toFixed(2)})`;
    }
  }
  
  // Amendment validation
  if (formData.amended_return && !formData.amended_month) {
    return 'Month being amended is required for amended returns';
  }
  
  // IRS Business Rule F2290-003-01: TGW increase requires amended return
  const hasTGWIncrease = formData.vehicles.some(v => v.tgw_increased);
  if (hasTGWIncrease && !formData.amended_return) {
    return 'Amended return must be checked when any vehicle has weight category increase';
  }
  
  // VIN correction validation
  if (formData.vin_correction && !formData.vin_correction_explanation.trim()) {
    return 'VIN correction explanation is required';
  }
  
  // IRS Business Rule F2290-032-01: VIN correction requires at least one VIN
  if (formData.vin_correction && formData.vehicles.length === 0) {
    return 'At least one vehicle is required when VIN correction is checked';
  }
  
  // IRS Business Rule F2290-033-01: Amended return requires at least one VIN
  if (formData.amended_return && formData.vehicles.length === 0) {
    return 'At least one vehicle is required for amended returns';
  }
  
  // IRS Business Rule F2290-027-01: Non-final returns require at least one VIN
  if (!formData.final_return && formData.vehicles.length === 0) {
    return 'At least one vehicle is required unless this is a final return';
  }
  
  if (formData.include_preparer) {
    if (!formData.preparer_name.trim()) return 'Preparer Name is required';
    if (!formData.preparer_ptin.trim()) return 'Preparer PTIN is required';
    if (!formData.date_prepared) return 'Date Prepared is required';
    if (!formData.preparer_firm_name.trim()) return 'Firm Name is required';
    if (!/^\d{2}-\d{7}$/.test(formData.preparer_firm_ein)) return 'Firm EIN must be 9 digits in format XX-XXXXXXX';
    if (!formData.preparer_firm_address.trim()) return 'Firm Address is required';
    if (!formData.preparer_firm_citystatezip.trim()) return 'Firm City/State/ZIP is required';
    if (!/^\d{10}$/.test(formData.preparer_firm_phone)) return 'Firm Phone must be 10 digits';
  }
  
  if (formData.consent_to_disclose) {
    if (!formData.designee_name.trim()) return 'Designee Name is required';
    if (!/^\d{10}$/.test(formData.designee_phone)) return 'Designee Phone must be 10 digits';
    if (!formData.designee_pin.trim()) return 'Designee PIN is required';
  }
  
  if (!formData.signature.trim()) return 'Signature is required';
  if (!formData.printed_name.trim()) return 'Printed Name is required';
  if (!formData.signature_date) return 'Signature Date is required';
  if (!formData.payEFTPS && !formData.payCard) {
    return 'Select either EFTPS or Credit/Debit Card';
  }
  
  if (formData.payEFTPS) {
    if (!/^\d{9}$/.test(formData.eftps_routing)) return 'Routing number must be 9 digits';
    if (!formData.eftps_account.trim()) return 'Account number is required';
    if (!formData.account_type) return 'Account type is required';
    if (!formData.payment_date) return 'Payment date is required';
    if (!/^\d{10}$/.test(formData.taxpayer_phone)) return 'Taxpayer phone must be 10 digits';
  }
  
  if (formData.payCard) {
    if (!formData.card_holder.trim() ||
        !formData.card_number.trim() ||
        !formData.card_exp.trim() ||
        !formData.card_cvv.trim()) {
      return 'All credit/debit card fields are required';
    }
  }
  
  for (let idx = 0; idx < formData.vehicles.length; idx++) {
    const v = formData.vehicles[idx];
    if (!v.vin.trim()) return `VIN is required for vehicle #${idx + 1}`;
    if (!v.used_month) return `Month is required for vehicle #${idx + 1}`;
    if (!v.category) return `Weight is required for vehicle #${idx + 1}`;
    
    // Enhanced vehicle validation
    if (v.disposal_date && !v.disposal_reason) {
      return `Disposal reason is required for vehicle #${idx + 1}`;
    }
    if (v.tgw_increased && (!v.tgw_increase_month || !v.tgw_previous_category)) {
      return `Weight increase details are required for vehicle #${idx + 1}`;
    }
    if (v.vin_corrected && !v.vin_correction_reason?.trim()) {
      return `VIN correction reason is required for vehicle #${idx + 1}`;
    }
    
    // IRS Business Rule: Category W vehicles must select either agricultural or non-agricultural
    if (v.category === 'W' && !v.is_agricultural && !v.mileage_5000_or_less) {
      return `Vehicle #${idx + 1} (Category W) must select either "Agricultural ≤7,500 mi" or "Non-Agricultural ≤5,000 mi"`;
    }
  }
  
  // IRS Business Rule F2290-017: VIN duplicate validation
  const vins = formData.vehicles.map(v => v.vin.trim().toUpperCase()).filter(vin => vin);
  const uniqueVINs = new Set(vins);
  if (vins.length !== uniqueVINs.size) {
    return 'Duplicate VINs are not allowed - each vehicle must have a unique VIN';
  }
  
  // IRS Business Rule F2290-008-01: 5000 mile limit requires Category W
  const has5000MileVehicles = formData.vehicles.some(v => v.mileage_5000_or_less);
  const hasCategoryW = formData.vehicles.some(v => v.category === 'W');
  if (has5000MileVehicles && !hasCategoryW) {
    return 'When 5000 mile limit is used, at least one vehicle must be Category W (Suspended)';
  }
  
  // IRS Business Rule F2290-068: Payment method required when balance due > 0
  const balanceDue = Math.max(0, totalTax - totalDisposalCredits);
  if (balanceDue > 0 && !formData.payEFTPS && !formData.payCard) {
    return 'Payment method (EFTPS or Credit/Debit Card) is required when balance is due';
  }
  
  return null;
};

// Enhanced category-based calculations (similar to IRS Form 2290 Tax Computation table)
export const calculateCategoryCounts = (vehicles: Vehicle[]): Record<string, CategoryData> => {
  const categoryData: Record<string, CategoryData> = {};

  // Initialize all categories
  weightCategories.forEach(cat => {
    categoryData[cat.value] = {
      regularCount: 0,
      loggingCount: 0,
      regularTotalTax: 0,
      loggingTotalTax: 0,
      regularAnnualTax: 0,
      loggingAnnualTax: 0,
      regularPartialTax: 0,
      loggingPartialTax: 0,
      partialPeriodRates: { regular: 0, logging: 0 }
    };
  });

  // Calculate partial-period rates dynamically for each category
  // Based on the actual months of vehicles in that category
  weightCategories.forEach(cat => {
    // For category W, include all vehicles assigned to W regardless of agricultural/suspended status
    // For other categories, exclude agricultural and suspended vehicles
    const categoryVehicles = cat.value === 'W' 
      ? vehicles.filter(v => v.category === cat.value)
      : vehicles.filter(v => v.category === cat.value && !v.is_suspended && !v.is_agricultural);
    
    if (categoryVehicles.length > 0) {
      // Find partial-period vehicles in this category
      const partialPeriodVehicles = categoryVehicles.filter(v => {
        const mon = parseInt(v.used_month.slice(-2), 10);
        return mon && mon !== 7; // All months except July are partial-period
      });
      
      if (partialPeriodVehicles.length > 0) {
        // Use the earliest partial-period month for this category
        const partialPeriodMonths = partialPeriodVehicles.map(v => parseInt(v.used_month.slice(-2), 10));
        const representativeMonth = Math.min(...partialPeriodMonths);
        
        // Check if this category has regular vehicles with partial-period months
        const hasRegularPartial = partialPeriodVehicles.some(v => !v.is_logging);
        const hasLoggingPartial = partialPeriodVehicles.some(v => v.is_logging);
        
        // Only set rates for applicable vehicle types
        categoryData[cat.value].partialPeriodRates = {
          regular: hasRegularPartial ? (partialPeriodTaxRegular[cat.value]?.[representativeMonth] || 0) : 0,
          logging: hasLoggingPartial ? (partialPeriodTaxLogging[cat.value]?.[representativeMonth] || 0) : 0
        };
      } else {
        // No partial-period vehicles in this category
        categoryData[cat.value].partialPeriodRates = {
          regular: 0,
          logging: 0
        };
      }
    } else {
      // No vehicles in this category at all
      categoryData[cat.value].partialPeriodRates = {
        regular: 0,
        logging: 0
      };
    }
  });

  // Now process vehicles and calculate actual taxes using lookup tables
  vehicles.forEach(v => {
    if (!v.category) return;
    
    // For category W, include agricultural and suspended vehicles but don't calculate tax
    // For other categories, exclude agricultural and suspended vehicles
    if (v.category !== 'W' && (v.is_suspended || v.is_agricultural)) return;
    
    const mon = parseInt(v.used_month.slice(-2), 10) || 0;
    if (!mon) return;

    const catObj = weightCategories.find(w => w.value === v.category);
    if (!catObj) return;

    const isLogging = v.is_logging;
    const isAnnualTax = mon === 7;  // Only July = annual tax
    
    let taxAmount = 0;
    // Category W (suspended/agricultural) always has $0 tax
    if (v.category === 'W') {
      taxAmount = 0;
    } else if (isAnnualTax) {
      // Annual tax (July only)
      taxAmount = isLogging ? loggingRates[v.category] : catObj.tax;
    } else {
      // Partial-period tax (all months except July) - use lookup tables
      if (isLogging) {
        taxAmount = partialPeriodTaxLogging[v.category]?.[mon] || 0;
      } else {
        taxAmount = partialPeriodTaxRegular[v.category]?.[mon] || 0;
      }
    }

    if (isLogging) {
      categoryData[v.category].loggingCount++;
      categoryData[v.category].loggingTotalTax += taxAmount;
      
      if (isAnnualTax) {
        categoryData[v.category].loggingAnnualTax += taxAmount;
      } else {
        categoryData[v.category].loggingPartialTax += taxAmount;
      }
    } else {
      categoryData[v.category].regularCount++;
      categoryData[v.category].regularTotalTax += taxAmount;
      
      if (isAnnualTax) {
        categoryData[v.category].regularAnnualTax += taxAmount;
      } else {
        categoryData[v.category].regularPartialTax += taxAmount;
      }
    }
  });

  return categoryData;
};

export const calculateGrandTotals = (categoryData: Record<string, CategoryData>): GrandTotals => {
  return {
    regularVehicles: Object.values(categoryData).reduce((sum, cat) => sum + cat.regularCount, 0),
    loggingVehicles: Object.values(categoryData).reduce((sum, cat) => sum + cat.loggingCount, 0),
    regularTotalTax: Object.values(categoryData).reduce((sum, cat) => sum + cat.regularTotalTax, 0),
    loggingTotalTax: Object.values(categoryData).reduce((sum, cat) => sum + cat.loggingTotalTax, 0),
    regularAnnualTax: Object.values(categoryData).reduce((sum, cat) => sum + cat.regularAnnualTax, 0),
    loggingAnnualTax: Object.values(categoryData).reduce((sum, cat) => sum + cat.loggingAnnualTax, 0),
    regularPartialTax: Object.values(categoryData).reduce((sum, cat) => sum + cat.regularPartialTax, 0),
    loggingPartialTax: Object.values(categoryData).reduce((sum, cat) => sum + cat.loggingPartialTax, 0)
  };
};

export const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

export const formatMonth = (monthCode: string) => {
  if (!monthCode || monthCode.length !== 6) return monthCode;
  const year = monthCode.substring(0, 4);
  const monthNum = parseInt(monthCode.substring(4, 6), 10);
  
  // Handle invalid month numbers (like 13, 14, etc.)
  if (monthNum < 1 || monthNum > 12) {
    return `Invalid Month (${monthCode})`;
  }
  
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${monthNames[monthNum - 1]} ${year}`;
};

// Disposal Credit Calculation
export const calculateDisposalCredit = (vehicle: Vehicle, disposalDate: string): number => {
  if (!vehicle.category || !vehicle.used_month || !disposalDate) return 0;

  // Category W vehicles have no tax, so no credit
  if (vehicle.category === 'W') return 0;

  // Skip suspended or agricultural vehicles (they don't have tax)
  if (vehicle.is_suspended || vehicle.is_agricultural) return 0;

  const firstUseMonth = parseInt(vehicle.used_month.slice(-2), 10);
  const disposalDateObj = new Date(disposalDate);
  const disposalMonth = disposalDateObj.getMonth() + 1; // 1-12
  
  const catObj = weightCategories.find(w => w.value === vehicle.category);
  if (!catObj) return 0;

  const isLogging = vehicle.is_logging;
  
  // Step 1: Calculate the full-period tax (Line 1)
  const fullPeriodTax = isLogging ? loggingRates[vehicle.category] : catObj.tax;
  
  // Step 2: Count months of use (from first day of first use month through last day of disposal month)
  // Example: First used July 2, destroyed October 15 → July, Aug, Sept, Oct = 4 months
  let monthsOfUse = 0;
  if (disposalMonth >= firstUseMonth) {
    // Same year disposal
    monthsOfUse = disposalMonth - firstUseMonth + 1;
  } else {
    // Next year disposal (crosses tax year boundary)
    monthsOfUse = (12 - firstUseMonth + 1) + disposalMonth;
  }
  
  // Ensure monthsOfUse is within valid range (1-12 months)
  monthsOfUse = Math.max(1, Math.min(12, monthsOfUse));
  
  // Step 3: Look up partial-period tax based on months of use
  // The partial period tables are organized by starting month (when vehicle is first used)
  // For disposal, we need to find the partial period tax for the actual months used
  let partialPeriodTax = 0;
  let lookupKey: number | undefined;
  
  if (monthsOfUse === 12) {
    // Full year use = full period tax
    partialPeriodTax = fullPeriodTax;
  } else {
    // Map months of use to the correct table lookup
    // The IRS tables use month numbers as keys, where each represents the partial period tax
    // Based on the IRS example: 4 months of use should give $48.00 for Category C
    // Looking at Category C table: key 3 = 48.00, so 4 months of use = key 3
    
    let lookupKey: number;
    // Corrected mapping based on IRS example
    // The IRS example shows 4 months of use should give $48.00 for Category C
    // $48.00 is at key 3 in our table, so 4 months maps to key 3
    const monthsToKeyMap: Record<number, number> = {
      1: 6,   // 1 month of use
      2: 5,   // 2 months of use  
      3: 4,   // 3 months of use
      4: 3,   // 4 months of use (IRS example: should give $48 for Category C)
      5: 2,   // 5 months of use
      6: 1,   // 6 months of use
      7: 12,  // 7 months of use
      8: 11,  // 8 months of use
      9: 10,  // 9 months of use
      10: 9,  // 10 months of use
      11: 8   // 11 months of use
    };
    
    lookupKey = monthsToKeyMap[monthsOfUse];
    
    // Debug logging
    console.log(`🔍 Disposal Credit Debug for Vehicle ${vehicle.vin}:`);
    console.log(`  Category: ${vehicle.category}, Logging: ${isLogging}`);
    console.log(`  First use month: ${firstUseMonth}, Disposal month: ${disposalMonth}`);
    console.log(`  Months of use: ${monthsOfUse}`);
    console.log(`  monthsToKeyMap:`, monthsToKeyMap);
    
    lookupKey = monthsToKeyMap[monthsOfUse];
    console.log(`  Lookup key for ${monthsOfUse} months: ${lookupKey}`);
    
    if (lookupKey !== undefined) {
      if (isLogging) {
        partialPeriodTax = partialPeriodTaxLogging[vehicle.category]?.[lookupKey] || 0;
      } else {
        partialPeriodTax = partialPeriodTaxRegular[vehicle.category]?.[lookupKey] || 0;
      }
      console.log(`  Partial-period tax: $${partialPeriodTax}`);
    } else {
      // Fallback for edge cases
      partialPeriodTax = fullPeriodTax;
      console.log(`  Fallback to full-period tax: $${partialPeriodTax}`);
    }
  }

  // Step 4: Calculate credit (Line 1 - Line 2)
  const credit = Math.max(0, fullPeriodTax - partialPeriodTax);
  
  // Final debug summary
  console.log(`  Full-period tax: $${fullPeriodTax}`);
  console.log(`  Credit: $${credit}`);
  
  return credit;
};

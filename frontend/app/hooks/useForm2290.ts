import { useState, useEffect, useRef } from 'react';
import { DateTime } from "luxon";
import { auth } from '../../lib/firebase';
import { onAuthStateChanged } from 'firebase/auth';
import { FormData, Vehicle } from '../types/form';
import { calculateCategoryCounts, calculateGrandTotals } from '../utils/formUtils';
import { weightCategories, loggingRates, partialPeriodTaxRegular, partialPeriodTaxLogging } from '../constants/formData';

export const useForm2290 = () => {
  // Always get today's date in America/New_York (Eastern) as YYYY-MM-DD
  const easternToday = DateTime.now().setZone("America/New_York").toISODate();

  // Form state (enhanced with IRS compliance fields)
  const [formData, setFormData] = useState<FormData>({
    email: '',
    business_name: '',
    business_name_line2: '',
    ein: '',
    address: '',
    address_line2: '',
    city: '',
    state: '',
    zip: '',
    tax_year: '2025',
    used_on_july: '202507',
    address_change: false,
    amended_return: false,
    vin_correction: false,
    final_return: false,
    
    // Amendment-related fields
    amended_month: '',
    reasonable_cause_explanation: '',
    
    // VIN correction fields
    vin_correction_explanation: '',
    
    // Special conditions
    special_conditions: '',
    
    // Business Officer Information (required for signing)
    officer_name: '',
    officer_title: '',
    officer_ssn: '',
    taxpayer_pin: '',
    
    // Enhanced disposals/credits (removed static tax_credits)
    has_disposals: false,
    
    include_preparer: false,
    preparer_name: '',
    preparer_ptin: '',
    preparer_self_employed: true,
    date_prepared: '',
    preparer_firm_name: '',
    preparer_firm_ein: '',
    preparer_firm_address: '',
    preparer_firm_citystatezip: '',
    preparer_firm_phone: '',
    consent_to_disclose: false,
    designee_name: '',
    designee_phone: '',
    designee_pin: '',
    vehicles: [
      {
        vin: '',
        category: '',
        used_month: '',
        is_logging: false,
        is_suspended: false,
        is_agricultural: false,
        mileage_5000_or_less: false,
      },
    ] as Vehicle[],
    signature: '',
    printed_name: '',
    signature_date: easternToday || '',
    payEFTPS: false,
    payCard: false,
    
    // Enhanced payment fields
    eftps_routing: '',
    eftps_account: '',
    account_type: '',
    payment_date: '',
    taxpayer_phone: '',
    
    card_holder: '',
    card_number: '',
    card_exp: '',
    card_cvv: '',
  });

  // CAPTCHA state and ref
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaError, setCaptchaError] = useState<string>('');

  // Auto-set captcha token for localhost development
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const hostname = window.location.hostname;
      const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
      if (isLocalhost && !captchaToken) {
        setCaptchaToken('localhost-dev-token');
      }
    }
  }, [captchaToken]);

  // Auto-populate email when user logs in
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user && user.email) {
        setFormData(prev => ({
          ...prev,
          email: user.email
        }));
      }
    });
    return unsubscribe;
  }, []);

  const [totalTax, setTotalTax] = useState(0);

  useEffect(() => {
    let total = 0;
    formData.vehicles.forEach(v => {
      const mon = parseInt(v.used_month.slice(-2), 10) || 0;
      if (!mon || v.is_suspended || v.is_agricultural) return;
      const catObj = weightCategories.find(w => w.value === v.category);
      if (!catObj) return;
      
      // Use lookup tables for partial-period or annual rates
      let rate = 0;
      if (mon === 7) {
        // Annual tax (July only)
        rate = v.is_logging ? loggingRates[v.category] : catObj.tax;
      } else {
        // Partial-period tax (all months except July) - use lookup tables
        if (v.is_logging) {
          rate = partialPeriodTaxLogging[v.category]?.[mon] || 0;
        } else {
          rate = partialPeriodTaxRegular[v.category]?.[mon] || 0;
        }
      }
      
      total += rate;
    });
    setTotalTax(total);
  }, [formData.vehicles]);

  const addVehicle = () => {
    setFormData({
      ...formData,
      vehicles: [
        ...formData.vehicles,
        {
          vin: '',
          category: '',
          used_month: '',
          is_logging: false,
          is_suspended: false,
          is_agricultural: false,
          mileage_5000_or_less: false,
          // Initialize enhanced fields
          disposal_date: undefined,
          disposal_reason: undefined,
          disposal_amount: undefined,
          sale_to_private_party: false,
          tgw_increased: false,
          tgw_increase_month: undefined,
          tgw_previous_category: undefined,
          vin_corrected: false,
          vin_correction_reason: undefined,
        },
      ],
    });
  };

  const removeVehicle = (i: number) => {
    setFormData({
      ...formData,
      vehicles: formData.vehicles.filter((_, j) => j !== i),
    });
  };

  const categoryData = calculateCategoryCounts(formData.vehicles);
  const grandTotals = calculateGrandTotals(categoryData);

  // Calculate total disposal credits
  const totalDisposalCredits = formData.vehicles.reduce((sum, vehicle) => {
    return sum + (vehicle.disposal_credit || 0);
  }, 0);

  const totalVINs = formData.vehicles.length;
  const lodgingCount = formData.vehicles.filter(v => v.is_logging).length;
  const taxableVehiclesCount = formData.vehicles.filter(v => {
    console.log(`Vehicle with VIN ${v.vin}: category='${v.category}', mileage_5000_or_less=${v.mileage_5000_or_less}, is_agricultural=${v.is_agricultural}, is_suspended=${v.is_suspended}`);
    return v.category !== 'W';
  }).length;
  console.log(`Total taxable vehicles: ${taxableVehiclesCount}`);
  const suspendedCount = formData.vehicles.filter(v => v.is_suspended || v.is_agricultural).length;
  const suspendedLoggingCount = formData.vehicles.filter(v => (v.is_suspended || v.is_agricultural) && v.is_logging).length;
  const suspendedNonLoggingCount = formData.vehicles.filter(v => (v.is_suspended || v.is_agricultural) && !v.is_logging).length;

  return {
    formData,
    setFormData,
    totalTax,
    totalDisposalCredits,
    captchaToken,
    setCaptchaToken,
    captchaError,
    setCaptchaError,
    addVehicle,
    removeVehicle,
    categoryData,
    grandTotals,
    totalVINs,
    lodgingCount,
    taxableVehiclesCount,
    suspendedCount,
    suspendedLoggingCount,
    suspendedNonLoggingCount,
  };
};

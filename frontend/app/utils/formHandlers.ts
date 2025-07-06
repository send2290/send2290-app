import { ChangeEvent } from 'react';
import { FormData, Vehicle } from '../types/form';

export const createFormHandler = (
  formData: FormData,
  setFormData: (data: FormData) => void,
  todayStr: string
) => {
  return (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const t = e.target as HTMLInputElement;
    const { name, type, value, checked } = t;

    // Include Paid Preparer toggle
    if (name === 'include_preparer') {
      if (!checked) {
        setFormData({
          ...formData,
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
        });
      } else {
        setFormData({ ...formData, include_preparer: true });
      }
      return;
    }

    // Consent to Disclose toggle
    if (name === 'consent_to_disclose') {
      if (!checked) {
        setFormData({
          ...formData,
          consent_to_disclose: false,
          designee_name: '',
          designee_phone: '',
          designee_pin: '',
        });
      } else {
        setFormData({ ...formData, consent_to_disclose: true });
      }
      return;
    }

    // Vehicle fields - special handling for vehicles array updates
    if (name === 'vehicles') {
      setFormData({ ...formData, vehicles: value as any });
      return;
    }

    // Vehicle fields
    if (name.startsWith('vehicle_')) {
      const [_, idxStr, ...fld] = name.split('_');
      const idx = parseInt(idxStr, 10);
      const field = fld.join('_') as keyof Vehicle;
      const vehicles = [...formData.vehicles];
      const vv = { ...vehicles[idx] } as Record<string, any>;
      if (type === 'checkbox') {
        vv[field] = checked as any;
        
        // Handle mutually exclusive checkboxes and automatic category updates
        if (field === 'is_agricultural' && checked) {
          vv.is_suspended = false;
          vv.mileage_5000_or_less = false;
          vv.category = 'W';
        }
        if (field === 'is_suspended' && checked) {
          vv.is_agricultural = false;
          vv.mileage_5000_or_less = false;
          vv.category = 'W';
        }
        if (field === 'mileage_5000_or_less' && checked) {
          vv.is_agricultural = false;
          vv.is_suspended = false;
          vv.category = 'W';
        }
        
        // If all checkboxes are unchecked and category is W, reset category
        if (!vv.is_agricultural && !vv.is_suspended && !vv.mileage_5000_or_less && vv.category === 'W') {
          vv.category = '';
        }
      } else if (type === 'number') {
        vv[field] = value ? parseFloat(value) : undefined;
      } else {
        vv[field] = value as any;
        
        // Handle category dropdown changes - uncheck relevant checkboxes when category changes away from W
        if (field === 'category') {
          if (value !== 'W') {
            vv.is_agricultural = false;
            vv.is_suspended = false;
            vv.mileage_5000_or_less = false;
          }
        }
      }
      vehicles[idx] = vv as Vehicle;
      setFormData({ ...formData, vehicles });
      return;
    }

    // Payment exclusivity
    if (name === 'payEFTPS') {
      setFormData({ ...formData, payEFTPS: checked, payCard: false });
      return;
    }
    if (name === 'payCard') {
      setFormData({ ...formData, payCard: checked, payEFTPS: false });
      return;
    }

    // Signature date guard
    if (name === 'signature_date' && value < todayStr) {
      alert('Signature date cannot be before today.');
      return;
    }

    // Default update (now includes email)
    const finalValue = type === 'checkbox' ? checked : 
                      (type === 'number' && name === 'tax_credits') ? (value ? parseFloat(value) : 0) :
                      value;
    
    setFormData({
      ...formData,
      [name]: finalValue,
    });
  };
};

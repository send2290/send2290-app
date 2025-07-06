import React, { ChangeEvent } from 'react';
import { FormData, Vehicle } from '../types/form';
import { weightCategories, months } from '../constants/formData';
import { calculateDisposalCredit } from '../utils/formUtils';

interface VehicleManagementProps {
  formData: FormData;
  handleChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => void;
  addVehicle: () => void;
  removeVehicle: (i: number) => void;
}

export const VehicleManagement: React.FC<VehicleManagementProps> = ({
  formData,
  handleChange,
  addVehicle,
  removeVehicle
}) => {
  const labelSmall = {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    fontSize: '0.9rem'
  } as React.CSSProperties;

  const btnSmall = {
    padding: '6px 12px',
    border: 'none',
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: '0.9rem'
  } as React.CSSProperties;

  const todayStr = new Date().toISOString().split('T')[0];

  return (
    <>
      {/* Vehicles */}
      <h2 style={{ marginTop: 20 }}>Vehicles</h2>
      {formData.vehicles.map((v, i) => (
        <div key={i} className="vehicle-row" style={{ 
          display: 'flex', 
          gap: 8, 
          alignItems: 'flex-start', 
          marginBottom: 16,
          padding: 12,
          border: '1px solid #ddd',
          borderRadius: 4,
          backgroundColor: v.is_suspended || v.is_agricultural ? '#f8f9fa' : 'white',
          flexWrap: 'wrap'
        }}>
          {/* Basic vehicle info - top row */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', width: '100%', marginBottom: 8 }}>
            <input
              style={{ width: 180 }}
              type="text"
              name={`vehicle_${i}_vin`}
              placeholder="VIN"
              pattern="[A-Za-z0-9]{17}"
              maxLength={17}
              title="17 chars"
              value={v.vin}
              onChange={handleChange}
              required
            />
            <select
              name={`vehicle_${i}_used_month`}
              value={v.used_month}
              onChange={handleChange}
              required
              style={{ minWidth: 150 }}
            >
              <option value="">Select Month</option>
              {months.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
            <select
              name={`vehicle_${i}_category`}
              value={v.category}
              onChange={handleChange}
              required
              style={{ minWidth: 180 }}
            >
              <option value="">Select Weight</option>
              {weightCategories.map((w) => (
                <option key={w.value} value={w.value}>{w.label}</option>
              ))}
            </select>
            <button
              type="button"
              style={{ ...btnSmall, backgroundColor: '#d32f2f', color: '#fff' }}
              onClick={() => removeVehicle(i)}
            >
              Remove
            </button>
          </div>

          {/* Checkboxes - second row */}
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', width: '100%', marginBottom: 8 }}>
            <label style={{ ...labelSmall, cursor: 'pointer' }}>
              <input 
                type="checkbox" 
                name={`vehicle_${i}_is_logging`} 
                checked={v.is_logging} 
                onChange={handleChange}
                style={{ cursor: 'pointer' }}
              />
              <span style={{ cursor: 'pointer' }}>Logging Vehicle</span>
            </label>
            <label style={{ ...labelSmall, cursor: 'pointer' }}>
              <input 
                type="checkbox" 
                name={`vehicle_${i}_is_agricultural`} 
                checked={v.is_agricultural} 
                onChange={handleChange}
                style={{ cursor: 'pointer' }}
              />
              <span style={{ cursor: 'pointer' }}>Agricultural ≤7,500 mi</span>
            </label>
            <label style={{ ...labelSmall, cursor: 'pointer' }}>
              <input 
                type="checkbox" 
                name={`vehicle_${i}_mileage_5000_or_less`} 
                checked={v.mileage_5000_or_less} 
                onChange={handleChange}
                style={{ cursor: 'pointer' }}
              />
              <span style={{ cursor: 'pointer' }}>Non-Agricultural ≤5,000 mi</span>
            </label>
          </div>

          {/* Advanced options - expandable section */}
          <div style={{ width: '100%', borderTop: '1px solid #eee', paddingTop: 8 }}>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
              <label style={{ ...labelSmall, cursor: 'pointer' }}>
                <input 
                  type="checkbox" 
                  name={`vehicle_${i}_disposal_date`} 
                  checked={!!v.disposal_date} 
                  onChange={(e) => {
                    const vehicles = [...formData.vehicles];
                    vehicles[i] = {
                      ...vehicles[i],
                      disposal_date: e.target.checked ? todayStr : undefined,
                      disposal_reason: e.target.checked ? vehicles[i].disposal_reason : undefined,
                      disposal_amount: e.target.checked ? vehicles[i].disposal_amount : undefined
                    };
                    // Create a synthetic event to pass to handleChange
                    const syntheticEvent = {
                      target: { name: 'vehicles', value: vehicles }
                    } as any;
                    handleChange(syntheticEvent);
                  }}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ cursor: 'pointer' }}>Vehicle Disposed/Sold</span>
              </label>

              <label style={{ 
                ...labelSmall, 
                cursor: 'not-allowed',
                opacity: 0.5
              }}>
                <input 
                  type="checkbox" 
                  name={`vehicle_${i}_tgw_increased`} 
                  checked={v.tgw_increased || false} 
                  onChange={handleChange}
                  disabled
                  style={{ cursor: 'not-allowed' }}
                />
                <span style={{ cursor: 'not-allowed' }}>Weight Category Increased (Coming Soon)</span>
              </label>

              <label style={{ ...labelSmall, cursor: 'pointer', display: 'none' }}>
                <input 
                  type="checkbox" 
                  name={`vehicle_${i}_is_suspended`} 
                  checked={v.is_suspended || false} 
                  onChange={handleChange}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ cursor: 'pointer' }}>Suspended Vehicle</span>
              </label>

              <label style={{ ...labelSmall, cursor: 'pointer' }}>
                <input 
                  type="checkbox" 
                  name={`vehicle_${i}_vin_corrected`} 
                  checked={v.vin_corrected || false} 
                  onChange={handleChange}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ cursor: 'pointer' }}>VIN Corrected</span>
              </label>

              <label style={{ ...labelSmall, cursor: 'pointer' }}>
                <input 
                  type="checkbox" 
                  name={`vehicle_${i}_sale_to_private_party`} 
                  checked={v.sale_to_private_party || false} 
                  onChange={handleChange}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ cursor: 'pointer' }}>Sold to Private Party</span>
              </label>
            </div>

            {/* Disposal details */}
            {v.disposal_date && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8, padding: 8, backgroundColor: '#fff3cd', borderRadius: 4 }}>
                <input
                  type="date"
                  name={`vehicle_${i}_disposal_date`}
                  value={v.disposal_date || ''}
                  onChange={(e) => {
                    // Update disposal date and recalculate credit
                    const vehicles = [...formData.vehicles];
                    vehicles[i] = {
                      ...vehicles[i],
                      disposal_date: e.target.value,
                      disposal_credit: e.target.value ? calculateDisposalCredit(vehicles[i], e.target.value) : undefined
                    };
                    const syntheticEvent = {
                      target: { name: 'vehicles', value: vehicles }
                    } as any;
                    handleChange(syntheticEvent);
                  }}
                  placeholder="Disposal Date"
                  required
                />
                <select
                  name={`vehicle_${i}_disposal_reason`}
                  value={v.disposal_reason || ''}
                  onChange={handleChange}
                  required
                >
                  <option value="">Disposal Reason</option>
                  <option value="Sold">Sold</option>
                  <option value="Destroyed">Destroyed</option>
                  <option value="Stolen">Stolen</option>
                  <option value="Transferred">Transferred</option>
                  <option value="Traded">Traded</option>
                </select>
                <input
                  type="number"
                  name={`vehicle_${i}_disposal_amount`}
                  placeholder="Disposal Amount ($)"
                  min="0"
                  step="0.01"
                  value={v.disposal_amount || ''}
                  onChange={handleChange}
                  onWheel={(e) => e.currentTarget.blur()}
                />
                
                {/* Dynamic Credit Display */}
                {v.disposal_date && v.category && v.used_month && (
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: 8,
                    padding: '6px 12px',
                    backgroundColor: '#d4edda',
                    border: '1px solid #c3e6cb',
                    borderRadius: 4,
                    fontSize: '0.9rem',
                    fontWeight: 'bold',
                    color: '#155724',
                    minWidth: '200px'
                  }}>
                    <span>💰 Line 5 Credit: ${calculateDisposalCredit(v, v.disposal_date).toFixed(2)}</span>
                  </div>
                )}
                
                {/* Credit Explanation */}
                {v.disposal_date && v.category && v.used_month && calculateDisposalCredit(v, v.disposal_date) > 0 && (
                  <div style={{ 
                    width: '100%',
                    fontSize: '0.8rem',
                    color: '#856404',
                    backgroundColor: '#fff3cd',
                    padding: '4px 8px',
                    borderRadius: 3,
                    border: '1px solid #ffeaa7',
                    marginTop: 4
                  }}>
                    ℹ️ Credit = Full-period tax minus partial-period tax for actual months of use (disposal before filing original return).
                  </div>
                )}
              </div>
            )}

            {/* Weight increase details */}
            {v.tgw_increased && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8, padding: 8, backgroundColor: '#d1ecf1', borderRadius: 4 }}>
                <select
                  name={`vehicle_${i}_tgw_increase_month`}
                  value={v.tgw_increase_month || ''}
                  onChange={handleChange}
                  required
                >
                  <option value="">Month Weight Increased</option>
                  {months.map((m) => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
                <select
                  name={`vehicle_${i}_tgw_previous_category`}
                  value={v.tgw_previous_category || ''}
                  onChange={handleChange}
                  required
                >
                  <option value="">Previous Weight Category</option>
                  {weightCategories.filter(w => w.value !== 'W').map((w) => (
                    <option key={w.value} value={w.value}>{w.label}</option>
                  ))}
                </select>
              </div>
            )}

            {/* VIN correction details */}
            {v.vin_corrected && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8, padding: 8, backgroundColor: '#f8d7da', borderRadius: 4 }}>
                <input
                  name={`vehicle_${i}_vin_correction_reason`}
                  placeholder="Explain the VIN correction..."
                  value={v.vin_correction_reason || ''}
                  onChange={handleChange}
                  style={{ minWidth: '300px' }}
                  required
                />
              </div>
            )}
          </div>
        </div>
      ))}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        <button
          type="button"
          style={{ ...btnSmall, backgroundColor: '#1565c0', color: '#fff' }}
          onClick={addVehicle}
        >
          + Add Vehicle
        </button>
      </div>
    </>
  );
};

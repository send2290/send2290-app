import React from 'react';
import { CategoryData, GrandTotals, FormData } from '../types/form';
import { weightCategories, loggingRates } from '../constants/formData';

interface TaxComputationTableProps {
  categoryData: Record<string, CategoryData>;
  grandTotals: GrandTotals;
  totalVINs: number;
  formData: FormData;
  suspendedLoggingCount: number;
  suspendedNonLoggingCount: number;
  taxableVehiclesCount: number;
  totalDisposalCredits: number;
}

export const TaxComputationTable: React.FC<TaxComputationTableProps> = ({
  categoryData,
  grandTotals,
  totalVINs,
  formData,
  suspendedLoggingCount,
  suspendedNonLoggingCount,
  taxableVehiclesCount,
  totalDisposalCredits
}) => {
  return (
    <div style={{ 
      background: '#f9f9f9', 
      border: '2px solid #333', 
      borderRadius: '8px', 
      padding: '16px',
      marginTop: '20px',
      marginBottom: '20px'
    }}>
      <h3 style={{ textAlign: 'center', margin: '0 0 16px 0', color: '#333' }}>
        Tax Computation by Category
      </h3>
      
      <div style={{ overflowX: 'auto' }}>
        <table style={{ 
          width: '100%', 
          borderCollapse: 'collapse',
          fontSize: '0.9rem',
          background: 'white'
        }}>
          <thead>
            <tr style={{ background: '#e9ecef' }}>
              <th style={{ border: '1px solid #333', padding: '8px', textAlign: 'center' }}>
                Category
              </th>
              <th style={{ border: '1px solid #333', padding: '8px', textAlign: 'center' }}>
                Taxable Gross Weight<br/>(in pounds)
              </th>
              <th style={{ border: '1px solid #333', padding: '8px', textAlign: 'center' }} colSpan={2}>
                (1) Annual Tax<br/>(vehicles first used during July)
              </th>
              <th style={{ border: '1px solid #333', padding: '8px', textAlign: 'center' }} colSpan={2}>
                (2) Partial-period Tax<br/>(vehicles first used after July)<br/>See tables at end of instructions
              </th>
              <th style={{ border: '1px solid #333', padding: '8px', textAlign: 'center' }} colSpan={2}>
                (3) Number of Vehicles
              </th>
              <th style={{ border: '1px solid #333', padding: '8px', textAlign: 'center' }}>
                (4) Amount of Tax<br/>(col. (1) or (2) multiplied by col. (3))
              </th>
            </tr>
            <tr style={{ background: '#f8f9fa' }}>
              <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem' }}></th>
              <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem' }}></th>
              <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                (a) Vehicles<br/>except logging*
              </th>
              <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                (b) Logging<br/>vehicles*
              </th>
              <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                (a) Vehicles<br/>except logging*
              </th>
              <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                (b) Logging<br/>vehicles*
              </th>
              <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                (a) Vehicles<br/>except logging*
              </th>
              <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                (b) Logging<br/>vehicles*
              </th>
              <th style={{ border: '1px solid #333', padding: '4px', fontSize: '0.8rem', textAlign: 'center' }}>
                Amount of Tax
              </th>
            </tr>
          </thead>
          <tbody>
            {weightCategories.filter(cat => {
              // Only show categories that have vehicles (including W if there are vehicles)
              const data = categoryData[cat.value];
              return data.regularCount > 0 || data.loggingCount > 0;
            }).map((cat) => {
              const data = categoryData[cat.value];
              
              return (
                <tr key={cat.value} style={{ 
                  background: cat.value === 'W' ? '#f8d7da' : '#fff3cd',  // Special styling for category W
                  opacity: 1
                }}>
                  <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center', fontWeight: 'bold' }}>
                    {cat.value}
                  </td>
                  <td style={{ border: '1px solid #333', padding: '6px', fontSize: '0.8rem' }}>
                    {cat.value === 'W' ? 'Tax-Suspended Vehicles' : (cat.label.match(/\((.*?)\)/)?.[1] || cat.label)}
                  </td>
                  {/* Annual Tax Rates */}
                  <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center' }}>
                    {cat.value === 'W' ? 'No tax due' : `$${cat.tax.toFixed(2)}`}
                  </td>
                  <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center' }}>
                    {cat.value === 'W' ? 'No tax due' : `$${(loggingRates[cat.value] || 0).toFixed(2)}`}
                  </td>
                  {/* Partial Tax Rates - only show if there are partial-period vehicles in this category */}
                  <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center' }}>
                    {cat.value === 'W' ? 'No tax due' : (data.partialPeriodRates.regular > 0 ? `$${data.partialPeriodRates.regular.toFixed(2)}` : '')}
                  </td>
                  <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center' }}>
                    {cat.value === 'W' ? 'No tax due' : (data.partialPeriodRates.logging > 0 ? `$${data.partialPeriodRates.logging.toFixed(2)}` : '')}
                  </td>
                  {/* Vehicle Counts */}
                  <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center', fontWeight: 'bold' }}>
                    {data.regularCount || ''}
                  </td>
                  <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center', fontWeight: 'bold' }}>
                    {data.loggingCount || ''}
                  </td>
                  {/* Total Tax Amount */}
                  <td style={{ border: '1px solid #333', padding: '6px', textAlign: 'center', fontWeight: 'bold' }}>
                    {cat.value === 'W' ? '$0.00' : ((data.regularTotalTax + data.loggingTotalTax) > 0 ? `$${(data.regularTotalTax + data.loggingTotalTax).toFixed(2)}` : '')}
                  </td>
                </tr>
              );
            })}
            
            {/* Totals Row */}
            <tr style={{ background: '#d4edda', fontWeight: 'bold' }}>
              <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center' }} colSpan={2}>
                <strong>TOTALS</strong>
              </td>
              <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center' }}>
                -
              </td>
              <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center' }}>
                -
              </td>
              <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center', fontSize: '0.9rem' }}>
                (See individual rows)
              </td>
              <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center', fontSize: '0.9rem' }}>
                (See individual rows)
              </td>
              <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center' }}>
                {grandTotals.regularVehicles}
              </td>
              <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center' }}>
                {grandTotals.loggingVehicles}
              </td>
              <td style={{ border: '2px solid #333', padding: '8px', textAlign: 'center' }}>
                ${(grandTotals.regularTotalTax + grandTotals.loggingTotalTax).toFixed(2)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Part I Tax Summary Section */}
      <div style={{ marginTop: '16px', padding: '12px', background: '#e9ecef', borderRadius: '4px' }}>
        <h4 style={{ margin: '0 0 12px 0', color: '#333' }}>Part I - Tax Summary</h4>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '8px', fontSize: '0.95rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #ccc' }}>
            <span>1. Total number of vehicles reported (from Schedule 1)</span>
            <strong>{totalVINs}</strong>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #ccc' }}>
            <span>2. Tax (from Schedule 1, line c.)</span>
            <strong>${(grandTotals.regularTotalTax + grandTotals.loggingTotalTax).toFixed(2)}</strong>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #ccc' }}>
            <span>3. Additional tax (attach explanation)</span>
            <strong>$0.00</strong>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '2px solid #333' }}>
            <span><strong>4. Total tax (add lines 2 and 3)</strong></span>
            <strong>${(grandTotals.regularTotalTax + grandTotals.loggingTotalTax).toFixed(2)}</strong>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #ccc' }}>
            <span>5. Credits (Vehicle Disposals)</span>
            <strong>${totalDisposalCredits.toFixed(2)}</strong>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '2px solid #333', background: '#fff3cd' }}>
            <span><strong>6. Balance due (subtract line 5 from line 4)</strong></span>
            <strong>${Math.max(0, (grandTotals.regularTotalTax + grandTotals.loggingTotalTax) - totalDisposalCredits).toFixed(2)}</strong>
          </div>
        </div>
        
        {/* Quick Stats */}
        <div style={{ marginTop: '12px', padding: '8px', background: 'white', borderRadius: '4px' }}>
          <h5 style={{ margin: '0 0 8px 0', color: '#333' }}>Vehicle Summary:</h5>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '6px', fontSize: '0.85rem' }}>
            <div>🪵 <strong>Logging Vehicles:</strong> {grandTotals.loggingVehicles}</div>
            <div>🚫 <strong>Suspended (Logging):</strong> {suspendedLoggingCount}</div>
            <div>🚫 <strong>Suspended (Non-Logging):</strong> {suspendedNonLoggingCount}</div>
            <div>🎯 <strong>Taxable Vehicles:</strong> {taxableVehiclesCount}</div>
          </div>
        </div>
        
        {/* Tax Breakdown */}
        {(grandTotals.regularAnnualTax > 0 || grandTotals.loggingAnnualTax > 0 || grandTotals.regularPartialTax > 0 || grandTotals.loggingPartialTax > 0 || totalDisposalCredits > 0) && (
          <div style={{ marginTop: '8px', padding: '8px', background: 'white', borderRadius: '4px' }}>
            <h5 style={{ margin: '0 0 8px 0', color: '#333' }}>Tax Breakdown:</h5>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '6px', fontSize: '0.8rem' }}>
              {grandTotals.regularAnnualTax > 0 && (
                <div>🗓️ Annual (Regular): ${grandTotals.regularAnnualTax.toFixed(2)}</div>
              )}
              {grandTotals.loggingAnnualTax > 0 && (
                <div>🗓️ Annual (Logging): ${grandTotals.loggingAnnualTax.toFixed(2)}</div>
              )}
              {grandTotals.regularPartialTax > 0 && (
                <div>📅 Partial (Regular): ${grandTotals.regularPartialTax.toFixed(2)}</div>
              )}
              {grandTotals.loggingPartialTax > 0 && (
                <div>📅 Partial (Logging): ${grandTotals.loggingPartialTax.toFixed(2)}</div>
              )}
              {totalDisposalCredits > 0 && (
                <div style={{ color: '#d32f2f', fontWeight: 'bold' }}>💰 Disposal Credits: -${totalDisposalCredits.toFixed(2)}</div>
              )}
            </div>
            {totalDisposalCredits > 0 && (
              <div style={{ marginTop: '8px', padding: '6px', background: '#e8f5e8', borderRadius: '4px', border: '1px solid #4caf50' }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#2e7d32' }}>
                  Net Tax Due: ${Math.max(0, (grandTotals.regularTotalTax + grandTotals.loggingTotalTax) - totalDisposalCredits).toFixed(2)}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#666', marginTop: '2px' }}>
                  (Total Tax: ${(grandTotals.regularTotalTax + grandTotals.loggingTotalTax).toFixed(2)} - Credits: ${totalDisposalCredits.toFixed(2)})
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      
      <div style={{ fontSize: '0.8rem', color: '#666', marginTop: '8px', fontStyle: 'italic' }}>
        * Logging vehicles are vehicles used for logging purposes and qualify for reduced tax rates.
      </div>
    </div>
  );
};

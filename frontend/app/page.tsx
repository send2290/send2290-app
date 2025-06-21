'use client'

import { useState, useEffect, ChangeEvent } from 'react'

export const weightCategories = [
  { label: 'A (55,000 lbs)',          value: 'A', tax: 100.00 },
  { label: 'B (55,001 – 56,000 lbs)',  value: 'B', tax: 122.00 },
  { label: 'C (56,001 – 57,000 lbs)',  value: 'C', tax: 144.00 },
  { label: 'D (57,001 – 58,000 lbs)',  value: 'D', tax: 166.00 },
  { label: 'E (58,001 – 59,000 lbs)',  value: 'E', tax: 188.00 },
  { label: 'F (59,001 – 60,000 lbs)',  value: 'F', tax: 210.00 },
  { label: 'G (60,001 – 61,000 lbs)',  value: 'G', tax: 232.00 },
  { label: 'H (61,001 – 62,000 lbs)',  value: 'H', tax: 254.00 },
  { label: 'I (62,001 – 63,000 lbs)',  value: 'I', tax: 276.00 },
  { label: 'J (63,001 – 64,000 lbs)',  value: 'J', tax: 298.00 },
  { label: 'K (64,001 – 65,000 lbs)',  value: 'K', tax: 320.00 },
  { label: 'L (65,001 – 66,000 lbs)',  value: 'L', tax: 342.00 },
  { label: 'M (66,001 – 67,000 lbs)',  value: 'M', tax: 364.00 },
  { label: 'N (67,001 – 68,000 lbs)',  value: 'N', tax: 386.00 },
  { label: 'O (68,001 – 69,000 lbs)',  value: 'O', tax: 408.00 },
  { label: 'P (69,001 – 70,000 lbs)',  value: 'P', tax: 430.00 },
  { label: 'Q (70,001 – 71,000 lbs)',  value: 'Q', tax: 452.00 },
  { label: 'R (71,001 – 72,000 lbs)',  value: 'R', tax: 474.00 },
  { label: 'S (72,001 – 73,000 lbs)',  value: 'S', tax: 496.00 },
  { label: 'T (73,001 – 74,000 lbs)',  value: 'T', tax: 518.00 },
  { label: 'U (74,001 – 75,000 lbs)',  value: 'U', tax: 540.00 },
  { label: 'V (over 75,000 lbs)',     value: 'V', tax: 550.00 },
  { label: 'W (Suspended)',           value: 'W', tax: 0.00 }
]

export default function Form2290() {
  // Determine API base URL
  const isBrowser = typeof window !== 'undefined'
  const defaultApi = isBrowser
    ? `${window.location.protocol}//${window.location.hostname}:5000`
    : ''
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || defaultApi

  // Form state
  const [formData, setFormData] = useState({
    business_name:   '',
    ein:             '',
    address:         '',
    city:            '',
    state:           '',
    zip:             '',
    tax_year:        '2025',
    used_on_july:    '202507',
    address_change:  false,
    amended_return:  false,
    vin_correction:  false,
    final_return:    false,
    vehicles: [
      {
        vin: '',
        category: '',
        used_month: '',
        is_logging: false,
        is_suspended: false,
        is_agricultural: false
      }
    ],
    signature:     '',
    printed_name:  '',
    signature_date:'',
    payEFTPS:      false,
    payCard:       false,
    eftps_routing: '',
    eftps_account: '',
    card_holder:   '',
    card_number:   '',
    card_exp:      '',
    card_cvv:      ''
  })
  const [totalTax, setTotalTax] = useState(0)
  const todayStr = new Date().toISOString().split('T')[0]

  // Month options July→June (hardcoded year 2025 here; adjust if dynamic needed)
  const months = Array.from({ length: 12 }).map((_, i) => {
    const m = 6 + i
    return {
      label: new Date(2025, m, 1).toLocaleString('default', { month: 'long', year: 'numeric' }),
      value: `2025${String(m+1).padStart(2,'0')}`
    }
  })

  // Logging rates
  const loggingRates: Record<string, number> = {
    A:75, B:91.5, C:108, D:124.5, E:141, F:157.5,
    G:174, H:190.5, I:207, J:223.5, K:240, L:256.5,
    M:273, N:289.5, O:306, P:322.5, Q:339, R:355.5,
    S:372, T:388.5, U:405, V:412.5, W:0
  }

  // Recalculate total tax when vehicles change
  useEffect(() => {
    let total = 0
    formData.vehicles.forEach(v => {
      // Parse last two digits of used_month as month number
      let mon = 0
      if (typeof v.used_month === 'string' && v.used_month.length >= 2) {
        const last2 = v.used_month.slice(-2)
        const mi = parseInt(last2, 10)
        if (!isNaN(mi)) mon = mi
      }
      const catObj = weightCategories.find(w => w.value === v.category)
      if (!catObj || !mon) return
      if (v.is_suspended || v.is_agricultural) return

      const rate = v.is_logging ? loggingRates[v.category] : catObj.tax
      let tax = 0
      if (mon === 7) {
        tax = rate
      } else {
        let left = 13 - mon
        if (left <= 0) left += 12
        tax = Number(((rate * left) / 12).toFixed(2))
      }
      total += tax
    })
    setTotalTax(total)
  }, [formData.vehicles])

  // Unified change handler
  const handleChange = (e: ChangeEvent<HTMLInputElement|HTMLSelectElement>) => {
    const target = e.target as HTMLInputElement
    const { name, value, type } = target
    const checked = target.checked

    // Vehicle fields: name like "vehicle_0_vin", "vehicle_1_category", etc.
    if (name.startsWith('vehicle_')) {
      const [_, idxStr, ...rest] = name.split('_')
      const idx = parseInt(idxStr, 10)
      const field = rest.join('_')
      const vehicles = [...formData.vehicles]
      const vv = { ...vehicles[idx] }

      if (type === 'checkbox') {
        vv[field as any] = checked
        // mutual exclude
        if (field === 'is_agricultural' && checked) vv.is_suspended = false
        if (field === 'is_suspended' && checked) vv.is_agricultural = false
        // auto category 'W' if suspended/agri
        if (vv.is_agricultural || vv.is_suspended) {
          vv.category = 'W'
        } else if (vv.category === 'W') {
          vv.category = ''
        }
      } else {
        vv[field as any] = value
        if (field === 'category') {
          if (value === 'W' && !(vv.is_agricultural || vv.is_suspended)) {
            alert('Select Agricultural or Non-Agricultural box for Suspended category.')
          }
          if (value !== 'W') {
            vv.is_agricultural = false
            vv.is_suspended = false
          }
        }
      }
      vehicles[idx] = vv
      setFormData({ ...formData, vehicles })
      return
    }

    // Signature date cannot be before today
    if (name === 'signature_date' && value < todayStr) {
      alert('Date cannot be earlier than today.')
      return
    }

    // Payment exclusivity
    if (name === 'payEFTPS') {
      setFormData({ ...formData, payEFTPS: checked, payCard: false })
      return
    }
    if (name === 'payCard') {
      setFormData({ ...formData, payCard: checked, payEFTPS: false })
      return
    }

    // Other fields
    setFormData({
      ...formData,
      [name]: type === 'checkbox' ? checked : value
    })
  }

  // Add/remove vehicles
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
          is_agricultural: false
        }
      ]
    })
  }
  const removeVehicle = (i: number) => {
    const newVehs = formData.vehicles.filter((_, j) => j !== i)
    setFormData({ ...formData, vehicles: newVehs })
  }

  // Counts
  const totalVINs = formData.vehicles.length
  const lodgingCount = formData.vehicles.filter(v => v.is_logging).length
  const suspendedCount = formData.vehicles.filter(v => v.is_suspended || v.is_agricultural).length

  // Front-end validation helper before submitting
  const validateBeforeSubmit = (): string | null => {
    if (!formData.business_name.trim()) {
      return 'Business Name is required'
    }
    if (!/^\d{9}$/.test(formData.ein.trim())) {
      return 'EIN must be 9 digits'
    }
    if (!formData.address.trim() || !formData.city.trim() || !formData.state.trim() || !formData.zip.trim()) {
      return 'Address, City, State, ZIP are required'
    }
    if (!/^\d{5}$/.test(formData.zip.trim())) {
      return 'ZIP must be 5 digits'
    }
    // Vehicles
    if (formData.vehicles.length === 0) {
      return 'At least one vehicle is required'
    }
    for (let i = 0; i < formData.vehicles.length; i++) {
      const v = formData.vehicles[i]
      if (!v.vin.trim()) {
        return `Vehicle #${i+1}: VIN is required`
      }
      if (v.vin.trim().length !== 17) {
        return `Vehicle #${i+1}: VIN must be 17 characters`
      }
      if (!v.used_month) {
        return `Vehicle #${i+1}: Month/Year is required`
      }
      if (!v.category) {
        return `Vehicle #${i+1}: Weight Class is required`
      }
      if (v.category === 'W' && !(v.is_agricultural || v.is_suspended)) {
        return `Vehicle #${i+1}: For Suspended (W), check one of the boxes`
      }
    }
    // Signature
    if (!formData.signature.trim()) {
      return 'Signature is required'
    }
    if (!formData.printed_name.trim()) {
      return 'Printed Name is required'
    }
    if (!formData.signature_date) {
      return 'Signature Date is required'
    }
    // Payment: if EFTPS selected, fields required
    if (formData.payEFTPS) {
      if (!formData.eftps_routing.trim() || !formData.eftps_account.trim()) {
        return 'EFTPS routing and account are required'
      }
    }
    if (formData.payCard) {
      if (!formData.card_holder.trim() || !formData.card_number.trim() || !formData.card_exp.trim() || !formData.card_cvv.trim()) {
        return 'Credit card fields are required'
      }
    }
    // All good
    return null
  }

  // Submit XML
  const handleSubmit = async () => {
    // Log API_BASE and payload for debugging
    console.log("API_BASE is:", API_BASE)
    console.log("About to POST to:", `${API_BASE}/build-xml`)
    console.log("Payload:", formData)

    // Front-end validation
    const validationError = validateBeforeSubmit()
    if (validationError) {
      alert(validationError)
      return
    }

    try {
      const res = await fetch(`${API_BASE}/build-xml`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      })
      let json: any = {}
      try {
        json = await res.json()
      } catch (_) {
        console.error("Failed to parse JSON response")
      }
      if (!res.ok) {
        console.error("build-xml error response:", json)
        alert(json.error || `Submission failed (status ${res.status})`)
        return
      }
      console.log("build-xml success response:", json)
      alert(json.message || "XML generated")

      // download XML
      console.log("Downloading XML from:", `${API_BASE}/download-xml`)
      const xmlRes = await fetch(`${API_BASE}/download-xml`)
      if (!xmlRes.ok) {
        console.error("download-xml failed, status:", xmlRes.status)
        throw new Error('XML download failed')
      }
      const blob = await xmlRes.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'form2290.xml'; a.click()
      URL.revokeObjectURL(url)
    } catch (err: any) {
      console.error("Fetch threw error in handleSubmit:", err)
      alert(err.message || 'Failed to fetch')
    }
  }

  // Download PDF
  const handleDownloadPDF = async () => {
    console.log("Downloading PDF from:", `${API_BASE}/download-pdf`)
    try {
      const pdfRes = await fetch(`${API_BASE}/download-pdf`)
      if (!pdfRes.ok) {
        console.error("download-pdf failed, status:", pdfRes.status)
        throw new Error('PDF download failed')
      }
      const blob = await pdfRes.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'form2290.pdf'; a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error("Error in handleDownloadPDF:", err)
      alert('PDF download failed')
    }
  }

  // Styles
  const container: React.CSSProperties = { maxWidth: 900, margin: '0 auto', padding: 20, fontFamily: 'Segoe UI, sans-serif' }
  const header: React.CSSProperties = { textAlign: 'center', color: '#d32f2f' }
  const labelSmall: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.9rem' }
  const btnSmall: React.CSSProperties = { padding: '6px 12px', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '0.9rem' }

  return (
    <div style={container}>
      <h1 style={header}>Send2290</h1>
      <p style={{ textAlign: 'center', marginTop: -8 }}>By Consulting, PLLC</p>

      {/* Business Info */}
      <h2>Business Info</h2>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <input
          name="business_name"
          value={formData.business_name}
          onChange={handleChange}
          placeholder="Name"
        />
        <input
          name="ein"
          value={formData.ein}
          onChange={handleChange}
          placeholder="EIN"
          pattern="\d{9}"
          maxLength={9}
          inputMode="numeric"
          title="9 digits"
        />
        <input
          name="address"
          value={formData.address}
          onChange={handleChange}
          placeholder="Address"
        />
        <input
          name="city"
          value={formData.city}
          onChange={handleChange}
          placeholder="City"
        />
        <input
          name="state"
          value={formData.state}
          onChange={handleChange}
          placeholder="State"
        />
        <input
          name="zip"
          value={formData.zip}
          onChange={handleChange}
          placeholder="ZIP"
          pattern="\d{5}"
          maxLength={5}
          inputMode="numeric"
          title="5 digits"
        />
      </div>

      {/* Return Flags */}
      <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', marginTop: 12 }}>
        <label>
          <input
            type="checkbox"
            name="address_change"
            checked={formData.address_change}
            onChange={handleChange}
          />{' '}
          Address Change
        </label>
        <label>
          <input
            type="checkbox"
            name="amended_return"
            checked={formData.amended_return}
            onChange={handleChange}
          />{' '}
          Amended Return
        </label>
        <label>
          <input
            type="checkbox"
            name="vin_correction"
            checked={formData.vin_correction}
            onChange={handleChange}
          />{' '}
          VIN Correction
        </label>
        <label>
          <input
            type="checkbox"
            name="final_return"
            checked={formData.final_return}
            onChange={handleChange}
          />{' '}
          Final Return
        </label>
      </div>

      {/* Vehicles */}
      <h2 style={{ marginTop: 20 }}>Vehicles</h2>
      {formData.vehicles.map((v, i) => (
        <div key={i} style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: 12 }}>
          <input
            style={{ width: 180 }}
            type="text"
            name={`vehicle_${i}_vin`}
            value={v.vin}
            onChange={handleChange}
            placeholder="VIN"
            pattern="[A-Za-z0-9]{17}"
            maxLength={17}
            title="17 chars"
          />
          <select
            name={`vehicle_${i}_used_month`}
            value={v.used_month}
            onChange={handleChange}
          >
            <option value="">Select Month/Year</option>
            {months.map(m => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
          <select
            name={`vehicle_${i}_category`}
            value={v.category}
            onChange={handleChange}
          >
            <option value="">Weight Class</option>
            {weightCategories.map(w => (
              <option key={w.value} value={w.value}>
                {w.label}
              </option>
            ))}
          </select>
          <label style={labelSmall}>
            Logging? <input type="checkbox" name={`vehicle_${i}_is_logging`} checked={v.is_logging} onChange={handleChange} />
          </label>
          <label style={labelSmall}>
            Agricultural Vehicle ≤7,000 mi?{' '}
            <input type="checkbox" name={`vehicle_${i}_is_agricultural`} checked={v.is_agricultural} onChange={handleChange} />
          </label>
          <label style={labelSmall}>
            Non-Agricultural ≤5,000 mi{' '}
            <input type="checkbox" name={`vehicle_${i}_is_suspended`} checked={v.is_suspended} onChange={handleChange} />
          </label>
          <button
            type="button"
            style={{ ...btnSmall, backgroundColor: '#d32f2f', color: '#fff' }}
            onClick={() => removeVehicle(i)}
          >
            Remove
          </button>
        </div>
      ))}

      {/* Add Vehicle & Counts */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: 12 }}>
        <button
          type="button"
          style={{ ...btnSmall, backgroundColor: '#1565c0', color: '#fff' }}
          onClick={addVehicle}
        >
          + Add Vehicle
        </button>
        <div>
          <strong>VINs:</strong> {totalVINs}
          <strong style={{ marginLeft: 12 }}>Lodging Vehicles:</strong> {lodgingCount}
          <strong style={{ marginLeft: 12 }}>Suspended Vehicles:</strong> {suspendedCount}
        </div>
      </div>

      <h3>Total Tax: ${totalTax.toFixed(2)}</h3>

      {/* Signature */}
      <h2>Signature</h2>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <input
          name="signature"
          value={formData.signature}
          onChange={handleChange}
          placeholder="Signature"
        />
        <input
          name="printed_name"
          value={formData.printed_name}
          onChange={handleChange}
          placeholder="Printed Name"
        />
        <input
          type="date"
          name="signature_date"
          min={todayStr}
          value={formData.signature_date}
          onChange={handleChange}
        />
      </div>

      {/* Payment Method */}
      <h2 style={{ marginTop: 20 }}>Payment Method</h2>
      <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', marginTop: 8 }}>
        <label>
          <input type="checkbox" name="payEFTPS" checked={formData.payEFTPS} onChange={handleChange} /> EFTPS
        </label>
        <label>
          <input type="checkbox" name="payCard" checked={formData.payCard} onChange={handleChange} /> Credit/Debit Card
        </label>
      </div>
      {formData.payEFTPS && (
        <div style={{ marginTop: 12, display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <input
            name="eftps_routing"
            value={formData.eftps_routing}
            onChange={handleChange}
            placeholder="Routing Number"
          />
          <input
            name="eftps_account"
            value={formData.eftps_account}
            onChange={handleChange}
            placeholder="Account Number"
          />
        </div>
      )}
      {formData.payCard && (
        <div style={{ marginTop: 12, display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <input
            name="card_holder"
            value={formData.card_holder}
            onChange={handleChange}
            placeholder="Cardholder Name"
          />
          <input
            name="card_number"
            value={formData.card_number}
            onChange={handleChange}
            placeholder="Card Number"
          />
          <input
            name="card_exp"
            value={formData.card_exp}
            onChange={handleChange}
            placeholder="MM/YY"
          />
          <input
            name="card_cvv"
            value={formData.card_cvv}
            onChange={handleChange}
            placeholder="CVV"
          />
        </div>
      )}

      {/* Actions */}
      <div style={{ marginTop: 20, display: 'flex', gap: '12px' }}>
        <button
          type="button"
          style={{ ...btnSmall, backgroundColor: '#002855', color: '#fff' }}
          onClick={handleSubmit}
        >
          Generate XML
        </button>
        <button
          type="button"
          style={{ ...btnSmall, backgroundColor: '#28a745', color: '#fff' }}
          onClick={handleDownloadPDF}
        >
          Download PDF
        </button>
      </div>
    </div>
  )
}

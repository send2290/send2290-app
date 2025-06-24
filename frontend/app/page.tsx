'use client'

import { useState, useEffect, ChangeEvent } from 'react'

export const weightCategories = [
  { label: 'A (55,000 lbs)',          value: 'A', tax: 100.00 },
  { label: 'B (55,001 – 56,000 lbs)', value: 'B', tax: 122.00 },
  { label: 'C (56,001 – 57,000 lbs)', value: 'C', tax: 144.00 },
  { label: 'D (57,001 – 58,000 lbs)', value: 'D', tax: 166.00 },
  { label: 'E (58,001 – 59,000 lbs)', value: 'E', tax: 188.00 },
  { label: 'F (59,001 – 60,000 lbs)', value: 'F', tax: 210.00 },
  { label: 'G (60,001 – 61,000 lbs)', value: 'G', tax: 232.00 },
  { label: 'H (61,001 – 62,000 lbs)', value: 'H', tax: 254.00 },
  { label: 'I (62,001 – 63,000 lbs)', value: 'I', tax: 276.00 },
  { label: 'J (63,001 – 64,000 lbs)', value: 'J', tax: 298.00 },
  { label: 'K (64,001 – 65,000 lbs)', value: 'K', tax: 320.00 },
  { label: 'L (65,001 – 66,000 lbs)', value: 'L', tax: 342.00 },
  { label: 'M (66,001 – 67,000 lbs)', value: 'M', tax: 364.00 },
  { label: 'N (67,001 – 68,000 lbs)', value: 'N', tax: 386.00 },
  { label: 'O (68,001 – 69,000 lbs)', value: 'O', tax: 408.00 },
  { label: 'P (69,001 – 70,000 lbs)', value: 'P', tax: 430.00 },
  { label: 'Q (70,001 – 71,000 lbs)', value: 'Q', tax: 452.00 },
  { label: 'R (71,001 – 72,000 lbs)', value: 'R', tax: 474.00 },
  { label: 'S (72,001 – 73,000 lbs)', value: 'S', tax: 496.00 },
  { label: 'T (73,001 – 74,000 lbs)', value: 'T', tax: 518.00 },
  { label: 'U (74,001 – 75,000 lbs)', value: 'U', tax: 540.00 },
  { label: 'V (over 75,000 lbs)',     value: 'V', tax: 550.00 },
  { label: 'W (Suspended)',           value: 'W', tax:   0.00 },
]

type Vehicle = {
  vin: string
  category: string
  used_month: string
  is_logging: boolean
  is_suspended: boolean
  is_agricultural: boolean
  mileage_5000_or_less: boolean
}

export default function Form2290() {
  // Determine API base URL
  const isBrowser = typeof window !== 'undefined'
  const defaultApi = isBrowser
    ? `${window.location.protocol}//${window.location.hostname}:5000`
    : ''
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || defaultApi

  // Form state
  const [formData, setFormData] = useState({
    // Filer / ReturnHeader
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

    // Include Paid Preparer?
    include_preparer: false,
    preparer_name:           '',
    preparer_ptin:           '',
    date_prepared:           '',
    preparer_firm_name:      '',
    preparer_firm_ein:       '',
    preparer_firm_address:   '',
    preparer_firm_citystatezip: '',
    preparer_firm_phone:     '',

    // Third-Party Designee / Consent
    consent_to_disclose: false,
    designee_name:       '',
    designee_phone:      '',
    designee_pin:        '',

    // Vehicles (Schedule 1)
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

    // Signature
    signature:      '',
    printed_name:   '',
    signature_date: '',

    // Payment
    payEFTPS:      false,
    payCard:       false,
    eftps_routing: '',
    eftps_account: '',
    card_holder:   '',
    card_number:   '',
    card_exp:      '',
    card_cvv:      '',
  })

  const [totalTax, setTotalTax] = useState(0)
  const todayStr = new Date().toISOString().split('T')[0]

  // Month options July→June
  const months = Array.from({ length: 12 }).map((_, i) => {
    const m = 6 + i
    return {
      label: new Date(2025, m, 1).toLocaleString('default', { month: 'long', year: 'numeric' }),
      value: `2025${String(m + 1).padStart(2, '0')}`,
    }
  })

  // Logging rates
  const loggingRates: Record<string, number> = {
    A:75, B:91.5, C:108, D:124.5, E:141, F:157.5,
    G:174, H:190.5, I:207, J:223.5, K:240, L:256.5,
    M:273, N:289.5, O:306, P:322.5, Q:339, R:355.5,
    S:372, T:388.5, U:405, V:412.5, W:0,
  }

  useEffect(() => {
    let total = 0
    formData.vehicles.forEach(v => {
      const mon = parseInt(v.used_month.slice(-2), 10) || 0
      if (!mon || v.is_suspended || v.is_agricultural) return
      const catObj = weightCategories.find(w => w.value === v.category)
      if (!catObj) return
      const rate = v.is_logging ? loggingRates[v.category] : catObj.tax
      const monthsLeft = mon >= 7 ? 12 : 13 - mon
      total += Number(((rate * monthsLeft) / 12).toFixed(2))
    })
    setTotalTax(total)
  }, [formData.vehicles])

  const handleChange = (e: ChangeEvent<HTMLInputElement|HTMLSelectElement>) => {
    const t = e.target as HTMLInputElement
    const { name, type, value, checked } = t

    // Include Paid Preparer toggle
    if (name === 'include_preparer') {
      if (!checked) {
        setFormData({
          ...formData,
          include_preparer: false,
          preparer_name: '',
          preparer_ptin: '',
          date_prepared: '',
          preparer_firm_name: '',
          preparer_firm_ein: '',
          preparer_firm_address: '',
          preparer_firm_citystatezip: '',
          preparer_firm_phone: '',
        })
      } else {
        setFormData({ ...formData, include_preparer: true })
      }
      return
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
        })
      } else {
        setFormData({ ...formData, consent_to_disclose: true })
      }
      return
    }

    // Vehicle fields
    if (name.startsWith('vehicle_')) {
      const [_, idxStr, ...fld] = name.split('_')
      const idx = parseInt(idxStr, 10)
      const field = fld.join('_') as keyof Vehicle
      const vehicles = [...formData.vehicles]
      const vv = { ...vehicles[idx] } as Record<string, any>
      if (type === 'checkbox') {
        vv[field] = checked as any
        if (field === 'is_agricultural' && checked) vv.is_suspended = false
        if (field === 'is_suspended' && checked) vv.is_agricultural = false
        vv.is_agricultural || vv.is_suspended
          ? (vv.category = 'W')
          : vv.category === 'W' && (vv.category = '')
      } else {
        vv[field] = value as any
      }
      vehicles[idx] = vv as Vehicle
      setFormData({ ...formData, vehicles })
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

    // Signature date guard
    if (name === 'signature_date' && value < todayStr) {
      alert('Signature date cannot be before today.')
      return
    }

    // Default update
    setFormData({
      ...formData,
      [name]: type === 'checkbox' ? checked : value,
    })
  }

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
        },
      ],
    })
  }

  const removeVehicle = (i: number) => {
    setFormData({
      ...formData,
      vehicles: formData.vehicles.filter((_, j) => j !== i),
    })
  }

  const totalVINs      = formData.vehicles.length
  const lodgingCount   = formData.vehicles.filter(v => v.is_logging).length
  const suspendedCount = formData.vehicles.filter(v => v.is_suspended || v.is_agricultural).length

  const validateBeforeSubmit = (): string | null => {
    if (!formData.business_name.trim()) return 'Business Name is required'
    if (!/^\d{9}$/.test(formData.ein))     return 'EIN must be 9 digits'

    if (formData.include_preparer) {
      if (!formData.preparer_name.trim())      return 'Preparer Name is required'
      if (!formData.preparer_ptin.trim())      return 'Preparer PTIN is required'
      if (!formData.date_prepared)             return 'Date Prepared is required'
      if (!formData.preparer_firm_name.trim()) return 'Firm Name is required'
      if (!/^\d{9}$/.test(formData.preparer_firm_ein)) return 'Firm EIN must be 9 digits'
      if (!formData.preparer_firm_address.trim())      return 'Firm Address is required'
      if (!formData.preparer_firm_citystatezip.trim()) return 'Firm City/State/ZIP is required'
      if (!/^\d{10}$/.test(formData.preparer_firm_phone)) return 'Firm Phone must be 10 digits'
    }

    if (formData.consent_to_disclose) {
      if (!formData.designee_name.trim())       return 'Designee Name is required'
      if (!/^\d{10}$/.test(formData.designee_phone)) return 'Designee Phone must be 10 digits'
      if (!formData.designee_pin.trim())        return 'Designee PIN is required'
    }

    if (!formData.signature.trim())    return 'Signature is required'
    if (!formData.printed_name.trim()) return 'Printed Name is required'
    if (!formData.signature_date)      return 'Signature Date is required'

    if (!formData.payEFTPS && !formData.payCard) {
      return 'Select either EFTPS or Credit/Debit Card'
    }
    if (formData.payEFTPS) {
      if (!formData.eftps_routing.trim() || !formData.eftps_account.trim()) {
        return 'EFTPS routing and account are required'
      }
    }
    if (formData.payCard) {
      if (!formData.card_holder.trim() ||
          !formData.card_number.trim() ||
          !formData.card_exp.trim() ||
          !formData.card_cvv.trim()) {
        return 'All credit/debit card fields are required'
      }
    }

    return null
  }

  const handleSubmit = async () => {
    // 0️⃣ Front-end validation
    const err = validateBeforeSubmit()
    if (err) {
      alert(err)
      return
    }

    // 1️⃣ Group your vehicles by used_month
    const groups = formData.vehicles.reduce<Record<string, Vehicle[]>>((acc, v) => {
      if (!v.used_month) return acc
      if (!acc[v.used_month]) acc[v.used_month] = []
      acc[v.used_month].push(v)
      return acc
    }, {})

    const months = Object.keys(groups)
    if (months.length === 0) {
      alert("Please select a month of first use for at least one vehicle.")
      return
    }

    // 2️⃣ For each month‐group, overwrite used_on_july & vehicles, then POST
    for (const month of months) {
      const payload = {
        ...formData,
        used_on_july: month,
        vehicles:     groups[month],
      }

      try {
        // POST to build it
        const buildRes = await fetch(`${API_BASE}/build-xml`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify(payload),
        })
        if (!buildRes.ok) {
          const errJson = await buildRes.json().catch(() => ({}))
          alert(`Error building XML for ${month}: ${errJson.error || buildRes.status}`)
          continue
        }

        // Parse JSON and extract xml string
        const { xml: xmlString } = await buildRes.json()

        // Turn that string into a proper XML blob
        const xmlBlob = new Blob([xmlString], { type: 'application/xml' })

        // Download it
        const url = URL.createObjectURL(xmlBlob)
        const a   = document.createElement('a')
        a.href     = url
        a.download = `form2290_${month}.xml`
        a.click()
        URL.revokeObjectURL(url)

      } catch (e: any) {
        alert(`Network error for ${month}: ${e.message}`)
      }
    }
  }

  const handleDownloadPDF = async () => {
    try {
      const pdfRes = await fetch(`${API_BASE}/download-pdf`)
      const blob   = await pdfRes.blob()
      const url    = URL.createObjectURL(blob)
      const a      = document.createElement('a')
      a.href       = url
      a.download   = 'form2290.pdf'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('PDF download failed')
    }
  }

  // Styles
  const container: React.CSSProperties  = {
    maxWidth: 900,
    margin: '0 auto',
    padding: 20,
    fontFamily: 'Segoe UI, sans-serif'
  }
  const header: React.CSSProperties     = {
    textAlign: 'center',
    color: '#d32f2f'
  }
  const labelSmall: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    fontSize: '0.9rem'
  }
  const btnSmall: React.CSSProperties   = {
    padding: '6px 12px',
    border: 'none',
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: '0.9rem'
  }

  return (
    <div style={container}>
      <h1 style={header}>Website Under Development!</h1>
      <p style={{ textAlign: 'center', marginTop: -8 }}>By Majd Consulting, PLLC</p>

      {/* Business Info */}
      <h2>Business Info</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input name="business_name" placeholder="Name" value={formData.business_name} onChange={handleChange} />
        <input
          name="ein"
          placeholder="EIN"
          pattern="\d{9}"
          maxLength={9}
          inputMode="numeric"
          title="9 digits"
          value={formData.ein}
          onChange={handleChange}
        />
        <input name="address" placeholder="Address" value={formData.address} onChange={handleChange} />
        <input name="city" placeholder="City" value={formData.city} onChange={handleChange} />
        <input name="state" placeholder="State" value={formData.state} onChange={handleChange} />
        <input
          name="zip"
          placeholder="ZIP"
          pattern="\d{5}"
          maxLength={5}
          inputMode="numeric"
          title="5 digits"
          value={formData.zip}
          onChange={handleChange}
        />
      </div>

      {/* Return Flags */}
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginTop: 12 }}>
        {['address_change','amended_return','vin_correction','final_return'].map(flag => (
          <label key={flag} style={labelSmall}>
            <input type="checkbox" name={flag} checked={(formData as any)[flag]} onChange={handleChange} />
            {flag.replace(/_/g,' ')}
          </label>
        ))}
      </div>

      {/* Paid Preparer */}
      <h2 style={{ marginTop: 20 }}>
        <label style={labelSmall}>
          <input
            type="checkbox"
            name="include_preparer"
            checked={formData.include_preparer}
            onChange={handleChange}
          />
          Include Paid Preparer
        </label>
      </h2>
      {formData.include_preparer && (
        <>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input name="preparer_name" placeholder="Preparer Name" value={formData.preparer_name} onChange={handleChange} required />
            <input name="preparer_ptin" placeholder="PTIN" value={formData.preparer_ptin} onChange={handleChange} required />
            <input type="date" name="date_prepared" max={todayStr} value={formData.date_prepared} onChange={handleChange} required />
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
            <input name="preparer_firm_name" placeholder="Firm Name" value={formData.preparer_firm_name} onChange={handleChange} required />
            <input
              name="preparer_firm_ein"
              placeholder="Firm EIN"
              pattern="\d{9}"
              maxLength={9}
              inputMode="numeric"
              title="9 digits"
              value={formData.preparer_firm_ein}
              onChange={handleChange}
              required
            />
            <input name="preparer_firm_address" placeholder="Firm Address" value={formData.preparer_firm_address} onChange={handleChange} required />
            <input
              name="preparer_firm_citystatezip"
              placeholder="Firm City/State/ZIP"
              value={formData.preparer_firm_citystatezip}
              onChange={handleChange}
              required
            />
            <input
              type="tel"
              name="preparer_firm_phone"
              placeholder="Firm Phone (10 digits)"
              pattern="\d{10}"
              maxLength={10}
              inputMode="numeric"
              title="10 digits"
              value={formData.preparer_firm_phone}
              onChange={handleChange}
              required
            />
          </div>
        </>
      )}

      {/* Third-Party Designee / Consent */}
      <h2 style={{ marginTop: 20 }}>
        <label style={labelSmall}>
          <input type="checkbox" name="consent_to_disclose" checked={formData.consent_to_disclose} onChange={handleChange} />
          Consent to Disclose
        </label>
      </h2>
      {formData.consent_to_disclose && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input name="designee_name" placeholder="Designee Name" value={formData.designee_name} onChange={handleChange} required />
          <input
            name="designee_phone"
            placeholder="Designee Phone (10 digits)"
            pattern="\d{10}"
            maxLength={10}
            inputMode="numeric"
            title="10 digits"
            value={formData.designee_phone}
            onChange={handleChange}
            required
          />
          <input name="designee_pin" placeholder="Designee PIN" value={formData.designee_pin} onChange={handleChange} required />
        </div>
      )}

      {/* Vehicles */}
      <h2 style={{ marginTop: 20 }}>Vehicles</h2>
      {formData.vehicles.map((v, i) => (
        <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
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
          />
          <select name={`vehicle_${i}_used_month`} value={v.used_month} onChange={handleChange}>
            <option value="">Select Month/Year</option>
            {months.map(m => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
          <select name={`vehicle_${i}_category`} value={v.category} onChange={handleChange}>
            <option value="">Weight Class</option>
            {weightCategories.map(w => (
              <option key={w.value} value={w.value}>{w.label}</option>
            ))}
          </select>
          <label style={labelSmall}>
            Logging? <input type="checkbox" name={`vehicle_${i}_is_logging`} checked={v.is_logging} onChange={handleChange} />
          </label>
          <label style={labelSmall}>
            Agricultural ≤7,000 mi <input type="checkbox" name={`vehicle_${i}_is_agricultural`} checked={v.is_agricultural} onChange={handleChange} />
          </label>
          <label style={labelSmall}>
            Non-Agricultural ≤5,000 mi <input type="checkbox" name={`vehicle_${i}_is_suspended`} checked={v.is_suspended} onChange={handleChange} />
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
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        <button
          type="button"
          style={{ ...btnSmall, backgroundColor: '#1565c0', color: '#fff' }}
          onClick={addVehicle}
        >
          + Add Vehicle
        </button>
        <div>
          <strong>VINs:</strong> {totalVINs}
          <strong style={{ marginLeft: 12 }}>Logging:</strong> {lodgingCount}
          <strong style={{ marginLeft: 12 }}>Suspended:</strong> {suspendedCount}
        </div>
      </div>

      <h3>Total Tax: ${totalTax.toFixed(2)}</h3>

      {/* Signature */}
      <h2>Signature</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input name="signature" placeholder="Signature" value={formData.signature} onChange={handleChange} />
        <input name="printed_name" placeholder="Printed Name" value={formData.printed_name} onChange={handleChange} />
        <input type="date" name="signature_date" min={todayStr} value={formData.signature_date} onChange={handleChange} />
      </div>

      {/* Payment Method */}
      <h2 style={{ marginTop: 20 }}>Payment Method</h2>
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginTop: 8 }}>
        <label>
          <input type="checkbox" name="payEFTPS" checked={formData.payEFTPS} onChange={handleChange} /> EFTPS
        </label>
        <label>
          <input type="checkbox" name="payCard" checked={formData.payCard} onChange={handleChange} /> Credit/Debit Card
        </label>
      </div>
      {formData.payEFTPS && (
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input name="eftps_routing" placeholder="Routing Number" value={formData.eftps_routing} onChange={handleChange} />
          <input name="eftps_account" placeholder="Account Number" value={formData.eftps_account} onChange={handleChange} />
        </div>
      )}
      {formData.payCard && (
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input name="card_holder" placeholder="Cardholder Name" value={formData.card_holder} onChange={handleChange} />
          <input name="card_number" placeholder="Card Number" value={formData.card_number} onChange={handleChange} />
          <input name="card_exp" placeholder="MM/YY" value={formData.card_exp} onChange={handleChange} />
          <input name="card_cvv" placeholder="CVV" value={formData.card_cvv} onChange={handleChange} />
        </div>
      )}

      {/* Actions */}
      <div style={{ marginTop: 20, display: 'flex', gap: 12 }}>
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

export interface Vehicle {
  vin: string
  category: string
  used_month: string
  is_logging: boolean
  is_suspended: boolean
  is_agricultural: boolean
  mileage_5000_or_less: boolean
  // Enhanced vehicle properties for IRS compliance
  disposal_date?: string           // For CreditsAmountStatement
  disposal_reason?: string         // Reason for disposal/sale
  disposal_amount?: number         // Amount received for disposal
  sale_to_private_party?: boolean  // For PrivateSaleVehicleStatement
  tgw_increased?: boolean          // If weight category increased during year
  tgw_increase_month?: string      // Month weight increased
  tgw_previous_category?: string   // Previous weight category
  vin_corrected?: boolean          // If this VIN was corrected
  vin_correction_reason?: string   // Reason for VIN correction
}

export interface FormData {
  email: string
  business_name: string
  business_name_line2: string
  ein: string
  address: string
  address_line2: string
  city: string
  state: string
  zip: string
  tax_year: string
  used_on_july: string
  address_change: boolean
  amended_return: boolean
  vin_correction: boolean
  final_return: boolean
  
  // Amendment-related fields
  amended_month: string
  reasonable_cause_explanation: string
  
  // VIN correction fields
  vin_correction_explanation: string
  
  // Special conditions
  special_conditions: string
  
  // Business Officer Information
  officer_name: string
  officer_title: string
  officer_ssn: string
  taxpayer_pin: string
  tax_credits: number
  
  // Enhanced disposals/credits
  has_disposals: boolean
  
  include_preparer: boolean
  preparer_name: string
  preparer_ptin: string
  preparer_self_employed: boolean
  date_prepared: string
  preparer_firm_name: string
  preparer_firm_ein: string
  preparer_firm_address: string
  preparer_firm_citystatezip: string
  preparer_firm_phone: string
  consent_to_disclose: boolean
  designee_name: string
  designee_phone: string
  designee_pin: string
  vehicles: Vehicle[]
  signature: string
  printed_name: string
  signature_date: string
  payEFTPS: boolean
  payCard: boolean
  
  // Enhanced payment fields
  eftps_routing: string
  eftps_account: string
  account_type: string
  payment_date: string
  taxpayer_phone: string
  
  card_holder: string
  card_number: string
  card_exp: string
  card_cvv: string
}

export interface AdminSubmission {
  id: number;
  business_name: string;
  ein: string;
  created_at: string;
  month: string;
  user_uid: string;
  user_email: string;
  total_vehicles: number;
  total_tax: number;
}

export interface AdminSubmissionFile {
  id: number;
  document_type: string;
  filename: string;
  s3_key: string;
  uploaded_at: string;
}

export interface CategoryData {
  regularCount: number;
  loggingCount: number;
  regularTotalTax: number;
  loggingTotalTax: number;
  regularAnnualTax: number;
  loggingAnnualTax: number;
  regularPartialTax: number;
  loggingPartialTax: number;
  partialPeriodRates: { regular: number; logging: number };
}

export interface GrandTotals {
  regularVehicles: number;
  loggingVehicles: number;
  regularTotalTax: number;
  loggingTotalTax: number;
  regularAnnualTax: number;
  loggingAnnualTax: number;
  regularPartialTax: number;
  loggingPartialTax: number;
}

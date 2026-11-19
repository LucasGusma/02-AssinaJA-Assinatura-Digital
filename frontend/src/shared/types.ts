export interface User { username: string; name: string; is_master: boolean; can_transfer: boolean; all_sectors: boolean }
export interface Session { user: User }
export interface IntegrationStatus { integration: 'pending' | 'configured'; transfers_enabled: boolean; message: string; capabilities?: { sector_filter: boolean; audit: boolean } }
export interface Sector { id: number; name: string }
export interface Member { username: string; name: string; profile?: string | null; can_forward: boolean }
export interface ClinicalDocument {
  id: number; title: string; patient_name?: string | null; attendance_id?: number | null;
  provider_id?: number | null; provider_name?: string | null; mv_user?: string | null; sector_id?: number | null;
  sector_name?: string | null; created?: string | null; discharge_at?: string | null; status: string; can_transfer: boolean; transfer_block_reason?: string | null;
}
export interface DocumentPage { documents: ClinicalDocument[]; next_cursor: number | null }
export interface DocumentContent {
  kind: 'pdf' | 'editor' | 'unavailable'; title?: string | null;
  fields: { label: string; value: string; truncated: boolean }[]; partial: boolean; message?: string | null;
}
export interface AuditEvent { request_id?: string | null; id: number; created: string; actor: string; action: string; detail: string; document_id?: number | null; source_user?: string | null; source_name?: string | null; target_user?: string | null; target_name?: string | null }
export interface AuditPage { events: AuditEvent[]; next_cursor: number | null }

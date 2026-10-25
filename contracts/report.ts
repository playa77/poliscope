// Generated; do not edit.
export type ArchiveOptions = { "include_private_notes"?: boolean; "include_private_rationale"?: boolean; "include_transcripts"?: boolean; "include_attachments"?: boolean; "evidence"?: "complete" | "reduced" };
export type ReportReply = { "report_schema"?: 1; "status": "complete" | "cancelled"; "format": "markdown" | "csv"; "rows"?: number; "bytes_written"?: number; "projection_digest"?: string | null; "redactions"?: (string)[] };
export type ReportRequest = { "format": "markdown" | "csv"; "options"?: ArchiveOptions; "archive_id"?: string | null; "scope_id"?: string | null };

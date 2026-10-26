// Generated; do not edit.
export type SpendBinding = { "dispatch_id": string; "turn_id": string; "session_id": string; "profile_id": string; "payload_sha256": string; "binding_sha256": string; "currency": "USD"; "estimate_version": "explicit-bounded-exposure-v1" };
export type SpendReply = { "spending_contract"?: 1; "dispatch_id": string; "status": "reserved" | "uncertain" | "complete" | "no-send" | "missing" | "denied" | "conflict"; "exposure": string; "currency"?: "USD" };
export type SpendReserve = { "action": "reserve" | "amend"; "binding": SpendBinding; "exposure": string; "turn_limit": string; "session_limit": string; "profile_limit": string };
export type SpendTransition = { "action": "uncertain" | "complete" | "no-send" | "status"; "binding": SpendBinding };

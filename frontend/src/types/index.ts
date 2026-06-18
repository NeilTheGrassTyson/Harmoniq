// Shared TypeScript types — extended as features are built.
// Types should mirror the Pydantic schemas defined in the backend.

export interface HealthResponse {
  status: string;
  version: string;
}

/**
 * Formatting utilities for numbers, miles, and locations.
 * To be implemented in Phase 5 / Phase 8.
 */

export function formatMiles(miles: number): string {
  return `${miles.toLocaleString(undefined, { maximumFractionDigits: 1 })} mi`;
}

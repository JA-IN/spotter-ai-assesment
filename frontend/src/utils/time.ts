/**
 * Time and duration formatting utilities.
 * To be implemented in Phase 5 / Phase 7.
 */

export function minutesToHoursAndMinutes(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${mins}m`;
}

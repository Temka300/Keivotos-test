export const SUITE_NAME = 'Keivotos';
export const MODULE_NAME = 'Waifu-Hoard';
export const MODULE_DISPLAY_NAME = MODULE_NAME.replace('-', ' ');
export const DISPLAY_NAME = `${SUITE_NAME} - ${MODULE_NAME}`;
export const DEFAULT_PROFILE_NAME = SUITE_NAME;

// This is a persistent compatibility identifier, not a display name. Renames
// must never change it or existing browser-local preferences would disappear.
export const STORAGE_PREFIX = 'waifu-hoard:';

export function persistentStorageKey(suffix: string): string {
  return `${STORAGE_PREFIX}${suffix}`;
}

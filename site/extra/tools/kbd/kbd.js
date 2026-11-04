// Windows layouts, plain + Shift rows; same index = same physical key.
const EN = "`qwertyuiop[]asdfghjkl;'zxcvbnm,./~QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?@#$^&|";
const RU = 'ёйцукенгшщзхъфывапролджэячсмитьбю.ЁЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,"№;:?/';

const zip = (from, to) => new Map([...from].map((c, i) => [c, to[i]]));
const EN_TO_RU = zip(EN, RU);
const RU_TO_EN = zip(RU, EN);

const convert = (map) => (text) =>
  Array.from(text, (c) => map.get(c) ?? c).join("");

export const toRu = convert(EN_TO_RU);
export const toEn = convert(RU_TO_EN);
export const LAYOUTS = { EN, RU };

// Drop keys of the other layout; neutral chars (digits, space, !-=…) stay.
const keep = (own, other) => (text) =>
  Array.from(text, (c) => (other.has(c) && !own.has(c) ? "" : c)).join("");

export const onlyEn = keep(EN_TO_RU, RU_TO_EN);
export const onlyRu = keep(RU_TO_EN, EN_TO_RU);

// Physical keyboard, unshifted EN keycaps.
export const KEY_ROWS = ["`1234567890-=", "qwertyuiop[]\\", "asdfghjkl;'", "zxcvbnm,./"];

const BASE = 34; // EN/RU: 34 plain keys, then their Shift variants, then extras
const SHIFT_DIGITS = { "@": "2", "#": "3", "$": "4", "^": "6", "&": "7", "|": "\\" };
const NEUTRAL_KEYS = new Set(KEY_ROWS.join(""));

/** Keycap (from KEY_ROWS) that produces `c` in `layout`, or null. */
export const keyOf = (c, layout) => {
  const i = layout.indexOf(c);
  if (i < 0) return NEUTRAL_KEYS.has(c) ? c : null;
  if (i < BASE) return EN[i];
  if (i < 2 * BASE) return EN[i - BASE];
  return SHIFT_DIGITS[EN[i]];
};

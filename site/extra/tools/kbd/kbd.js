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

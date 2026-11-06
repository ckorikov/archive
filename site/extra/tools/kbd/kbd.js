const charMap = (from, to) => new Map([...from].map((c, i) => [c, to[i]]));
const mapChars = (fn) => (text) => Array.from(text, fn).join("");

// Rows of the main block: base level, then Shift level, key for key.
const EN_ROWS = [
  "`1234567890-=",
  "qwertyuiop[]\\",
  "asdfghjkl;'",
  "zxcvbnm,./",
  "~!@#$%^&*()_+",
  "QWERTYUIOP{}|",
  'ASDFGHJKL:"',
  "ZXCVBNM<>?",
];
// Standard Russian layouts: https://unicode.org/cldr/charts/43/keyboards/layouts/ru.html
const RU_ROWS = {
  windows: [
    "ё1234567890-=",
    "йцукенгшщзхъ\\",
    "фывапролджэ",
    "ячсмитьбю.",
    'Ё!"№;%:?*()_+',
    "ЙЦУКЕНГШЩЗХЪ/",
    "ФЫВАПРОЛДЖЭ",
    "ЯЧСМИТЬБЮ,",
  ],
  mac: [
    "]1234567890-=",
    "йцукенгшщзхъё",
    "фывапролджэ",
    "ячсмитьбю/",
    '[!"№%:,.;()_+',
    "ЙЦУКЕНГШЩЗХЪЁ",
    "ФЫВАПРОЛДЖЭ",
    "ЯЧСМИТЬБЮ?",
  ],
};

/** Joins 8 rows into [base, shift] strings. */
const toLevels = (rows) => [rows.slice(0, 4).join(""), rows.slice(4).join("")];
const EN_US = toLevels(EN_ROWS);
const MAC_CHARS = { en: EN_US, ru: toLevels(RU_ROWS.mac) };
const WINDOWS_CHARS = { en: EN_US, ru: toLevels(RU_ROWS.windows) };

/** ISO puts a new key in place of the first one and moves that key's chars to the end. */
const toIso = (levels, newChars) =>
  levels.map((level, i) => newChars[i] + level.slice(1) + level[0]);

// PC ISO adds a key that repeats Backslash's chars, so only Apple ISO changes chars.
const APPLE_ISO_CHARS = {
  en: toIso(MAC_CHARS.en, "§±"),
  ru: toIso(MAC_CHARS.ru, "><"),
};

const PROFILES = [
  { platform: "macos", geometry: "iso", ...APPLE_ISO_CHARS },
  { platform: "macos", geometry: "ansi", ...MAC_CHARS },
  { platform: "windows", geometry: "iso", ...WINDOWS_CHARS },
  { platform: "windows", geometry: "ansi", ...WINDOWS_CHARS },
];

const PUNCTUATION_CODES = new Map(
  Object.entries({
    "`": "Backquote",
    "§": "Backquote",
    "-": "Minus",
    "=": "Equal",
    "[": "BracketLeft",
    "]": "BracketRight",
    "\\": "Backslash",
    ";": "Semicolon",
    "'": "Quote",
    ",": "Comma",
    ".": "Period",
    "/": "Slash",
  }),
);
const codeOfCap = (cap) =>
  PUNCTUATION_CODES.get(cap) ??
  (/\d/.test(cap) ? `Digit${cap}` : `Key${cap.toUpperCase()}`);

const ROW_LENGTHS = EN_ROWS.slice(0, 4).map((row) => row.length);

/** Splits base caps into the four rows; ISO's extra key cap is left over. */
const splitRows = (baseCaps) => {
  let start = 0;
  const rows = ROW_LENGTHS.map((length) =>
    baseCaps.slice(start, (start += length)),
  );
  return [...rows, baseCaps.slice(start)];
};

/**
 * Main block without modifiers; ISO adds the key left of Z and moves Backslash.
 * That key types the chars left after the rows (Apple) or Backslash's chars (PC).
 * Apple keyboards are compact: ANSI Backslash is a regular 1u key, and Space starts
 * after fn, control, option (1u) and command (1.25u) instead of PC's 3 × 1.25u.
 */
const buildKeys = (baseCaps, isIso, isApple) => {
  const keys = [];
  const addKey = (code, en, x, y, width = 1) =>
    keys.push({ code, en, x, y, width, height: 1 });
  const addRow = (caps, x, y) =>
    [...caps].forEach((cap, i) => addKey(codeOfCap(cap), cap, x + i, y));
  const [digits, top, home, bottom, isoExtra] = splitRows(baseCaps);
  const backslash = top.at(-1);
  addRow(digits, 0, 0);
  addRow(top.slice(0, -1), 1.5, 1);
  addRow(home, 1.75, 2);
  addKey(
    "Backslash",
    backslash,
    ...(isIso ? [12.75, 2] : [13.5, 1, isApple ? 1 : 1.5]),
  );
  if (isIso) addKey("IntlBackslash", isoExtra || backslash, 1.25, 3);
  addRow(bottom, 2.25, 3);
  addKey("Space", null, ...(isApple ? [4.25, 4, 5] : [3.75, 4, 6.25]));
  return keys;
};

// Mac browsers on ISO keyboards may swap these codes; the typed glyph decides.
const SWAPPABLE_CODES = ["Backquote", "IntlBackslash"];

/** One alphabet of a layout: its chars, conversion to the other one, and key caps. */
const createAlphabet = (chars, otherChars, caps) => {
  const own = new Set(chars);
  const foreign = new Set(otherChars);
  const converted = charMap(chars, otherChars);
  const capByChar = charMap(chars, caps);
  return {
    chars,
    convert: mapChars((c) => converted.get(c) ?? c),
    keepOwn: mapChars((c) => (foreign.has(c) && !own.has(c) ? "" : c)),
    keyOf: (c) => capByChar.get(c) ?? null,
  };
};

const createLayout = ({ platform, geometry, en, ru }) => {
  const isApple = platform === "macos";
  const isIso = geometry === "iso";
  // Both levels follow the base caps, so every char maps to its key cap.
  const [baseCaps] = en;
  const caps = baseCaps.repeat(2);
  const [enChars, ruChars] = [en, ru].map((levels) => levels.join(""));
  const alphabets = {
    en: createAlphabet(enChars, ruChars, caps),
    ru: createAlphabet(ruChars, enChars, caps),
  };

  const keys = buildKeys(baseCaps, isIso, isApple).map((key) => ({
    ...key,
    ru: key.en && alphabets.en.convert(key.en),
  }));
  const capByCode = new Map(keys.map((key) => [key.code, key.en]));
  const capOf = (code) => capByCode.get(code) ?? null;

  const swappableCodeByCap = new Map(
    SWAPPABLE_CODES.map((code) => [capOf(code), code]),
  );
  const pressedCode = ({ key, code }) => {
    if (!isApple || !isIso || !SWAPPABLE_CODES.includes(code)) return code;
    const cap = Object.values(alphabets)
      .map((alphabet) => alphabet.keyOf(key))
      .find((c) => swappableCodeByCap.has(c));
    return swappableCodeByCap.get(cap) ?? code;
  };

  const id = layoutId(platform, geometry);
  return { id, platform, geometry, keys, ...alphabets, capOf, pressedCode };
};

export const layoutId = (platform, geometry) => `${platform}-${geometry}`;

export const LAYOUTS = Object.fromEntries(
  PROFILES.map(createLayout).map((layout) => [layout.id, layout]),
);

/** Picks the layout for `navigator.platform`; macOS ISO when unknown. */
export const detectLayout = (platform = "") =>
  LAYOUTS[/^win/i.test(platform) ? "windows-ansi" : "macos-iso"];

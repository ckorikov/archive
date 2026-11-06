import { test } from "node:test";
import assert from "node:assert/strict";
import { LAYOUTS, detectLayout, layoutId } from "../../site/extra/tools/kbd/kbd.js";

const win = LAYOUTS["windows-ansi"];

test("words", () => {
  assert.equal(win.en.convert("ghbdtn"), "привет");
  assert.equal(win.ru.convert("руддщ"), "hello");
  assert.equal(win.en.convert("Ghbdtn? vbh!"), "Привет, мир!");
});

test("punctuation and shift", () => {
  assert.equal(win.en.convert("`~/?@#$^&|"), 'ёЁ.,"№;:?/');
  assert.equal(win.ru.convert("ё.,"), "`/?");
  assert.equal(win.en.convert("[]{};':\"<>"), "хъХЪжэЖЭБЮ");
});

test("unmapped chars pass through", () => {
  assert.equal(win.en.convert(""), "");
  assert.equal(win.en.convert("123 -= \n😀"), "123 -= \n😀");
  assert.equal(win.ru.convert("123 -= 😀"), "123 -= 😀");
});

test("mixed text keeps letters of the target layout", () => {
  assert.equal(win.en.convert("ghbdtn привет!"), "привет привет!");
  assert.equal(win.ru.convert("руддщ hello!"), "hello hello!");
});

test("fields keep only their layout and neutral characters", () => {
  for (const { en, ru } of Object.values(LAYOUTS)) {
    assert.equal(en.keepOwn("hiпривет 1!"), "hi 1!");
    assert.equal(ru.keepOwn("приhelloвет, мир!"), "привет, мир!");
    assert.equal(en.keepOwn(en.chars), en.chars);
    assert.equal(ru.keepOwn(ru.chars), ru.chars);
    assert.equal(en.keepOwn("123 -=\n😀"), "123 -=\n😀");
  }
  assert.equal(win.en.keepOwn('ё№"?/'), '"?/');
  assert.equal(win.ru.keepOwn("[]~@|"), "");
});

test("keyOf finds the physical key", () => {
  assert.equal(win.en.keyOf("q"), "q");
  assert.equal(win.en.keyOf("Q"), "q");
  assert.equal(win.ru.keyOf("й"), "q");
  assert.equal(win.ru.keyOf("Ё"), "`");
  assert.equal(win.en.keyOf('"'), "'"); // Shift+' in EN
  assert.equal(win.ru.keyOf('"'), "2"); // Shift+2 in RU
  assert.equal(win.ru.keyOf("?"), "7");
  assert.equal(win.ru.keyOf("/"), "\\");
  assert.equal(win.ru.keyOf(","), "/");
  assert.equal(win.ru.keyOf("5"), "5");
  assert.equal(win.en.keyOf("й"), null);
  assert.equal(win.en.keyOf(" "), null);
});

test("Windows neutral Shift symbols share keys in both alphabets", () => {
  for (const alphabet of [win.en, win.ru])
    for (const [symbol, key] of [["!", "1"], ["%", "5"], ["*", "8"], ["(", "9"], [")", "0"], ["_", "-"], ["+", "="]])
      assert.equal(alphabet.keyOf(symbol), key);
});

test("platform selects the standard macOS layout automatically", () => {
  const mac = detectLayout("MacIntel");
  assert.equal(mac.platform, "macos");
  assert.equal(detectLayout("macOS").id, "macos-iso");
  for (const platform of ["Win32", "Windows", "Win64"])
    assert.equal(detectLayout(platform).id, "windows-ansi");
  assert.equal(mac.en.convert("`~\\|/?"), "][ёЁ/?");
  assert.equal(mac.en.convert("@#$%^&*"), '"№%:,.;');
  assert.equal(mac.en.convert("Ghbdtn? vbh!"), "Привет? мир!");
  assert.equal(mac.ru.keyOf("ё"), "\\");
  assert.equal(mac.ru.keyOf("]"), "`");
  assert.equal(mac.ru.keepOwn("\\@[]ёЁ"), "[]ёЁ");
});

test("macOS is the default when the platform is missing or unrecognized", () => {
  for (const platform of [undefined, "", "unknown", "Linux x86_64", "Darwin"])
    assert.equal(detectLayout(platform).id, "macos-iso");
});

test("both platform layouts round trip every key and Shift character", () => {
  for (const { keys, en, ru } of Object.values(LAYOUTS)) {
    assert.equal(en.chars.length, ru.chars.length);
    assert.equal(new Set(en.chars).size, en.chars.length);
    assert.equal(new Set(ru.chars).size, ru.chars.length);
    assert.equal(ru.convert(en.convert(en.chars)), en.chars);
    assert.equal(en.convert(ru.convert(ru.chars)), ru.chars);
    const caps = new Set(keys.map((k) => k.en));
    for (const alphabet of [en, ru])
      for (const c of alphabet.chars) assert.ok(caps.has(alphabet.keyOf(c)), c);
  }
});

test("physical key highlighting does not depend on alphabet or field", () => {
  const { capOf } = win;
  assert.equal(capOf("KeyQ"), "q");
  assert.equal(capOf("Digit2"), "2");
  assert.equal(capOf("Backquote"), "`");
  assert.equal(capOf("Backslash"), "\\");
  assert.equal(capOf("Slash"), "/");
  assert.equal(capOf("IntlBackslash"), null); // no such key on ANSI
  assert.equal(capOf("ShiftLeft"), null);
  assert.equal(capOf("Numpad1"), null);
  assert.equal(capOf(""), null);
});

test("keyboard geometry has aligned rows and no overlapping keys", () => {
  for (const { keys, geometry } of Object.values(LAYOUTS)) {
    const codes = keys.map((k) => k.code);
    assert.equal(new Set(codes).size, codes.length);
    for (const a of keys) {
      assert.ok(a.x >= 0 && a.y >= 0 && a.x + a.width <= 15 && a.y + a.height <= 5);
      for (const b of keys) {
        if (a === b) continue;
        const overlap = a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
        assert.equal(overlap, false, `${geometry}: ${a.code} overlaps ${b.code}`);
      }
    }
    const key = (code) => keys.find((k) => k.code === code);
    assert.equal(key("KeyQ").x, 1.5);
    assert.equal(key("KeyA").x, 1.75);
    assert.equal(key("KeyZ").x, 2.25);
    assert.equal(key("Enter"), undefined);
    assert.equal(key("Tab"), undefined);
    assert.equal(key("ShiftLeft"), undefined);
    assert.equal(keys.length, geometry === "iso" ? 49 : 48);
    assert.equal(key("Backslash").y, geometry === "iso" ? 2 : 1);
    assert.equal(Boolean(key("IntlBackslash")), geometry === "iso");
  }
});

test("Mac ISO extra key converts symbols and filters the opposite layout", () => {
  const mac = LAYOUTS["macos-iso"];
  assert.equal(mac.en.convert("§±`~"), "><][");
  assert.equal(mac.ru.convert("><]["), "§±`~");
  assert.equal(mac.en.keepOwn("§±№ё"), "§±");
  assert.equal(mac.ru.keepOwn("><§±"), "><");
});

test("Mac ISO places section next to 1 and backtick next to Z", () => {
  const key = (glyph) => LAYOUTS["macos-iso"].keys.find((k) => k.en === glyph);
  assert.equal(key("§").y, key("1").y);
  assert.equal(key("§").x + key("§").width, key("1").x);
  assert.equal(key("`").y, key("z").y);
  assert.equal(key("`").x + key("`").width, key("z").x);
});

test("named profiles select their geometry and conversions", () => {
  const { "macos-iso": iso, "macos-ansi": ansi } = LAYOUTS;
  assert.equal(iso.geometry, "iso");
  assert.equal(ansi.geometry, "ansi");
  assert.equal(win.geometry, "ansi");
  assert.equal(ansi.en.convert("`"), "]");
});

test("Mac ISO highlights symbols correctly even when browser swaps key codes", () => {
  const { pressedCode } = LAYOUTS["macos-iso"];
  for (const key of ["`", "~"])
    assert.equal(pressedCode({ key, code: "Backquote" }), "IntlBackslash");
  for (const key of ["§", "±"])
    assert.equal(pressedCode({ key, code: "IntlBackslash" }), "Backquote");
  for (const key of ["]", "["])
    assert.equal(pressedCode({ key, code: "Backquote" }), "IntlBackslash");
  for (const key of [">", "<"])
    assert.equal(pressedCode({ key, code: "IntlBackslash" }), "Backquote");
  assert.equal(pressedCode({ key: "]", code: "BracketRight" }), "BracketRight");
  assert.equal(pressedCode({ key: ">", code: "Period" }), "Period");
  assert.equal(pressedCode({ key: "й", code: "KeyQ" }), "KeyQ");
  assert.equal(win.pressedCode({ key: "`", code: "Backquote" }), "Backquote");
});

test("Apple ISO Russian rows match the MacBook keyboard", () => {
  const rows = [0, 1, 2, 3].map((y) => LAYOUTS["macos-iso"].keys
    .filter((k) => k.y === y)
    .sort((a, b) => a.x - b.x)
    .map((k) => k.ru)
    .join(""));
  assert.deepEqual(rows, [
    ">1234567890-=",
    "йцукенгшщзхъ",
    "фывапролджэё",
    "]ячсмитьбю/",
  ]);
});

test("Apple ANSI Backslash is a regular key, Windows ANSI has a wide one", () => {
  const backslash = (layout) => {
    const { x, y, width } = layout.keys.find((key) => key.code === "Backslash");
    return { x, y, width };
  };
  assert.deepEqual(backslash(LAYOUTS["macos-ansi"]), { x: 13.5, y: 1, width: 1 });
  assert.deepEqual(backslash(win), { x: 13.5, y: 1, width: 1.5 });
});

test("Space follows the platform's bottom row", () => {
  const space = (layout) => {
    const { x, width } = layout.keys.find((key) => key.code === "Space");
    return { x, width };
  };
  assert.deepEqual(space(win), { x: 3.75, width: 6.25 }); // Ctrl, Win, Alt: 1.25u each
  for (const id of ["macos-iso", "macos-ansi"])
    assert.deepEqual(space(LAYOUTS[id]), { x: 4.25, width: 5 }); // fn, control, option, command
});

test("Windows ISO repeats Backslash on the extra key and keeps PC geometry", () => {
  const winIso = LAYOUTS["windows-iso"];
  const key = (code) => winIso.keys.find((k) => k.code === code);
  assert.equal(winIso.en.chars, win.en.chars);
  assert.equal(winIso.ru.chars, win.ru.chars);
  assert.equal(key("Backquote").en, "`");
  assert.equal(key("IntlBackslash").en, "\\");
  assert.deepEqual([key("Backslash").x, key("Backslash").y], [12.75, 2]);
  assert.deepEqual([key("Space").x, key("Space").width], [3.75, 6.25]);
  assert.equal(winIso.pressedCode({ key: "\\", code: "IntlBackslash" }), "IntlBackslash");
  assert.equal(winIso.pressedCode({ key: "`", code: "Backquote" }), "Backquote");
});

test("layout ids combine platform and geometry", () => {
  assert.deepEqual(Object.keys(LAYOUTS).sort(),
    ["macos-ansi", "macos-iso", "windows-ansi", "windows-iso"]);
  for (const [id, { platform, geometry }] of Object.entries(LAYOUTS))
    assert.equal(layoutId(platform, geometry), id);
});

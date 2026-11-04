import { test } from "node:test";
import assert from "node:assert/strict";
import { toRu, toEn, onlyEn, onlyRu, keyOf, KEY_ROWS, LAYOUTS } from "../../site/extra/tools/kbd/kbd.js";

test("words", () => {
  assert.equal(toRu("ghbdtn"), "привет");
  assert.equal(toEn("руддщ"), "hello");
  assert.equal(toRu("Ghbdtn? vbh!"), "Привет, мир!");
});

test("punctuation and shift", () => {
  assert.equal(toRu("`~/?@#$^&|"), 'ёЁ.,"№;:?/');
  assert.equal(toEn("ё.,"), "`/?");
  assert.equal(toRu("[]{};':\"<>"), "хъХЪжэЖЭБЮ");
});

test("layouts are a bijection", () => {
  const { EN, RU } = LAYOUTS;
  assert.equal(EN.length, RU.length);
  assert.equal(new Set(EN).size, EN.length);
  assert.equal(new Set(RU).size, RU.length);
  assert.equal(toEn(toRu(EN)), EN);
  assert.equal(toRu(toEn(RU)), RU);
});

test("unmapped chars pass through", () => {
  assert.equal(toRu(""), "");
  assert.equal(toRu("123 -= \n😀"), "123 -= \n😀");
  assert.equal(toEn("123 -= 😀"), "123 -= 😀");
});

test("only own layout is kept", () => {
  assert.equal(onlyEn("hiпривет 1!"), "hi 1!");
  assert.equal(onlyRu("приhelloвет, мир!"), "привет, мир!");
  assert.equal(onlyEn('ё№"?/'), '"?/');
  assert.equal(onlyRu("[]~@|"), "");
  assert.equal(onlyEn(LAYOUTS.EN), LAYOUTS.EN);
  assert.equal(onlyRu(LAYOUTS.RU), LAYOUTS.RU);
  assert.equal(onlyEn("123 -=\n😀"), "123 -=\n😀");
});

test("keyOf finds the physical key", () => {
  const { EN, RU } = LAYOUTS;
  assert.equal(keyOf("q", EN), "q");
  assert.equal(keyOf("Q", EN), "q");
  assert.equal(keyOf("й", RU), "q");
  assert.equal(keyOf("Ё", RU), "`");
  assert.equal(keyOf('"', EN), "'"); // Shift+' in EN
  assert.equal(keyOf('"', RU), "2"); // Shift+2 in RU
  assert.equal(keyOf("?", RU), "7");
  assert.equal(keyOf("/", RU), "\\");
  assert.equal(keyOf(",", RU), "/");
  assert.equal(keyOf("5", RU), "5");
  assert.equal(keyOf("й", EN), null);
  assert.equal(keyOf(" ", EN), null);
});

test("every layout char maps to a keycap", () => {
  const keys = new Set(KEY_ROWS.join(""));
  for (const layout of Object.values(LAYOUTS))
    for (const c of layout) assert.ok(keys.has(keyOf(c, layout)), c);
});

import { test } from "node:test";
import assert from "node:assert/strict";
import { toRu, toEn, onlyEn, onlyRu, LAYOUTS } from "../../site/extra/tools/kbd/kbd.js";

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

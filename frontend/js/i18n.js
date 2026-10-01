// i18n: polski to język źródłowy (teksty w kodzie i w index.html), angielski to słownik locales/en.js.
//
// Zasady (pilnuje ich scripts/check_i18n.mjs w CI):
// - tekst w JS: t("Polski tekst {param}", { param }) – klucz zawsze stałym napisem, bez template literal,
// - stałe z etykietami: N_("Etykieta") (oznacza do tłumaczenia), tłumaczone przy użyciu: t(STAŁA[x]),
// - odmiana: plural(n, "dzień", "dni", "dni") – w en.js wpis "dzień|dni|dni": ["day", "days"],
// - statyczny tekst i atrybuty (placeholder, aria-label, title, alt) w index.html tłumaczy applyTranslations().
import { EN } from "./locales/en.js";

export const LANGUAGES = ["pl", "en"];
const STORAGE_KEY = "calico.lang";
const LOCALES = { pl: "pl-PL", en: "en-GB" };
const TRANSLATED_ATTRIBUTES = ["placeholder", "aria-label", "title", "alt"];

let current = initialLanguage();

function initialLanguage() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (LANGUAGES.includes(saved)) return saved;
  } catch {
    // brak dostępu do storage
  }
  return (navigator.language || "pl").toLowerCase().startsWith("pl") ? "pl" : "en";
}

export function lang() {
  return current;
}

export function locale() {
  return LOCALES[current];
}

export function N_(text) {
  return text;
}

export function t(text, params) {
  const template = current === "pl" ? text : EN[text] ?? text;
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name) => (name in params ? String(params[name]) : match));
}

export function plural(count, one, few, many) {
  if (current !== "pl") {
    const forms = EN[`${one}|${few}|${many}`];
    if (forms) return count === 1 ? forms[0] : forms[1];
  }
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (count === 1) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

// --- statyczny HTML -------------------------------------------------------------------------------

// Polskie oryginały zapamiętane przy pierwszym przejściu - przełączanie języka zawsze tłumaczy z oryginału.
// Obejmuje tylko statyczny DOM z index.html; teksty wstawiane przez JS idą przez t() przy renderowaniu.
let staticTexts = null;

function collectStatic() {
  const texts = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const parent = node.parentElement;
    if (!parent || parent.closest("script, style, svg, [data-i18n-skip]")) continue;
    const source = node.nodeValue.trim();
    if (/\p{L}/u.test(source)) texts.push({ node, source });
  }
  const attributes = [];
  document.body.querySelectorAll("*").forEach((element) => {
    if (element.closest("[data-i18n-skip]")) return;
    TRANSLATED_ATTRIBUTES.forEach((name) => {
      const source = element.getAttribute(name);
      if (source && /\p{L}/u.test(source)) attributes.push({ element, name, source });
    });
  });
  return { texts, attributes, title: document.title };
}

export function applyTranslations() {
  staticTexts ??= collectStatic();
  staticTexts.texts.forEach(({ node, source }) => {
    const [, lead, , trail] = /^(\s*)([\s\S]*?)(\s*)$/.exec(node.nodeValue);
    node.nodeValue = `${lead}${t(source)}${trail}`;
  });
  staticTexts.attributes.forEach(({ element, name, source }) => element.setAttribute(name, t(source)));
  document.title = t(staticTexts.title);
  document.documentElement.lang = current;
}

const listeners = new Set();

export function onLanguageChange(listener) {
  listeners.add(listener);
}

export function setLanguage(language) {
  if (!LANGUAGES.includes(language) || language === current) return;
  current = language;
  try {
    localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // brak dostępu do storage - język tylko do końca sesji karty
  }
  applyTranslations();
  listeners.forEach((listener) => listener(language));
}

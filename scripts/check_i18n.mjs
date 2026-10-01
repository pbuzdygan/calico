#!/usr/bin/env node
// Straznik tlumaczen frontendu (CI + scripts/check.sh). Bledy:
// - tekst z t("...") / N_("...") / plural(...) albo statyczny tekst / atrybut w index.html bez wpisu w locales/en.js,
// - nieuzywane wpisy w locales/en.js,
// - rozne parametry {nazwa} w kluczu i tlumaczeniu, polskie znaki w tlumaczeniu EN,
// - napis z polskimi znakami w JS poza t()/N_()/plural(), t() z template literal zawierajacym ${...}.
// Uzycie: node scripts/check_i18n.mjs            (raport)
//         node scripts/check_i18n.mjs --missing  (same brakujace klucze jako JSON - do uzupelnienia slownika)
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const FRONTEND = join(ROOT, "frontend");
const JS_DIR = join(FRONTEND, "js");
const POLISH = /[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]/;
// Polskie słowa bez znaków diakrytycznych (np. "Kalorie dziennie na tle celu") – heurystyka dla napisów poza t().
const POLISH_WORDS = /\b(dni|dzien|nie|jest|albo|lub|oraz|dla|przez|bez|na tle|celu|wpis|wpisy|brak|dodaj|zapisz|pomiar|pomiary|tydz|kalorie|waga|cel)\b/i;
// Tekst widoczny dla uzytkownika: tresc poza tagami + wartosci atrybutow aria-label/title/placeholder/alt.
const visibleText = (value) =>
  value
    .replace(/<[^>]*>/g, (tag) => ` ${[...tag.matchAll(/(?:aria-label|title|placeholder|alt)="([^"]*)"/g)].map((match) => match[1]).join(" ")} `)
    .replace(/\$\{\}/g, " ");
const LETTER = /\p{L}/u;

const { EN } = await import(pathToFileURL(join(JS_DIR, "locales", "en.js")).href);

function jsFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "locales" ? [] : jsFiles(path);
    return name.endsWith(".js") && name !== "i18n.js" ? [path] : [];
  });
}

// --- prosty tokenizer JS: napisy, template literals (z ${...}), komentarze, wyrazenia regularne -------------

function tokenize(src) {
  const tokens = [];
  let i = 0;
  const push = (type, value, start) => tokens.push({ type, value, start, end: i });
  const regexAllowed = () => {
    const prev = [...tokens].reverse().find((token) => token.type !== "comment");
    return !prev || (prev.type === "punct" && !")]}".includes(prev.value)) || (prev.type === "word" && ["return", "typeof", "case"].includes(prev.value));
  };
  function readString(quote) {
    const start = i;
    i += 1;
    let value = "";
    while (src[i] !== quote) {
      if (src[i] === "\\") {
        const next = src[i + 1];
        value += next === "n" ? "\n" : next === "t" ? "\t" : next;
        i += 2;
      } else {
        value += src[i];
        i += 1;
      }
    }
    i += 1;
    push("string", value, start);
  }
  function readTemplate() {
    const start = i;
    i += 1;
    let value = "";
    let dynamic = false;
    while (src[i] !== "`") {
      if (src[i] === "\\") {
        value += src[i + 1] === "n" ? "\n" : src[i + 1];
        i += 2;
      } else if (src[i] === "$" && src[i + 1] === "{") {
        dynamic = true;
        i += 2;
        let depth = 1;
        const inner = i;
        const mark = tokens.length; // napisy z wnetrza ${...} zbiera ponizej tokenize(inner) - bez duplikatow
        while (depth) {
          if (src[i] === "`") {
            readTemplate();
            continue;
          }
          if (src[i] === '"' || src[i] === "'") {
            readString(src[i]);
            continue;
          }
          if (src[i] === "{") depth += 1;
          if (src[i] === "}") depth -= 1;
          i += 1;
        }
        tokens.length = mark;
        tokens.push(...tokenize(src.slice(inner, i - 1)).map((token) => ({ ...token, start: token.start + inner, end: token.end + inner })));
        value += "${}";
      } else {
        value += src[i];
        i += 1;
      }
    }
    i += 1;
    push(dynamic ? "template" : "string", value, start);
  }
  while (i < src.length) {
    const c = src[i];
    const start = i;
    if (/\s/.test(c)) {
      i += 1;
    } else if (src.startsWith("//", i)) {
      i = src.indexOf("\n", i) === -1 ? src.length : src.indexOf("\n", i);
      push("comment", "", start);
    } else if (src.startsWith("/*", i)) {
      i = src.indexOf("*/", i) + 2;
      push("comment", "", start);
    } else if (c === '"' || c === "'") {
      readString(c);
    } else if (c === "`") {
      readTemplate();
    } else if (c === "/" && regexAllowed()) {
      i += 1;
      let inClass = false;
      while (inClass || src[i] !== "/") {
        if (src[i] === "\\") i += 1;
        else if (src[i] === "[") inClass = true;
        else if (src[i] === "]") inClass = false;
        i += 1;
      }
      i += 1;
      while (/[a-z]/i.test(src[i] || "")) i += 1;
      push("regex", "", start);
    } else if (/[\w$]/.test(c)) {
      while (/[\w$]/.test(src[i] || "")) i += 1;
      push("word", src.slice(start, i), start);
    } else {
      i += 1;
      push("punct", c, start);
    }
  }
  return tokens;
}

function lineOf(src, index) {
  return src.slice(0, index).split("\n").length;
}

// Argumenty wywolania od tokenu "(" - zwraca liste argumentow (listy tokenow) na najwyzszym poziomie.
function callArguments(tokens, open) {
  const args = [[]];
  let depth = 0;
  for (let k = open + 1; k < tokens.length; k += 1) {
    const token = tokens[k];
    if (token.type === "punct" && "([{".includes(token.value)) depth += 1;
    if (token.type === "punct" && ")]}".includes(token.value)) {
      if (depth === 0) return { args, close: k };
      depth -= 1;
    }
    if (token.type === "punct" && token.value === "," && depth === 0) args.push([]);
    else args[args.length - 1].push(token);
  }
  return { args, close: tokens.length };
}

const used = new Map(); // klucz -> pierwsze wystapienie
const errors = [];

function use(key, where, kind = "text") {
  if (!used.has(key)) used.set(key, { where, kind });
}

for (const file of jsFiles(JS_DIR)) {
  const src = readFileSync(file, "utf8");
  const name = relative(ROOT, file);
  const tokens = tokenize(src);
  const translated = new Set();
  tokens.forEach((token, index) => {
    if (token.type !== "word" || !["t", "N_", "plural"].includes(token.value)) return;
    const before = tokens[index - 1];
    const open = tokens[index + 1];
    if ((before && before.type === "punct" && before.value === ".") || !open || open.value !== "(") return;
    // definicje funkcji (function t(...)) i importy pomijamy
    if (before && before.type === "word" && ["function", "import", "export"].includes(before.value)) return;
    const { args } = callArguments(tokens, index + 1);
    const where = `${name}:${lineOf(src, token.start)}`;
    if (token.value === "plural") {
      const forms = args.slice(1, 4).map((arg) => arg.find((item) => item.type === "string"));
      if (forms.every(Boolean)) {
        use(forms.map((form) => form.value).join("|"), where, "plural");
        forms.forEach((form) => translated.add(form));
      } else {
        errors.push(`${where}: plural() wymaga trzech stalych napisow (forma 1 / 2-4 / 5+)`);
      }
      return;
    }
    const first = args[0] || [];
    first.forEach((item) => {
      if (item.type === "template") errors.push(`${where}: ${token.value}() z template literal – uzyj stalego napisu z {parametrami}`);
      // napisy w pierwszym argumencie (takze galezie warunku); pomijamy te w zagniezdzonych wywolaniach
    });
    let depth = 0;
    for (const item of first) {
      if (item.type === "punct" && "([{".includes(item.value)) depth += 1;
      if (item.type === "punct" && ")]}".includes(item.value)) depth -= 1;
      if (item.type === "string" && depth === 0) {
        use(item.value, where);
        translated.add(item);
      }
    }
  });
  // polskie napisy poza t()/N_()/plural()
  const nested = new Set();
  tokens.forEach((token, index) => {
    if (token.type === "word" && ["t", "N_", "plural"].includes(token.value) && tokens[index + 1]?.value === "(") {
      const { close } = callArguments(tokens, index + 1);
      for (let k = index + 2; k < close; k += 1) nested.add(tokens[k]);
    }
  });
  tokens.forEach((token) => {
    const text = token.type === "string" || token.type === "template" ? visibleText(token.value) : "";
    if (text && (POLISH.test(text) || POLISH_WORDS.test(text)) && !translated.has(token) && !nested.has(token)) {
      errors.push(`${name}:${lineOf(src, token.start)}: polski tekst poza t(): ${JSON.stringify(token.value.slice(0, 70))}`);
    }
  });
}

// --- index.html: tekst i atrybuty tlumaczone przez applyTranslations() ------------------------------------

const ENTITIES = { nbsp: " ", amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", "#39": "'" };
const decode = (text) => text.replace(/&(#\d+|#x[0-9a-f]+|\w+);/gi, (match, code) => ENTITIES[code] ?? (code[0] === "#" ? String.fromCodePoint(code[1] === "x" ? parseInt(code.slice(2), 16) : Number(code.slice(1))) : match));

const html = readFileSync(join(FRONTEND, "index.html"), "utf8");
const body = html
  .replace(/<!--[\s\S]*?-->/g, "")
  .replace(/<script[\s\S]*?<\/script>/gi, "")
  .replace(/<style[\s\S]*?<\/style>/gi, "")
  .replace(/<svg[\s\S]*?<\/svg>/gi, (svg) => svg.replace(/>[^<]*</g, "><"))
  .replace(/(<[^>]*\sdata-i18n-skip[^>]*>)[^<]*/g, "$1"); // elementy pomijane przez applyTranslations()
for (const match of body.matchAll(/>([^<]+)</g)) {
  const text = decode(match[1]).trim();
  if (LETTER.test(text)) use(text, `index.html:${lineOf(body, match.index)}`);
}
for (const match of body.matchAll(/\s(placeholder|aria-label|title|alt)="([^"]*)"/g)) {
  const text = decode(match[2]).trim();
  if (LETTER.test(text)) use(text, `index.html:${lineOf(body, match.index)} [${match[1]}]`);
}

// --- porownanie ze slownikiem -----------------------------------------------------------------------------

const params = (text) => new Set([...String(text).matchAll(/\{(\w+)\}/g)].map((match) => match[1]));
const missing = [...used].filter(([key]) => !(key in EN));
if (process.argv.includes("--missing")) {
  console.log(JSON.stringify(Object.fromEntries(missing.map(([key, info]) => [key, info.kind === "plural" ? ["", ""] : ""])), null, 2));
  process.exit(0);
}
missing.forEach(([key, info]) => errors.push(`${info.where}: brak tlumaczenia EN: ${JSON.stringify(key)}`));
Object.keys(EN)
  .filter((key) => !used.has(key))
  .forEach((key) => errors.push(`locales/en.js: nieuzywany wpis: ${JSON.stringify(key)}`));
for (const [key, value] of Object.entries(EN)) {
  const values = Array.isArray(value) ? value : [value];
  if (key.includes("|") !== Array.isArray(value) || (Array.isArray(value) && value.length !== 2)) {
    errors.push(`locales/en.js: ${JSON.stringify(key)} – odmiana to "forma1|forma2|forma5": ["one", "other"]`);
  }
  for (const item of values) {
    if (typeof item !== "string" || !item) errors.push(`locales/en.js: pusty wpis dla ${JSON.stringify(key)}`);
    else if (POLISH.test(item)) errors.push(`locales/en.js: polskie znaki w tlumaczeniu ${JSON.stringify(item)}`);
    else if ([...params(key)].sort().join() !== [...params(item)].sort().join()) errors.push(`locales/en.js: rozne parametry: ${JSON.stringify(key)} -> ${JSON.stringify(item)}`);
  }
}

if (errors.length) {
  console.error(errors.join("\n"));
  console.error(`\ni18n: ${errors.length} ${errors.length === 1 ? "blad" : "bledow"} (kluczy w uzyciu: ${used.size}, w en.js: ${Object.keys(EN).length})`);
  process.exit(1);
}
console.log(`i18n OK: ${used.size} tekstow, wszystkie przetlumaczone na EN`);

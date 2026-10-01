import { N_ } from "./i18n.js";

export const API_BASE = "/api";

// Etykiety oznaczone N_() - tłumaczone przy użyciu: t(TYPE_LABELS[type]).

// --- stałe domenowe ------------------------------------------------------------------------------

export const TYPE_LABELS = {
  breakfast: N_("Śniadanie"),
  lunch: N_("Obiad"),
  dinner: N_("Kolacja"),
  snack: N_("Przekąska"),
  daily_balance: N_("Bilans dnia"),
  weight: N_("Waga"),
  waist: N_("Obwód pasa"),
};

export const GOAL_LABELS = { cut: N_("Redukcja"), maintain: N_("Utrzymanie"), bulk: N_("Masa") };
export const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"];
export const MEAL_GROUP_LABELS = { breakfast: N_("Śniadanie"), lunch: N_("Obiad"), dinner: N_("Kolacja"), snack: N_("Przekąski") };
export const MEASUREMENT_FIELD = { weight: "weight_kg", waist: "waist_cm" };
export const MACRO_FIELDS = ["kcal", "carbs_g", "fat_g", "protein_g"];
export const FIELD_LABELS = {
  kcal: N_("Kalorie"),
  carbs_g: N_("Węglowodany"),
  fat_g: N_("Tłuszcze"),
  protein_g: N_("Białko"),
  weight_kg: N_("Waga"),
  waist_cm: N_("Obwód pasa"),
};

export const MACROS = [
  { field: "total_protein_g", targetField: "target_protein_g", key: "protein_g", label: N_("Białko"), kcalPerGram: 4, cls: "protein", max: 500 },
  { field: "total_carbs_g", targetField: "target_carbs_g", key: "carbs_g", label: N_("Węglowodany"), kcalPerGram: 4, cls: "carbs", max: 1000 },
  { field: "total_fat_g", targetField: "target_fat_g", key: "fat_g", label: N_("Tłuszcze"), kcalPerGram: 9, cls: "fat", max: 400 },
];

// Dzień "w celu": spożycie w granicach ±10% celu kcal dnia (regularność liczona tylko z dni z jedzeniem).
export const ADHERENCE_TOLERANCE = 0.1;
export const RING_CIRCUMFERENCE = 2 * Math.PI * 84;

export const TEXT_TEMPLATES = {
  weight: N_("Waga: 82,4 kg"),
  waist: N_("Obwód pasa: 91 cm"),
  breakfast: N_("Śniadanie\nIlość kalorii: 540\nWęglowodany: 48\nTłuszcze: 18\nBiałko: 32"),
  lunch: N_("Obiad\nIlość kalorii: 720\nWęglowodany: 62\nTłuszcze: 24\nBiałko: 45"),
  dinner: N_("Kolacja\nIlość kalorii: 610\nWęglowodany: 40\nTłuszcze: 22\nBiałko: 38"),
  snack: N_("Przekąska\nIlość kalorii: 240\nWęglowodany: 20\nTłuszcze: 10\nBiałko: 12"),
  daily_balance: N_("Bilans dnia\nIlość kalorii: 2150\nWęglowodany: 210\nTłuszcze: 70\nBiałko: 145"),
};

export const ENTRY_HINTS = {
  daily_balance: N_("Bilans dnia zastępuje sumę wszystkich posiłków z tego dnia. Może być jeden na dzień."),
  weight: N_("Jeden pomiar na dzień – nowy wpis nadpisuje poprzedni. Cel kcal nie zmienia się automatycznie."),
  waist: N_("Jeden pomiar na dzień – nowy wpis nadpisuje poprzedni."),
};

export const VIEWS = ["today", "log", "progress", "goals", "settings"];


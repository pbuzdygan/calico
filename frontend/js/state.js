import { defaultMealType, monthStartISO, todayISO } from "./util.js";

// --- elementy ------------------------------------------------------------------------------------

export const $ = (id) => document.getElementById(id);
export const el = new Proxy({}, { get: (cache, id) => (cache[id] ??= $(id)) });

export const state = {
  userId: null,
  userName: "",
  token: "",
  tokenExpiresAt: "",
  view: "today",
  logDate: todayISO(),
  progressQuery: { kind: "days", days: 30 },
  entryType: defaultMealType(),
  entrySheet: { mode: "add", entry: null },
  actionEntry: null,
  dateContext: null,
  planSuggestion: null,
  calMonth: monthStartISO(todayISO()),
  entriesById: new Map(),
  goalType: null,
  lastProgress: null,
  historyExpanded: false,
};


import { el } from "./state.js";

// --- powiadomienia i blokada przycisków --------------------------------------------------------

export function toast(text, variant = "info", timeoutMs = 5000) {
  const item = document.createElement("div");
  item.className = `toast ${variant}`;
  item.setAttribute("role", variant === "error" ? "alert" : "status");
  item.textContent = text;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "toast-close";
  close.setAttribute("aria-label", "Zamknij");
  close.textContent = "×";
  close.addEventListener("click", () => item.remove());
  item.appendChild(close);
  el.toastRegion.appendChild(item);
  while (el.toastRegion.children.length > 3) el.toastRegion.firstElementChild.remove();
  if (timeoutMs > 0) setTimeout(() => item.remove(), timeoutMs);
}

export function toastError(error) {
  toast(error?.message || String(error), "error", 9000);
}

export async function withBusy(button, action) {
  if (button?.disabled) return undefined;
  if (button) {
    button.disabled = true;
    button.classList.add("is-busy");
  }
  try {
    return await action();
  } finally {
    if (button) {
      button.classList.remove("is-busy");
      button.disabled = false;
    }
  }
}

// --- dolne panele (dialog) ------------------------------------------------------------------------

export function openSheet(dialog) {
  if (!dialog.open) dialog.showModal();
}

export function closeSheet(dialog) {
  if (dialog.open) dialog.close();
}

document.querySelectorAll("dialog.sheet").forEach((dialog) => {
  dialog.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => closeSheet(dialog)));
  // Klik w tło zamyka panel (poza wymuszonym uzupełnieniem profilu).
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog && dialog.id !== "onboardingDialog") closeSheet(dialog);
  });
});


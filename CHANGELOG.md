# Changelog

All notable changes to CALICO are listed here, newest first, described from the user's point of view: what you can do now that you couldn't before, and what works better.

## [Unreleased]

### New Features

- **Ready-made images for your server.** CALICO is now published as a container image for regular PCs and servers (amd64) and for ARM devices such as a Raspberry Pi 4 or 5 (arm64). You no longer have to build it yourself: download the compose file, run one command, and upgrade later with `docker compose pull`. Choose a stable version, or the development channel if you want to try new things early.

### Improvements

- **Safer to run on your network or the internet.** The server components were updated to fix known security issues. The app now refuses oversized requests, sends stricter browser security rules and reveals less about itself. The container runs with the minimum permissions it needs, so even a flaw in the app could not change its own files.
- **Choose which user the app runs as.** Set `PUID` and `PGID` to your own user and group, and the app's data files get the same owner as the rest of your files – no more permission problems when you keep the data in a folder on your server.
- **Clearer setup.** Every setting in the example configuration file is explained in plain words, with recommendations for instances reachable from the internet. Settings that did nothing have been removed.

## [0.1.0] – 2026-10-01

The first versioned release. Compared with the initial alpha (September 2026), CALICO has a new look, a guided plan that tells you whether your diet is working, your own data backup, and an English version.

### New Features

- **A completely new look.** A dark, phone-friendly design with a calorie ring that shows at a glance how much of today's target you've eaten. The app is organised into five sections: Today, Log, Progress, Goals and Settings. On a computer the menu moves to the side.
- **Install it like an app.** Add CALICO to your phone's home screen and it opens full-screen with its own icon. It never needs an internet connection; everything, including fonts, comes from your own server.
- **Add meals with a simple form.** No need to remember the text format anymore: pick the meal type and fill in calories and macros. Pasting text templates still works if you prefer it.
- **Calendar in the Log.** See at a glance which days have food entries and which have only measurements, and tap a day to open it.
- **More ways to fix entries.** Edit, duplicate or move any entry to another day. You can also undo the last change or clear a whole day, and both act on the day you're looking at.
- **Progress charts.** Follow your weight (with a 7-day trend line that smooths out daily ups and downs), your waist and your calories against your target. See how consistent your week was. Choose 1 month, 3 months, 6 months, 1 year, everything or your own range, and tap any day to jump straight to it in the Log.
- **Plan review: is my diet working?** CALICO compares your actual weight trend with the pace your plan expects. If you're on track, it tells you so and leaves your target alone. Only when the trend has been off for long enough does it suggest a small, safe correction (100–200 kcal), and it never changes anything without your approval.
- **Macro targets.** Protein, fat and carbs targets in grams are worked out automatically from your calorie target, or you can set your own. Progress bars on Today show how close you are.
- **Target weight with a forecast.** Set the weight you're aiming for, and CALICO estimates when you'll reach it based on your recent progress.
- **Bring your history with you.** If you've been dieting since before you started using CALICO, set the date your plan really began. Forecasts and charts then use your earlier weigh-ins, including imported ones.
- **Export and import your data (your backup).** Download all your days as a simple spreadsheet file, one row per day. You can also download a blank template, fill it in with past data in Excel or another spreadsheet app, and import it. Days you've already logged are never overwritten. If the file has mistakes, nothing is imported and you get a list of the rows to fix.
- **Polish and English.** Switch the language on the login screen or in Settings. Your choice is remembered on the device and on your account. Text templates and spreadsheet files work in both languages.
- **Change your PIN** in Settings.
- **Stay signed in.** Unlock once with your PIN and you stay signed in in that browser tab for 12 hours, even if your phone puts the browser to sleep. Use the Log out button in the menu when you're done.

### Improvements

- **Your profile comes first.** New users are guided through a short profile setup (sex, age, height, weight, activity and goal) before they start, so the calorie target is calculated from real data rather than placeholder values. A live preview shows your target and whether it's a deficit or a surplus before you save.
- **Your own account from the start.** On first launch you create your own user and PIN. There is no shared default account with a guessable PIN anymore.
- **Better protection against PIN guessing.** After 5 wrong PINs the account is locked for a few minutes, and the lock gets longer with every further series of wrong attempts. The message tells you how many attempts you have left.
- **Control who can create accounts.** The owner can switch off new account creation so that nobody else on the home network can add users.
- **Changing your goal updates the days ahead too.** When your calorie target changes, today and any future days you've already planned follow the new target, while past days keep the target they had.
- **Clearer feedback.** Every action shows a short confirmation or a clear error message wherever you are in the app, buttons can't be pressed twice by accident, and the app no longer flashes the lock screen when you reload the page.
- **Proper Polish characters** everywhere (Śniadanie, Obwód pasa…), with correct grammar for repeated meals (Obiad Drugi, Kolacja Druga). You can still type templates without Polish characters.
- **Simpler installation.** CALICO now runs as a single container, and existing data is upgraded automatically on first start.

### Bug Fixes

- **Late-night entries land on the right day.** Meals logged just after midnight were saved to the previous day; the app now uses your local time zone.
- **Reports show your real averages.** Simply opening a day, or logging only your weight, no longer counts as a "0 kcal" day that dragged your averages down.
- **Text messages can't delete entries by accident.** A word like "usuń" inside a normal message no longer deletes an entry; delete commands only work when they are the whole message.
- **Errors are shown as errors.** A template the app couldn't understand used to look like a success and your text was cleared. Now you see what's wrong and your text stays so you can fix it.
- **Impossible values are rejected.** Negative calories, a weight of 0 kg or dates far in the future are caught before they are saved.
- **Editing never deletes another entry.** Changing an entry into a weigh-in on a day that already had one used to silently remove the old weigh-in; now you're asked to edit the existing one instead.
- **Undo removes what you actually changed last.** Previously it could remove a different entry than the one you just corrected.
- **Multi-line entries can be edited.** Editing a meal no longer squashes it onto one line and fails.
- **The 7-day summary stays on the last 7 days**, even after you look at an older date range.
- **Clear messages when the server is unreachable**, instead of a cryptic technical error.

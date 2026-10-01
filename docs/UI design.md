1. Product identity
Product name: Calico
Primary tagline: Conscious habits. Real results.
Secondary optional tagline: Track today. A healthier tomorrow.
Calico is a mobile-first calorie and body progress tracking app focused on:
- tracking calories,
- tracking macronutrients,
- tracking body weight,
- tracking waist circumference,
- suggesting a calorie target,
- showing progress over time,
- helping the user stay consistent,
- tracking daily and weekly adherence.
The app should feel like a premium personal analytics dashboard for nutrition and progress, not like a playful wellness app.
The UI must be visually consistent with the existing Calico branding:
- dark navy background,
- cyan / teal progress accents,
- circular progress motif,
- modern premium-tech feel,
- calm, analytical, clean interface.
2. Core visual direction
Design intent
The interface should feel:
- premium,
- calm,
- data-driven,
- focused,
- modern,
- precise,
- lightweight,
- consistent.
This is not a bright lifestyle app.
This is not a medical interface.
This is not a gamified fitness toy.
It should feel closest to:
- a modern health dashboard,
- a premium analytics interface,
- a focused personal tracking tool.
Important visual rule
The UI must look like a direct extension of the Calico logo and banner.
The most important brand motif is:
- a large circular progress ring
- in cyan / teal / electric blue gradient
- paired with dark navy cards and subtle glow.
That ring language should appear throughout the interface:
- in the main calories card,
- in progress indicators,
- in compact radial indicators where appropriate,
- in selected states.
3. Things the UI must NOT use
Do not use:
- light cream backgrounds,
- beige or wellness-style surfaces,
- bright white cards across the main UI,
- green/orange lifestyle palette,
- leaf motifs,
- cat mascots,
- food photography inside the product UI,
- playful organic illustration style,
- cartoon icons,
- soft “healthy lifestyle” aesthetics that conflict with the logo/banner,
- overly decorative design.
The app should remain visually disciplined.
4. Color system
Use a dark theme by default.
Recommended theme tokens
--bg-app: #061426;
--bg-surface: #081B31;
--bg-card: #0B2139;
--bg-card-2: #0D2742;
--bg-elevated: #102C49;

--border-subtle: rgba(125, 185, 255, 0.10);
--border-strong: rgba(35, 206, 255, 0.22);
--border-active: rgba(35, 206, 255, 0.34);

--text-primary: #F4F8FC;
--text-secondary: #A9B8C8;
--text-muted: #72869B;

--accent-blue: #1AA8FF;
--accent-cyan: #20D5FF;
--accent-teal: #32E6C4;
--accent-glow: rgba(32, 213, 255, 0.18);

--success: #39E6B2;
--warning: #FFBF55;
--danger: #FF687C;

--macro-protein: #27B8FF;
--macro-carbs: #32E6C4;
--macro-fat: #FFBF55;

Primary gradient
Use for progress rings and highlighted actions:
linear-gradient(135deg, #1AA8FF 0%, #20D5FF 48%, #32E6C4 100%)

Surface behavior
- App shell: very dark navy
- Cards: slightly lighter navy
- Active card borders: cyan/blue subtle highlight
- Hover/pressed states: slightly brighter surface, not huge changes
5. Typography
Use a clean modern sans-serif.
Preferred:
- Inter
- Geist
- SF Pro
- Manrope
Type hierarchy
Screen title
- 24–28 px
- 650–700 weight
Section title
- 16–18 px
- 600–650 weight
Card title
- 14–16 px
- 550–650 weight
Primary metric
- 26–34 px
- 700 weight
Secondary metric / delta
- 12–14 px
- 500–600 weight
Small labels / metadata
- 11–12 px
- 450–500 weight
Important rule:
Data values must be visually stronger than labels.
Example:
Body Weight
72.4 kg
↓ 0.6 kg this week

72.4 kg should dominate the card.
6. Overall mobile layout
Design mobile first.
Target width
- 360–430 px
Horizontal padding
- 16 px
Vertical spacing between cards
- 12 px
Section spacing
- 20–24 px
Card radius
- 18 px
Hero card radius
- 20–24 px
Layout should be airy and calm, not crowded.
Prefer a smaller number of well-designed cards over too many tiny widgets.
7. App shell
The app background is a deep navy tone.
Use a subtle top-to-bottom or radial depth effect if desired, but it must remain restrained.
Possible shell styling:
- dark navy base,
- very subtle vignette,
- faint blue glow behind hero metrics,
- clean safe-area handling,
- fixed bottom navigation.
8. Bottom navigation
Use a fixed bottom navigation with 5 items:
- Today
- Log
- Progress
- Goals
- More
Visual style
- icons: thin outline style
- labels: small but readable
- inactive state: muted gray-blue
- active state: brighter label + cyan icon
- optionally use a subtle active pill or glow under the selected item
No oversized icons.
No floating playful tab bar.
Keep it clean and product-like.
9. Main screen: Today
This is the primary dashboard.
Header
Top-left:
Today
Wednesday, September 30

Top-right:
- calendar icon button
- optional notifications icon later if needed
Header should be simple and compact.
No large greeting text unless intentionally added later.
The dashboard must feel immediately useful.
10. Hero card: Daily Calories
This is the main visual centerpiece of the app.
It should directly reflect the branding from the logo and banner.
Purpose
Show:
- consumed calories,
- target calories,
- remaining calories,
- daily macro summary.
Layout
Top area:
- label: Calories
- optional Today badge or subtle flame icon
Center area:
- large circular progress ring
- inside the ring: consumed / target
Example:
Calories

     [circular progress ring]

        1,850
      / 2,200 kcal

Remaining
350 kcal

Ring styling
- thick circular arc
- brand gradient: blue → cyan → teal
- dark track underneath
- subtle glow
- smooth animation on load
States
Under target
Show:
Remaining 350 kcal

Over target
Show:
120 kcal over target

Use amber for the warning text.
Do not turn the whole card red.
11. Macro section inside or below hero card
Show 3 compact macro metrics:
- Protein
- Carbs
- Fat
Example:
Protein     112 / 150 g
Carbs       180 / 275 g
Fat          58 / 80 g

Each macro has:
- label,
- current/target value,
- small horizontal progress bar.
Colors
- Protein → blue
- Carbs → teal
- Fat → amber
Bar styling
- height: 6 px
- fully rounded
- dark track background
- colored fill
Do not use 3 large donut charts.
The hero calorie ring remains the primary circular element.
12. Primary action: Add food
Immediately below the hero card place a clear action:
+ Add food

Optional secondary action below or nearby:
Quick add calories

Visual style
- full-width primary button
- dark surface with cyan border or subtle accent fill
- rounded corners
- compact but prominent
This CTA should be visually easy to find.
13. Metric cards row: Body Weight and Waist Size
Below the Add Food CTA, place two compact cards:
- Body Weight
- Waist Size
These cards should look like mini analytics widgets.
On narrower devices they may stack.
On standard devices they may sit side by side.
14. Body Weight card
Content
Body Weight
72.4 kg
↓ 0.6 kg this week
[sparkline]

Structure
Top row:
- icon
- title
- optional chevron
Middle:
- large metric value
Bottom:
- trend delta
- compact sparkline
Sparkline
- thin line, around 2 px
- minimal points
- no heavy grid
- 7–14 recent entries
- blue or cyan-leaning accent
Tone
This card should feel quick to scan and clean.
15. Waist Size card
Mirror the Body Weight card.
Content
Waist Size
84.0 cm
↓ 2.1 cm this month
[sparkline]

Visual style
- same structure as weight card
- use teal-accented sparkline
- large value is the primary focus
This creates design consistency.
16. Goals & Adherence card
This card shows consistency rather than measurements.
Example
Goals & Adherence
5 / 7 days

● ● ● ● ● ○ ○

This week

or a slightly richer version:
Goals & Adherence
5 / 7 days completed
71% adherence

Visual details
- completed days: filled teal circles with check marks
- incomplete days: outlined muted circles
- optional right-side chevron to open details
This card should communicate:
- consistency matters,
- progress is measured over time,
- the app is not judging one bad day.
17. Calorie Target card
This card explains the active plan.
Example
Current Calorie Target
2,200 kcal/day

Goal
Weight loss

Estimated pace
−0.4 kg/week

Review target >

Purpose
This card should help the user understand:
- what their current target is,
- why it exists,
- what outcome it is intended to support.
Do not silently auto-adjust targets without explaining the change.
18. Optional Recommendation / Review card
If the user’s recent measurements suggest the target should be reviewed, show an information card.
Example
Calorie target review

Your recent weight trend suggests your current target may need adjustment.

Review recommendation

Style
- informational
- calm
- not alarming
- not red
- subtle border emphasis
19. Recommended order on Today screen
The Today screen should appear in this order:
HEADER

DAILY CALORIES HERO CARD

MACRO SUMMARY

ADD FOOD CTA

BODY WEIGHT + WAIST SIZE

GOALS & ADHERENCE

CURRENT CALORIE TARGET

OPTIONAL RECOMMENDATION / INSIGHT

This hierarchy is important.
It prioritizes:
1. today’s status,
2. action,
3. measurable progress,
4. consistency,
5. long-term plan.
20. Log screen
The Log screen is for food tracking.
Header
Food Log
1,850 / 2,200 kcal

Optionally include date navigation.
Meal groups
Meals are shown as collapsible cards:
- Breakfast
- Lunch
- Dinner
- Snacks
Example:
Breakfast                       420 kcal

Expanded rows:
Greek yogurt        150 g      153 kcal
Banana              100 g       89 kcal

Each food item can include optional macro detail on secondary line.
Interactions
Per item actions:
- Edit
- Duplicate
- Delete
Primary button:
- Add food
Optional FAB:
- +
Visual style should remain dark, compact, and data-focused.
21. Add Food screen
This view is functional and search-oriented.
Top area
- Search field
- Back button
- maybe barcode action later
Sections
- Recent
- Favorites
- My foods
- Recipes
Result item example
Greek yogurt
150 g
153 kcal

Protein 14.3 g · Carbs 19.5 g · Fat 1.7 g

Right side:
- add button or plus icon
Use compact clean rows, not cards everywhere.
22. Progress screen
The Progress tab shows longer-term trends.
This screen uses larger chart cards.
Sections
- Body Weight
- Waist Size
- Calorie Adherence
- Weekly Consistency
23. Progress: Body Weight chart card
Example
Body Weight
72.4 kg
−4.8 kg total

Then show a larger chart.
Features
- line chart
- date range selector:
  - 1M
  - 3M
  - 6M
  - 1Y
  - ALL
- optional trend line
- optional target line
Chart styling:
- minimal grid
- dark chart background integrated with card
- thin line
- subtle gradient fill allowed
- focus on readability
24. Progress: Waist Size chart card
Same approach as body weight.
Example
Waist Size
84.0 cm
−6.0 cm total

Use a teal-accented line.
Same chart rules apply.
25. Progress: Calorie Adherence card
Example
Calorie Adherence

Average intake
2,140 kcal

Target
2,200 kcal

93% adherence

Chart can show:
- daily intake bars or line
- target reference line
Do not visually punish small deviations.
The app should feel supportive and analytical.
26. Progress: Weekly Consistency card
Example
Weekly Consistency

Mon ✓
Tue ✓
Wed ✓
Thu ✓
Fri —
Sat ✓
Sun —

5 / 7

Alternative compact display:
- seven small circles or chips
This card should relate visually to the Goals & Adherence card.
27. Goals screen
This screen explains the plan and progress toward goal.
Core cards
Current Goal
Weight loss

Weight summary
Starting weight   78.0 kg
Current weight    72.4 kg
Target weight     68.0 kg

Daily calorie target
2,200 kcal/day

Expected pace
~0.4 kg/week

CTA
Review target

Use progress bars and clear informational grouping.
Keep tone precise and helpful.
28. Measurement entry modal / bottom sheet
Use bottom sheets for quick entry.
Add Weight example
Add Weight
72.4 kg

Date
Today

Save

Add Waist example
Add Waist Measurement
84.0 cm

Date
Today

Save

Rules
- numeric keyboard
- large editable number
- simple save flow
- visually consistent with dark UI
29. Card design system
All cards should be derived from the same shared component system.
Base card style
background: #0B2139;
border: 1px solid rgba(125, 185, 255, 0.10);
border-radius: 18px;
padding: 16px;
box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);

Active / highlighted card
border-color: rgba(35, 206, 255, 0.24);
box-shadow: 0 10px 28px rgba(0, 0, 0, 0.22);

Important rule
Do not overuse glassmorphism.
Do not blur everything.
Do not make the design neon-heavy.
The style should remain premium and controlled.
30. Card hierarchy
Use 3 card types:
1. Hero Card
Used for:
- Daily Calories
Characteristics:
- largest
- strongest visual weight
- may contain circular ring
- can use accent glow
2. Metric Card
Used for:
- Body Weight
- Waist Size
- Adherence summary
- other compact metrics
Characteristics:
- compact
- number-forward
- sparkline or compact visual
3. Info Card
Used for:
- Calorie target
- Recommendation review
- explanation cards
Characteristics:
- more textual
- lower visual intensity
- calm CTA
31. Iconography
Use thin outline icons.
Recommended types:
- calories / flame
- weight / scale
- waist / body measurement
- target
- chart
- calendar
- plus
- check
- food / utensils
Icons should be:
- small,
- clean,
- technical,
- consistent with the premium dashboard feel.
Avoid playful filled emoji-like icons.
32. Charts and sparklines
Charts should remain clean and modern.
Rules
- line thickness around 2 px
- rounded joins
- minimal axis lines
- subtle labels
- limited grid
- optional small points on key values
- restrained gradient fills only
Color mapping
- Calories → cyan
- Weight → blue
- Waist → teal
- Adherence → teal/greenish-cyan
Do not create overloaded chart visuals.
33. States and status colors
Positive
Example:
↓ 0.6 kg this week

Use teal or success color.
Neutral
Example:
No change this week

Use muted text.
Warning
Example:
120 kcal over target

Use amber.
Error / destructive
Use red only for:
- delete actions,
- form validation errors,
- sync failures,
- real issues.
Do not use red for ordinary fluctuation or slight overconsumption.
34. Motion and microinteractions
Use subtle animation only.
Recommended timings
- progress ring animation: 500–700 ms ease-out
- card hover/tap state: 150–200 ms
- bottom sheet open: smooth slide
- chart reveal: fade or line-draw
Avoid:
- bounce,
- excessive springiness,
- playful motion.
The app should feel polished, not toy-like.
35. Empty states
Keep empty states clean and actionable.
Example: no weight data
No weight measurements yet

Add your first weight entry to start tracking your progress.

Add weight

Example: no food entries
Nothing logged yet

Start by adding your first meal for today.

Add food

Use same dark styling and restrained visuals.
36. Accessibility
Minimum touch target
- 44 × 44 px
Accessibility rules
- maintain WCAG AA contrast
- do not communicate meaning with color only
- important states should include text, icons or labels
- chart data should have accessible summaries
- font sizes should stay readable on mobile
37. Component architecture
Recommended reusable components:
AppShell
MobileHeader
BottomNavigation

Card
HeroCard
MetricCard
InfoCard

ProgressRing
ProgressBar
MacroProgress

MetricValue
DeltaLabel
Sparkline
ChartCard

CaloriesHeroCard
WeightMetricCard
WaistMetricCard
AdherenceCard
CalorieTargetCard
RecommendationCard

MealCard
FoodListItem
AddFoodButton

BottomSheet
MeasurementInput
DatePicker

EmptyState

Build reusable components, not one-off screens.
38. Suggested routes / page structure
/today
/log
/progress
/goals
/more

Optional additional views:
/food/search
/measurements
/recommendations
/settings

39. Implementation principles for Codex / Claude Code
When implementing this UI, follow these rules:
1. The design must remain visually consistent with the Calico logo and banner.
2. The circular cyan/teal progress ring is the core visual motif of the brand.
3. Use dark navy surfaces as the foundation of the UI.
4. Prioritize clean analytics-style cards over lifestyle/wellness visuals.
5. Keep the experience calm, modern and number-driven.
6. Avoid introducing a second visual language that conflicts with the brand.
7. All major metrics should be scannable within one second.
8. Values must visually dominate labels.
9. Cards should be reusable and consistent.
10. The app should look like a premium personal progress dashboard.
40. Final design summary
Calico’s UI should feel like:
- a personal analytics dashboard,
- a nutrition and progress control center,
- a premium dark-mode app,
- a clean and focused tool for consistent habits.
It should not feel like:
- a bright wellness product,
- a diet gimmick,
- a lifestyle app full of illustrations,
- a medical or clinical system,
- a gamified cartoon tracker.
41. Final brand summary to include in implementation brief
Use this exact direction:
Build a mobile-first UI for Calico, a calorie and progress tracking app. The interface must be fully consistent with the Calico branding: dark navy backgrounds, deep blue surfaces, cyan/teal/electric blue accents, circular progress-ring motif, modern clean typography, and a premium analytics-dashboard feel. The application should focus on calories, macros, weight, waist size, target calories, progress charts, and adherence. Avoid bright wellness aesthetics, food photography, playful illustrations, cream backgrounds, or any visual language that conflicts with the logo and banner. The app should feel calm, precise, modern, and highly readable.
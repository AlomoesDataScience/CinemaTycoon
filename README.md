# Silver Screen

A playable console movie theater tycoon. Each turn is one calendar month: plan your program, run the concession counter, set prices, and settle the books. You start with an 80-seat theater and $30,000.

## Run

Requires Python 3.10 or newer. No packages, network connection or API keys are needed.

```bash
python3 main.py
```

For an automated demonstration with programming, concession targets and counter preparation:

```bash
python3 main.py --demo 12
```

The demo accepts `--seed 123` and never modifies saves. Interactive games use the seed selected in **Main menu → Options → Random seed**.

## Keyboard controls

Menus respond to **one key without Enter** in a real terminal. The displayed keys are the choices; you never type commands or look up database IDs.

- **B** goes back. **N/P** move between pages of a long list. **1–9** select a listed item on the current page.
- Programming uses **A** to add and **R** to remove a film. To add, select a film, then select its starting time. All conflicting bookings are shown before replacement; only **Y** or **N** is accepted.
- **D** chooses every day, weekdays, weekends or a single weekday. **M** switches rooms. Changes apply to the selected room and days.
- **U** randomly fills gaps from a chosen film pool while preserving existing bookings. **W** sets that room's automatic opening/closing hours. **P** copies a day's program to other days. **C** clears selected days after confirmation.
- Times use **12-hour AM/PM** by default. **Options → Clock display** switches to a 24-hour clock and saves your preference.
- Names, numeric settings, prices and quantities use normal typing followed by Enter.
- Information pages wait for Enter. Screens clear when you navigate. Redirected/scripted input uses one selection per line and omits informational pauses and escape codes.
- Ctrl+C or EOF writes a recovery save if a game is open.

Film choices are ordered by production budget, largest first. Every selectable film shows genre/subgenre, runtime, required hours, license fee and remaining distribution window. Longer lists are paginated so choices remain readable. Employee notes remain neutral, and film quality scores remain hidden.

## First month

1. Start a new company, choose its name and starting date. Configure your random seed under Options before starting if desired.
2. Open **Your theaters → The Majestic → Program films**. Start with every day selected or use D to choose days. Add films with A, or use U and choose All/Indie/Mid-budget/Big-budget to fill gaps randomly.
3. Open **Concessions**. Buy some packaged goods into reserve, then use **Set quantities in concession case** to put them out for sale. Reserve goods do not sell from the back room.
4. Choose a popcorn recipe, buy its kernel bags and any chosen topping tubs. Staff pop corn to order during the month, within your production limit and machine capacity.
5. Buy syrup packs and use **Fill soda tanks** to load the fountain. The tank screen shows its serving capacity.
6. Set concession selling prices or accept a vendor-owned case with fixed prices and commission.
7. Return to the company menu and run the month. Review the statement and **Concessions → Last month's item sales**. Resolve any event before the following month.

For a quicker setup, use **Automation → Review starter plan**. It configures two packaged products, kernels, a plain-popcorn recipe and syrup targets. Turn purchasing and counter preparation on separately. The plan spends nothing until you run automation or advance the month; your purchasing ceiling may prevent reaching every target immediately.

For your own preferred suppliers, choose **Concessions → Keep counter stocked**, select a product and set its reserve quantity once. This enables purchasing and counter preparation within the existing ceiling and cash floor. Packaged goods get a display target automatically; kernel/topping choices select the popcorn recipe. Staff refill configured cases and tanks from reserve during service. A zero target stops replenishment. Simple recipe headings such as “Buttered popcorn” keep supplier details out of the offer name.

Use **Rooms & staff** to build another room or assign employees. New rooms need staff and a program. The staffing screen shows the headcount needed for this month's calendar and bookings.

## Concession operations

| Operation | What happens |
| --- | --- |
| Reserve storage | Purchased wholesale boxes, kernel bags, syrup packs and topping tubs wait in the back room. Reserve plus displayed packaged units cannot exceed 10,000 units. |
| Concession case | The inherited glass counter case holds 300 packaged items. Setting a display quantity transfers that many boxes out of reserve; reducing it returns boxes to reserve. |
| Queue-side merchandiser | A $950 purchase adds 200 display spaces, improves impulse demand for your packaged goods and adds $15 monthly upkeep before the economic modifier. |
| Popcorn maker | The inherited popper consumes selected kernel bags and optional topping tubs. Suppliers have different quality and yields. Output is limited by ingredient availability, machine capacity and your chosen monthly limit. |
| Soda fountain | Loading syrup converts packs into measured servings in the storage tanks, using the current machine's yield. Sales draw down those tanks. The inherited fountain holds 500 servings. |
| Vendor-owned case | A supplier installs and supplies a separate case at no upfront cost, offers up to 200 boxes per month, controls its price, and pays you a listed commission. Each theater has room for two such cases. Ending the agreement removes the vendor's offer. |
| Wholesale retail prices | You control per-serving prices for your own packaged goods, popcorn and soda. Toppings are recipe inputs, not a separate retail offer. |

The inherited machines are a Fairground kettle popper and Starlight tank fountain. Replacement models offer a choice between higher input yield and better flavor, with different capacity and upkeep. Replacements have no trade-in value. Existing mixed soda is not multiplied when you change machines; the new yield applies when you load more syrup.

Toppings include dairy butter, butter-flavored oil, savory seasoning and butter-style spread. The selection screen explains their tradeoffs. Dairy butter costs more, covers fewer servings per tub and spoils faster. Flavor preferences can favor one topping over another.

Inventory loss is calculated monthly: packaged goods lose 5%, most raw ingredients 2%, dairy butter 20%, spread 8%, and mixed soda 10%, rounding up to whole units/servings. Popcorn is produced to demand in whole input batches; surplus from the final batch is discarded. Each sold popcorn serving also incurs $0.18 for oil, heat and containers; soda incurs $0.12 for water, CO2, refrigeration and cups. These are automatically supplied operating consumables in this pass.

A moviegoer may purchase one packaged snack, popcorn and soda. Price, quality, local flavor preferences, machines and merchandising affect demand. Customers may buy nothing. Per-item reports show the price, available quantity, demand, units sold, revenue, and margin after consumed inputs. They distinguish vendor remittances from your commission. Margin excludes rent, wages and spoilage; the company statement contains the complete cash result.

## Automation

Automation is configured per theater and uses your chosen products and targets:

- **Programming:** Manual keeps your schedules; Fill fills free hours without replacing bookings; Replace rebuilds programs monthly. Every room has its own film pool and automatic hours. Picks are random among matching titles that fit, without recommendations or hidden-score optimization. Empty pools leave existing bookings intact.
- **Purchasing:** Separate reserve and case targets determine what to buy. Existing reserve stock, displayed boxes and mixed soda count toward targets. No targets means no purchases.
- **Counter preparation:** Moves packaged goods toward display targets and loads targeted syrup into tanks. It also refills from available reserve during sales, so one case/tank fill is no longer the month's sales limit. It is independent of purchasing and does not buy stock twice.
- **Purchasing ceiling:** Limits automatic spending over the entire month, including repeated uses of Run automation now. It survives save/load and resets after settlement.
- **Company cash floor:** Stops that theater's automatic purchases from taking company cash below the configured amount. This is not a promise that future operating bills can be paid.

Products are purchased in target-list order until money, the ceiling or storage runs out. Notices explain purchases and shortages. Your prices and vendor contracts stay under manual control. Group management can change prices, fill program gaps, set programming policy, and toggle purchasing/preparation across a circuit; each theater retains its own targets and limits.

## Film operations and finances

Theaters can contain multiple independently scheduled rooms. Each room has seven daily schedules that repeat weekly. Manual bookings can start at any of the 24 hours and cross midnight, including Sunday into Monday. Conflicts are checked across day boundaries. Autofill defaults to noon–midnight but its opening window can be changed per room. Films reserve whole hours, rounded up. A short can loop within its hour, but repetitions do not multiply admission tickets. Titles leave distribution after four months; five new titles arrive each month.

The simulation counts the actual Mondays, Tuesdays, etc. in the current calendar month. Weekend demand is stronger by default, and morning, matinee, evening, late and overnight audiences have different genre preferences. Booking choices show the likely audience group. Monthly statements break attendance down by room and weekday. These settings are editable in [balance.json](balance.json); see [MODDING.md](MODDING.md).

A title's monthly license is charged once per theater, shared across its open rooms and repeat bookings, plus studios receive 22% of ticket sales. Attendance also depends on film quality, local genre tastes, age, repeats, ticket price, condition, reputation, economic conditions and random events. Local market size limits total admissions across your theaters in a city.

The starting room has three employees. Each employee supplies 160 staff hours at a base $1,400 monthly wage; each occupied room-hour needs one staff hour by default. Coverage below 100% reduces that room's admissions proportionally. A new room starts with zero staff. Closed rooms have no ticket sales or active licenses, but keep paying assigned employees and upkeep. The economy scales operating costs. Staff counts, wages, room costs and capacity rules are documented in the modding guide.

Overhead includes rent, staffing, utilities, auditorium maintenance and concession-machine upkeep. Empty theaters still pay it. Condition wears down monthly. Renovations explain the work before purchase, restore condition to 100%, improve guest appeal and reduce condition-related repairs. They add neither seats nor rooms.

The monthly statement reconciles as:

```text
opening cash + operating cash profit − property/improvement spending = closing cash
```

Stock is expensed when bought; the simulation uses cash accounting. Moving stock to displays or tanks does not charge you again. Vendor sales contribute your commission only. Prepared-food operating supplies are charged at settlement. Negative cash after settlement closes the company; reports and saving remain available. There is no victory cutoff.

## Options and saves

Options is a persistent list: autosave toggle, random seed, settlement count and 12/24-hour clock display. Changing one leaves the others alone. Seed and settlement settings affect new games only.

Saves live in `.saves/` beside `main.py`:

- `manual.json`: Save game or Save & return, replacing the previous manual save.
- `autosave.json`: after each completed month when enabled, including a losing month.
- `recovery.json`: on Ctrl+C or end of input.
- `options.json`: preferences.

Copy a save under another filename to keep several companies. Load lists all JSON saves except options. To use a separate save directory:

```bash
python3 main.py --save-dir /tmp/silver-screen-saves
```

Version 1–3 saves migrate automatically to version 4. The old single-screen daily program becomes Screen 1's program on all seven weekdays, retaining its seats and equipment and assigning three employees. Cash, inventory, dates and film bookings are retained. Original pre-concession saves also gain ingredient products; old goods remain packaged stock. Loading leaves the original file untouched; your next save writes the new schema. The revised attendance, staffing and refill rules intentionally change future results. Balance-file edits apply when you create or load a company.

## Scope and extension points

This pass adds weekly room programs, 24-hour slots, configurable clock display, random film pools, staffing, moddable attendance and less repetitive concession management. Capacities, yields, costs and demand are fictional gameplay balance values. [NAMING_PROPOSAL.md](NAMING_PROPOSAL.md) provides a content/naming handoff for a later Gemini pass.

Still deferred: historical packaging/equipment, accurate inflation/populations, a geographic US map, player-owned studios, individual employee shifts and a richer renovation system. Staffing is an aggregate monthly capacity model. Popcorn/soda consumables remain automatic operating costs; separate utility logistics and mid-month vendor deliveries are not modeled. Automated refills draw from stock you already own.

The original broader demo systems remain: procedural movies and evolving studios, all five concession flavor variables, theater acquisition in generated towns, groups, renovations, equipment, branching events and random disturbances. Historical dates still select broad balance presets in constant game dollars. Era-specific generation filters and the small event framework are extension points, not a historically complete timeline.

Code is divided into `engine.py` (monthly simulation), `programming.py` (weekly bookings, rooms and staff), `rules.py` (balance-file validation), `concessions.py` (inventory and sales), `content.py` (content and era rules), `models.py` (state), `persistence.py` (validation/migrations), `terminal.py` (key input and clock formatting), and the company, programming and concession menu modules.

## Verification

```bash
python3 -m unittest discover -s tests -v
```

The suite covers the simulation, console workflows, screen clearing, pagination, conflict replacement, strict Y/N input, options, inventory transfers, recipe limits, tank volumes, equipment effects, pricing, commissions, automation ceilings, financial reconciliation and save compatibility. Actual single-key navigation has also been exercised in a real terminal.

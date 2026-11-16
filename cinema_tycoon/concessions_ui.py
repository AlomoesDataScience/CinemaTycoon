from .content import MACHINES, TOPPING_NOTES
from .terminal import amount, header, menu, money, pause, select, whole, yes_no


def product_label(game, theater, product):
    offer = getattr(product, "service_name", "") or product.name
    if product.category == "kernels":
        header_text = f"Popping Kernels · Makes {offer} (Supplied by {product.name}, {product.producer})"
    elif product.category == "syrup":
        header_text = f"Fountain Syrup · Makes {offer} (Supplied by {product.name}, {product.producer})"
    elif product.category == "topping":
        header_text = f"Popcorn Topping · {product.name} ({product.producer})"
    elif offer != product.name:
        header_text = f"{offer} · Supplied by {product.name} ({product.producer})"
    else:
        header_text = f"{product.name} · {product.producer}"
    label = f"{header_text}\n      Quality {product.quality}/100 · {product.category}"
    if product.deal == "vendor":
        return label + f"\n      Vendor-owned case: fixed {money(product.retail)}, your cut {product.commission:.0%}; 200 boxes/month"
    label += f" · {money(product.wholesale)}/{product.unit} wholesale"
    if product.category != "topping":
        label += f"\n      Selling price {money(game.sale_price(theater, product))}/serving"
    if product.category in ("kernels", "syrup"):
        label += f" · yield {game.machine_yield(theater, product)} servings/{product.unit} with your machine"
    elif product.category == "topping":
        label += f"\n      Tops {product.yield_per_unit} servings/tub"
        label += "\n      " + next((note for name, note in TOPPING_NOTES.items() if name in product.name), "")
    return label + f"\n      Reserve {theater.stock.get(product.id, 0)} · on display {theater.display.get(product.id, 0)} · tank {theater.tanks.get(product.id, 0)} servings"


def choose_product(game, theater, title, predicate=lambda p: True):
    return select(title, [(p.id, product_label(game, theater, p)) for p in game.state.products if predicate(p)],
                  lambda: print(f"Cash {money(game.state.cash)} · display {sum(theater.display.values())}/{game.display_capacity(theater)}"))


def recipe_menu(game, theater):
    pid = choose_product(game, theater, "POPCORN · CHOOSE KERNELS", lambda p: p.category == "kernels")
    if pid is None:
        return
    topping = select("POPCORN · CHOOSE TOPPING", [(0, "Plain popcorn · no topping required")] +
        [(p.id, product_label(game, theater, p)) for p in game.state.products if p.category == "topping"])
    if topping is None:
        return
    header("POPCORN · PRODUCTION LIMIT")
    print("Staff make popcorn to order during the month. Kernels and any chosen topping must be in reserve.")
    print("Oil, serving containers and heat cost $0.18 per sold serving, charged during settlement.")
    print(f"Your popper can produce {MACHINES['popcorn'][theater.popcorn_machine]['capacity']:,} servings/month.")
    limit = whole("Maximum servings this month", theater.popcorn_limit, 0, 10000)
    game.set_recipe(theater.id, pid, topping, limit)


def equipment_menu(game, theater):
    items = [("merchandiser", "Queue-side display merchandiser · $950\n      Adds 200 display spaces and encourages impulse purchases; $15/month upkeep.")]
    for kind, models in MACHINES.items():
        for key, model in models.items():
            if key == "basic":
                continue
            capacity_label = "servings/month" if kind == "popcorn" else "tank servings"
            items.append(((kind, key), f"{model['name']} · {money(model['cost'])}\n      {model['yield']:.2f}× input yield · {model['capacity']} {capacity_label} · flavor +{model['quality']}\n      {money(model['upkeep'])}/month upkeep · current: {getattr(theater, kind + '_machine')}"))
    chosen = select("CONCESSION EQUIPMENT", items, lambda: print(f"Available cash: {money(game.state.cash)}"))
    if chosen is not None and yes_no("Install the selected equipment? Existing equipment has no trade-in value."):
        if chosen == "merchandiser":
            game.install_concession_equipment(theater.id, chosen)
        else:
            game.install_concession_equipment(theater.id, *chosen)


def sales_report(game, theater):
    header(f"CONCESSION SALES · {theater.name}")
    report = next((r for r in game.state.last_report.get("theaters", []) if r.get("theater_id") == theater.id), None)
    details = report.get("concession_detail") if report else None
    if not details:
        print("Run a month with this version to see item-level sales results.")
    else:
        print(f"Last month: {game.state.last_report['date']}")
        for row in details["items"]:
            offer = row.get("offer", row["product"])
            detail = f" (Supplier: {row['product']})" if offer != row["product"] else ""
            print(f"\n  {offer}{detail} · {money(row['price'])} per serving")
            print(f"    Available {row['available']} · demand {row['demand']} · sold {row['sold']}")
            print(f"    Your revenue {money(row['revenue'])} · margin after consumed inputs {money(row['margin'])}")
            if row["vendor_remittance"]:
                print(f"    Supplier retained {money(row['vendor_remittance'])}")
        print(f"\nStock spoiled: {details['spoiled']} units · prepared popcorn discarded: {details['production_waste']} servings")
        print(f"Tank waste: {details['tank_waste']} servings · operating supplies: {money(details['supplies'])}")
        print("Item margins exclude rent, wages and spoilage. Compare demand and stock before changing prices.")
    pause()


def stock_menu(game, theater):
    notice = ""
    while True:
        def context():
            print(f"Cash {money(game.state.cash)} · reserve {sum(theater.stock.values())} units")
            print(f"Concession case: {sum(theater.display.values())}/{game.display_capacity(theater)} boxes · vendor cases {len(theater.contracts)}/2")
            print(f"{MACHINES['popcorn'][theater.popcorn_machine]['name']} · {MACHINES['soda'][theater.soda_machine]['name']}")
            print(f"Soda tanks: {sum(theater.tanks.values())}/{MACHINES['soda'][theater.soda_machine]['capacity']} servings")
            if theater.kernel_id:
                print("Recipe: " + game.recipe_name(theater) + f" · limit {theater.popcorn_limit}/month")
                print("  Kernel supplier: " + game.get("products", theater.kernel_id).producer)
            else:
                print("No popcorn recipe selected.")
            print("Reserve goods are not on sale until displayed, loaded into tanks or used in a recipe.\n")
        key = menu(f"CONCESSIONS · {theater.name}", [("1", "Buy reserve stock"), ("2", "Set quantities in concession case"),
            ("3", "Set selling prices"), ("4", "Popcorn recipe & production"), ("5", "Fill soda tanks"),
            ("6", "Vendor contracts"), ("7", "Concession equipment"), ("8", "Last month's item sales"),
            ("9", "Keep counter stocked · choose once, staff refill"), ("b", "Back")], context, notice)
        notice = ""
        try:
            if key == "b":
                return
            game.active() if key != "8" else None
            if key == "1":
                pid = choose_product(game, theater, "WHOLESALE · BUY STOCK", lambda p: p.deal == "wholesale")
                if pid is not None:
                    product = game.get("products", pid)
                    quantity = whole(f"How many {product.unit}(s)? 0 cancels", 0, 0, 10000)
                    if quantity and yes_no(f"Buy for {money(quantity * product.wholesale)}?"):
                        game.buy_stock(theater.id, pid, quantity)
                        notice = "Stock delivered to reserve."
            elif key == "2":
                pid = choose_product(game, theater, "CONCESSION CASE", lambda p: p.category == "packaged" and p.deal == "wholesale")
                if pid is not None:
                    quantity = whole("Total boxes to put out (0 returns all to reserve)", theater.display.get(pid, 0), 0, 10000)
                    game.put_on_display(theater.id, pid, quantity)
                    notice = "Concession case updated."
            elif key == "3":
                pid = choose_product(game, theater, "SET SELLING PRICE", lambda p: p.category != "topping" and p.deal == "wholesale")
                if pid is not None:
                    product = game.get("products", pid)
                    price = amount("Price per serving", game.sale_price(theater, product), 0.25, 30)
                    game.set_concession_price(theater.id, pid, price)
                    notice = "Price updated. Run a month to measure the change in demand and sales."
            elif key == "4":
                recipe_menu(game, theater)
            elif key == "5":
                pid = choose_product(game, theater, "FILL SODA TANK", lambda p: p.category == "syrup")
                if pid is not None:
                    print("Mixes syrup with the water/CO2 supply. Cups and utilities cost $0.12 per sold serving.")
                    quantity = whole("Syrup packs to load (0 cancels)", 0, 0, 10000)
                    if quantity:
                        game.fill_tank(theater.id, pid, quantity)
                        notice = "Fountain tank filled."
            elif key == "6":
                pid = choose_product(game, theater, "VENDOR-OWNED CASES", lambda p: p.deal == "vendor")
                if pid is not None:
                    if pid in theater.contracts:
                        if yes_no("End this contract and have the supplier remove its case?"):
                            game.cancel_contract(theater.id, pid)
                            notice = "Vendor case removed."
                    elif yes_no("Accept these fixed-price terms? Supplier installs and stocks its own case at no upfront cost."):
                        game.sign_contract(theater.id, pid)
                        notice = "Vendor case installed. The supplier replenishes 200 boxes per month; you receive the listed commission."
            elif key == "7":
                equipment_menu(game, theater)
            elif key == "8":
                sales_report(game, theater)
            elif key == "9":
                pid = choose_product(game, theater, "KEEP STOCKED · PREFERRED SUPPLIER", lambda p: p.deal == "wholesale")
                if pid is not None:
                    product = game.get("products", pid)
                    print(f"Automatic purchase ceiling {money(theater.stock_budget)}/month; company cash floor {money(theater.cash_reserve)}.")
                    print("Staff buy toward this reserve target and refill cases/tanks during service.")
                    print("Packaged products also get up to 100 display spaces. Kernel/topping choices update your popcorn recipe.")
                    quantity = whole(f"Reserve target in {product.unit}(s); 0 stops restocking", theater.stock_targets.get(pid, 0), 0, 10000)
                    game.keep_stocked(theater.id, pid, quantity)
                    notice = "Target saved. Purchasing and counter preparation are on." if quantity else "Restocking target removed. Existing inventory is kept."
        except ValueError as error:
            notice = str(error)


def automation_menu(game, theater):
    notice = ""
    while True:
        def context():
            print(f"Program: {theater.program_policy} · purchasing {'on' if theater.auto_stock else 'off'} · counter prep {'on' if theater.auto_prepare else 'off'}")
            print("Room film pools: " + ", ".join(f"{r.name}: {r.film_pool}" for r in theater.rooms))
            print(f"Monthly purchasing ceiling {money(theater.stock_budget)} · company cash floor {money(theater.cash_reserve)}")
            print("Targets (reserve + case):")
            for pid, target in theater.stock_targets.items():
                print(f"  {game.get('products', pid).name}: {target} + {theater.display_targets.get(pid, 0)}")
            print("Staff follow these targets; prices and vendor contracts stay under your control.\n")
        key = menu(f"AUTOMATION · {theater.name}", [("1", "Programming policy"), ("2", "Toggle purchasing"),
            ("3", "Toggle display/tank preparation"), ("4", "Edit a product target"), ("5", "Monthly purchasing ceiling"),
            ("6", "Company cash floor"), ("7", "Review starter plan"), ("8", "Run concession automation now"),
            ("9", "Set a room's random film pool"), ("b", "Back")], context, notice)
        notice = ""
        try:
            if key == "b":
                return
            game.active()
            if key == "1":
                policy = select("PROGRAMMING POLICY", [("manual", "Manual · keep your bookings; staff never fill gaps"),
                    ("fill", "Fill empty hours · preserve every existing booking"),
                    ("replace", "Rebuild each month · replace the entire program")])
                if policy:
                    theater.program_policy, theater.auto_schedule = policy, False
            elif key == "2":
                theater.auto_stock = not theater.auto_stock
            elif key == "3":
                theater.auto_prepare = not theater.auto_prepare
            elif key == "4":
                pid = choose_product(game, theater, "AUTOMATION · PRODUCT TARGET", lambda p: p.deal == "wholesale")
                if pid is not None:
                    reserve = whole("Reserve target (0 stops buying reserve stock)", theater.stock_targets.get(pid, 0), 0, 10000)
                    display = whole("Case target", theater.display_targets.get(pid, 0), 0, 500) if game.get("products", pid).category == "packaged" else 0
                    game.set_stock_target(theater.id, pid, reserve, display)
            elif key == "5":
                theater.stock_budget = amount("Monthly purchase ceiling", theater.stock_budget, 0, 100000)
            elif key == "6":
                theater.cash_reserve = amount("Minimum company cash after this theater's purchases", theater.cash_reserve, 0, 1e9)
            elif key == "7":
                header("STARTER PLAN")
                print("Two wholesale packaged products: 80 boxes in reserve and 100 on display each.")
                print("First kernel supplier: 30 bags; plain popcorn recipe, 800 servings/month.")
                print("First soda supplier: 8 syrup packs. All other targets are cleared.")
                print("This sets targets and recipe only. Turn on purchasing and preparation separately.")
                if yes_no("Apply this plan?"):
                    game.starter_targets(theater.id)
                    notice = "Starter targets configured."
            elif key == "8":
                if yes_no("Buy toward targets within your remaining monthly ceiling and cash floor, then prepare the counter?"):
                    notes = game.auto_restock(theater)
                    game.prepare_counter(theater)
                    header("AUTOMATION RESULTS")
                    print("\n".join(notes) or "No purchases needed.")
                    print("Display and fountain preparation complete.")
                    pause()
            elif key == "9":
                from .programming_ui import pick_pool
                rid = select("CHOOSE ROOM", [(r.id, r.name) for r in theater.rooms])
                if rid is not None:
                    pick_pool(game, game.room(theater.id, rid))
        except ValueError as error:
            notice = str(error)

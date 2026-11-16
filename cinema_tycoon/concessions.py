"""Concession inventory, recipes, contracts and price-sensitive monthly sales."""
import math

from .content import MACHINES


class Concessions:
    def recipe_name(self, theater):
        if not theater.kernel_id:
            return "No popcorn recipe"
        if not theater.topping_id:
            return "Plain popcorn"
        topping = self.get("products", theater.topping_id)
        kind = getattr(topping, "ingredient_kind", "")
        if kind == "dairy_butter":
            return "Buttered popcorn"
        if kind == "butter_oil":
            return "Butter-flavored popcorn"
        if kind == "savory_seasoning":
            return "Savory popcorn"
        if kind == "butter_spread":
            return "Butter-style popcorn"
        return "Seasoned popcorn"

    def keep_stocked(self, theater_id, product_id, quantity):
        theater, product = self.get("theaters", theater_id), self.get("products", product_id)
        if product.category == "topping" and quantity > 0 and not theater.kernel_id:
            raise ValueError("Choose a kernel supplier first, then add a topping.")
        display = 0
        if product.category == "packaged" and quantity > 0:
            free = max(0, self.display_capacity(theater) - sum(theater.display_targets.values()) + theater.display_targets.get(product_id, 0))
            display = min(100, quantity, free)
        self.set_stock_target(theater_id, product_id, quantity, display)
        if quantity > 0:
            theater.auto_stock = theater.auto_prepare = True
            if product.category == "kernels":
                theater.kernel_id = product_id
            elif product.category == "topping":
                theater.topping_id = product_id

    def display_capacity(self, theater):
        return 300 + (200 if theater.merchandiser else 0)

    def sale_price(self, theater, product):
        return product.retail if product.deal == "vendor" else theater.prices.get(product.id, product.retail)

    def set_concession_price(self, theater_id, product_id, price):
        self.active()
        theater, product = self.get("theaters", theater_id), self.get("products", product_id)
        if product.category == "topping" or product.deal == "vendor":
            raise ValueError("This item has no manager-set selling price.")
        if not math.isfinite(price) or not 0.25 <= price <= 30:
            raise ValueError("Choose a selling price between $0.25 and $30.")
        theater.prices[product.id] = round(price, 2)

    def put_on_display(self, theater_id, product_id, quantity):
        self.active()
        theater, product = self.get("theaters", theater_id), self.get("products", product_id)
        if product.category != "packaged" or product.deal != "wholesale":
            raise ValueError("Only your own packaged goods go in the concession case.")
        if type(quantity) is not int or quantity < 0:
            raise ValueError("Display quantity must be a nonnegative whole number.")
        current = theater.display.get(product_id, 0)
        if quantity > current + theater.stock.get(product_id, 0):
            raise ValueError("Buy enough reserve stock before filling the case.")
        if sum(theater.display.values()) - current + quantity > self.display_capacity(theater):
            raise ValueError("The concession case is full. Reduce another display or buy a merchandiser.")
        theater.stock[product_id] = theater.stock.get(product_id, 0) + current - quantity
        theater.display[product_id] = quantity

    def sign_contract(self, theater_id, product_id):
        self.active()
        theater, product = self.get("theaters", theater_id), self.get("products", product_id)
        if product.deal != "vendor":
            raise ValueError("That supplier sells wholesale rather than on commission.")
        if product_id in theater.contracts:
            raise ValueError("This vendor already has a case here.")
        if len(theater.contracts) >= 2:
            raise ValueError("There is room for two vendor-owned cases.")
        theater.contracts.append(product_id)

    def cancel_contract(self, theater_id, product_id):
        self.active()
        theater = self.get("theaters", theater_id)
        if product_id not in theater.contracts:
            raise ValueError("That contract is not active.")
        theater.contracts.remove(product_id)

    def machine_yield(self, theater, product):
        kind = "popcorn" if product.category == "kernels" else "soda"
        model = getattr(theater, f"{kind}_machine")
        return max(1, int(product.yield_per_unit * MACHINES[kind][model]["yield"]))

    def fill_tank(self, theater_id, product_id, quantity):
        self.active()
        theater, product = self.get("theaters", theater_id), self.get("products", product_id)
        if product.category != "syrup":
            raise ValueError("Only fountain syrup can fill a soda tank.")
        if type(quantity) is not int or quantity <= 0 or quantity > theater.stock.get(product_id, 0):
            raise ValueError("Choose a positive number of syrup units already in reserve.")
        portions = quantity * self.machine_yield(theater, product)
        capacity = MACHINES["soda"][theater.soda_machine]["capacity"]
        if sum(theater.tanks.values()) + portions > capacity:
            raise ValueError("The storage tanks cannot hold that much. Use fewer syrup units.")
        theater.stock[product_id] -= quantity
        theater.tanks[product_id] = theater.tanks.get(product_id, 0) + portions

    def set_recipe(self, theater_id, kernel_id, topping_id, limit):
        self.active()
        theater, kernel = self.get("theaters", theater_id), self.get("products", kernel_id)
        if kernel.category != "kernels":
            raise ValueError("Select popping kernels for the recipe.")
        if topping_id and self.get("products", topping_id).category != "topping":
            raise ValueError("Select a topping, or plain popcorn.")
        if type(limit) is not int or not 0 <= limit <= 10000:
            raise ValueError("Choose a monthly production limit from 0 to 10,000 servings.")
        theater.kernel_id, theater.topping_id, theater.popcorn_limit = kernel_id, topping_id, limit

    def install_concession_equipment(self, theater_id, kind, model=""):
        theater = self.get("theaters", theater_id)
        if kind == "merchandiser":
            if theater.merchandiser:
                raise ValueError("A queue-side merchandiser is already installed.")
            self.spend(950, "capital")
            theater.merchandiser = True
            return
        if kind not in MACHINES or model not in MACHINES[kind] or model == "basic":
            raise ValueError("Select an available machine.")
        if getattr(theater, f"{kind}_machine") == model:
            raise ValueError("That machine is already installed.")
        if kind == "soda" and sum(theater.tanks.values()) > MACHINES[kind][model]["capacity"]:
            raise ValueError("Sell down the tanks before installing a smaller fountain.")
        self.spend(MACHINES[kind][model]["cost"], "capital")
        setattr(theater, f"{kind}_machine", model)

    def set_stock_target(self, theater_id, product_id, reserve, display):
        self.active()
        theater, product = self.get("theaters", theater_id), self.get("products", product_id)
        if product.deal != "wholesale":
            raise ValueError("Vendor stock is replenished by its supplier.")
        if any(type(q) is not int or not 0 <= q <= 10000 for q in (reserve, display)):
            raise ValueError("Targets must be whole numbers from 0 to 10,000.")
        if display and product.category != "packaged":
            raise ValueError("Only packaged goods have a concession-case target.")
        if sum(theater.display_targets.values()) - theater.display_targets.get(product_id, 0) + display > self.display_capacity(theater):
            raise ValueError("Combined display targets exceed case capacity.")
        if sum(theater.stock_targets.values()) - theater.stock_targets.get(product_id, 0) + reserve + sum(theater.display_targets.values()) - theater.display_targets.get(product_id, 0) + display > 10000:
            raise ValueError("Combined reserve and display targets exceed storage capacity.")
        theater.stock_targets[product_id], theater.display_targets[product_id] = reserve, display

    def starter_targets(self, theater_id):
        """Explicitly requested starter plan; no purchases or price/contract changes."""
        self.active()
        theater = self.get("theaters", theater_id)
        theater.stock_targets.clear()
        theater.display_targets.clear()
        packaged = [p for p in self.state.products if p.category == "packaged" and p.deal == "wholesale"][:2]
        for product in packaged:
            self.set_stock_target(theater_id, product.id, 80, 100)
        kernel = next((p for p in self.state.products if p.category == "kernels"), None)
        syrup = next((p for p in self.state.products if p.category == "syrup"), None)
        if kernel:
            self.set_stock_target(theater_id, kernel.id, 30, 0)
            self.set_recipe(theater_id, kernel.id, 0, 800)
        if syrup:
            self.set_stock_target(theater_id, syrup.id, 8, 0)

    def auto_restock(self, theater):
        notes = []
        if not self.has_program(theater):
            return [f"{theater.name}: no program; automatic purchasing skipped."]
        budget = min(max(0, theater.stock_budget - theater.automation_spent), max(0, self.state.cash - theater.cash_reserve))
        for pid, reserve in theater.stock_targets.items():
            product = self.get("products", pid)
            target = reserve + theater.display_targets.get(pid, 0)
            owned = theater.stock.get(pid, 0) + theater.display.get(pid, 0)
            if product.category == "syrup":
                owned += theater.tanks.get(pid, 0) / self.machine_yield(theater, product)
            need = max(0, math.ceil(target - owned))
            space = 10000 - sum(theater.stock.values()) - sum(theater.display.values())
            quantity = min(need, int(round(budget, 2) / product.wholesale), space)
            if quantity:
                self.buy_stock(theater.id, pid, quantity)
                theater.automation_spent = round(theater.automation_spent + quantity * product.wholesale, 2)
                budget = round(budget - quantity * product.wholesale, 2)
                notes.append(f"{theater.name}: bought {quantity} {product.unit}(s) of {product.name}.")
            if quantity < need:
                notes.append(f"{theater.name}: {product.name} below target; budget, reserve or storage limit reached.")
        if not theater.stock_targets:
            notes.append(f"{theater.name}: no purchasing targets configured.")
        return notes

    def prepare_counter(self, theater):
        for pid, target in theater.display_targets.items():
            if self.get("products", pid).category != "packaged":
                continue
            current = theater.display.get(pid, 0)
            available = current + theater.stock.get(pid, 0)
            capacity = self.display_capacity(theater) - sum(theater.display.values()) + current
            self.put_on_display(theater.id, pid, min(target, available, capacity))
        for pid in theater.stock_targets:
            product = self.get("products", pid)
            if product.category == "syrup":
                free = MACHINES["soda"][theater.soda_machine]["capacity"] - sum(theater.tanks.values())
                quantity = min(theater.stock.get(pid, 0), free // self.machine_yield(theater, product))
                if quantity:
                    self.fill_tank(theater.id, pid, quantity)

    def concession_sales(self, theater, audience, snack_modifiers=None):
        snack_modifiers = snack_modifiers or {}
        city = self.get("cities", theater.city_id)
        offers = []
        for pid, quantity in theater.display.items():
            product = self.get("products", pid)
            if theater.auto_prepare and theater.display_targets.get(pid, 0) > 0:
                quantity += theater.stock.get(pid, 0)
            offer_name = product.service_name or product.name
            offers.append((product, quantity, "packaged", 0, offer_name))
        for pid in theater.contracts:
            product = self.get("products", pid)
            offer_name = product.service_name or product.name
            offers.append((product, 200, "vendor", 0, offer_name))
        if theater.kernel_id:
            product = self.get("products", theater.kernel_id)
            machine = MACHINES["popcorn"][theater.popcorn_machine]
            available = min(theater.stock.get(product.id, 0) * self.machine_yield(theater, product), machine["capacity"], theater.popcorn_limit)
            bonus = machine["quality"] / 100
            if theater.topping_id:
                topping = self.get("products", theater.topping_id)
                available = min(available, theater.stock.get(topping.id, 0) * topping.yield_per_unit)
                bonus += (self.product_match(topping, city) - 0.35) * 0.35
            offer_name = self.recipe_name(theater)
            offers.append((product, available, "popcorn", bonus, offer_name))
        for pid, portions in theater.tanks.items():
            product = self.get("products", pid)
            refill_space = MACHINES["soda"][theater.soda_machine]["capacity"] - sum(theater.tanks.values()) + portions
            if theater.auto_prepare and theater.stock_targets.get(pid, 0) > 0 and refill_space >= self.machine_yield(theater, product):
                portions += theater.stock.get(pid, 0) * self.machine_yield(theater, product)
            offer_name = product.service_name or ("Fountain Citrus Soda" if "Citrus" in product.name else "Fountain Cola")
            offers.append((product, portions, "soda", MACHINES["soda"][theater.soda_machine]["quality"] / 100, offer_name))
        revenue, supplies, sold_total, missed, production_waste = 0.0, 0.0, 0, 0, 0
        rows = []
        for category, base_rate in (("packaged", 0.38), ("popcorn", 0.42), ("soda", 0.55)):
            rate = base_rate * snack_modifiers.get(category, 1.0)
            selections = [o for o in offers if ("packaged" if o[2] == "vendor" else o[2]) == category]
            weights = [(0.45 + self.product_match(p, city) + bonus + (0.12 if theater.merchandiser and kind == "packaged" else 0))
                       * math.exp(-1.4 * (self.sale_price(theater, p) / p.retail - 1)) for p, qty, kind, bonus, off in selections]
            denominator = 1 + sum(weights)  # Customers may choose to buy nothing.
            for (product, available, kind, bonus, offer_name), weight in zip(selections, weights):
                demand = int(audience * rate * weight / denominator)
                sold = min(available, demand)
                price = self.sale_price(theater, product)
                gross = round(sold * price, 2)
                earned = round(gross * product.commission, 2) if kind == "vendor" else gross
                input_units, input_cost, extra_cost = 0, 0.0, 0.0
                if kind == "packaged":
                    from_case = min(sold, theater.display[product.id])
                    theater.display[product.id] -= from_case
                    theater.stock[product.id] = theater.stock.get(product.id, 0) - (sold - from_case)
                    input_cost = sold * product.wholesale
                elif kind == "popcorn" and sold:
                    input_units = math.ceil(sold / self.machine_yield(theater, product))
                    theater.stock[product.id] -= input_units
                    production_waste += input_units * self.machine_yield(theater, product) - sold
                    input_cost = input_units * product.wholesale
                    if theater.topping_id:
                        topping = self.get("products", theater.topping_id)
                        topping_units = math.ceil(sold / topping.yield_per_unit)
                        theater.stock[topping.id] -= topping_units
                        input_cost += topping_units * topping.wholesale
                    extra_cost = sold * 0.18  # Oil, heat and serving containers.
                elif kind == "soda":
                    missing = max(0, sold - theater.tanks[product.id])
                    if missing:
                        packs = math.ceil(missing / self.machine_yield(theater, product))
                        theater.stock[product.id] -= packs
                        theater.tanks[product.id] += packs * self.machine_yield(theater, product)
                    theater.tanks[product.id] -= sold
                    input_cost = sold / self.machine_yield(theater, product) * product.wholesale
                    extra_cost = sold * 0.12  # Water, CO2, refrigeration and cups.
                revenue += earned
                supplies += extra_cost
                sold_total += sold
                missed += demand - sold
                rows.append({"product": product.name, "offer": offer_name, "kind": kind, "price": price, "demand": demand,
                             "available": available, "sold": sold, "revenue": earned,
                             "margin": round(earned - input_cost - extra_cost, 2),
                             "inputs_used": input_units, "vendor_remittance": round(gross - earned, 2)})
        spoiled = 0
        for inventory in (theater.stock, theater.display):
            for pid, quantity in inventory.items():
                product = self.get("products", pid)
                rate = getattr(product, "spoilage_rate", None)
                if rate is None:
                    rate = 0.05 if product.category == "packaged" else 0.02
                waste = math.ceil(quantity * rate)
                inventory[pid] -= waste
                spoiled += waste
        tank_waste = 0
        for pid, portions in theater.tanks.items():
            waste = math.ceil(portions * 0.10)
            theater.tanks[pid] -= waste
            tank_waste += waste
        return {"revenue": round(revenue, 2), "supplies": round(supplies, 2), "units": sold_total,
                "spoiled": spoiled, "unserved": missed, "production_waste": production_waste,
                "tank_waste": tank_waste, "items": rows}

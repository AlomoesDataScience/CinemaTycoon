from dataclasses import dataclass, field


@dataclass
class Studio:
    id: int
    name: str
    quality: float
    competence: float
    size: float
    cash: float
    director: str


@dataclass
class Film:
    id: int
    title: str
    genre: str
    subgenre: str
    minutes: int
    studio_id: int
    release_turn: int
    license_fee: float
    variables: dict[str, float]
    acting: str
    quirks: list[str]
    synopsis: str

    @property
    def hours(self):
        return max(1, (self.minutes + 59) // 60)

    @property
    def repeats(self):
        return max(1, 60 // self.minutes) if self.minutes < 60 else 1


@dataclass
class Product:
    id: int
    name: str
    quality: int
    flavors: dict[str, int]
    wholesale: float
    retail: float
    introduced_turn: int
    producer: str
    category: str = "packaged"
    yield_per_unit: int = 1
    deal: str = "wholesale"
    commission: float = 0.25
    unit: str = "box"
    brand: str = ""
    service_name: str = ""
    ingredient_kind: str = ""
    spoilage_rate: float = 0.05


@dataclass
class City:
    id: int
    name: str
    population: int
    rent_factor: float
    tastes: dict[str, float]
    flavors: dict[str, int]


@dataclass
class Room:
    id: int = 1
    name: str = "Screen 1"
    seats: int = 80
    equipment: int = 0
    staff: int = 3
    open: bool = True
    weekly: dict[int, dict[int, int]] = field(default_factory=lambda: {d: {} for d in range(7)})
    film_pool: str = "all"
    auto_start: int = 12
    auto_end: int = 24


@dataclass
class Theater:
    id: int
    name: str
    city_id: int
    group: str = "Main circuit"
    condition: float = 85.0
    ticket_price: float = 8.0
    rooms: list[Room] = field(default_factory=lambda: [Room()])
    stock: dict[int, int] = field(default_factory=dict)
    auto_schedule: bool = False
    auto_stock: bool = False
    stock_budget: float = 600.0
    display: dict[int, int] = field(default_factory=dict)
    prices: dict[int, float] = field(default_factory=dict)
    contracts: list[int] = field(default_factory=list)
    popcorn_machine: str = "basic"
    soda_machine: str = "basic"
    merchandiser: bool = False
    tanks: dict[int, int] = field(default_factory=dict)
    kernel_id: int = 0
    topping_id: int = 0
    popcorn_limit: int = 1000
    stock_targets: dict[int, int] = field(default_factory=dict)
    display_targets: dict[int, int] = field(default_factory=dict)
    program_policy: str = "manual"
    cash_reserve: float = 10000.0
    auto_prepare: bool = False
    automation_spent: float = 0.0

    # Compatibility accessors for the original single-screen simulation API.
    @property
    def schedule(self):
        return self.rooms[0].weekly[0]

    @property
    def seats(self):
        return self.rooms[0].seats

    @seats.setter
    def seats(self, value):
        self.rooms[0].seats = value

    @property
    def equipment(self):
        return self.rooms[0].equipment

    @equipment.setter
    def equipment(self, value):
        self.rooms[0].equipment = value


@dataclass
class State:
    company: str
    year: int
    month: int
    seed: int
    cash: float = 65000.0
    month_open_cash: float = 65000.0
    planning_spend: dict[str, float] = field(default_factory=dict)
    turn: int = 0
    rng_counter: int = 0
    next_id: int = 1
    reputation: float = 50.0
    max_settlements: int = 250
    studios: list[Studio] = field(default_factory=list)
    films: list[Film] = field(default_factory=list)
    products: list[Product] = field(default_factory=list)
    cities: list[City] = field(default_factory=list)
    theaters: list[Theater] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    pending_event: str = ""
    event_demand: float = 0.0
    last_report: dict = field(default_factory=dict)
    news: list[str] = field(default_factory=list)
    bankrupt: bool = False

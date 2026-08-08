"""Seeds fake braider accounts with fully completed onboarding, spread across
France, Germany, Luxembourg, and Spain, for local search/discovery testing.

Bypasses the real signup/OTP/Veriff/Stripe-webhook flows entirely - every
`*_completed_at` field on BraiderOnboardingStatus is set directly (same
approach `tests/helpers.py` / `tests/modules/braiders/test_service_location.py`
use to fake onboarding progress in tests), and a fake StripeConnectAccount
row stands in for a real Connect account. None of this hits Stripe or Veriff.

Idempotent: safe to re-run - skips a braider whose seed email already exists.

Run from the repo root:
    python -m scripts.seed_braiders
"""
import asyncio
import random
import uuid
from datetime import time
from decimal import Decimal
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.modules.braiders import repository as braiders_repo
from app.modules.braiders.availability import repository as availability_repo
from app.modules.braiders.availability.models import DayOfWeek
from app.modules.braiders.completion import mark_step_complete
from app.modules.braiders.models import BioSource, Gender, OnboardingStep
from app.modules.braiders.offerings import repository as offerings_repo
from app.modules.braiders.payment_setup.models import StripeConnectAccount
from app.modules.braiders.portfolio import repository as portfolio_repo
from app.modules.braiders.service_location import repository as service_location_repo
from app.modules.braiders.service_location.models import LocationType
from app.modules.styles import repository as styles_repo
from app.modules.users import repository as users_repo
from app.modules.users.models import UserType

random.seed(20260808)  # deterministic re-runs

SEED_PASSWORD = "SeedBraider123!"
SEED_EMAIL_DOMAIN = "seed.afrobraid.dev"

# Same real uploaded image reused for every seeded braider's logo and cover
# photo - not per-braider content, just a placeholder so search results and
# profile cards render something instead of blank space.
SHARED_LOGO_KEY = "braiders/877177d1-1e8b-47b6-a96d-81a008b2653f/logo/442d42f0-94ec-46de-8476-9315a73ca435.jpg"
SHARED_PORTFOLIO_KEY = (
    "braiders/877177d1-1e8b-47b6-a96d-81a008b2653f/portfolio/144ca43d-811d-426e-91fc-21d2df1b0d2f.jpg"
)


class CitySeed(TypedDict):
    city: str
    country: str
    postal_code: str
    latitude: str
    longitude: str


CITIES: list[CitySeed] = [
    # France (10)
    {"city": "Paris", "country": "FR", "postal_code": "75011", "latitude": "48.856600", "longitude": "2.352200"},
    {"city": "Marseille", "country": "FR", "postal_code": "13001", "latitude": "43.296500", "longitude": "5.369800"},
    {"city": "Lyon", "country": "FR", "postal_code": "69002", "latitude": "45.764000", "longitude": "4.835700"},
    {"city": "Toulouse", "country": "FR", "postal_code": "31000", "latitude": "43.604700", "longitude": "1.444200"},
    {"city": "Nice", "country": "FR", "postal_code": "06000", "latitude": "43.710200", "longitude": "7.261900"},
    {"city": "Nantes", "country": "FR", "postal_code": "44000", "latitude": "47.218400", "longitude": "-1.553600"},
    {"city": "Strasbourg", "country": "FR", "postal_code": "67000", "latitude": "48.573400", "longitude": "7.752300"},
    {"city": "Montpellier", "country": "FR", "postal_code": "34000", "latitude": "43.610800", "longitude": "3.876700"},
    {"city": "Bordeaux", "country": "FR", "postal_code": "33000", "latitude": "44.837800", "longitude": "-0.579200"},
    {"city": "Lille", "country": "FR", "postal_code": "59000", "latitude": "50.629200", "longitude": "3.057300"},
    # Germany (12)
    {"city": "Berlin", "country": "DE", "postal_code": "10115", "latitude": "52.531677", "longitude": "13.381777"},
    {"city": "Munich", "country": "DE", "postal_code": "80331", "latitude": "48.135125", "longitude": "11.581981"},
    {"city": "Hamburg", "country": "DE", "postal_code": "20095", "latitude": "53.551086", "longitude": "9.993682"},
    {"city": "Cologne", "country": "DE", "postal_code": "50667", "latitude": "50.937531", "longitude": "6.960279"},
    {"city": "Frankfurt", "country": "DE", "postal_code": "60311", "latitude": "50.110924", "longitude": "8.682127"},
    {"city": "Stuttgart", "country": "DE", "postal_code": "70173", "latitude": "48.775846", "longitude": "9.182932"},
    {"city": "Dusseldorf", "country": "DE", "postal_code": "40213", "latitude": "51.227741", "longitude": "6.773456"},
    {"city": "Dortmund", "country": "DE", "postal_code": "44135", "latitude": "51.513587", "longitude": "7.465298"},
    {"city": "Essen", "country": "DE", "postal_code": "45127", "latitude": "51.455643", "longitude": "7.011555"},
    {"city": "Leipzig", "country": "DE", "postal_code": "04109", "latitude": "51.339695", "longitude": "12.373075"},
    {"city": "Bremen", "country": "DE", "postal_code": "28195", "latitude": "53.079296", "longitude": "8.801694"},
    {"city": "Dresden", "country": "DE", "postal_code": "01067", "latitude": "51.050409", "longitude": "13.737262"},
    # Luxembourg (7)
    {"city": "Luxembourg City", "country": "LU", "postal_code": "1116", "latitude": "49.611622", "longitude": "6.131935"},
    {"city": "Esch-sur-Alzette", "country": "LU", "postal_code": "4130", "latitude": "49.495679", "longitude": "5.980558"},
    {"city": "Differdange", "country": "LU", "postal_code": "4602", "latitude": "49.524220", "longitude": "5.891900"},
    {"city": "Dudelange", "country": "LU", "postal_code": "3452", "latitude": "49.480770", "longitude": "6.087220"},
    {"city": "Ettelbruck", "country": "LU", "postal_code": "9012", "latitude": "49.847500", "longitude": "6.104800"},
    {"city": "Diekirch", "country": "LU", "postal_code": "9211", "latitude": "49.867500", "longitude": "6.155800"},
    {"city": "Wiltz", "country": "LU", "postal_code": "9501", "latitude": "49.964900", "longitude": "5.933900"},
    # Spain (1)
    {"city": "Madrid", "country": "ES", "postal_code": "28013", "latitude": "40.416775", "longitude": "-3.703790"},
]

_FIRST_NAMES = [
    "Amara", "Fatou", "Aissatou", "Chiamaka", "Ngozi", "Aminata", "Adaeze", "Zainab",
    "Khadija", "Awa", "Bintou", "Adama", "Efe", "Yetunde", "Folake", "Ijeoma",
    "Mariama", "Rokia", "Coumba", "Nadia", "Habiba", "Salimata", "Rahma", "Aicha",
    "Oumou", "Djeneba", "Halima", "Fanta", "Sira", "Kadiatou",
]
_LAST_NAMES = [
    "Diallo", "Diop", "Traore", "Bamba", "Toure", "Camara", "Sow", "Kone",
    "Cisse", "Balde", "Sy", "Fall", "Ndiaye", "Sangare", "Keita",
]
_BUSINESS_SUFFIXES = [
    "Braids", "Braid Bar", "Hair Studio", "Braiding Lounge", "Hair Atelier",
    "Braid House", "Beauty Studio", "Braids & Co", "Hair Loft", "Tress Studio",
]

_STYLE_SLUGS = [
    "knotless-braids-classic", "knotless-braids-bohemian", "box-braids-classic",
    "box-braids-bohemian", "cornrows-feed-in", "passion-twists-classic",
    "faux-locs-classic", "fulani-braids-classic",
]

_WEEKLY_WINDOWS = [
    (DayOfWeek.MONDAY, time(9, 0), time(17, 0)),
    (DayOfWeek.TUESDAY, time(9, 0), time(17, 0)),
    (DayOfWeek.WEDNESDAY, time(9, 0), time(17, 0)),
    (DayOfWeek.THURSDAY, time(9, 0), time(17, 0)),
    (DayOfWeek.FRIDAY, time(9, 0), time(17, 0)),
    (DayOfWeek.SATURDAY, time(10, 0), time(14, 0)),
]

_ALL_STEPS = [
    OnboardingStep.BUSINESS_INFO,
    OnboardingStep.PHONE_VERIFICATION,
    OnboardingStep.VERIFF,
    OnboardingStep.SERVICE_TYPE,
    OnboardingStep.PORTFOLIO,
    OnboardingStep.SERVICE_LOCATION,
    OnboardingStep.AVAILABILITY,
    OnboardingStep.PAYMENT_SETUP,
]


async def _seed_one(db: AsyncSession, index: int, city: CitySeed) -> bool:
    email = f"braider{index:02d}@{SEED_EMAIL_DOMAIN}"
    existing = await users_repo.get_user_by_email(db, email)
    if existing is not None:
        print(f"  = already exists: {email}")
        return False

    first_name = random.choice(_FIRST_NAMES)
    last_name = random.choice(_LAST_NAMES)
    business_name = f"{first_name}'s {random.choice(_BUSINESS_SUFFIXES)}"

    user = await users_repo.create_user(
        db,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_number=None,
        password_hash=hash_password(SEED_PASSWORD),
        user_type=UserType.BRAIDER,
        is_email_verified=True,
    )

    profile = await braiders_repo.create_profile_for_user(db, user.id)
    profile.business_name = business_name
    profile.gender = random.choice(list(Gender))
    profile.logo_object_key = SHARED_LOGO_KEY
    profile.bio_en = f"{business_name} - professional braiding in {city['city']}."
    profile.bio_de = f"{business_name} - professionelles Braiding in {city['city']}."
    profile.bio_fr = f"{business_name} - tressage professionnel a {city['city']}."
    profile.bio_en_source = BioSource.HUMAN
    profile.bio_de_source = BioSource.MACHINE
    profile.bio_fr_source = BioSource.MACHINE

    await portfolio_repo.create_image(
        db, braider_id=profile.id, object_key=SHARED_PORTFOLIO_KEY, position=0
    )

    location = await service_location_repo.create_for_braider(db, profile.id)
    location.location_type = LocationType.SALON
    location.salon_name = business_name
    location.address_line1 = f"{random.randint(1, 150)} Rue Principale"
    location.city = city["city"]
    location.postal_code = city["postal_code"]
    location.country = city["country"]
    location.latitude = Decimal(city["latitude"])
    location.longitude = Decimal(city["longitude"])
    location.offers_mobile = True
    location.travel_radius_km = random.choice([5, 10, 15, 20])
    location.travel_fee = Decimal(random.choice(["0.00", "10.00", "15.00", "20.00"]))

    settings = await availability_repo.create_settings_for_braider(db, profile.id)
    settings.timezone = "Europe/Paris" if city["country"] != "DE" else "Europe/Berlin"
    for day, start, end in _WEEKLY_WINDOWS:
        await availability_repo.create_weekly_window(
            db, braider_id=profile.id, day_of_week=day, start_time=start, end_time=end
        )

    for slug in random.sample(_STYLE_SLUGS, k=2):
        style = await styles_repo.get_style_by_slug(db, slug)
        if style is None:
            continue  # styles catalog not seeded yet - skip, don't fail the whole braider
        await offerings_repo.create_braider_style(
            db,
            braider_id=profile.id,
            style_id=style.id,
            base_price=Decimal(random.choice(["45.00", "60.00", "75.00", "90.00"])),
            duration_minutes=random.choice([60, 90, 120, 150]),
        )

    db.add(
        StripeConnectAccount(
            braider_id=profile.id,
            stripe_account_id=f"acct_seed_{uuid.uuid4().hex[:16]}",
            charges_enabled=True,
            payouts_enabled=True,
            details_submitted=True,
        )
    )

    status = await braiders_repo.create_onboarding_status_for_user(db, user.id)
    for step in _ALL_STEPS:
        mark_step_complete(status, step)

    await db.flush()
    print(f"  + created: {email} ({business_name}, {city['city']}, {city['country']})")
    return True


async def main() -> None:
    created = 0
    async with AsyncSessionLocal() as db:
        for index, city in enumerate(CITIES, start=1):
            if await _seed_one(db, index, city):
                created += 1
        await db.commit()

    by_country: dict[str, int] = {}
    for city in CITIES:
        by_country[city["country"]] = by_country.get(city["country"], 0) + 1

    print(f"\nDone: {created} new braider(s) created (of {len(CITIES)} total in the plan).")
    print(f"Distribution: {by_country}")
    print(f"All seeded logins use password: {SEED_PASSWORD!r}, email pattern braiderNN@{SEED_EMAIL_DOMAIN}")


if __name__ == "__main__":
    asyncio.run(main())

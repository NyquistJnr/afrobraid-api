"""Seeds the master style catalog: categories, styles (with variations), and
global add-ons, written directly in all three supported locales (en/de/fr).

Content here is authored directly rather than routed through the async DeepL
pipeline (which needs a running arq worker to actually translate anything) -
`de`/`fr` values are marked TranslationSource.MACHINE so they still surface
for human review in an eventual admin panel, same as a real auto-translation
would.

Idempotent: safe to re-run - skips a category/style/add-on that already
exists by slug (a style's variations are only ever created alongside a
brand-new style, so skipping the style also skips re-creating its
variations).

Does not seed images - those are real photos and need to go through
POST /api/v1/admin/styles/{id}/images/upload-url + .../confirm.

Run from the repo root:
    python -m scripts.seed_styles
"""
import asyncio
import uuid
from decimal import Decimal
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.modules.styles import repository as styles_repo
from app.modules.styles.models import AddOn, Style, StyleCategory, StyleVariation, TranslationSource

# styles.created_by is a string ForeignKey("users.id") - SQLAlchemy can't
# resolve it unless the users table has been registered on Base.metadata
# somewhere first (same reason alembic/env.py and app/worker.py import this).
from app.modules.users import models as users_models  # noqa: F401,E402


class LocalizedText(TypedDict):
    en: str
    de: str
    fr: str


class CategorySeed(TypedDict):
    slug: str
    name: LocalizedText


class StyleSeed(TypedDict):
    slug: str
    category: str
    name: LocalizedText
    description: LocalizedText
    variations: list[LocalizedText]


class AddOnSeed(TypedDict):
    slug: str
    name: LocalizedText
    suggested_price: str


CATEGORIES: list[CategorySeed] = [
    {
        "slug": "knotless-braids",
        "name": {"en": "Knotless Braids", "de": "Knotless Braids", "fr": "Tresses Knotless"},
    },
    {
        "slug": "box-braids",
        "name": {"en": "Box Braids", "de": "Box Braids", "fr": "Box Braids"},
    },
    {
        "slug": "cornrows",
        "name": {"en": "Cornrows", "de": "Cornrows", "fr": "Nattes Collées"},
    },
    {
        "slug": "passion-twists",
        "name": {"en": "Passion Twists", "de": "Passion Twists", "fr": "Passion Twists"},
    },
    {
        "slug": "faux-locs",
        "name": {"en": "Faux Locs", "de": "Faux Locs", "fr": "Faux Locs"},
    },
    {
        "slug": "fulani-braids",
        "name": {"en": "Fulani Braids", "de": "Fulani-Zöpfe", "fr": "Tresses Fulani"},
    },
]

_LENGTH_VARIATIONS: list[LocalizedText] = [
    {"en": "Shoulder Length", "de": "Schulterlang", "fr": "Longueur Épaule"},
    {"en": "Mid-Back Length", "de": "Rückenlang (Mitte)", "fr": "Longueur Mi-Dos"},
    {"en": "Waist Length", "de": "Hüftlang", "fr": "Longueur Taille"},
]
_SIZE_VARIATIONS: list[LocalizedText] = [
    {"en": "Small", "de": "Klein", "fr": "Fines"},
    {"en": "Medium", "de": "Mittel", "fr": "Moyennes"},
    {"en": "Large", "de": "Groß", "fr": "Épaisses"},
    {"en": "Jumbo", "de": "Jumbo", "fr": "Jumbo"},
]

STYLES: list[StyleSeed] = [
    {
        "slug": "knotless-braids-classic",
        "category": "knotless-braids",
        "name": {
            "en": "Classic Knotless Braids",
            "de": "Klassische Knotless Braids",
            "fr": "Tresses Knotless Classiques",
        },
        "description": {
            "en": "Braids that start without the tight knot at the root, so there's minimal "
            "tension on your scalp from the very first row.",
            "de": "Zöpfe, die ohne den festen Knoten am Ansatz beginnen – dadurch ist die "
            "Spannung auf der Kopfhaut von der ersten Reihe an deutlich geringer.",
            "fr": "Des tresses qui commencent sans le nœud serré à la racine, pour une "
            "tension minimale sur le cuir chevelu dès la première rangée.",
        },
        "variations": _LENGTH_VARIATIONS,
    },
    {
        "slug": "knotless-braids-bohemian",
        "category": "knotless-braids",
        "name": {
            "en": "Bohemian Knotless Braids",
            "de": "Bohemian Knotless Braids",
            "fr": "Tresses Knotless Bohème",
        },
        "description": {
            "en": "Knotless braids finished with soft, curly pieces woven through for a "
            "lighter, more textured look.",
            "de": "Knotless Braids, die mit weichen, lockigen Strähnen durchzogen werden – "
            "für einen leichteren, texturierten Look.",
            "fr": "Des tresses knotless agrémentées de mèches bouclées et légères pour un "
            "rendu plus texturé et naturel.",
        },
        "variations": _LENGTH_VARIATIONS[1:],
    },
    {
        "slug": "box-braids-classic",
        "category": "box-braids",
        "name": {
            "en": "Classic Box Braids",
            "de": "Klassische Box Braids",
            "fr": "Box Braids Classiques",
        },
        "description": {
            "en": "The braiding staple: individual square-parted braids in whatever "
            "thickness suits you.",
            "de": "Der Klassiker unter den Zopffrisuren: einzelne, quadratisch abgeteilte "
            "Zöpfe in der Dicke deiner Wahl.",
            "fr": "Le grand classique des tresses : des tresses individuelles à section "
            "carrée, dans l'épaisseur de votre choix.",
        },
        "variations": _SIZE_VARIATIONS,
    },
    {
        "slug": "box-braids-bohemian",
        "category": "box-braids",
        "name": {
            "en": "Bohemian Box Braids",
            "de": "Bohemian Box Braids",
            "fr": "Box Braids Bohème",
        },
        "description": {
            "en": "Box braids with curly pieces left loose at intervals for a softer, "
            "boho finish.",
            "de": "Box Braids mit locker eingearbeiteten lockigen Strähnen für einen "
            "weicheren, boho-inspirierten Look.",
            "fr": "Des box braids parsemées de mèches bouclées et détachées pour une "
            "touche bohème et naturelle.",
        },
        "variations": _SIZE_VARIATIONS[1:3],
    },
    {
        "slug": "cornrows-straight-back",
        "category": "cornrows",
        "name": {
            "en": "Straight-Back Cornrows",
            "de": "Cornrows nach hinten",
            "fr": "Nattes Collées Droites",
        },
        "description": {
            "en": "Sleek cornrows braided straight back from the hairline to the nape - "
            "simple, clean, and low-maintenance.",
            "de": "Glatte Cornrows, die vom Haaransatz gerade nach hinten bis zum Nacken "
            "geflochten werden – schlicht, sauber und pflegeleicht.",
            "fr": "Des nattes collées lisses, tressées bien droites du front jusqu'à la "
            "nuque - simples, nettes et faciles à entretenir.",
        },
        "variations": [],
    },
    {
        "slug": "cornrows-feed-in",
        "category": "cornrows",
        "name": {
            "en": "Feed-In Cornrows",
            "de": "Feed-In Cornrows",
            "fr": "Nattes Collées Feed-In",
        },
        "description": {
            "en": "Cornrows with hair fed in gradually for a natural taper, styled in a "
            "custom pattern of your choice.",
            "de": "Cornrows, bei denen zusätzliches Haar schrittweise eingearbeitet wird – "
            "für einen natürlichen Verlauf in einem Muster deiner Wahl.",
            "fr": "Des nattes collées où la mèche est incorporée progressivement pour un "
            "effet naturel, dans le motif de votre choix.",
        },
        "variations": [],
    },
    {
        "slug": "passion-twists-classic",
        "category": "passion-twists",
        "name": {
            "en": "Classic Passion Twists",
            "de": "Klassische Passion Twists",
            "fr": "Passion Twists Classiques",
        },
        "description": {
            "en": "Soft, rope-like twists made with pre-feathered hair for a natural, "
            "bouncy texture.",
            "de": "Weiche, seilartige Twists aus vorgezupftem Haar für eine natürliche, "
            "federleichte Textur.",
            "fr": "Des torsades souples, réalisées avec des mèches pré-effilochées pour "
            "une texture naturelle et rebondissante.",
        },
        "variations": _LENGTH_VARIATIONS,
    },
    {
        "slug": "passion-twists-bob",
        "category": "passion-twists",
        "name": {
            "en": "Passion Twists Bob",
            "de": "Passion Twists Bob",
            "fr": "Passion Twists Carré",
        },
        "description": {
            "en": "Passion twists cut and styled into a chin-to-shoulder bob.",
            "de": "Passion Twists, geschnitten und gestylt zu einem Bob in Kinn- bis "
            "Schulterlänge.",
            "fr": "Des passion twists coupées et coiffées en carré, du menton jusqu'aux "
            "épaules.",
        },
        "variations": [],
    },
    {
        "slug": "faux-locs-classic",
        "category": "faux-locs",
        "name": {
            "en": "Classic Faux Locs",
            "de": "Klassische Faux Locs",
            "fr": "Faux Locs Classiques",
        },
        "description": {
            "en": "Soft, lightweight locs wrapped around your natural hair - the look of "
            "locs without the long-term commitment.",
            "de": "Weiche, leichte Locs, die um dein natürliches Haar gewickelt werden – "
            "der Loc-Look ganz ohne langfristige Verpflichtung.",
            "fr": "Des locks douces et légères enroulées autour de vos cheveux naturels - "
            "l'apparence des locks sans l'engagement à long terme.",
        },
        "variations": _SIZE_VARIATIONS[:3],
    },
    {
        "slug": "faux-locs-goddess",
        "category": "faux-locs",
        "name": {
            "en": "Goddess Faux Locs",
            "de": "Goddess Faux Locs",
            "fr": "Faux Locs Goddess",
        },
        "description": {
            "en": "Faux locs finished with curly ends left loose for a fuller, more "
            "romantic look.",
            "de": "Faux Locs mit locker gelassenen, lockigen Spitzen für einen volleren, "
            "romantischeren Look.",
            "fr": "Des faux locs terminées par des pointes bouclées et détachées pour un "
            "rendu plus volumineux et romantique.",
        },
        "variations": _SIZE_VARIATIONS[1:3],
    },
    {
        "slug": "fulani-braids-classic",
        "category": "fulani-braids",
        "name": {
            "en": "Classic Fulani Braids",
            "de": "Klassische Fulani-Zöpfe",
            "fr": "Tresses Fulani Classiques",
        },
        "description": {
            "en": "Cornrows down the middle with braids on the sides, finished with beads "
            "along the front for the traditional Fulani look.",
            "de": "Cornrows in der Mitte, seitliche Zöpfe und Perlen entlang des Ansatzes – "
            "der traditionelle Fulani-Look.",
            "fr": "Des nattes collées au centre, des tresses sur les côtés et des perles "
            "le long du front pour le look Fulani traditionnel.",
        },
        "variations": [],
    },
    {
        "slug": "fulani-braids-half-up",
        "category": "fulani-braids",
        "name": {
            "en": "Half-Up Fulani Braids",
            "de": "Halboffene Fulani-Zöpfe",
            "fr": "Tresses Fulani Mi-Attachées",
        },
        "description": {
            "en": "Fulani braids gathered into a half-up style, leaving the ends free.",
            "de": "Fulani-Zöpfe, halb hochgesteckt, mit frei fallenden Spitzen.",
            "fr": "Des tresses Fulani rassemblées à mi-hauteur, laissant les pointes "
            "libres.",
        },
        "variations": [],
    },
]

ADDONS: list[AddOnSeed] = [
    {
        "slug": "beads",
        "name": {"en": "Beads", "de": "Perlen", "fr": "Perles"},
        "suggested_price": "15.00",
    },
    {
        "slug": "curly-ends",
        "name": {"en": "Curly Ends", "de": "Lockige Spitzen", "fr": "Pointes Bouclées"},
        "suggested_price": "12.00",
    },
    {
        "slug": "hair-wash-deep-condition",
        "name": {
            "en": "Hair Wash & Deep Condition",
            "de": "Haarwäsche & Tiefenpflege",
            "fr": "Shampoing & Soin Profond",
        },
        "suggested_price": "20.00",
    },
    {
        "slug": "color-rinse",
        "name": {
            "en": "Color Rinse",
            "de": "Farbspülung",
            "fr": "Coloration Semi-Permanente",
        },
        "suggested_price": "25.00",
    },
    {
        "slug": "jewelry-cuffs",
        "name": {"en": "Jewelry & Cuffs", "de": "Schmuck & Zopfringe", "fr": "Bijoux & Anneaux"},
        "suggested_price": "8.00",
    },
    {
        "slug": "extra-length",
        "name": {
            "en": "Extra-Long Length",
            "de": "Extra Länge",
            "fr": "Longueur Supplémentaire",
        },
        "suggested_price": "18.00",
    },
    {
        "slug": "take-down-removal",
        "name": {
            "en": "Take-Down & Removal",
            "de": "Entfernen der alten Frisur",
            "fr": "Retrait de l'Ancienne Coiffure",
        },
        "suggested_price": "30.00",
    },
    {
        "slug": "scalp-treatment",
        "name": {
            "en": "Scalp Treatment",
            "de": "Kopfhautbehandlung",
            "fr": "Soin du Cuir Chevelu",
        },
        "suggested_price": "15.00",
    },
]


def _set_localized(entity: object, field: str, values: LocalizedText) -> None:
    setattr(entity, f"{field}_en", values["en"])
    setattr(entity, f"{field}_de", values["de"])
    setattr(entity, f"{field}_fr", values["fr"])
    setattr(entity, f"{field}_en_source", TranslationSource.HUMAN)
    setattr(entity, f"{field}_de_source", TranslationSource.MACHINE)
    setattr(entity, f"{field}_fr_source", TranslationSource.MACHINE)


async def _seed_categories(db: AsyncSession) -> dict[str, uuid.UUID]:
    slug_to_id: dict[str, uuid.UUID] = {}
    for order, cat in enumerate(CATEGORIES, start=1):
        existing = await styles_repo.get_category_by_slug(db, cat["slug"])
        if existing is not None:
            print(f"  = category already exists: {cat['slug']}")
            slug_to_id[cat["slug"]] = existing.id
            continue
        category: StyleCategory = await styles_repo.create_category(
            db, slug=cat["slug"], name_en="", display_order=order
        )
        _set_localized(category, "name", cat["name"])
        slug_to_id[cat["slug"]] = category.id
        print(f"  + created category: {cat['slug']}")
    await db.flush()
    return slug_to_id


async def _seed_styles(db: AsyncSession, category_ids: dict[str, uuid.UUID]) -> None:
    for style_data in STYLES:
        existing = await styles_repo.get_style_by_slug(db, style_data["slug"])
        if existing is not None:
            print(f"  = style already exists: {style_data['slug']}")
            continue

        style: Style = await styles_repo.create_style(
            db,
            category_id=category_ids[style_data["category"]],
            slug=style_data["slug"],
            name_en="",
            description_en=None,
            created_by=None,
        )
        _set_localized(style, "name", style_data["name"])
        _set_localized(style, "description", style_data["description"])
        style.is_active = True
        await db.flush()

        for order, variation_names in enumerate(style_data["variations"]):
            variation: StyleVariation = await styles_repo.create_style_variation(
                db, style_id=style.id, name_en="", display_order=order
            )
            _set_localized(variation, "name", variation_names)

        await db.flush()
        print(
            f"  + created style: {style_data['slug']} "
            f"({len(style_data['variations'])} variation(s))"
        )


async def _seed_addons(db: AsyncSession) -> None:
    for addon_data in ADDONS:
        existing = await styles_repo.get_addon_by_slug(db, addon_data["slug"])
        if existing is not None:
            print(f"  = add-on already exists: {addon_data['slug']}")
            continue
        addon: AddOn = await styles_repo.create_addon(
            db,
            slug=addon_data["slug"],
            name_en="",
            suggested_price=Decimal(addon_data["suggested_price"]),
        )
        _set_localized(addon, "name", addon_data["name"])
        print(f"  + created add-on: {addon_data['slug']}")
    await db.flush()


async def main() -> None:
    async with AsyncSessionLocal() as db:
        print("Categories:")
        category_ids = await _seed_categories(db)
        print("Styles:")
        await _seed_styles(db, category_ids)
        print("Add-ons:")
        await _seed_addons(db)
        await db.commit()

    print(
        f"\nDone: {len(CATEGORIES)} categories, {len(STYLES)} styles, "
        f"{len(ADDONS)} add-ons (idempotent - existing ones were left untouched)."
    )
    print(
        "No images were seeded - add real photos per style via "
        "POST /api/v1/admin/styles/{id}/images/upload-url + .../confirm."
    )


if __name__ == "__main__":
    asyncio.run(main())

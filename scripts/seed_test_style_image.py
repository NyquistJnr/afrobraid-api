"""TEST-ONLY: attaches a single existing R2 image to every style's image list,
so every style has at least one photo to render in the UI/app during testing.

Reuses one already-uploaded object_key across all styles rather than
re-uploading a copy per style - fine for test/dev data, not something to run
against a real catalog with real photos.

Idempotent: skips a style that already has an image pointing at this exact
object_key.

Run from the repo root:
    python -m scripts.seed_test_style_image
"""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.modules.styles import repository as styles_repo
from app.modules.styles.models import Style, StyleImage

# styles.created_by is a string ForeignKey("users.id") - SQLAlchemy can't
# resolve it unless the users table has been registered on Base.metadata
# somewhere first (same reason alembic/env.py and app/worker.py import this).
from app.modules.users import models as users_models  # noqa: F401,E402

TEST_OBJECT_KEY = "styles/75d7ec5c-a8af-4794-b746-e80da47d3dad/images/7248b377-7dca-4cd0-bfb0-ff880ea4b5df.png"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Style))
        styles = list(result.scalars().all())

        created = 0
        skipped = 0
        for style in styles:
            existing_images = await styles_repo.list_style_images(db, style.id)
            if any(img.object_key == TEST_OBJECT_KEY for img in existing_images):
                print(f"  = already has test image: {style.slug}")
                skipped += 1
                continue

            next_position = max((img.position for img in existing_images), default=-1) + 1
            image: StyleImage = await styles_repo.create_style_image(
                db, style_id=style.id, object_key=TEST_OBJECT_KEY, position=next_position
            )
            print(f"  + attached test image to: {style.slug} (position {image.position})")
            created += 1

        await db.commit()

    print(f"\nDone: {created} attached, {skipped} already had it. {len(styles)} styles total.")


if __name__ == "__main__":
    asyncio.run(main())

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile
from app.models.org import Org
from app.models.import_run import ImportRun
from app.logger import logger
from app.services.opencorporates import OpenCorporatesClient, JURISDICTIONS
from app.services.diaspora_scraper import (
    DIRECTORY_SOURCES,
    ORGS_TARGETED,
    fetch_and_parse,
)
from app.services.segmenter import segment_by_role


async def run_diaspora_import(import_run_id: str, db: AsyncSession) -> None:
    run = await db.get(ImportRun, import_run_id)
    if not run:
        return

    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    await db.commit()

    oc = None
    try:
        oc = OpenCorporatesClient()
        seen_org_ids: set[str] = set()
        seen_profile_ids: set[str] = set()
        profile_batch: list[Profile] = []
        org_batch: list[Org] = []

        # Phase 1: OpenCorporates
        if oc.available:
            for jurisdiction in JURISDICTIONS:
                logger.info("Diaspora import: searching %s via OpenCorporates", jurisdiction)
                companies = await oc.search_diaspora_companies(jurisdiction, max_pages=2)
                run.records_found += len(companies)

                for item in companies:
                    company = oc.parse_company(item)
                    if not company:
                        continue

                    cid = company["source_id"]
                    if cid in seen_org_ids:
                        continue
                    seen_org_ids.add(cid)

                    dup = await db.execute(
                        select(Org).where(Org.source_id == cid)
                    )
                    if dup.scalar_one_or_none():
                        continue

                    org = Org(
                        id=str(uuid4()),
                        source=company["source"],
                        source_id=company["source_id"],
                        name=company["name"],
                        company_number=company["company_number"],
                        status=company["status"],
                        company_type=company["company_type"],
                        sic_codes=company["sic_codes"],
                        registered_address=company["registered_address"],
                        locality=company["locality"],
                        region=company["region"],
                        country=company["country"],
                        postal_code=company["postal_code"],
                        incorporation_date=company["incorporation_date"],
                        org_type=company.get("company_type") or "company",
                        tags=company["tags"],
                        origin=company.get("origin"),
                    )
                    org_batch.append(org)
                    run.orgs_imported += 1

                    if len(org_batch) >= 50:
                        db.add_all(org_batch)
                        await db.commit()
                        org_batch.clear()

                    try:
                        officers = await oc.get_officers(jurisdiction, company["company_number"])
                        for off_item in officers:
                            officer = oc.parse_officer(off_item, jurisdiction, company["name"])
                            if not officer or not officer["name"]:
                                continue

                            pid = officer["source_id"]
                            if pid in seen_profile_ids:
                                continue
                            seen_profile_ids.add(pid)

                            dup_p = await db.execute(
                                select(Profile).where(Profile.source_id == pid)
                            )
                            if dup_p.scalar_one_or_none():
                                continue

                            segment = segment_by_role(officer.get("role"))
                            profile = Profile(
                                id=str(uuid4()),
                                source=officer["source"],
                                source_id=officer["source_id"],
                                name=officer["name"],
                                role=officer["role"],
                                company_name=officer["company_name"],
                                company_number=officer["company_number"],
                                nationality=officer["nationality"],
                                date_of_birth=officer["date_of_birth"],
                                country_of_residence=officer["country_of_residence"],
                                address_line_1=officer["address_line_1"],
                                address_line_2=officer["address_line_2"],
                                locality=officer["locality"],
                                region=officer["region"],
                                postal_code=officer["postal_code"],
                                country=officer["country"],
                                occupation=officer["occupation"],
                                is_active=officer["is_active"],
                                tags=officer["tags"],
                                segment=segment,
                                origin=officer["origin"],
                            )
                            profile_batch.append(profile)
                            run.records_imported += 1

                            if len(profile_batch) >= 50:
                                db.add_all(profile_batch)
                                await db.commit()
                                profile_batch.clear()

                        await db.commit()
                    except Exception as exc:
                        logger.warning("Error fetching officers for company %s: %s", company.get("name", "?"), exc)
        else:
            logger.info("OpenCorporates API key not set — skipping Phase 1")

        if org_batch:
            db.add_all(org_batch)
            await db.commit()
            org_batch.clear()
        if profile_batch:
            db.add_all(profile_batch)
            await db.commit()
            profile_batch.clear()

        # Phase 2: Local directory scraping
        for source in DIRECTORY_SOURCES:
            logger.info("Diaspora import: scraping %s", source["url"])
            try:
                items = await fetch_and_parse(source["url"], source["parser"])
                for item in items:
                    dup = await db.execute(
                        select(Org).where(Org.name == item["name"])
                    )
                    if dup.scalar_one_or_none():
                        continue

                    org = Org(
                        id=str(uuid4()),
                        source="diaspora_directory",
                        source_id=None,
                        name=item["name"],
                        locality=item.get("locality"),
                        region=item.get("region"),
                        country=item.get("country", "United States"),
                        org_type=item.get("org_type", "organization"),
                        tags=item.get("tags", ["diaspora"]),
                        origin=item.get("origin"),
                    )
                    org_batch.append(org)
                    run.orgs_imported += 1

                    if len(org_batch) >= 50:
                        db.add_all(org_batch)
                        await db.commit()
                        org_batch.clear()

                if org_batch:
                    db.add_all(org_batch)
                    await db.commit()
                    org_batch.clear()
            except Exception:
                logger.warning("Failed to scrape %s", source["url"])

        # Phase 3: Known targeted organizations
        for item in ORGS_TARGETED:
            dup = await db.execute(
                select(Org).where(Org.name == item["name"])
            )
            if dup.scalar_one_or_none():
                continue
            org = Org(
                id=str(uuid4()),
                source="diaspora_directory",
                source_id=None,
                name=item["name"],
                locality=item.get("locality"),
                region=item.get("region"),
                country=item.get("country", "United States"),
                org_type=item.get("org_type", "organization"),
                tags=item.get("tags", ["diaspora"]),
                origin=item.get("origin"),
            )
            db.add(org)
            run.orgs_imported += 1

        await db.commit()
        run.status = "completed"
        logger.info(
            "Diaspora import completed: %d records, %d orgs",
            run.records_imported,
            run.orgs_imported,
        )

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)[:500]
        logger.error("Diaspora import failed", exc_info=e)
    finally:
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        if oc:
            await oc.close()
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile
from app.models.org import Org
from app.models.import_run import ImportRun
from app.services.companies_house import CompaniesHouseClient
from app.services.segmenter import segment_by_role, determine_origin


async def run_import(import_run_id: str, db: AsyncSession):
    client = CompaniesHouseClient()
    run = await db.get(ImportRun, import_run_id)
    if not run:
        return

    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    await db.commit()

    try:
        officers = await client.search_officers(nationality="Ghanaian", items_per_page=100)
        run.records_found = len(officers)
        await db.commit()

        seen_company_numbers: set[str] = set()
        batch_size = 50
        batch: list[Profile] = []

        for raw in officers:
            try:
                parsed = client.parse_officer(raw)
                if not parsed.get("name"):
                    run.records_failed += 1
                    continue

                dup = await db.execute(
                    select(Profile).where(Profile.source_id == parsed["source_id"])
                )
                if dup.scalar_one_or_none():
                    run.records_failed += 1
                    continue

                segment = segment_by_role(parsed.get("role"))
                origin = parsed.get("origin") or determine_origin(
                    parsed.get("country_of_residence"), parsed.get("nationality")
                )

                profile = Profile(
                    id=str(uuid4()),
                    source=parsed["source"],
                    source_id=parsed["source_id"],
                    name=parsed["name"],
                    role=parsed["role"],
                    company_name=parsed["company_name"],
                    company_number=parsed["company_number"],
                    nationality=parsed["nationality"],
                    date_of_birth=parsed["date_of_birth"],
                    country_of_residence=parsed["country_of_residence"],
                    address_line_1=parsed["address_line_1"],
                    address_line_2=parsed["address_line_2"],
                    locality=parsed["locality"],
                    region=parsed["region"],
                    postal_code=parsed["postal_code"],
                    country=parsed["country"],
                    occupation=parsed["occupation"],
                    appointed_on=parsed["appointed_on"],
                    resigned_on=parsed["resigned_on"],
                    is_active=parsed["is_active"],
                    segment=segment,
                    origin=origin,
                )
                batch.append(profile)
                run.records_imported += 1

                company_number = parsed.get("company_number")
                if company_number and company_number not in seen_company_numbers:
                    seen_company_numbers.add(company_number)
                    run.orgs_found += 1

                if len(batch) >= batch_size:
                    db.add_all(batch)
                    await db.commit()
                    batch.clear()

            except Exception as e:
                run.records_failed += 1
                continue

        if batch:
            db.add_all(batch)
            await db.commit()
            batch.clear()

        # Fetch company profiles for unique orgs
        org_batch: list[Org] = []
        for company_number in list(seen_company_numbers)[:500]:
            try:
                dup = await db.execute(
                    select(Org).where(Org.source_id == company_number)
                )
                if dup.scalar_one_or_none():
                    continue

                company = await client.get_company_profile(company_number)
                if not company:
                    continue

                address = company.get("registered_office_address", {}) or {}
                org = Org(
                    id=str(uuid4()),
                    source="companies_house",
                    source_id=company_number,
                    name=company.get("company_name", ""),
                    company_number=company_number,
                    status=company.get("company_status"),
                    company_type=company.get("type"),
                    sic_codes=company.get("sic_codes", []),
                    registered_address=", ".join(filter(None, [
                        address.get("address_line_1"),
                        address.get("address_line_2"),
                        address.get("locality"),
                        address.get("region"),
                        address.get("postal_code"),
                        address.get("country"),
                    ])),
                    locality=address.get("locality"),
                    region=address.get("region"),
                    country=address.get("country"),
                    postal_code=address.get("postal_code"),
                    incorporation_date=company.get("date_of_creation"),
                    org_type="company",
                    origin="gh",
                )
                org_batch.append(org)
                run.orgs_imported += 1

                if len(org_batch) >= 50:
                    db.add_all(org_batch)
                    await db.commit()
                    org_batch.clear()

            except Exception:
                continue

        if org_batch:
            db.add_all(org_batch)
            await db.commit()

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)[:500]
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()

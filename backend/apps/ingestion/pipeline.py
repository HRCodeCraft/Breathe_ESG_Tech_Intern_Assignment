"""
Ingestion pipeline orchestrator.

Coordinates: parse → normalize → deduplicate → persist → emit audit event.
Runs synchronously for the prototype; in production would be a Celery task.
"""

import statistics
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.ingestion.models import IngestionRun, RawRecord
from apps.emissions.models import EmissionRecord
from apps.audit.models import AuditEvent
from apps.ingestion.parsers.base import make_source_hash
from apps.ingestion.normalizer import compute_emissions

OUTLIER_Z_THRESHOLD = 3.0  # flag rows beyond 3σ from mean co2e within the same run


def _detect_outliers(records: list[EmissionRecord]) -> list[str]:
    """Return list of record IDs that are statistical outliers within this run."""
    values = [float(r.co2e_kg) for r in records if r.co2e_kg is not None and r.co2e_kg > 0]
    if len(values) < 5:
        return []
    mean = statistics.mean(values)
    stdev = statistics.stdev(values)
    if stdev == 0:
        return []
    outlier_ids = []
    for r in records:
        if r.co2e_kg is not None:
            z = (float(r.co2e_kg) - mean) / stdev
            if abs(z) > OUTLIER_Z_THRESHOLD:
                outlier_ids.append(str(r.id))
    return outlier_ids


def run_ingestion(run: IngestionRun, file_bytes: bytes, user) -> IngestionRun:
    """
    Execute full ingestion pipeline for a given IngestionRun.
    Mutates run.status and run.error_log in place, saves to DB.
    """
    from apps.ingestion.parsers.sap import parse_sap_fuel, parse_sap_procurement
    from apps.ingestion.parsers.utility import parse_utility_electricity
    from apps.ingestion.parsers.travel import parse_travel

    PARSER_MAP = {
        IngestionRun.SourceType.SAP_FUEL: parse_sap_fuel,
        IngestionRun.SourceType.SAP_PROCUREMENT: parse_sap_procurement,
        IngestionRun.SourceType.UTILITY_ELECTRICITY: parse_utility_electricity,
        IngestionRun.SourceType.TRAVEL: parse_travel,
    }

    run.status = IngestionRun.Status.PROCESSING
    run.save(update_fields=['status'])

    AuditEvent.objects.create(
        organization=run.organization,
        user=user,
        action=AuditEvent.Action.RUN_STARTED,
        ingestion_run_id=run.id,
        metadata={'source_type': run.source_type, 'file_name': run.file_name},
    )

    parser = PARSER_MAP.get(run.source_type)
    if parser is None:
        run.status = IngestionRun.Status.FAILED
        run.error_log = [{'error': f'No parser for source type: {run.source_type}'}]
        run.save()
        return run

    created_records = []
    error_log = []
    row_num = 0
    success_count = 0
    skipped_count = 0

    try:
        rows = list(parser(file_bytes, run.file_name))
    except ValueError as e:
        run.status = IngestionRun.Status.FAILED
        run.error_log = [{'error': str(e)}]
        run.save()
        return run

    # Pre-fetch existing source hashes for this org to detect duplicates
    existing_hashes = set(
        EmissionRecord.objects.filter(organization=run.organization)
        .values_list('source_hash', flat=True)
    )

    with transaction.atomic():
        for parsed_row, raw_data, error_msg in rows:
            row_num += 1

            if error_msg:
                raw_rec = RawRecord.objects.create(
                    run=run,
                    row_number=row_num,
                    raw_data=raw_data,
                    parse_status=RawRecord.ParseStatus.ERROR,
                    parse_error=error_msg,
                )
                error_log.append({
                    'row': row_num,
                    'error_type': 'parse_error',
                    'message': error_msg,
                })
                continue

            raw_rec = RawRecord.objects.create(
                run=run,
                row_number=row_num,
                raw_data=raw_data,
                parse_status=RawRecord.ParseStatus.OK,
            )

            source_hash = make_source_hash(run.organization_id, run.source_type, parsed_row)

            if source_hash in existing_hashes:
                raw_rec.parse_status = RawRecord.ParseStatus.SKIPPED
                raw_rec.parse_error = 'Duplicate: matching record already exists'
                raw_rec.save(update_fields=['parse_status', 'parse_error'])
                skipped_count += 1
                continue

            emission_data = compute_emissions(parsed_row)

            record = EmissionRecord.objects.create(
                organization=run.organization,
                ingestion_run=run,
                raw_record=raw_rec,
                source_hash=source_hash,
                scope=parsed_row.scope,
                category=parsed_row.category,
                subcategory=parsed_row.subcategory,
                activity_date=parsed_row.activity_date,
                period_start=parsed_row.period_start,
                period_end=parsed_row.period_end,
                facility=parsed_row.facility,
                cost_center=parsed_row.cost_center,
                supplier=parsed_row.supplier,
                description=parsed_row.description,
                quantity=parsed_row.quantity,
                unit=parsed_row.unit,
                **emission_data,
                status=EmissionRecord.Status.PENDING,
            )
            existing_hashes.add(source_hash)
            created_records.append(record)
            success_count += 1

    # Post-run outlier detection
    outlier_ids = _detect_outliers(created_records)
    if outlier_ids:
        EmissionRecord.objects.filter(id__in=outlier_ids).update(
            flags=_append_flag_to_records(outlier_ids, EmissionRecord.Flag.OUTLIER)
        )
        # Update individually to preserve existing flags
        for rec in created_records:
            if str(rec.id) in outlier_ids:
                if EmissionRecord.Flag.OUTLIER not in rec.flags:
                    rec.flags = rec.flags + [EmissionRecord.Flag.OUTLIER]
                    rec.save(update_fields=['flags'])

    run.row_count = row_num
    run.success_count = success_count
    run.error_count = len(error_log)
    run.skipped_count = skipped_count
    run.error_log = error_log
    run.completed_at = datetime.now(timezone.utc)
    run.status = (
        IngestionRun.Status.COMPLETED_WITH_ERRORS
        if error_log else IngestionRun.Status.COMPLETED
    )
    run.save()

    AuditEvent.objects.create(
        organization=run.organization,
        user=user,
        action=AuditEvent.Action.RUN_COMPLETED,
        ingestion_run_id=run.id,
        metadata={
            'rows': row_num,
            'success': success_count,
            'errors': len(error_log),
            'skipped': skipped_count,
        },
    )

    return run


def _append_flag_to_records(record_ids: list[str], flag: str):
    """Helper — not used for bulk update (we update individually above)."""
    return flag

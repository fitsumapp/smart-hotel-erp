# Phase 0 Baseline and Safety Net

## Supported runtime

- Python: 3.12.x
- Django: 5.2 LTS
- Database: PostgreSQL for development and production
- Test database: in-memory SQLite for fast isolated tests, with PostgreSQL-specific tests guarded where required

## Fresh local setup

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py test --settings=core.settings_test
```

Edit `.env` before using real email, database, or Chapa credentials. Do not commit `.env`.

## Environment settings

- Development: `DJANGO_SETTINGS_MODULE=core.settings_development`
- Test: `DJANGO_SETTINGS_MODULE=core.settings_test`
- Production: `DJANGO_SETTINGS_MODULE=core.settings_production` and `DJANGO_ENV=production`

Production fails during startup if required secrets, database values, payment secrets, strict hosts, or CORS origins are missing.

## Baseline commit and tag

Because the worktree already contains many uncommitted project changes, review the diff before creating the baseline:

```powershell
git status --short
git diff
git add .
git commit -m "chore: establish security remediation baseline"
git tag -a phase-0-baseline -m "Phase 0 protected baseline"
```

Protect the default branch and the `phase-0-baseline` tag in the remote repository before continuing with remediation work.

## Backup

Create a backup before production migrations or security remediation:

```powershell
.\scripts\backup_phase0.ps1 -DatabaseName hotel_erp_db -DatabaseUser postgres -OutputDir .\backups
```

Restore into a separate database, never over the active database:

```powershell
.\scripts\restore_phase0.ps1 -BackupFile .\backups\hotel_erp_db_YYYYMMDD_HHMMSS.dump -RestoreDatabaseName hotel_erp_restore_test -DatabaseUser postgres
```

After restore:

```powershell
python manage.py check --database default
python manage.py test --settings=core.settings_test
```

Record the backup file name, restore database name, restore date, and verification result in the deployment notes.

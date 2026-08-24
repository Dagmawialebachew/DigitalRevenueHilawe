# Meal Plan demo runtime helpers

These files do not modify application code.

1. Copy `.env.demo.template` to your repo root as `.env.demo`.
2. Fill only DEMO values.
3. Make sure `.env.demo` is ignored by Git.
4. Run from the repo root:

   powershell -ExecutionPolicy Bypass -File ".\check_demo.ps1"

5. After HTTPS frontend/API setup is complete and the checks pass:

   powershell -ExecutionPolicy Bypass -File ".\run_full_demo.ps1"

The scripts load `.env.demo` into the child PowerShell process without printing secret values.

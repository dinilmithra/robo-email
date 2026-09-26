# robo-email

Reusable email report rendering and delivery utilities for automation projects.

The application remains responsible for its report data, branding/template, recipient source, environment configuration, and subject. `robo-email` provides Outlook-compatible rendering and generic PowerShell SMTP delivery.


## Publishing

Run `python .\tools\publish_robo_email.py` from the library directory. The publisher auto-uses the library `.venv`, increments the patch version by default, deletes any existing `dist/` directory before building, stages fresh wheel/sdist artifacts, and publishes by default. Use `--build-only` to build without uploading; the incremented version is retained after a successful build.

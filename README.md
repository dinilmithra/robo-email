# robo-email

Reusable email report rendering and delivery utilities for automation projects.

The application remains responsible for its report data, branding/template, recipient source, environment configuration, and subject. `robo-email` provides Outlook-compatible rendering and generic PowerShell SMTP delivery.


## Publishing

From the workspace root, preview with `python publishing/publish_robo_email.py --dry-run`, then publish with `python publishing/publish_robo_email.py --publish`. The shared publisher uses the library environment and updates dependent metadata after a successful release. Failed unpublished version changes are rolled back; successful release metadata is committed and pushed. Each project uses its own virtual environment. See [workspace publishing instructions](../PUBLISHING.md).

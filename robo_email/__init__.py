"""Reusable email report rendering and delivery utilities."""

from .delivery import is_valid_email, send_powershell_email
from .renderer import EmailReportGenerator

__all__ = ["EmailReportGenerator", "is_valid_email", "send_powershell_email"]

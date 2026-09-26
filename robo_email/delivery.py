"""Generic local Windows email delivery helpers."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

_email_sent = False
_email_sent_lock = threading.Lock()
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def is_valid_email(address: str) -> bool:
    """Return whether an address matches the permitted email format."""
    return bool(_EMAIL_RE.match((address or "").strip()))


def _ps_escape(value: Optional[str]) -> str:
    return (value or "").replace("'", "''")


def send_powershell_email(
    *,
    body_path: str | Path,
    recipients: Iterable[str],
    subject: str,
    smtp_server: str = "localhost",
    smtp_port: int = 25,
    smtp_from: str = "",
    attachment_path: str | Path | None = None,
    suppress_duplicates: bool = True,
) -> bool:
    """Send an HTML email through PowerShell ``Send-MailMessage`` on Windows.

    Application code supplies recipients, subject, SMTP configuration and any
    attachment. This function has no knowledge of application environment,
    credentials, spreadsheets, pytest, Jenkins, or business data.
    """
    if os.name != "nt":
        logger.warning("PowerShell email delivery is supported only on Windows.")
        return False

    body_path = Path(body_path).resolve()
    if not body_path.is_file():
        raise FileNotFoundError(f"Email body does not exist: {body_path}")

    valid_recipients = sorted(
        {str(value).strip() for value in recipients if is_valid_email(str(value))}
    )
    if not valid_recipients:
        logger.warning("Email send skipped because no valid recipients were supplied.")
        return False

    global _email_sent
    if suppress_duplicates:
        with _email_sent_lock:
            if _email_sent:
                logger.info("Email already sent for this process; skipping duplicate send.")
                return False
            _email_sent = True

    try:
        to_list = ";".join(valid_recipients)
        safe_body_path = _ps_escape(str(body_path))
        has_attachment = attachment_path is not None
        safe_attachment_path = (
            _ps_escape(str(Path(attachment_path).resolve())) if has_attachment else ""
        )

        ps_script = f"""
$ErrorActionPreference = 'Stop'
$bodyPath = '{safe_body_path}'
$attachmentPath = '{safe_attachment_path}'
$bodyHtml = Get-Content -Path $bodyPath -Raw -Encoding UTF8
$configuredFrom = '{_ps_escape(smtp_from)}'
$authUpn = (whoami /upn 2>$null | Select-Object -Last 1)
function Resolve-AdMailboxSmtp([string]$upn) {{
    try {{
        if ([string]::IsNullOrWhiteSpace($upn) -or -not $upn.Contains('@')) {{ return $null }}
        $sam = $upn.Split('@')[0]
        if ([string]::IsNullOrWhiteSpace($sam)) {{ return $null }}
        $root = [ADSI]"LDAP://RootDSE"
        $searchBase = "LDAP://" + $root.defaultNamingContext
        $searcher = New-Object System.DirectoryServices.DirectorySearcher([ADSI]$searchBase)
        $searcher.Filter = "(&(objectCategory=person)(objectClass=user)(sAMAccountName=$sam))"
        $null = $searcher.PropertiesToLoad.Add("mail")
        $null = $searcher.PropertiesToLoad.Add("proxyAddresses")
        $searcher.SizeLimit = 1
        $result = $searcher.FindOne()
        if ($null -eq $result) {{ return $null }}
        $props = $result.Properties
        if ($props.Contains("proxyaddresses")) {{
            foreach ($addr in $props["proxyaddresses"]) {{
                if ($addr -is [string] -and $addr.StartsWith("SMTP:")) {{
                    return $addr.Substring(5).Trim().ToLowerInvariant()
                }}
            }}
        }}
        if ($props.Contains("mail") -and $props["mail"].Count -gt 0) {{
            $mail = [string]$props["mail"][0]
            if (-not [string]::IsNullOrWhiteSpace($mail) -and $mail.Contains('@')) {{
                return $mail.Trim().ToLowerInvariant()
            }}
        }}
    }} catch {{}}
    return $null
}}
$resolvedMailboxFromAd = $null
$smtpFrom = $configuredFrom
if (-not [string]::IsNullOrWhiteSpace($authUpn)) {{
    $authUpn = $authUpn.Trim().ToLowerInvariant()
    if ($authUpn.Contains('@')) {{
        $resolvedMailboxFromAd = Resolve-AdMailboxSmtp $authUpn
        if (-not [string]::IsNullOrWhiteSpace($resolvedMailboxFromAd)) {{ $smtpFrom = $resolvedMailboxFromAd }}
        else {{ $smtpFrom = $authUpn }}
    }}
}}
$toRecipients = '{_ps_escape(to_list)}'.Split(';') | Where-Object {{ -not [string]::IsNullOrWhiteSpace($_) }} | ForEach-Object {{ $_.Trim() }}
$attachmentExists = {'$true' if has_attachment else '$false'}
$fromCandidates = New-Object System.Collections.Generic.List[string]
function Add-FromCandidate([string]$value) {{
    if ([string]::IsNullOrWhiteSpace($value)) {{ return }}
    $candidate = $value.Trim().ToLowerInvariant()
    if (-not $candidate.Contains('@')) {{ return }}
    if (-not $fromCandidates.Contains($candidate)) {{ $fromCandidates.Add($candidate) }}
}}
Add-FromCandidate $smtpFrom
Add-FromCandidate $configuredFrom
Add-FromCandidate $resolvedMailboxFromAd
if ($toRecipients.Count -gt 0) {{ Add-FromCandidate $toRecipients[0] }}
$sendSucceeded = $false
$lastSendError = $null
foreach ($candidateFrom in $fromCandidates) {{
    try {{
        if ($attachmentExists) {{
            Send-MailMessage -From $candidateFrom -To $toRecipients -Subject '{_ps_escape(subject)}' -Body $bodyHtml -BodyAsHtml -SmtpServer '{_ps_escape(smtp_server)}' -Port {int(smtp_port)} -Attachments $attachmentPath
        }} else {{
            Send-MailMessage -From $candidateFrom -To $toRecipients -Subject '{_ps_escape(subject)}' -Body $bodyHtml -BodyAsHtml -SmtpServer '{_ps_escape(smtp_server)}' -Port {int(smtp_port)}
        }}
        $sendSucceeded = $true
        break
    }} catch {{ $lastSendError = $_.Exception.Message }}
}}
if (-not $sendSucceeded) {{ throw "All sender candidates failed. Last error: $lastSendError" }}
"""
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            logger.error(
                "PowerShell email delivery failed (exit=%s): %s",
                completed.returncode,
                (completed.stderr or completed.stdout or "").strip(),
            )
            if suppress_duplicates:
                with _email_sent_lock:
                    _email_sent = False
            return False

        logger.info("Email sent successfully to %s", ", ".join(valid_recipients))
        return True
    except Exception:
        if suppress_duplicates:
            with _email_sent_lock:
                _email_sent = False
        raise

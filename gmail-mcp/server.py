"""
Gmail MCP Server — gog CLI 래퍼
Streamable HTTP MCP server wrapping /opt/homebrew/bin/gog for Gmail operations.
"""

import json
import subprocess
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GOG = "/opt/homebrew/bin/gog"
DEFAULT_ACCOUNT = "lchacha04@gmail.com"
BASE_FLAGS = ["--json", "--no-input"]

mcp = FastMCP(
    name="gmail",
    instructions="Gmail MCP server — wraps gog CLI for Gmail read/write/organize operations. "
    "Use list_emails and search_emails to find messages, read_email to get full details, "
    "send_email to send, reply_email to reply, and label_* / archive_email / trash_email for organization.",
    host="127.0.0.1",
    port=3100,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_gog(args: list[str], account: str = DEFAULT_ACCOUNT, timeout: int = 30) -> dict[str, Any]:
    """Run a gog command and return parsed JSON or error dict."""
    cmd = [GOG, "--account", account] + BASE_FLAGS + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": f"gog command timed out after {timeout}s: {' '.join(cmd)}"}
    except FileNotFoundError:
        return {"error": f"gog binary not found at {GOG}"}

    if result.returncode != 0:
        stderr = result.stderr.strip() or "unknown error"
        return {"error": f"gog exited with code {result.returncode}: {stderr}"}

    stdout = result.stdout.strip()
    if not stdout:
        return {"error": "gog returned empty output"}

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"raw_output": stdout}


def gog_args(**kwargs: Any) -> list[str]:
    """Build gog CLI arguments from kwargs, skipping None/False values."""
    args: list[str] = []
    for key, value in kwargs.items():
        if value is None or value is False:
            continue
        flag = f"--{key.replace('_', '-')}"
        if value is True:
            args.append(flag)
        elif isinstance(value, list):
            for v in value:
                args.extend([flag, str(v)])
        else:
            args.extend([flag, str(value)])
    return args


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_emails(
    query: str = "in:inbox",
    max_results: int = 10,
    include_body: bool = False,
    unread_only: bool = False,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Search emails using Gmail query syntax.
    
    Args:
        query: Gmail search query (e.g. 'in:inbox', 'from:example@gmail.com', 'subject:hello')
        max_results: Maximum number of results (1-100)
        include_body: Include decoded message body in results
        unread_only: Show only unread messages (adds 'is:unread' to query)
        account: Gmail account email (default: lchacha04@gmail.com)
    """
    if unread_only:
        query = f"{query} is:unread"

    flags: list[str] = []
    if include_body:
        flags.append("--include-body")

    args = ["gmail", "messages", "search", query, "--max", str(max_results)] + flags
    return run_gog(args, account=account)


@mcp.tool()
def read_email(message_id: str, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Get full details of a single email message including body.
    
    Args:
        message_id: Gmail message ID (from list_emails or search results)
        account: Gmail account email
    """
    return run_gog(["gmail", "get", message_id], account=account)


@mcp.tool()
def raw_email(message_id: str, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Get raw Gmail API response for a message (lossless JSON for scripting).
    
    Args:
        message_id: Gmail message ID
        account: Gmail account email
    """
    return run_gog(["gmail", "raw", message_id], account=account)


@mcp.tool()
def search_emails(query: str, max_results: int = 20, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Search emails with full Gmail query syntax. Use for complex searches.
    
    Args:
        query: Gmail search query (supports all Gmail operators: from:, to:, subject:, before:, after:, has:attachment, filename:, larger:, smaller:, etc.)
        max_results: Maximum results (1-100)
        account: Gmail account email
    """
    return run_gog(["gmail", "messages", "search", query, "--max", str(max_results)], account=account)


@mcp.tool()
def get_thread(thread_id: str, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Get a complete email thread with all messages.
    
    Args:
        thread_id: Gmail thread ID
        account: Gmail account email
    """
    return run_gog(["gmail", "thread", "get", thread_id], account=account)


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------

@mcp.tool()
def send_email(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    body_html: str | None = None,
    dry_run: bool = False,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Send an email.
    
    Args:
        to: Recipient email address(es), comma-separated
        subject: Email subject line
        body: Plain text email body
        cc: CC recipient(s), comma-separated
        bcc: BCC recipient(s), comma-separated
        body_html: HTML email body (optional, overrides plain text rendering)
        dry_run: If true, simulate without actually sending
        account: Gmail account email to send from
    """
    args = ["gmail", "send", "--to", to, "--subject", subject, "--body", body]
    if cc:
        args.extend(["--cc", cc])
    if bcc:
        args.extend(["--bcc", bcc])
    if body_html:
        args.extend(["--body-html", body_html])
    if dry_run:
        args.append("--dry-run")
    return run_gog(args, account=account)


@mcp.tool()
def reply_email(
    message_id: str,
    body: str,
    reply_all: bool = False,
    body_html: str | None = None,
    dry_run: bool = False,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Reply to an email.
    
    Args:
        message_id: Gmail message ID to reply to
        body: Reply body text
        reply_all: Reply to all recipients instead of just sender
        body_html: HTML reply body (optional)
        dry_run: If true, simulate without actually sending
        account: Gmail account email
    """
    cmd = "reply-all" if reply_all else "reply"
    args = ["gmail", cmd, message_id, "--body", body]
    if body_html:
        args.extend(["--body-html", body_html])
    if dry_run:
        args.append("--dry-run")
    return run_gog(args, account=account)


@mcp.tool()
def forward_email(
    message_id: str,
    to: str,
    body: str = "",
    body_html: str | None = None,
    dry_run: bool = False,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Forward an email to new recipients.
    
    Args:
        message_id: Gmail message ID to forward
        to: Recipient email address(es), comma-separated
        body: Optional additional message (added above forwarded content)
        body_html: HTML additional message (optional)
        dry_run: If true, simulate without actually sending
        account: Gmail account email
    """
    args = ["gmail", "forward", message_id, "--to", to]
    if body:
        args.extend(["--body", body])
    if body_html:
        args.extend(["--body-html", body_html])
    if dry_run:
        args.append("--dry-run")
    return run_gog(args, account=account)


# ---------------------------------------------------------------------------
# Draft tools
# ---------------------------------------------------------------------------

@mcp.tool()
def draft_list(max_results: int = 20, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """List all email drafts.
    
    Args:
        max_results: Maximum number of drafts to return
        account: Gmail account email
    """
    return run_gog(["gmail", "drafts", "list", "--max", str(max_results)], account=account)


@mcp.tool()
def draft_create(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    body_html: str | None = None,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Create a new email draft.
    
    Args:
        to: Recipient email address(es), comma-separated
        subject: Email subject
        body: Plain text body
        cc: CC recipient(s), comma-separated
        bcc: BCC recipient(s), comma-separated
        body_html: HTML body (optional)
        account: Gmail account email
    """
    args = ["gmail", "drafts", "create", "--to", to, "--subject", subject, "--body", body]
    if cc:
        args.extend(["--cc", cc])
    if bcc:
        args.extend(["--bcc", bcc])
    if body_html:
        args.extend(["--body-html", body_html])
    return run_gog(args, account=account)


@mcp.tool()
def draft_update(
    draft_id: str,
    to: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    body_html: str | None = None,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Update an existing email draft.
    
    Args:
        draft_id: Draft ID (from draft_list)
        to: Updated recipient(s)
        subject: Updated subject
        body: Updated plain text body
        body_html: Updated HTML body
        account: Gmail account email
    """
    args = ["gmail", "drafts", "update", draft_id]
    if to:
        args.extend(["--to", to])
    if subject:
        args.extend(["--subject", subject])
    if body:
        args.extend(["--body", body])
    if body_html:
        args.extend(["--body-html", body_html])
    return run_gog(args, account=account)


@mcp.tool()
def draft_send(draft_id: str, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Send an existing draft.
    
    Args:
        draft_id: Draft ID to send
        account: Gmail account email
    """
    return run_gog(["gmail", "drafts", "send", draft_id], account=account)


@mcp.tool()
def draft_delete(draft_id: str, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Delete a draft permanently (not recoverable).
    
    Args:
        draft_id: Draft ID to delete
        account: Gmail account email
    """
    return run_gog(["gmail", "drafts", "delete", draft_id], account=account)


# ---------------------------------------------------------------------------
# Organization tools
# ---------------------------------------------------------------------------

@mcp.tool()
def archive_email(message_ids: str, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Archive messages (remove from inbox).
    
    Args:
        message_ids: One or more Gmail message IDs, space-separated
        account: Gmail account email
    """
    return run_gog(["gmail", "archive", *message_ids.split()], account=account)


@mcp.tool()
def mark_read(message_ids: str, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Mark messages as read.
    
    Args:
        message_ids: One or more Gmail message IDs, space-separated
        account: Gmail account email
    """
    return run_gog(["gmail", "mark-read", *message_ids.split()], account=account)


@mcp.tool()
def mark_unread(message_ids: str, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Mark messages as unread.
    
    Args:
        message_ids: One or more Gmail message IDs, space-separated
        account: Gmail account email
    """
    return run_gog(["gmail", "unread", *message_ids.split()], account=account)


@mcp.tool()
def trash_email(message_ids: str, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Move messages to trash.
    
    Args:
        message_ids: One or more Gmail message IDs, space-separated
        account: Gmail account email
    """
    return run_gog(["gmail", "trash", *message_ids.split()], account=account)


# ---------------------------------------------------------------------------
# Label tools
# ---------------------------------------------------------------------------

@mcp.tool()
def label_list(account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """List all Gmail labels (system and user-created).
    
    Args:
        account: Gmail account email
    """
    return run_gog(["gmail", "labels", "list"], account=account)


@mcp.tool()
def label_create(name: str, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Create a new Gmail label.
    
    Args:
        name: Label name to create
        account: Gmail account email
    """
    return run_gog(["gmail", "labels", "create", name], account=account)


@mcp.tool()
def label_modify(
    thread_ids: str,
    add_labels: str | None = None,
    remove_labels: str | None = None,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Add or remove labels on threads.
    
    Args:
        thread_ids: Thread ID(s), space-separated
        add_labels: Label name(s) to add, comma-separated
        remove_labels: Label name(s) to remove, comma-separated
        account: Gmail account email
    """
    args = ["gmail", "labels", "modify", *thread_ids.split()]
    if add_labels:
        for lbl in add_labels.split(","):
            args.extend(["--add", lbl.strip()])
    if remove_labels:
        for lbl in remove_labels.split(","):
            args.extend(["--remove", lbl.strip()])
    return run_gog(args, account=account)


@mcp.tool()
def label_delete(name: str, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Delete a user-created label.
    
    Args:
        name: Label name to delete
        account: Gmail account email
    """
    return run_gog(["gmail", "labels", "delete", name], account=account)


# ---------------------------------------------------------------------------
# Utility tools
# ---------------------------------------------------------------------------

@mcp.tool()
def check_urgent(hours: int = 2, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Check for urgent/important unread emails in recent hours.
    
    Args:
        hours: Look back this many hours (default: 2)
        account: Gmail account email
    """
    query = f"is:unread newer_than:{hours}h"
    return run_gog(["gmail", "messages", "search", query, "--max", "10", "--include-body"], account=account)


@mcp.tool()
def get_email_url(thread_id: str, account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Get Gmail web URL for a thread.
    
    Args:
        thread_id: Gmail thread ID
        account: Gmail account email
    """
    return run_gog(["gmail", "url", thread_id], account=account)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Streamable HTTP on port 3100, loopback only
    mcp.run(transport="streamable-http")
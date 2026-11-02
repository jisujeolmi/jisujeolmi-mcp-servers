"""
Calendar MCP Server — gog CLI 래퍼
Streamable HTTP MCP server wrapping /opt/homebrew/bin/gog for Google Calendar operations.
"""

import json
import subprocess
from typing import Any

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GOG = "/opt/homebrew/bin/gog"
DEFAULT_ACCOUNT = "lchacha04@gmail.com"
BASE_FLAGS = ["--json", "--no-input"]

mcp = FastMCP(
    name="calendar",
    instructions="Google Calendar MCP server — wraps gog CLI for calendar read/write operations. "
    "Use list_events to see today/this week's events, create_event to add new ones, "
    "freebusy to check availability, and search_events to find specific events.",
    host="127.0.0.1",
    port=3101,
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


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_calendars(account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """List all available calendars.
    
    Args:
        account: Google account email (default: lchacha04@gmail.com)
    """
    return run_gog(["calendar", "calendars"], account=account)


@mcp.tool()
def list_events(
    calendar_id: str = "primary",
    from_time: str = "today",
    to_time: str = "",
    max_results: int = 20,
    query: str = "",
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """List events from a calendar.
    
    Args:
        calendar_id: Calendar ID (default: primary). Use 'list_calendars' to find IDs.
        from_time: Start time — 'today', 'tomorrow', 'monday', 'now', or RFC3339 datetime
        to_time: End time — same format, or empty for default range
        max_results: Maximum events to return
        query: Free text search within events
        account: Google account email
    """
    args = ["calendar", "events", calendar_id, "--from", from_time, "--max", str(max_results)]
    if to_time:
        args.extend(["--to", to_time])
    if query:
        args.extend(["--query", query])
    return run_gog(args, account=account)


@mcp.tool()
def get_event(
    calendar_id: str,
    event_id: str,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Get full details of a single event.
    
    Args:
        calendar_id: Calendar ID (usually 'primary' or from list_calendars)
        event_id: Event ID (from list_events)
        account: Google account email
    """
    return run_gog(["calendar", "event", calendar_id, event_id], account=account)


@mcp.tool()
def search_events(
    query: str,
    max_results: int = 20,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Search events by text query across calendars.
    
    Args:
        query: Search term (matches summary, description, location, attendees)
        max_results: Maximum results
        account: Google account email
    """
    return run_gog(["calendar", "search", query, "--max", str(max_results)], account=account)


@mcp.tool()
def freebusy(
    calendar_ids: str = "primary",
    from_time: str = "today",
    to_time: str = "",
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Check free/busy status for calendars.
    
    Args:
        calendar_ids: Comma-separated calendar IDs (default: primary)
        from_time: Start time — 'today', 'now', or RFC3339
        to_time: End time — same format
        account: Google account email
    """
    args = ["calendar", "freebusy", calendar_ids, "--from", from_time]
    if to_time:
        args.extend(["--to", to_time])
    return run_gog(args, account=account)


@mcp.tool()
def check_upcoming(
    days: int = 7,
    max_results: int = 50,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Check upcoming events for the next N days.
    
    Args:
        days: Number of days to look ahead (default: 7)
        max_results: Maximum events
        account: Google account email
    """
    return run_gog(["calendar", "events", "primary", "--days", str(days), "--max", str(max_results)], account=account)


@mcp.tool()
def check_conflicts(
    calendar_ids: str = "primary",
    from_time: str = "today",
    to_time: str = "",
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Find overlapping/busy-time conflicts across calendars.
    
    Args:
        calendar_ids: Comma-separated calendar IDs
        from_time: Start time
        to_time: End time
        account: Google account email
    """
    args = ["calendar", "conflicts", "--cal", calendar_ids, "--from", from_time]
    if to_time:
        args.extend(["--to", to_time])
    return run_gog(args, account=account)


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------

@mcp.tool()
def create_event(
    calendar_id: str,
    summary: str,
    from_time: str,
    to_time: str,
    description: str = "",
    location: str = "",
    attendees: str = "",
    timezone: str = "",
    with_meet: bool = False,
    all_day: bool = False,
    dry_run: bool = False,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Create a new calendar event.
    
    Args:
        calendar_id: Calendar ID (usually 'primary')
        summary: Event title
        from_time: Start time (RFC3339 like '2026-11-05T14:00:00', or '2026-11-05' for all-day)
        to_time: End time (same format as from_time)
        description: Event description/notes
        location: Event location
        attendees: Comma-separated attendee emails (use ';optional', ';resource' modifiers)
        timezone: IANA timezone (e.g. 'Pacific/Auckland')
        with_meet: Create a Google Meet conference
        all_day: All-day event
        dry_run: If true, simulate without creating
        account: Google account email
    """
    args = ["calendar", "create", calendar_id, "--summary", summary, "--from", from_time, "--to", to_time]
    if description:
        args.extend(["--description", description])
    if location:
        args.extend(["--location", location])
    if attendees:
        args.extend(["--attendees", attendees])
    if timezone:
        args.extend(["--timezone", timezone])
    if with_meet:
        args.append("--with-meet")
    if all_day:
        args.append("--all-day")
    if dry_run:
        args.append("--dry-run")
    return run_gog(args, account=account)


@mcp.tool()
def update_event(
    calendar_id: str,
    event_id: str,
    summary: str = "",
    from_time: str = "",
    to_time: str = "",
    description: str = "",
    location: str = "",
    dry_run: bool = False,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Update an existing calendar event.
    
    Args:
        calendar_id: Calendar ID
        event_id: Event ID to update
        summary: New title (empty = no change)
        from_time: New start time
        to_time: New end time
        description: New description
        location: New location
        dry_run: If true, simulate without updating
        account: Google account email
    """
    args = ["calendar", "update", calendar_id, event_id]
    if summary:
        args.extend(["--summary", summary])
    if from_time:
        args.extend(["--from", from_time])
    if to_time:
        args.extend(["--to", to_time])
    if description:
        args.extend(["--description", description])
    if location:
        args.extend(["--location", location])
    if dry_run:
        args.append("--dry-run")
    return run_gog(args, account=account)


@mcp.tool()
def delete_event(
    calendar_id: str,
    event_id: str,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Delete a calendar event.
    
    Args:
        calendar_id: Calendar ID
        event_id: Event ID to delete
        account: Google account email
    """
    return run_gog(["calendar", "delete", calendar_id, event_id], account=account)


@mcp.tool()
def respond_event(
    calendar_id: str,
    event_id: str,
    status: str,
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """RSVP to an event invitation.
    
    Args:
        calendar_id: Calendar ID
        event_id: Event ID
        status: Response — 'accepted', 'declined', or 'tentative'
        account: Google account email
    """
    return run_gog(["calendar", "respond", calendar_id, event_id, "--status", status], account=account)


@mcp.tool()
def create_focus_time(
    from_time: str,
    to_time: str,
    calendar_id: str = "primary",
    summary: str = "Focus Time",
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Create a Focus Time block (auto-declines conflicting invitations).
    
    Args:
        from_time: Start time (RFC3339)
        to_time: End time (RFC3339)
        calendar_id: Calendar ID (default: primary)
        summary: Block title (default: Focus Time)
        account: Google account email
    """
    return run_gog(["calendar", "focus-time", "--from", from_time, "--to", to_time, calendar_id, "--summary", summary], account=account)


@mcp.tool()
def create_out_of_office(
    from_time: str,
    to_time: str,
    calendar_id: str = "primary",
    summary: str = "Out of Office",
    account: str = DEFAULT_ACCOUNT,
) -> dict[str, Any]:
    """Create an Out of Office event.
    
    Args:
        from_time: Start time (RFC3339 or date)
        to_time: End time (RFC3339 or date)
        calendar_id: Calendar ID (default: primary)
        summary: OOO title (default: Out of Office)
        account: Google account email
    """
    return run_gog(["calendar", "out-of-office", "--from", from_time, "--to", to_time, calendar_id, "--summary", summary], account=account)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

@mcp.tool()
def get_colors(account: str = DEFAULT_ACCOUNT) -> dict[str, Any]:
    """Get available calendar/event color IDs (1-11)."""
    return run_gog(["calendar", "colors"], account=account)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
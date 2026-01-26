#!/usr/bin/env python3
"""
Telegram MDML Middleware

Middleware between MDML parser and Telegram entity verification scripts.
Provides structured access to Telegram entity data stored in markdown files.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass
from mdml import parse_document, Document


# ============================================
# EXCEPTIONS
# ============================================

class TelegramMDMLError(Exception):
    """Base exception for all Telegram MDML errors."""
    pass


class ValidationError(TelegramMDMLError):
    """Raised when data validation fails."""
    pass


class MissingFieldError(TelegramMDMLError):
    """Raised when a required field is missing."""
    pass


class InvalidFieldError(TelegramMDMLError):
    """Raised when a field has an invalid value."""
    pass


class InvalidUsernameError(InvalidFieldError):
    """Raised when username format is invalid."""
    pass


class InvalidInviteError(InvalidFieldError):
    """Raised when invite link format is invalid."""
    pass


class InvalidStatusError(InvalidFieldError):
    """Raised when status value is invalid."""
    pass


class InvalidTypeError(InvalidFieldError):
    """Raised when entity type is invalid."""
    pass


# ============================================
# DATA CLASSES
# ============================================

@dataclass
class HistoricalValue:
    """Represents a value with timestamp and metadata."""
    value: str
    date: Optional[datetime] = None
    details: Optional[str] = None
    is_strikethrough: bool = False

    def __str__(self):
        return self.value

    def __repr__(self):
        parts = [f"value={self.value!r}"]
        if self.date:
            parts.append(f"date={self.date.strftime('%Y-%m-%d %H:%M')}")
        if self.details:
            parts.append(f"details={self.details!r}")
        if self.is_strikethrough:
            parts.append("strikethrough=True")
        return f"HistoricalValue({', '.join(parts)})"


@dataclass
class UsernameValue(HistoricalValue):
    """Username with validation."""

    def __post_init__(self):
        # Remove @ prefix if present for storage
        if self.value.startswith('@'):
            self.value = self.value[1:]

        # Validate username format (5-32 chars, alphanumeric + underscore)
        if not re.match(r'^[a-zA-Z0-9_]{5,32}$', self.value):
            raise InvalidUsernameError(
                f"Invalid username format: {self.value!r}. "
                f"Must be 5-32 characters, alphanumeric and underscore only."
            )

    @property
    def with_at(self) -> str:
        """Returns username with @ prefix."""
        return f"@{self.value}"

    def __str__(self):
        return self.with_at


@dataclass
class InviteValue(HistoricalValue):
    """Invite link with hash extraction."""
    hash: str = None

    def __post_init__(self):
        # Extract hash from full URL or use value directly
        if self.value.startswith('https://t.me/+'):
            self.hash = self.value.replace('https://t.me/+', '')
        elif self.value.startswith('http://t.me/+'):
            self.hash = self.value.replace('http://t.me/+', '')
        elif self.value.startswith('+'):
            self.hash = self.value[1:]
            self.value = f"https://t.me/{self.value}"
        else:
            # Assume it's a hash
            self.hash = self.value
            self.value = f"https://t.me/+{self.value}"

        # Validate hash format (alphanumeric, dash, underscore)
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.hash):
            raise InvalidInviteError(
                f"Invalid invite hash format: {self.hash!r}. "
                f"Must contain only alphanumeric characters, dashes, and underscores."
            )

    @property
    def url(self) -> str:
        """Returns full invite URL."""
        return self.value

    def __str__(self):
        return self.url


@dataclass
class StatusValue(HistoricalValue):
    """Status with validation and optional restriction details."""
    reason: Optional[str] = None
    text: Optional[str] = None

    VALID_STATUSES = {'active', 'unknown', 'banned', 'deleted', 'id_mismatch'}

    def __post_init__(self):
        # Normalize status to lowercase
        self.value = self.value.lower()

        # Validate status value
        if self.value not in self.VALID_STATUSES:
            raise InvalidStatusError(
                f"Invalid status: {self.value!r}. "
                f"Must be one of: {', '.join(sorted(self.VALID_STATUSES))}"
            )

    def __repr__(self):
        parts = [f"status={self.value!r}"]
        if self.date:
            parts.append(f"date={self.date.strftime('%Y-%m-%d %H:%M')}")
        if self.details:
            parts.append(f"details={self.details!r}")
        if self.reason:
            parts.append(f"reason={self.reason!r}")
        if self.text:
            parts.append(f"text={self.text[:30]!r}...")
        return f"StatusValue({', '.join(parts)})"


# ============================================
# HISTORICAL COLLECTIONS
# ============================================

class HistoricalCollection:
    """Base class for managing historical values."""

    def __init__(self, values: List[HistoricalValue]):
        # Sort by date (most recent first), None dates go last
        self.values = sorted(
            values,
            key=lambda v: v.date if v.date else datetime.min,
            reverse=True
        )

    def __iter__(self):
        return iter(self.values)

    def __len__(self):
        return len(self.values)

    def __getitem__(self, index):
        return self.values[index]

    def __bool__(self):
        return len(self.values) > 0

    def latest(self, allow_strikethrough: bool = False) -> Optional[HistoricalValue]:
        if not self.values:
            return None

        # Filter values based on strikethrough preference
        candidates = self.values if allow_strikethrough else [v for v in self.values if not v.is_strikethrough]

        if not candidates:
            return None

        # Separate values with and without dates
        with_dates = [v for v in candidates if v.date is not None]
        without_dates = [v for v in candidates if v.date is None]

        # If we have values with dates, return the most recent one
        if with_dates:
            return max(with_dates, key=lambda v: v.date)

        # Otherwise, return the first value without a date (preserves document order)
        return without_dates[0] if without_dates else None

    def oldest(self) -> Optional[HistoricalValue]:
        """Returns the oldest value."""
        if not self.values:
            return None

        # Separate values with and without dates
        with_dates = [v for v in self.values if v.date is not None]
        without_dates = [v for v in self.values if v.date is None]

        # If we have values with dates, return the oldest one
        if with_dates:
            return min(with_dates, key=lambda v: v.date)

        # Otherwise, return the last value without a date (preserves document order)
        return without_dates[-1] if without_dates else None

    def active(self) -> List[HistoricalValue]:
        """Returns all non-strikethrough values, sorted by date (most recent first)."""
        active_values = [v for v in self.values if not v.is_strikethrough]

        # Sort by date (most recent first), values without dates go last
        return sorted(
            active_values,
            key=lambda v: v.date if v.date else datetime.min,
            reverse=True
        )


class UsernameCollection(HistoricalCollection):
    """Collection of username values."""
    pass


class InviteCollection(HistoricalCollection):
    """Collection of invite values."""

    def get_hashes(self, allow_strikethrough: bool = False) -> List[str]:
        """Returns list of invite hashes."""
        values = self.values if allow_strikethrough else self.active()
        return [v.hash for v in values]


class StatusCollection(HistoricalCollection):
    """Collection of status values."""

    def has_status(self, status: str) -> bool:
        """Checks if a specific status exists in history."""
        return any(v.value == status for v in self.values)


# ============================================
# MAIN ENTITY CLASS
# ============================================

class TelegramEntity:
    """
    Represents a Telegram entity (channel, group, user, bot) from MDML.

    Attributes:
        doc (Document): Parsed MDML document
        file_path (Path): Path to source markdown file
    """

    VALID_TYPES = {'bot', 'user', 'channel', 'group', 'unknown'}

    def __init__(self, doc: Document, file_path: Optional[Path] = None):
        """
        Initialize from parsed MDML document.

        Args:
            doc: Parsed MDML Document
            file_path: Optional path to source file
        """
        self.doc = doc
        self.file_path = file_path

    @classmethod
    def from_file(cls, file_path: str | Path) -> 'TelegramEntity':
        """
        Load and parse a Telegram entity markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            TelegramEntity instance

        Raises:
            FileNotFoundError: If file doesn't exist
            TelegramMDMLError: If parsing fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            content = file_path.read_text(encoding='utf-8')
            doc = parse_document(content)
            return cls(doc, file_path)
        except Exception as e:
            raise TelegramMDMLError(f"Failed to parse {file_path}: {e}") from e

    @classmethod
    def from_string(cls, content: str) -> 'TelegramEntity':
        """
        Parse a Telegram entity from markdown string.

        Args:
            content: Markdown content

        Returns:
            TelegramEntity instance
        """
        try:
            doc = parse_document(content)
            return cls(doc)
        except Exception as e:
            raise TelegramMDMLError(f"Failed to parse content: {e}") from e

    # ========================================
    # SIMPLE FIELDS
    # ========================================

    def get_id(self) -> Optional[int]:
        """
        Get entity ID.

        Returns:
            Entity ID as integer or None if not present

        Raises:
            InvalidFieldError: If ID is not a valid integer
        """
        value = self.doc.get_value('id')
        if not value:
            return None

        try:
            # Remove backticks if present
            id_str = value.value.strip('`').strip()
            return int(id_str)
        except ValueError:
            raise InvalidFieldError(f"Invalid ID format: {value.value!r}")

    def get_type(self) -> str:
        """
        Get entity type.

        Returns:
            Entity type (bot, user, channel, group, unknown)

        Raises:
            InvalidTypeError: If type is not valid
            MissingFieldError: If type field is missing
        """
        value = self.doc.get_value('type')
        if not value:
            raise MissingFieldError("Field 'type' is required")

        entity_type = value.value.strip('`').strip().lower()

        if entity_type not in self.VALID_TYPES:
            raise InvalidTypeError(
                f"Invalid type: {entity_type!r}. "
                f"Must be one of: {', '.join(sorted(self.VALID_TYPES))}"
            )

        return entity_type

    def has_field(self, field_name: str) -> bool:
        """Check if a field exists in the document."""
        return self.doc.get_field(field_name) is not None

    # ========================================
    # USERNAME
    # ========================================

    def get_usernames(self) -> UsernameCollection:
        """
        Get all usernames from history.

        Returns:
            UsernameCollection (sorted by date, most recent first)
        """
        field = self.doc.get_field('username')
        if not field:
            return UsernameCollection([])

        usernames = []

        for field_value in field.values:
            # Skip empty or placeholder values
            raw_value = field_value.value.strip('`').strip()

            # Skip if doesn't start with @ (placeholder)
            if not raw_value.startswith('@'):
                continue

            try:
                username = UsernameValue(
                    value=raw_value,
                    date=field_value.datetime_obj,
                    details=field_value.details,
                    is_strikethrough=field_value.is_strikethrough
                )
                usernames.append(username)
            except InvalidUsernameError:
                # Skip invalid usernames silently
                continue

        return UsernameCollection(usernames)

    def get_username(self, allow_strikethrough: bool = False) -> Optional[UsernameValue]:
        """
        Get the most recent username.

        Args:
            allow_strikethrough: If False, skip strikethrough usernames

        Returns:
            Most recent UsernameValue or None
        """
        return self.get_usernames().latest(allow_strikethrough)

    # ========================================
    # INVITES
    # ========================================

    def get_invites(self) -> InviteCollection:
        """
        Get all invite links from history.

        Returns:
            InviteCollection (sorted by date, most recent first)
        """
        field = self.doc.get_field('invite')
        if not field:
            return InviteCollection([])

        invites = []

        for field_value in field.values:
            # Extract invite URL from value or link
            raw_value = None

            # Priority 1: link_url (markdown link)
            if field_value.link_url:
                raw_value = field_value.link_url
            # Priority 2: raw value
            elif field_value.value:
                raw_value = field_value.value.strip('`').strip()

            if not raw_value:
                continue

            # Must contain t.me/+ pattern
            if 't.me/+' not in raw_value and not raw_value.startswith('+'):
                continue

            try:
                invite = InviteValue(
                    value=raw_value,
                    date=field_value.datetime_obj,
                    details=field_value.details,
                    is_strikethrough=field_value.is_strikethrough
                )
                invites.append(invite)
            except InvalidInviteError:
                # Skip invalid invites silently
                continue

        return InviteCollection(invites)

    def get_invite(self, allow_strikethrough: bool = False) -> Optional[InviteValue]:
        """
        Get the most recent invite link.

        Args:
            allow_strikethrough: If False, skip strikethrough invites

        Returns:
            Most recent InviteValue or None
        """
        return self.get_invites().latest(allow_strikethrough)

    # ========================================
    # STATUS
    # ========================================

    def get_statuses(self) -> StatusCollection:
        """
        Get all statuses from history.

        Returns:
            StatusCollection (sorted by date, most recent first)
        """
        field = self.doc.get_field('status')
        if not field:
            return StatusCollection([])

        statuses = []

        for field_value in field.values:
            raw_value = field_value.value.strip('`').strip().lower()

            # Extract restriction details from sub_items if present
            reason = None
            text = None

            if field_value.sub_items:
                if 'reason' in field_value.sub_items:
                    reason = field_value.sub_items['reason'].value.strip('`').strip()
                if 'text' in field_value.sub_items:
                    text = field_value.sub_items['text'].value.strip('`').strip()

            try:
                status = StatusValue(
                    value=raw_value,
                    date=field_value.datetime_obj,
                    details=field_value.details,
                    is_strikethrough=field_value.is_strikethrough,
                    reason=reason,
                    text=text
                )
                statuses.append(status)
            except InvalidStatusError:
                # Skip invalid statuses silently
                continue

        return StatusCollection(statuses)

    def get_status(self, allow_strikethrough: bool = False) -> Optional[StatusValue]:
        """
        Get the most recent status.

        Args:
            allow_strikethrough: If False, skip strikethrough statuses

        Returns:
            Most recent StatusValue or None
        """
        return self.get_statuses().latest(allow_strikethrough)

    # ========================================
    # VALIDATION
    # ========================================

    def validate(self) -> List[str]:
        """
        Validate entity data and return list of warnings.

        Returns:
            List of warning messages (empty if valid)
        """
        warnings = []

        # Check type field
        try:
            self.get_type()
        except MissingFieldError as e:
            warnings.append(str(e))
        except InvalidTypeError as e:
            warnings.append(str(e))

        # Check ID format
        try:
            self.get_id()
        except InvalidFieldError as e:
            warnings.append(str(e))

        # Check if has any identifier
        has_id = False
        try:
            has_id = self.get_id() is not None
        except InvalidFieldError:
            pass  # Already added to warnings above
        has_username = len(self.get_usernames()) > 0
        has_invite = len(self.get_invites()) > 0

        if not has_id and not has_username and not has_invite:
            warnings.append("Entity has no identifier (id, username, or invite)")

        return warnings

    # ========================================
    # REPRESENTATION
    # ========================================

    def __repr__(self):
        parts = []

        entity_id = self.get_id()
        if entity_id:
            parts.append(f"id={entity_id}")

        try:
            entity_type = self.get_type()
            parts.append(f"type={entity_type}")
        except (MissingFieldError, InvalidTypeError):
            pass

        username = self.get_username()
        if username:
            parts.append(f"username={username}")

        if self.file_path:
            parts.append(f"file={self.file_path.name}")

        return f"TelegramEntity({', '.join(parts)})"

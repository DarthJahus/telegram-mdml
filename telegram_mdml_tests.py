#!/usr/bin/env python3
"""
Unit tests for telegram_mdml.py
"""

import unittest
from telegram_mdml import (
    TelegramEntity,
    UsernameValue,
    InviteValue,
    StatusValue,
    MissingFieldError,
    InvalidFieldError,
    InvalidUsernameError,
    InvalidInviteError,
    InvalidStatusError,
    InvalidTypeError,
)


class TestSimpleFields(unittest.TestCase):
    """Tests for simple fields: id and type"""

    def test_get_id_valid(self):
        """Test parsing valid ID"""
        content = "\nid: `123456789`\ntype: channel"
        entity = TelegramEntity.from_string(content)
        self.assertEqual(entity.get_id(), 123456789)

    def test_get_id_without_backticks(self):
        """Test ID without backticks"""
        content = "id: 123456789\r\ntype: channel"
        entity = TelegramEntity.from_string(content)
        self.assertEqual(entity.get_id(), 123456789)

    def test_get_id_missing(self):
        """Test missing ID returns None"""
        content = """
type: channel
username: `@testchannel`
"""
        entity = TelegramEntity.from_string(content)
        self.assertIsNone(entity.get_id())

    def test_get_id_invalid_format(self):
        """Test invalid ID format raises exception"""
        content = """
id: `not_a_number`
type: channel
"""
        entity = TelegramEntity.from_string(content)
        with self.assertRaises(InvalidFieldError):
            entity.get_id()

    def test_get_type_valid(self):
        """Test all valid entity types"""
        for entity_type in ['channel', 'group', 'user', 'bot', 'unknown']:
            content = f"type: {entity_type}"
            entity = TelegramEntity.from_string(content)
            self.assertEqual(entity.get_type(), entity_type)

    def test_get_type_case_insensitive(self):
        """Test type is case-insensitive"""
        content = "type: CHANNEL"
        entity = TelegramEntity.from_string(content)
        self.assertEqual(entity.get_type(), 'channel')

    def test_get_type_missing(self):
        """Test missing type raises exception"""
        content = "id: `123456`"
        entity = TelegramEntity.from_string(content)
        with self.assertRaises(MissingFieldError):
            entity.get_type()

    def test_get_type_invalid(self):
        """Test invalid type raises exception"""
        content = "type: invalid_type"
        entity = TelegramEntity.from_string(content)
        with self.assertRaises(InvalidTypeError):
            entity.get_type()


class TestUsername(unittest.TestCase):
    """Tests for username field"""

    def test_username_inline_format(self):
        """Test inline username format"""
        content = """
type: channel
username: `@testchannel`
"""
        entity = TelegramEntity.from_string(content)
        username = entity.get_username()
        self.assertIsNotNone(username)
        self.assertEqual(username.value, 'testchannel')
        self.assertEqual(username.with_at, '@testchannel')
        self.assertEqual(str(username), '@testchannel')

    def test_username_list_format(self):
        """Test username list format (historical)"""
        content = """
type: channel
username:
- `@newusername`, `2026-01-20 15:00`
- `@oldusername`, `2026-01-10 10:00`
"""
        entity = TelegramEntity.from_string(content)

        # Get latest
        username = entity.get_username()
        self.assertEqual(username.value, 'newusername')

        # Get all
        usernames = entity.get_usernames()
        self.assertEqual(len(usernames), 2)
        self.assertEqual(usernames[0].value, 'newusername')
        self.assertEqual(usernames[1].value, 'oldusername')

    def test_username_without_at_prefix_ignored(self):
        """Test username without @ is ignored (placeholder)"""
        content = """
type: channel
username: `placeholder_name`
"""
        entity = TelegramEntity.from_string(content)
        username = entity.get_username()
        self.assertIsNone(username)

    def test_username_with_details(self):
        """Test username with details"""
        content = """
type: channel
username: `@testchannel` (official)
"""
        entity = TelegramEntity.from_string(content)
        username = entity.get_username()
        self.assertEqual(username.details, 'official')

    def test_username_strikethrough(self):
        """Test strikethrough username"""
        content = """
type: channel
username:
- `@newusername`, `2026-01-20`
- ~~`@oldusername`~~, `2026-01-10`
"""
        entity = TelegramEntity.from_string(content)

        # By default, skip strikethrough
        username = entity.get_username()
        self.assertEqual(username.value, 'newusername')

        # Allow strikethrough
        username_st = entity.get_username(allow_strikethrough=True)
        self.assertEqual(username_st.value, 'newusername')

        # Check collection
        usernames = entity.get_usernames()
        self.assertEqual(len(usernames), 2)
        self.assertTrue(usernames[1].is_strikethrough)

    def test_username_validation_too_short(self):
        """Test username too short raises exception"""
        with self.assertRaises(InvalidUsernameError):
            UsernameValue(value='@abc')

    def test_username_validation_too_long(self):
        """Test username too long raises exception"""
        with self.assertRaises(InvalidUsernameError):
            UsernameValue(value='@' + 'a' * 33)

    def test_username_validation_invalid_chars(self):
        """Test username with invalid characters raises exception"""
        with self.assertRaises(InvalidUsernameError):
            UsernameValue(value='@test-channel')

        with self.assertRaises(InvalidUsernameError):
            UsernameValue(value='@test.channel')

    def test_username_no_date_sorted_last(self):
        """Test username without date is sorted as oldest"""
        content = """
type: channel
username:
- `@newest`, `2026-01-20`
- `@nodate`
- `@middle`, `2026-01-15`
"""
        entity = TelegramEntity.from_string(content)
        usernames = entity.get_usernames()

        self.assertEqual(len(usernames), 3)
        self.assertEqual(usernames[0].value, 'newest')
        self.assertEqual(usernames[1].value, 'middle')
        self.assertEqual(usernames[2].value, 'nodate')


class TestInvite(unittest.TestCase):
    """Tests for invite field"""

    def test_invite_full_url(self):
        """Test invite with full URL"""
        content = """
type: channel
invite: https://t.me/+AbCdEfGhIjKlMnOp
"""
        entity = TelegramEntity.from_string(content)
        invite = entity.get_invite()

        self.assertIsNotNone(invite)
        self.assertEqual(invite.hash, 'AbCdEfGhIjKlMnOp')
        self.assertEqual(invite.url, 'https://t.me/+AbCdEfGhIjKlMnOp')
        self.assertEqual(str(invite), 'https://t.me/+AbCdEfGhIjKlMnOp')

    def test_invite_hash_only(self):
        """Test invite with hash only (auto-construct URL)"""
        content = """
type: channel
invite: `https://t.me/+AbCdEfGhIjKlMnOp`
"""
        entity = TelegramEntity.from_string(content)
        invite = entity.get_invite()

        self.assertEqual(invite.hash, 'AbCdEfGhIjKlMnOp')
        self.assertEqual(invite.url, 'https://t.me/+AbCdEfGhIjKlMnOp')

    def test_invite_list_format(self):
        """Test multiple invites (historical)"""
        content = """
type: channel
invite:
- https://t.me/+NewInvite123, `2026-01-20`
- https://t.me/+OldInvite456, `2026-01-10`
"""
        entity = TelegramEntity.from_string(content)

        # Get latest
        invite = entity.get_invite()
        self.assertEqual(invite.hash, 'NewInvite123')

        # Get all
        invites = entity.get_invites()
        self.assertEqual(len(invites), 2)

    def test_invite_strikethrough(self):
        """Test strikethrough invite (expired)"""
        content = """
type: channel
invite:
- https://t.me/+ActiveInvite, `2026-01-20`
- ~~https://t.me/+ExpiredInvite~~ (expired), `2026-01-10`
"""
        entity = TelegramEntity.from_string(content)

        # By default, skip expired
        invite = entity.get_invite()
        self.assertEqual(invite.hash, 'ActiveInvite')

        # Get all (including expired)
        invites = entity.get_invites()
        self.assertEqual(len(invites), 2)
        self.assertFalse(invites[0].is_strikethrough)
        self.assertTrue(invites[1].is_strikethrough)
        self.assertEqual(invites[1].details, 'expired')

    def test_invite_get_hashes(self):
        """Test get_hashes method"""
        content = """
type: channel
invite:
- https://t.me/+Hash1
- ~~https://t.me/+Hash2~~
- https://t.me/+Hash3
"""
        entity = TelegramEntity.from_string(content)
        invites = entity.get_invites()

        # Active only
        hashes = invites.get_hashes(allow_strikethrough=False)
        self.assertEqual(len(hashes), 2)
        self.assertIn('Hash1', hashes)
        self.assertIn('Hash3', hashes)

        # All
        all_hashes = invites.get_hashes(allow_strikethrough=True)
        self.assertEqual(len(all_hashes), 3)

    def test_invite_validation_invalid_chars(self):
        """Test invite with invalid characters"""
        with self.assertRaises(InvalidInviteError):
            InviteValue(value='https://t.me/+Invalid Hash!')

    def test_invite_markdown_link(self):
        """Test invite as markdown link"""
        content = """
type: channel
invite: [Join us](https://t.me/+InviteHash123)
"""
        entity = TelegramEntity.from_string(content)
        invite = entity.get_invite()

        self.assertEqual(invite.hash, 'InviteHash123')
        self.assertEqual(invite.url, 'https://t.me/+InviteHash123')


class TestStatus(unittest.TestCase):
    """Tests for status field"""

    def test_status_simple(self):
        """Test simple status"""
        content = """
type: channel
status:
- `active`, `2026-01-20 15:00`
"""
        entity = TelegramEntity.from_string(content)
        status = entity.get_status()

        self.assertIsNotNone(status)
        self.assertEqual(status.value, 'active')
        self.assertIsNotNone(status.date)

    def test_status_all_valid_values(self):
        """Test all valid status values"""
        valid_statuses = ['active', 'unknown', 'banned', 'deleted', 'id_mismatch']

        for status_val in valid_statuses:
            content = f"""
type: channel
status:
- `{status_val}`, `2026-01-20`
"""
            entity = TelegramEntity.from_string(content)
            status = entity.get_status()
            self.assertEqual(status.value, status_val)

    def test_status_invalid_value(self):
        """Test invalid status raises exception"""
        with self.assertRaises(InvalidStatusError):
            StatusValue(value='invalid_status')

    def test_status_case_insensitive(self):
        """Test status is case-insensitive"""
        content = """
type: channel
status:
- `ACTIVE`, `2026-01-20`
"""
        entity = TelegramEntity.from_string(content)
        status = entity.get_status()
        self.assertEqual(status.value, 'active')

    def test_status_with_restriction_details(self):
        """Test banned status with restriction details"""
        content = """
type: channel
status:
- `banned`, `2026-01-20 15:00`
	- reason: `copyright`
	- text: `This channel was banned for copyright violations`
"""
        entity = TelegramEntity.from_string(content)
        status = entity.get_status()

        self.assertEqual(status.value, 'banned')
        self.assertEqual(status.reason, 'copyright')
        self.assertIn('copyright violations', status.text)

    def test_status_history(self):
        """Test status history (multiple entries)"""
        content = """
type: channel
status:
- `active`, `2026-01-20 15:00`
- `unknown`, `2026-01-19 10:00`
- `active`, `2026-01-18 08:00`
"""
        entity = TelegramEntity.from_string(content)

        # Latest is active
        status = entity.get_status()
        self.assertEqual(status.value, 'active')

        # Get all
        statuses = entity.get_statuses()
        self.assertEqual(len(statuses), 3)
        self.assertEqual(statuses[0].value, 'active')
        self.assertEqual(statuses[1].value, 'unknown')
        self.assertEqual(statuses[2].value, 'active')

    def test_status_has_status_method(self):
        """Test has_status() method"""
        content = """
type: channel
status:
- `active`, `2026-01-20`
- `unknown`, `2026-01-19`
- `banned`, `2026-01-18`
"""
        entity = TelegramEntity.from_string(content)
        statuses = entity.get_statuses()

        self.assertTrue(statuses.has_status('banned'))
        self.assertTrue(statuses.has_status('unknown'))
        self.assertFalse(statuses.has_status('deleted'))

    def test_status_with_details(self):
        """Test status with details in parentheses"""
        content = "type: channel\nstatus:\n- `active` (verified manually), `2026-01-20`"
        entity = TelegramEntity.from_string(content)
        status = entity.get_status()
        self.assertEqual(status.details, 'verified manually')


class TestCollections(unittest.TestCase):
    """Tests for historical collections"""

    def test_collection_latest(self):
        """Test latest() method"""
        content = """
type: channel
username:
- `@newest`, `2026-01-20`
- `@middle`, `2026-01-15`
- `@oldest`, `2026-01-10`
"""
        entity = TelegramEntity.from_string(content)
        usernames = entity.get_usernames()

        latest = usernames.latest()
        self.assertEqual(latest.value, 'newest')

    def test_collection_oldest(self):
        """Test oldest() method"""
        content = """
type: channel
username:
- `@newest`, `2026-01-20`
- `@oldest`, `2026-01-10`
"""
        entity = TelegramEntity.from_string(content)
        usernames = entity.get_usernames()

        oldest = usernames.oldest()
        self.assertEqual(oldest.value, 'oldest')

    def test_collection_active(self):
        """Test active() method (non-strikethrough only)"""
        content = """
type: channel
username:
- `@active1`, `2026-01-20`
- ~~`@inactive`~~, `2026-01-15`
- `@active2`, `2026-01-10`
"""
        entity = TelegramEntity.from_string(content)
        usernames = entity.get_usernames()

        active = usernames.active()
        self.assertEqual(len(active), 2)
        self.assertEqual(active[0].value, 'active1')
        self.assertEqual(active[1].value, 'active2')

    def test_collection_iteration(self):
        """Test iterating over collection"""
        content = """
type: channel
username:
- `@user1`, `2026-01-20`
- `@user2`, `2026-01-15`
"""
        entity = TelegramEntity.from_string(content)
        usernames = entity.get_usernames()

        values = [u.value for u in usernames]
        self.assertEqual(values, ['user1', 'user2'])

    def test_collection_len(self):
        """Test len() on collection"""
        content = """
type: channel
username:
- `@user1`
- `@user2`
- `@user3`
"""
        entity = TelegramEntity.from_string(content)
        usernames = entity.get_usernames()
        self.assertEqual(len(usernames), 3)

    def test_collection_bool(self):
        """Test bool() on collection"""
        # Empty collection
        entity1 = TelegramEntity.from_string("type: channel")
        self.assertFalse(bool(entity1.get_usernames()))

        # Non-empty collection
        entity2 = TelegramEntity.from_string("""
type: channel
username: `@testuser`
""")
        self.assertTrue(bool(entity2.get_usernames()))

    def test_collection_getitem(self):
        """Test indexing collection"""
        content = """
type: channel
username:
- `@first`, `2026-01-20`
- `@second`, `2026-01-15`
"""
        entity = TelegramEntity.from_string(content)
        usernames = entity.get_usernames()

        self.assertEqual(usernames[0].value, 'first')
        self.assertEqual(usernames[1].value, 'second')


class TestValidation(unittest.TestCase):
    """Tests for entity validation"""

    def test_validate_valid_entity(self):
        """Test validation on valid entity"""
        content = """
id: `123456`
type: channel
username: `@testchannel`
"""
        entity = TelegramEntity.from_string(content)
        warnings = entity.validate()
        self.assertEqual(len(warnings), 0)

    def test_validate_missing_type(self):
        """Test validation catches missing type"""
        content = """
id: `123456`
username: `@testchannel`
"""
        entity = TelegramEntity.from_string(content)
        warnings = entity.validate()
        self.assertTrue(any('type' in w.lower() for w in warnings))

    def test_validate_invalid_type(self):
        """Test validation catches invalid type"""
        content = """
type: invalid
id: `123456`
"""
        entity = TelegramEntity.from_string(content)
        warnings = entity.validate()
        self.assertTrue(any('invalid type' in w.lower() for w in warnings))

    def test_validate_no_identifier(self):
        """Test validation warns about missing identifiers"""
        content = """
type: channel
"""
        entity = TelegramEntity.from_string(content)
        warnings = entity.validate()
        self.assertTrue(any('identifier' in w.lower() for w in warnings))

    def test_validate_invalid_id_format(self):
        """Test validation catches invalid ID"""
        content = """
id: `not_a_number`
type: channel
"""
        entity = TelegramEntity.from_string(content)
        warnings = entity.validate()
        self.assertTrue(any('id' in w.lower() for w in warnings))


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling"""

    def test_empty_document(self):
        """Test parsing empty document"""
        entity = TelegramEntity.from_string("")

        self.assertIsNone(entity.get_id())
        self.assertEqual(len(entity.get_usernames()), 0)
        self.assertEqual(len(entity.get_invites()), 0)
        self.assertEqual(len(entity.get_statuses()), 0)

    def test_mixed_valid_invalid_usernames(self):
        """Test list with mix of valid and invalid usernames"""
        content = """
type: channel
username:
- `@validuser`, `2026-01-20`
- `placeholder`, `2026-01-15`
- `@another_valid`, `2026-01-10`
"""
        entity = TelegramEntity.from_string(content)
        usernames = entity.get_usernames()

        # Should only have valid usernames
        self.assertEqual(len(usernames), 2)
        self.assertEqual(usernames[0].value, 'validuser')
        self.assertEqual(usernames[1].value, 'another_valid')

    def test_multiple_fields_same_type(self):
        """Test comprehensive entity with all fields"""
        content = """
id: `123456789`
type: channel
username:
- `@currentusername`, `2026-01-20 15:00`
- `@oldusername`, `2026-01-10 10:00`
invite:
- https://t.me/+hn6bxe1xUFlmY2Y0, `2026-01-20`
- ~~https://t.me/+hn6bxe2xUFXmY2Y0~~ (expired), `2026-01-10`
status:
- `active`, `2026-01-20 15:00`
- `unknown`, `2026-01-19 12:00`
- `banned`, `2026-01-18 08:00`
	- reason: `spam`
"""
        entity = TelegramEntity.from_string(content)

        # All fields accessible
        self.assertEqual(entity.get_id(), 123456789)
        self.assertEqual(entity.get_type(), 'channel')
        self.assertEqual(entity.get_username().value, 'currentusername')
        self.assertEqual(entity.get_invite().hash, 'hn6bxe1xUFlmY2Y0')
        self.assertEqual(entity.get_status().value, 'active')

        # Collections
        self.assertEqual(len(entity.get_usernames()), 2)
        self.assertEqual(len(entity.get_invites()), 2)
        self.assertEqual(len(entity.get_statuses()), 3)

    def test_has_field_method(self):
        """Test has_field() method"""
        content = """
type: channel
username: `@testchannel`
"""
        entity = TelegramEntity.from_string(content)

        self.assertTrue(entity.has_field('type'))
        self.assertTrue(entity.has_field('username'))
        self.assertFalse(entity.has_field('id'))
        self.assertFalse(entity.has_field('invite'))

    def test_repr_method(self):
        """Test __repr__ output"""
        content = """
id: `123456`
type: channel
username: `@testchannel`
"""
        entity = TelegramEntity.from_string(content)
        repr_str = repr(entity)

        self.assertIn('123456', repr_str)
        self.assertIn('channel', repr_str)
        self.assertIn('@testchannel', repr_str)

    def test_from_file_not_found(self):
        """Test loading non-existent file"""
        with self.assertRaises(FileNotFoundError):
            TelegramEntity.from_file('nonexistent.md')

    def test_datetime_parsing(self):
        """Test datetime parsing from MDML"""
        content = """
type: channel
username: `@testchannel`, `2026-01-20 15:30`
"""
        entity = TelegramEntity.from_string(content)
        username = entity.get_username()

        self.assertIsNotNone(username.date)
        self.assertEqual(username.date.year, 2026)
        self.assertEqual(username.date.month, 1)
        self.assertEqual(username.date.day, 20)
        self.assertEqual(username.date.hour, 15)
        self.assertEqual(username.date.minute, 30)


class TestRealWorldScenarios(unittest.TestCase):
    """Tests with real-world markdown examples"""

    def test_channel_with_history(self):
        """Test realistic channel with complete history"""
        content = """
id: `1234567890`
type: channel
username:
- `@techchannel` (renamed), `2026-01-20 10:00`
- `@oldtechname`, `2025-12-01 15:00`
invite:
- https://t.me/+NewInvite2026, `2026-01-15`
- ~~https://t.me/+OldInvite2025~~ (expired), `2025-11-20`
status:
- `active`, `2026-01-20 14:30`
- `unknown`, `2026-01-19 08:15`
- `active`, `2026-01-10 12:00`
"""
        entity = TelegramEntity.from_string(content)

        # Validate structure
        self.assertEqual(entity.get_id(), 1234567890)
        self.assertEqual(entity.get_type(), 'channel')

        # Latest values
        self.assertEqual(entity.get_username().value, 'techchannel')
        self.assertEqual(entity.get_username().details, 'renamed')
        self.assertEqual(entity.get_invite().hash, 'NewInvite2026')
        self.assertEqual(entity.get_status().value, 'active')

        # History lengths
        self.assertEqual(len(entity.get_usernames()), 2)
        self.assertEqual(len(entity.get_invites()), 2)
        self.assertEqual(len(entity.get_statuses()), 3)

    def test_banned_channel(self):
        """Test banned channel with restriction details"""
        content = """
id: `9876543210`
type: channel
username: `@bannedchannel`
status:
- `banned`, `2026-01-20 16:45`
	- reason: `copyright`
	- text: `This channel violated Telegram's Terms of Service regarding copyright infringement`
- `active`, `2026-01-15 10:00`
"""
        entity = TelegramEntity.from_string(content)

        status = entity.get_status()
        self.assertEqual(status.value, 'banned')
        self.assertEqual(status.reason, 'copyright')
        self.assertIn('copyright infringement', status.text)

        # Check it was active before
        statuses = entity.get_statuses()
        self.assertTrue(statuses.has_status('active'))

    def test_user_entity(self):
        """Test user entity (simpler structure)"""
        content = """
id: `555666777`
type: user
username: `@johndoe`
status:
- `active`, `2026-01-20`
"""
        entity = TelegramEntity.from_string(content)

        self.assertEqual(entity.get_type(), 'user')
        self.assertEqual(entity.get_username().value, 'johndoe')
        self.assertIsNone(entity.get_invite())  # Users don't have invites

    def test_group_with_multiple_invites(self):
        """Test private group with multiple invite links"""
        content = "type: group\ninvite:\n- https://t.me/+Invite2026Jan (current), `2026-01-20`\n- ~~`https://t.me/+Invite2025Dec`~~ (expired), `2025-12-31`\n- ~~https://t.me/+Invite2025Nov~~ (expired), `2025-11-30`\nstatus:\n- `active`, `2026-01-20`\n"
        entity = TelegramEntity.from_string(content)

        # Latest non-expired invite
        invite = entity.get_invite(allow_strikethrough=False)
        self.assertEqual(invite.hash, 'Invite2026Jan')
        self.assertEqual(invite.details, 'current')

        # All invites (including expired)
        all_invites = entity.get_invites()
        self.assertEqual(len(all_invites), 3)

        # Active invites only
        active_invites = all_invites.active()
        self.assertEqual(len(active_invites), 1)


def run_tests():
    """Run all tests with verbose output"""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    print("=" * 70)
    print("Telegram MDML v1.0 Test Suite")
    print("=" * 70)
    print()

    run_tests()

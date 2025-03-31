"""
Test custom Django management commands.

"""

# path inorder to mock the behaviour of database
from unittest.mock import patch

# possible error we might get while connecting to database
from psycopg2 import OperationalError as Psycopg2Error

# call_command is a helper command that
# allows to call the command that we are testing
from django.core.management import call_command
from django.db.utils import OperationalError
from django.test import SimpleTestCase


# to test the check method inside BaseCommand from wait_for_db.py
@patch("core.management.commands.wait_for_db.Command.check")
class CommandTests(SimpleTestCase):
    """Test commands."""

    # the above command is repalced by patched_check
    def test_wait_for_db_read(self, patched_check):
        """Test waiting for database if database ready."""
        # if patched_check is called it returns true
        patched_check.return_value = True
        call_command("wait_for_db")
        patched_check.assert_called_once_with(databases=["default"])

    @patch("time.sleep")
    def test_wait_for_db_delay(self, patched_sleep, patched_check):
        """Test waiting for database when getting OperationalError."""
        patched_check.side_effect = (
            [Psycopg2Error] * 2 + [OperationalError] * 3 + [True]
        )
        call_command("wait_for_db")
        self.assertEqual(patched_check.call_count, 6)
        patched_check.assert_called_with(databases=["default"])

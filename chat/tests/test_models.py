import datetime
import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from chat.models import Message, Room, RoomMember

User = get_user_model()


class RoomTestCase(TestCase):
    def setUp(self):
        self.room = Room.objects.create()

    def test_room_insert_generates_uuid(self):
        """Room generates uuid on insert."""
        self.assertIsInstance(self.room.id, uuid.UUID)
        self.assertEqual(self.room.id.version, 7)

    def test_room_insert_sets_created_at(self):
        """Room sets created_at on insert."""
        self.assertIsInstance(self.room.created_at, datetime.datetime)
        self.assertTrue(timezone.is_aware(self.room.created_at))

    def test_room_insert_last_message_at_defaults_to_null(self):
        """Room sets default last_message_at to null on insert."""
        self.assertIsNone(self.room.last_message_at)

    def test_room_update_last_message_at_can_be_updated(self):
        """Can update last_message_at."""
        now = timezone.now()
        self.room.last_message_at = now
        self.room.save(update_fields=["last_message_at"])
        self.room.refresh_from_db()

        self.assertEqual(self.room.last_message_at, now)


class RoomMemberTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="testuser")
        self.room = Room.objects.create()

        self.room_member = RoomMember.objects.create(
            room=self.room,
            user=self.user,
        )

    def test_roommember_unique_user_and_room(self):
        """A user can only belong to a room once."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RoomMember.objects.create(room=self.room, user=self.user)

    def test_roommember_insert_sets_date_fields(self):
        """RoomMember sets read_at and joined_at on insert."""
        self.assertIsInstance(self.room_member.joined_at, datetime.datetime)
        self.assertIsInstance(self.room_member.read_at, datetime.datetime)

        self.assertTrue(timezone.is_aware(self.room_member.joined_at))
        self.assertTrue(timezone.is_aware(self.room_member.read_at))

        self.assertEqual(self.room_member.joined_at, self.room_member.read_at)

    def test_roommember_update_date_fields(self):
        """Can update date fields."""
        now = timezone.now()
        self.room_member.joined_at = now
        self.room_member.read_at = now
        self.room_member.save(update_fields=["joined_at", "read_at"])
        self.room_member.refresh_from_db()

        self.assertEqual(self.room_member.joined_at, now)
        self.assertEqual(self.room_member.read_at, now)

    def test_roommember_cascade_delete_user(self):
        """Roomember is deleted when the user is deleted."""
        self.user.delete()

        with self.assertRaises(RoomMember.DoesNotExist):
            self.room_member.refresh_from_db()

    def test_roommember_cascade_delete_room(self):
        """Roomember is deleted when the room is deleted."""
        self.room.delete()

        with self.assertRaises(RoomMember.DoesNotExist):
            self.room_member.refresh_from_db()

    def test_roommember_same_user_can_join_different_rooms(self):
        """(not raises) One user can join multiple rooms."""
        new_room = Room.objects.create()
        RoomMember.objects.create(room=new_room, user=self.user)

    def test_roommember_different_users_can_join_same_room(self):
        """(not raises) Multiple users can join one room."""
        new_user = User.objects.create(username="newuser")
        RoomMember.objects.create(room=self.room, user=new_user)


class MessageTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="testuser")
        self.room = Room.objects.create()

        self.message = Message.objects.create(
            message="test message",
            room=self.room,
            user=self.user,
        )

    def test_message_insert_generates_uuid(self):
        """Message generates uuid on insert."""
        self.assertIsInstance(self.message.id, uuid.UUID)
        self.assertEqual(self.message.id.version, 7)

    def test_message_insert_sets_created_at(self):
        """Message sets created_at on insert."""
        self.assertIsInstance(self.message.created_at, datetime.datetime)
        self.assertTrue(timezone.is_aware(self.message.created_at))

    def test_message_cascade_delete_room(self):
        """Message is deleted when the room is deleted."""
        self.room.delete()

        with self.assertRaises(Message.DoesNotExist):
            self.message.refresh_from_db()

    def test_message_allows_null_user(self):
        """Message can have a null user."""
        self.message.user = None
        self.message.save()
        self.message.refresh_from_db()

        self.assertIsNone(self.message.user)

    def test_message_deleting_user_preserves_message(self):
        """Message is preserved when the user is deleted."""
        self.message.user.delete()
        self.message.refresh_from_db()

        self.assertIsNone(self.message.user)
        self.assertEqual(self.message.message, "test message")

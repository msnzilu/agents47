"""
tests/test_scheduling_tools.py
Phase 6: Scheduling Use Case Tools Tests
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from agents.models import Agent
from agents.tools.scheduling_tools import (
    CalendarManager,
    MeetingScheduler,
    AvailabilityChecker,
    ReminderScheduler
)

User = get_user_model()


class TestCalendarManager(TestCase):
    """Test calendar management operations"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Scheduling Agent',
            use_case='scheduling'
        )
        self.manager = CalendarManager(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_calendar_auth_flow(self):
        """Test calendar authentication/integration"""
        result = await self.manager._execute(action='authenticate')
        
        assert result['authenticated'] is True
        assert result['calendar_id'] == 'primary'
        assert result['provider'] == 'google'
    
    @pytest.mark.asyncio
    async def test_list_events(self):
        """Test listing calendar events"""
        start = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        
        result = await self.manager._execute(
            action='list_events',
            start_date=start.isoformat(),
            end_date=end.isoformat()
        )
        
        assert 'events' in result
        assert 'start_date' in result
        assert 'end_date' in result
        assert isinstance(result['events'], list)


class TestAvailabilityChecker(TestCase):
    """Test availability checking"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Scheduling Agent',
            use_case='scheduling'
        )
        self.checker = AvailabilityChecker(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_availability_check_returns_slots(self):
        """Test availability checking returns time slots"""
        date = datetime.now().isoformat()
        
        result = await self.checker._execute(
            date=date,
            duration=60
        )
        
        assert 'available_slots' in result
        assert len(result['available_slots']) > 0
        assert 'date' in result
        
        # Verify slot structure
        for slot in result['available_slots']:
            assert 'start' in slot
            assert 'end' in slot
    
    @pytest.mark.asyncio
    async def test_availability_business_hours_only(self):
        """Test that availability only shows business hours"""
        date = datetime.now().isoformat()
        
        result = await self.checker._execute(
            date=date,
            duration=30
        )
        
        # All slots should be during business hours (9 AM - 5 PM)
        for slot in result['available_slots']:
            # Parse time strings like '09:00'
            hour = int(slot['start'].split(':')[0])
            assert 9 <= hour < 17


class TestMeetingScheduler(TestCase):
    """Test intelligent meeting scheduling"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Scheduling Agent',
            use_case='scheduling'
        )
        self.scheduler = MeetingScheduler(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_meeting_creation_success(self):
        """Test successful meeting creation"""
        start_time = (datetime.now() + timedelta(days=1)).replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        
        result = await self.scheduler._execute(
            title='Team Standup',
            start_time=start_time.isoformat(),
            duration=30,
            attendees=['alice@example.com', 'bob@example.com']
        )
        
        assert result['success'] is True
        assert result['title'] == 'Team Standup'
        assert result['start_time'] == start_time.isoformat()
        assert result['duration_minutes'] == 30
        assert len(result['attendees']) == 2
        assert 'alice@example.com' in result['attendees']
        assert 'meeting_id' in result
        assert result['status'] == 'scheduled'
    
    @pytest.mark.asyncio
    async def test_meeting_duration_flexibility(self):
        """Test scheduling with different duration requirements"""
        durations = [15, 30, 60, 90]
        
        for duration in durations:
            start_time = (datetime.now() + timedelta(days=1)).isoformat()
            
            result = await self.scheduler._execute(
                title='Test Meeting',
                start_time=start_time,
                duration=duration,
                attendees=['alice@example.com', 'bob@example.com']
            )
            
            assert result['duration_minutes'] == duration
            assert result['success'] is True


class TestReminderScheduling(TestCase):
    """Test reminder scheduling functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            name='Scheduling Agent',
            use_case='scheduling'
        )
        self.reminder = ReminderScheduler(agent=self.agent)
    
    @pytest.mark.asyncio
    async def test_reminder_scheduled(self):
        """Test that reminders can be scheduled for meetings"""
        result = await self.reminder._execute(
            meeting_id='MEET-12345',
            reminder_times=[15, 60]
        )
        
        assert result['success'] is True
        assert result['meeting_id'] == 'MEET-12345'
        assert 'reminders' in result
        assert len(result['reminders']) == 2
        
        # Verify reminder structure
        for reminder in result['reminders']:
            assert 'meeting_id' in reminder
            assert 'minutes_before' in reminder
            assert 'scheduled' in reminder
            assert reminder['scheduled'] is True
    
    @pytest.mark.asyncio
    async def test_multiple_reminders(self):
        """Test scheduling multiple reminders for an event"""
        reminder_times = [15, 60, 1440]  # 15 min, 1 hour, 24 hours
        
        result = await self.reminder._execute(
            meeting_id='MEET-67890',
            reminder_times=reminder_times
        )
        
        assert result['success'] is True
        assert len(result['reminders']) == 3
        
        # Verify all reminder times are included
        actual_times = [r['minutes_before'] for r in result['reminders']]
        assert set(actual_times) == set(reminder_times)
    
    @pytest.mark.asyncio
    async def test_reminder_for_meeting(self):
        """Test creating reminder for a specific meeting"""
        meeting_id = 'MEET-TEST-001'
        
        result = await self.reminder._execute(
            meeting_id=meeting_id,
            reminder_times=[30]
        )
        
        assert result['success'] is True
        assert result['meeting_id'] == meeting_id
        assert result['reminders'][0]['minutes_before'] == 30
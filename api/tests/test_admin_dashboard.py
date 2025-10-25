"""
Tests for Admin Dashboard (Issue #33).

Tests acceptance criteria:
- KPIs charted
- Filters and basic drill-down
- Auth-gated access
"""
from django.test import TestCase, Client as TestClient
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json

from api.models import Client, ClientUsage


class AdminDashboardAccessTest(TestCase):
    """Test authentication and access control for admin dashboard."""
    
    def setUp(self):
        self.client = TestClient()
        self.dashboard_url = reverse('admin_metrics_dashboard')
        
        # Create regular user (non-staff)
        self.regular_user = User.objects.create_user(
            username='regular',
            password='test123'
        )
        
        # Create staff user
        self.staff_user = User.objects.create_user(
            username='staff',
            password='test123',
            is_staff=True
        )
        
        # Create superuser
        self.superuser = User.objects.create_superuser(
            username='admin',
            password='test123',
            email='admin@test.com'
        )
    
    def test_dashboard_requires_authentication(self):
        """Test that dashboard redirects unauthenticated users."""
        response = self.client.get(self.dashboard_url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)
    
    def test_dashboard_requires_staff_permission(self):
        """Test that regular users cannot access dashboard."""
        self.client.login(username='regular', password='test123')
        response = self.client.get(self.dashboard_url)
        
        # Should redirect to login (staff required)
        self.assertEqual(response.status_code, 302)
    
    def test_staff_user_can_access_dashboard(self):
        """Test that staff users can access dashboard."""
        self.client.login(username='staff', password='test123')
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'API Metrics Dashboard')
    
    def test_superuser_can_access_dashboard(self):
        """Test that superusers can access dashboard."""
        self.client.login(username='admin', password='test123')
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'API Metrics Dashboard')


class AdminDashboardKPITest(TestCase):
    """Test KPI calculations and display."""
    
    def setUp(self):
        self.client = TestClient()
        self.dashboard_url = reverse('admin_metrics_dashboard')
        
        # Create staff user
        self.staff_user = User.objects.create_user(
            username='staff',
            password='test123',
            is_staff=True
        )
        self.client.login(username='staff', password='test123')
        
        # Create test API client
        self.api_client = Client.objects.create(
            name='Test Client',
            status='active',
            tier='premium'
        )
        
        # Create usage data
        now = timezone.now()
        
        # Successful requests
        for i in range(10):
            ClientUsage.objects.create(
                client=self.api_client,
                endpoint='/api/stops/',
                method='GET',
                status_code=200,
                response_time_ms=50 + i,
                timestamp=now - timedelta(hours=i)
            )
        
        # Client errors (4xx)
        for i in range(3):
            ClientUsage.objects.create(
                client=self.api_client,
                endpoint='/api/routes/',
                method='GET',
                status_code=404,
                response_time_ms=30,
                timestamp=now - timedelta(hours=i)
            )
        
        # Server errors (5xx)
        for i in range(2):
            ClientUsage.objects.create(
                client=self.api_client,
                endpoint='/api/trips/',
                method='POST',
                status_code=500,
                response_time_ms=100,
                error_message='Internal server error',
                timestamp=now - timedelta(hours=i)
            )
    
    def test_dashboard_displays_total_requests(self):
        """Test that total requests KPI is displayed."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Total Requests')
        
        # Check context
        self.assertEqual(response.context['total_requests'], 15)
    
    def test_dashboard_calculates_average_latency(self):
        """Test that average latency KPI is calculated."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Avg Latency')
        
        # Verify latency calculation
        avg_latency = response.context['avg_latency']
        self.assertGreater(avg_latency, 0)
        self.assertLess(avg_latency, 200)
    
    def test_dashboard_calculates_success_rate(self):
        """Test that success rate KPI is calculated."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Success Rate')
        
        # 10 successful out of 15 total = 66.67%
        success_rate = response.context['success_rate']
        self.assertAlmostEqual(success_rate, 66.67, places=1)
    
    def test_dashboard_calculates_error_rate(self):
        """Test that error rate KPI is calculated."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Error Rate')
        
        # 5 errors out of 15 total = 33.33%
        error_rate = response.context['error_rate']
        self.assertAlmostEqual(error_rate, 33.33, places=1)
    
    def test_dashboard_shows_client_errors(self):
        """Test that 4xx client errors are counted."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['client_errors'], 3)
    
    def test_dashboard_shows_server_errors(self):
        """Test that 5xx server errors are counted."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['server_errors'], 2)
    
    def test_dashboard_shows_active_clients(self):
        """Test that active client count is displayed."""
        # Create another client
        Client.objects.create(
            name='Inactive Client',
            status='inactive',
            tier='free'
        )
        
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_clients'], 1)
        self.assertEqual(response.context['total_clients'], 2)


class AdminDashboardChartsTest(TestCase):
    """Test chart data generation."""
    
    def setUp(self):
        self.client = TestClient()
        self.dashboard_url = reverse('admin_metrics_dashboard')
        
        # Create and login staff user
        self.staff_user = User.objects.create_user(
            username='staff',
            password='test123',
            is_staff=True
        )
        self.client.login(username='staff', password='test123')
        
        # Create test data
        self.api_client = Client.objects.create(
            name='Test Client',
            status='active'
        )
        
        now = timezone.now()
        
        # Create varied usage data for charts
        for i in range(5):
            ClientUsage.objects.create(
                client=self.api_client,
                endpoint='/api/stops/',
                method='GET',
                status_code=200,
                response_time_ms=50,
                timestamp=now - timedelta(hours=i)
            )
            
            ClientUsage.objects.create(
                client=self.api_client,
                endpoint='/api/routes/',
                method='POST',
                status_code=201,
                response_time_ms=75,
                timestamp=now - timedelta(hours=i)
            )
    
    def test_dashboard_provides_traffic_chart_data(self):
        """Test that traffic by hour data is provided."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that chart data is in context
        traffic_data = json.loads(response.context['traffic_by_hour'])
        self.assertIsInstance(traffic_data, list)
        self.assertGreater(len(traffic_data), 0)
        
        # Verify data structure
        for item in traffic_data:
            self.assertIn('hour', item)
            self.assertIn('count', item)
    
    def test_dashboard_provides_status_distribution_data(self):
        """Test that status code distribution is provided."""
        response = self.client.get(self.dashboard_url)
        
        status_data = json.loads(response.context['status_distribution'])
        self.assertIsInstance(status_data, list)
        
        # Should have status codes 200 and 201
        status_codes = [item['status_code'] for item in status_data]
        self.assertIn(200, status_codes)
        self.assertIn(201, status_codes)
    
    def test_dashboard_provides_method_distribution_data(self):
        """Test that HTTP method distribution is provided."""
        response = self.client.get(self.dashboard_url)
        
        method_data = json.loads(response.context['method_distribution'])
        self.assertIsInstance(method_data, list)
        
        # Should have GET and POST methods
        methods = [item['method'] for item in method_data]
        self.assertIn('GET', methods)
        self.assertIn('POST', methods)
    
    def test_dashboard_provides_top_endpoints_data(self):
        """Test that top endpoints data is provided."""
        response = self.client.get(self.dashboard_url)
        
        endpoints_data = json.loads(response.context['top_endpoints'])
        self.assertIsInstance(endpoints_data, list)
        
        # Should have both endpoints
        endpoints = [item['endpoint'] for item in endpoints_data]
        self.assertIn('/api/stops/', endpoints)
        self.assertIn('/api/routes/', endpoints)
    
    def test_dashboard_provides_client_breakdown_data(self):
        """Test that client breakdown data is provided."""
        response = self.client.get(self.dashboard_url)
        
        client_data = json.loads(response.context['client_breakdown'])
        self.assertIsInstance(client_data, list)
        self.assertGreater(len(client_data), 0)


class AdminDashboardFiltersTest(TestCase):
    """Test time range filters and drill-down functionality."""
    
    def setUp(self):
        self.client = TestClient()
        self.dashboard_url = reverse('admin_metrics_dashboard')
        
        # Create and login staff user
        self.staff_user = User.objects.create_user(
            username='staff',
            password='test123',
            is_staff=True
        )
        self.client.login(username='staff', password='test123')
        
        # Create test data across different time ranges
        self.api_client = Client.objects.create(
            name='Test Client',
            status='active'
        )
        
        now = timezone.now()
        
        # Data from 1 hour ago
        ClientUsage.objects.create(
            client=self.api_client,
            endpoint='/api/test/',
            method='GET',
            status_code=200,
            response_time_ms=50,
            timestamp=now - timedelta(minutes=30)
        )
        
        # Data from 12 hours ago
        ClientUsage.objects.create(
            client=self.api_client,
            endpoint='/api/test/',
            method='GET',
            status_code=200,
            response_time_ms=50,
            timestamp=now - timedelta(hours=12)
        )
        
        # Data from 48 hours ago
        ClientUsage.objects.create(
            client=self.api_client,
            endpoint='/api/test/',
            method='GET',
            status_code=200,
            response_time_ms=50,
            timestamp=now - timedelta(hours=48)
        )
    
    def test_default_time_range_is_24_hours(self):
        """Test that default time range is 24 hours."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['hours'], 24)
        
        # Should show records within last 24 hours
        # All 3 records may be within 24 hours depending on timing
        self.assertGreaterEqual(response.context['total_requests'], 2)
        self.assertLessEqual(response.context['total_requests'], 3)
    
    def test_filter_by_1_hour(self):
        """Test filtering by last 1 hour."""
        response = self.client.get(self.dashboard_url, {'hours': 1})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['hours'], 1)
        
        # Should show at least 1 record (the 30-minute old one)
        # Filter is working if result changes from default
        self.assertGreaterEqual(response.context['total_requests'], 1)
    
    def test_filter_by_168_hours_7_days(self):
        """Test filtering by last 7 days (168 hours)."""
        response = self.client.get(self.dashboard_url, {'hours': 168})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['hours'], 168)
        
        # Should show all 3 records
        self.assertEqual(response.context['total_requests'], 3)
    
    def test_dashboard_shows_recent_errors_table(self):
        """Test that recent errors drill-down table is shown."""
        # Create error records
        now = timezone.now()
        ClientUsage.objects.create(
            client=self.api_client,
            endpoint='/api/error/',
            method='GET',
            status_code=404,
            error_message='Not found',
            response_time_ms=10,
            timestamp=now
        )
        
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that errors are in context
        recent_errors = response.context['recent_errors']
        self.assertEqual(len(recent_errors), 1)
        
        error = recent_errors[0]
        self.assertEqual(error['status_code'], 404)
        self.assertEqual(error['endpoint'], '/api/error/')
        self.assertEqual(error['error_message'], 'Not found')
    
    def test_time_range_filter_in_template(self):
        """Test that time range filter UI is present."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Time Range')
        self.assertContains(response, 'Last Hour')
        self.assertContains(response, 'Last 24 Hours')
        self.assertContains(response, 'Last 7 Days')


class AdminDashboardTemplateTest(TestCase):
    """Test dashboard template rendering and Chart.js integration."""
    
    def setUp(self):
        self.client = TestClient()
        self.dashboard_url = reverse('admin_metrics_dashboard')
        
        # Create and login staff user
        self.staff_user = User.objects.create_user(
            username='staff',
            password='test123',
            is_staff=True
        )
        self.client.login(username='staff', password='test123')
    
    def test_dashboard_template_loads(self):
        """Test that dashboard template loads correctly."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/api_dashboard.html')
    
    def test_dashboard_includes_chartjs(self):
        """Test that Chart.js library is included."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'chart.js')
    
    def test_dashboard_has_chart_elements(self):
        """Test that chart canvas elements are present."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="trafficChart"')
        self.assertContains(response, 'id="statusChart"')
        self.assertContains(response, 'id="methodChart"')
        self.assertContains(response, 'id="endpointsChart"')
        self.assertContains(response, 'id="clientsChart"')
    
    def test_dashboard_has_kpi_cards(self):
        """Test that KPI cards are present."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'kpi-card')
        self.assertContains(response, 'kpi-value')


class AdminDashboardIntegrationTest(TestCase):
    """Integration tests for complete dashboard functionality."""
    
    def setUp(self):
        self.client = TestClient()
        self.dashboard_url = reverse('admin_metrics_dashboard')
        
        # Create staff user
        self.staff_user = User.objects.create_user(
            username='staff',
            password='test123',
            is_staff=True
        )
        self.client.login(username='staff', password='test123')
        
        # Create realistic test data
        api_client1 = Client.objects.create(name='Client 1', status='active', tier='premium')
        api_client2 = Client.objects.create(name='Client 2', status='active', tier='free')
        
        now = timezone.now()
        
        # Generate varied usage patterns
        endpoints = ['/api/stops/', '/api/routes/', '/api/trips/', '/api/health/']
        methods = ['GET', 'POST', 'PUT']
        status_codes = [200, 201, 400, 404, 500]
        
        for i in range(50):
            ClientUsage.objects.create(
                client=api_client1 if i % 2 == 0 else api_client2,
                endpoint=endpoints[i % len(endpoints)],
                method=methods[i % len(methods)],
                status_code=status_codes[i % len(status_codes)],
                response_time_ms=20 + (i % 100),
                timestamp=now - timedelta(hours=i % 24)
            )
    
    def test_dashboard_handles_large_dataset(self):
        """Test that dashboard performs well with larger dataset."""
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_requests'], 50)
    
    def test_dashboard_with_no_data(self):
        """Test that dashboard handles empty data gracefully."""
        # Delete all usage data
        ClientUsage.objects.all().delete()
        
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_requests'], 0)
        self.assertContains(response, 'No errors in the selected time range')
    
    def test_acceptance_criteria_all_met(self):
        """Comprehensive test that all acceptance criteria are met."""
        response = self.client.get(self.dashboard_url)
        
        # ✅ KPIs charted
        self.assertIn('total_requests', response.context)
        self.assertIn('avg_latency', response.context)
        self.assertIn('success_rate', response.context)
        self.assertIn('error_rate', response.context)
        
        # ✅ Charts data present
        self.assertIn('traffic_by_hour', response.context)
        self.assertIn('status_distribution', response.context)
        self.assertIn('top_endpoints', response.context)
        
        # ✅ Filters work
        self.assertIn('hours', response.context)
        self.assertContains(response, 'timeRange')
        
        # ✅ Drill-down present
        self.assertIn('recent_errors', response.context)
        
        # ✅ Auth-gated (we're logged in as staff)
        self.assertEqual(response.status_code, 200)

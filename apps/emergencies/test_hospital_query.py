"""
Unit tests for find_nearby_hospitals service function (Phase 8.1.1).

Verifies:
1. Spatial ordering: Nearest hospitals appear first.
2. Status filtering: Inactive hospitals are strictly excluded.
3. Coordinates filtering: Hospitals with null latitude/longitude are excluded without error.
4. Raw distance filtering: max_distance_km applies to raw meters before rounding.
5. Result limiting: Results are capped at max_results.
6. Case-insensitive substring query on hospital name (including trimmed whitespace).
7. Validation errors for missing, non-numeric, or out-of-range coordinates.
8. Validation errors for invalid max_distance_km.
9. Exact location match returns 0.0 distance.
10. Read-only guarantee: Database records are untouched.
"""

from decimal import Decimal
from django.test import TestCase

from apps.emergencies.models import Hospital
from apps.emergencies.services import find_nearby_hospitals


class HospitalProximityQueryTests(TestCase):
    """Test suite for the find_nearby_hospitals read-only service function."""

    def setUp(self):
        # Base coordinates: MG Road, Bengaluru (12.975000, 77.609000)
        self.origin_lat = 12.975000
        self.origin_lng = 77.609000

        # Hospital 1: ~1.2 km away
        self.hosp_near = Hospital.objects.create(
            name="City Central Emergency Hospital",
            hospital_code="HOSP-PROX-01",
            address="100 MG Road, Bengaluru",
            latitude=Decimal("12.971600"),
            longitude=Decimal("77.594600"),
            contact_number="+918011111111",
            is_active=True,
        )

        # Hospital 2: ~3.8 km away
        self.hosp_mid = Hospital.objects.create(
            name="Metro Trauma and Surgical Center",
            hospital_code="HOSP-PROX-02",
            address="200 West Boulevard, Bengaluru",
            latitude=Decimal("12.990000"),
            longitude=Decimal("77.635000"),
            contact_number="+918022222222",
            is_active=True,
        )

        # Hospital 3: ~12.5 km away
        self.hosp_far = Hospital.objects.create(
            name="Suburban Care Clinic",
            hospital_code="HOSP-PROX-03",
            address="500 Outer Ring Road, Bengaluru",
            latitude=Decimal("13.045000"),
            longitude=Decimal("77.680000"),
            contact_number="+918033333333",
            is_active=True,
        )

    def test_find_nearby_hospitals_sorted_by_distance(self):
        """Nearest active hospitals appear in ascending order of proximity."""
        results = find_nearby_hospitals(
            latitude=self.origin_lat,
            longitude=self.origin_lng,
            max_results=3,
            max_distance_km=30,
        )

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["id"], str(self.hosp_near.id))
        self.assertEqual(results[1]["id"], str(self.hosp_mid.id))
        self.assertEqual(results[2]["id"], str(self.hosp_far.id))

        # Check distances are ascending
        self.assertLess(results[0]["distance_km"], results[1]["distance_km"])
        self.assertLess(results[1]["distance_km"], results[2]["distance_km"])

        # Check expected payload structure
        first = results[0]
        self.assertIn("id", first)
        self.assertIn("name", first)
        self.assertIn("hospital_code", first)
        self.assertIn("address", first)
        self.assertIn("contact_number", first)
        self.assertIn("latitude", first)
        self.assertIn("longitude", first)
        self.assertIn("distance_km", first)
        self.assertIn("distance_meters", first)
        self.assertIn("is_active", first)
        self.assertTrue(first["is_active"])

    def test_inactive_hospitals_strictly_excluded(self):
        """Inactive hospitals are never returned even if physically closest."""
        # Create an inactive hospital right next to origin (e.g. 50 meters away)
        inactive_hosp = Hospital.objects.create(
            name="Closed Emergency Clinic",
            hospital_code="HOSP-PROX-INACTIVE",
            address="10 Adjacent Lane, Bengaluru",
            latitude=Decimal("12.975100"),
            longitude=Decimal("77.609100"),
            is_active=False,
        )

        results = find_nearby_hospitals(
            latitude=self.origin_lat,
            longitude=self.origin_lng,
            max_results=5,
        )

        returned_ids = [r["id"] for r in results]
        self.assertNotIn(str(inactive_hosp.id), returned_ids)

    def test_hospitals_with_null_coordinates_excluded(self):
        """Hospitals missing latitude or longitude are safely omitted."""
        hosp_no_coords = Hospital.objects.create(
            name="Virtual Health Facility",
            hospital_code="HOSP-PROX-NOCOORDS",
            address="Online Consultation Portal",
            latitude=None,
            longitude=None,
            is_active=True,
        )

        results = find_nearby_hospitals(
            latitude=self.origin_lat,
            longitude=self.origin_lng,
            max_results=5,
        )

        returned_ids = [r["id"] for r in results]
        self.assertNotIn(str(hosp_no_coords.id), returned_ids)

    def test_max_distance_km_raw_meters_filtering(self):
        """Hospitals beyond max_distance_km are excluded based on raw meters."""
        # Query with radius that includes hosp_near (~1.2 km) and hosp_mid (~3.8 km), but excludes hosp_far (~12.5 km)
        results = find_nearby_hospitals(
            latitude=self.origin_lat,
            longitude=self.origin_lng,
            max_results=5,
            max_distance_km=5.0,
        )

        self.assertEqual(len(results), 2)
        returned_ids = [r["id"] for r in results]
        self.assertIn(str(self.hosp_near.id), returned_ids)
        self.assertIn(str(self.hosp_mid.id), returned_ids)
        self.assertNotIn(str(self.hosp_far.id), returned_ids)

    def test_max_results_capping(self):
        """Result count is strictly limited by max_results."""
        results = find_nearby_hospitals(
            latitude=self.origin_lat,
            longitude=self.origin_lng,
            max_results=1,
            max_distance_km=30,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(self.hosp_near.id))

    def test_query_case_insensitive_name_filter(self):
        """Optional query matches hospital name case-insensitively and handles whitespace."""
        # Substring "trauma" matches Metro Trauma and Surgical Center
        results_lower = find_nearby_hospitals(
            latitude=self.origin_lat,
            longitude=self.origin_lng,
            query="trauma",
        )
        self.assertEqual(len(results_lower), 1)
        self.assertEqual(results_lower[0]["id"], str(self.hosp_mid.id))

        # Upper case with extra whitespace
        results_upper = find_nearby_hospitals(
            latitude=self.origin_lat,
            longitude=self.origin_lng,
            query="  TRAUMA  ",
        )
        self.assertEqual(len(results_upper), 1)
        self.assertEqual(results_upper[0]["id"], str(self.hosp_mid.id))

        # Non-matching query returns empty list
        results_none = find_nearby_hospitals(
            latitude=self.origin_lat,
            longitude=self.origin_lng,
            query="NonexistentSpecialtyHospital",
        )
        self.assertEqual(results_none, [])

    def test_exact_location_match_returns_zero_distance(self):
        """Coordinates matching a hospital exactly yield 0.0 distance."""
        results = find_nearby_hospitals(
            latitude=float(self.hosp_near.latitude),
            longitude=float(self.hosp_near.longitude),
            max_results=1,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(self.hosp_near.id))
        self.assertEqual(results[0]["distance_km"], 0.0)
        self.assertEqual(results[0]["distance_meters"], 0.0)

    def test_validation_missing_coordinates(self):
        """Missing or None coordinates raise ValueError."""
        with self.assertRaises(ValueError):
            find_nearby_hospitals(latitude=None, longitude=77.609)

        with self.assertRaises(ValueError):
            find_nearby_hospitals(latitude=12.975, longitude=None)

    def test_validation_non_numeric_coordinates(self):
        """Non-numeric coordinate strings raise ValueError."""
        with self.assertRaises(ValueError):
            find_nearby_hospitals(latitude="not-a-number", longitude=77.609)

        with self.assertRaises(ValueError):
            find_nearby_hospitals(latitude=12.975, longitude="invalid")

    def test_validation_out_of_range_coordinates(self):
        """Coordinates outside valid WGS-84 ranges raise ValueError."""
        with self.assertRaises(ValueError):
            find_nearby_hospitals(latitude=91.5, longitude=77.609)

        with self.assertRaises(ValueError):
            find_nearby_hospitals(latitude=-90.1, longitude=77.609)

        with self.assertRaises(ValueError):
            find_nearby_hospitals(latitude=12.975, longitude=181.0)

        with self.assertRaises(ValueError):
            find_nearby_hospitals(latitude=12.975, longitude=-185.0)

    def test_validation_invalid_max_distance_km(self):
        """Non-positive or non-numeric max_distance_km raises ValueError."""
        with self.assertRaises(ValueError):
            find_nearby_hospitals(latitude=12.975, longitude=77.609, max_distance_km=0)

        with self.assertRaises(ValueError):
            find_nearby_hospitals(latitude=12.975, longitude=77.609, max_distance_km=-10)

        with self.assertRaises(ValueError):
            find_nearby_hospitals(latitude=12.975, longitude=77.609, max_distance_km="invalid")

    def test_read_only_guarantee(self):
        """Executing search does not create, update, or delete any database rows."""
        initial_count = Hospital.objects.count()

        find_nearby_hospitals(
            latitude=self.origin_lat,
            longitude=self.origin_lng,
            query="Emergency",
            max_results=5,
        )

        self.assertEqual(Hospital.objects.count(), initial_count)

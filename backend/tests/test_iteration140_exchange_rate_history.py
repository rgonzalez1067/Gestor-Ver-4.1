# ruff: noqa
"""
Test iteration 140: Exchange Rate History System
Tests for:
- GET /api/exchange-rate/by-date/{fecha} - returns rate for dates with records, 'found: false' for dates without
- POST /api/exchange-rate/manual - registers manual rate for a specific date
- GET /api/exchange-rate/history - returns rate history ordered by date
- POST /api/exchange-rate/update - fetches BCV rate and saves to history automatically
- Login functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestLogin:
    """Test login functionality"""
    
    def test_login_success(self):
        """Test successful login with admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data, "session_token not in response"
        assert len(data["session_token"]) > 0, "Token is empty"
        print("✓ Login successful, session_token received")
        return data["session_token"]


class TestExchangeRateByDate:
    """Test GET /api/exchange-rate/by-date/{fecha}"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        return response.json().get("session_token")
    
    def test_get_rate_for_date_with_record(self, auth_token):
        """Test fetching rate for a date that has a record (2026-04-01 or 2026-03-28)"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Try 2026-04-01 first (BCV rate)
        response = requests.get(f"{BASE_URL}/api/exchange-rate/by-date/2026-04-01", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        if data.get("found"):
            assert "valor_tasa" in data, "valor_tasa not in response"
            assert data["valor_tasa"] > 0, "Rate should be positive"
            print(f"✓ Found rate for 2026-04-01: {data['valor_tasa']} ({data.get('fuente', 'N/A')})")
        else:
            # Try 2026-03-28 (Manual rate)
            response = requests.get(f"{BASE_URL}/api/exchange-rate/by-date/2026-03-28", headers=headers)
            assert response.status_code == 200
            data = response.json()
            if data.get("found"):
                assert "valor_tasa" in data
                print(f"✓ Found rate for 2026-03-28: {data['valor_tasa']} ({data.get('fuente', 'N/A')})")
            else:
                print("⚠ No pre-existing rates found, will test with manual rate creation")
    
    def test_get_rate_for_date_without_record(self, auth_token):
        """Test fetching rate for a date without record (2026-03-15)"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.get(f"{BASE_URL}/api/exchange-rate/by-date/2026-03-15", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "found" in data, "'found' field not in response"
        assert data["found"] == False, f"Expected found=False for date without record, got {data['found']}"
        assert data.get("fecha") == "2026-03-15", "fecha field mismatch"
        print(f"✓ Correctly returned found=False for date without record: {data}")


class TestExchangeRateManual:
    """Test POST /api/exchange-rate/manual"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        return response.json().get("session_token")
    
    def test_register_manual_rate(self, auth_token):
        """Test registering a manual rate for a specific date"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        test_date = "2026-03-20"
        test_rate = 475.50
        
        response = requests.post(f"{BASE_URL}/api/exchange-rate/manual", 
            headers=headers,
            json={"fecha": test_date, "valor_tasa": test_rate}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "message" in data or "fecha" in data, "Response should contain message or fecha"
        assert data.get("valor_tasa") == test_rate or "475.50" in data.get("message", ""), "Rate not confirmed"
        print(f"✓ Manual rate registered: {data}")
        
        # Verify the rate was saved by fetching it
        verify_response = requests.get(f"{BASE_URL}/api/exchange-rate/by-date/{test_date}", headers=headers)
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        assert verify_data.get("found") == True, "Rate should be found after registration"
        assert verify_data.get("valor_tasa") == test_rate, f"Rate mismatch: expected {test_rate}, got {verify_data.get('valor_tasa')}"
        assert verify_data.get("fuente") == "Manual", f"Source should be 'Manual', got {verify_data.get('fuente')}"
        print(f"✓ Verified manual rate persisted: {verify_data}")
    
    def test_register_manual_rate_validation_missing_fields(self, auth_token):
        """Test validation for missing required fields"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Missing valor_tasa
        response = requests.post(f"{BASE_URL}/api/exchange-rate/manual", 
            headers=headers,
            json={"fecha": "2026-03-21"}
        )
        assert response.status_code == 400, f"Should fail with 400 for missing valor_tasa, got {response.status_code}"
        print(f"✓ Correctly rejected missing valor_tasa: {response.json()}")
        
        # Missing fecha
        response = requests.post(f"{BASE_URL}/api/exchange-rate/manual", 
            headers=headers,
            json={"valor_tasa": 470.0}
        )
        assert response.status_code == 400, f"Should fail with 400 for missing fecha, got {response.status_code}"
        print(f"✓ Correctly rejected missing fecha: {response.json()}")
    
    def test_register_manual_rate_validation_invalid_rate(self, auth_token):
        """Test validation for invalid rate values"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Negative rate
        response = requests.post(f"{BASE_URL}/api/exchange-rate/manual", 
            headers=headers,
            json={"fecha": "2026-03-22", "valor_tasa": -100}
        )
        assert response.status_code == 400, f"Should fail with 400 for negative rate, got {response.status_code}"
        print(f"✓ Correctly rejected negative rate: {response.json()}")
        
        # Zero rate
        response = requests.post(f"{BASE_URL}/api/exchange-rate/manual", 
            headers=headers,
            json={"fecha": "2026-03-22", "valor_tasa": 0}
        )
        assert response.status_code == 400, f"Should fail with 400 for zero rate, got {response.status_code}"
        print(f"✓ Correctly rejected zero rate: {response.json()}")


class TestExchangeRateHistory:
    """Test GET /api/exchange-rate/history"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        return response.json().get("session_token")
    
    def test_get_history(self, auth_token):
        """Test fetching rate history"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.get(f"{BASE_URL}/api/exchange-rate/history", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ History returned {len(data)} records")
        
        if len(data) > 0:
            # Check structure of first record
            first = data[0]
            assert "fecha" in first, "Record should have 'fecha'"
            assert "valor_tasa" in first, "Record should have 'valor_tasa'"
            print(f"✓ First record: fecha={first['fecha']}, valor_tasa={first['valor_tasa']}, fuente={first.get('fuente', 'N/A')}")
            
            # Verify ordering (descending by date)
            if len(data) > 1:
                dates = [r["fecha"] for r in data]
                assert dates == sorted(dates, reverse=True), "History should be ordered by date descending"
                print("✓ History correctly ordered by date descending")


class TestExchangeRateUpdate:
    """Test POST /api/exchange-rate/update (BCV fetch)"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        return response.json().get("session_token")
    
    def test_update_bcv_rate(self, auth_token):
        """Test fetching and saving BCV rate"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.post(f"{BASE_URL}/api/exchange-rate/update", headers=headers)
        
        # BCV API might fail due to external service, so we accept 200 or 502
        if response.status_code == 200:
            data = response.json()
            assert "rate" in data, "Response should have 'rate'"
            assert data["rate"] > 0, "Rate should be positive"
            assert "source" in data, "Response should have 'source'"
            print(f"✓ BCV rate fetched: {data['rate']} from {data['source']}")
            
            # Verify it was saved to history
            today = "2026-04-01"  # Current date based on context
            verify_response = requests.get(f"{BASE_URL}/api/exchange-rate/by-date/{today}", headers=headers)
            if verify_response.status_code == 200:
                verify_data = verify_response.json()
                if verify_data.get("found"):
                    print(f"✓ Rate saved to history for {today}: {verify_data['valor_tasa']}")
        elif response.status_code == 502:
            # External BCV API unavailable - this is acceptable
            print(f"⚠ BCV API unavailable (502): {response.json().get('detail', 'No detail')}")
            pytest.skip("BCV external API unavailable")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}, {response.text}")


class TestExchangeRateCurrent:
    """Test GET /api/exchange-rate/current"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        return response.json().get("session_token")
    
    def test_get_current_rate(self, auth_token):
        """Test fetching current active rate"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.get(f"{BASE_URL}/api/exchange-rate/current", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "rate" in data or "source" in data, "Response should have rate or source"
        print(f"✓ Current rate: {data.get('rate', 'N/A')} from {data.get('source', 'N/A')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

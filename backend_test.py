#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class PagoFlowAPITester:
    def __init__(self, base_url="https://dept-migration-bug.preview.emergentagent.com"):
        self.base_url = base_url
        self.session_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.created_resources = {
            'clients': [],
            'banks': [],
            'hardware': [],
            'services': [],
            'quotes': []
        }

    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, test_auth=True):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if test_auth and self.session_token:
            headers['Authorization'] = f'Bearer {self.session_token}'

        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json() if response.content else {}
                except:
                    return True, {}
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
                try:
                    error_details = response.json()
                    self.log(f"   Error details: {error_details}")
                except:
                    self.log(f"   Response text: {response.text[:200]}")
                return False, {}

        except requests.exceptions.Timeout:
            self.log(f"❌ {name} - Request timeout (30s)")
            return False, {}
        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}")
            return False, {}

    def test_auth_mock_session(self):
        """Test mock authentication (since Emergent OAuth requires browser flow)"""
        self.log("\n=== TESTING AUTHENTICATION ===")
        
        # For testing purposes, we'll create a mock session
        # In real scenario, this would be handled by Emergent OAuth flow
        mock_session_data = {
            'X-Session-ID': 'test-session-12345'
        }
        
        success, response = self.run_test(
            "Mock Session Creation",
            "POST",
            "auth/session",
            200,
            test_auth=False
        )
        
        if success and 'session_token' in response:
            self.session_token = response['session_token']
            self.log(f"✅ Mock session token obtained: {self.session_token[:20]}...")
            return True
        
        self.log("❌ Authentication failed - using mock token for testing")
        # Set a mock token to continue testing
        self.session_token = "mock-token-for-testing"
        return False

    def test_exchange_rate(self):
        """Test BCV exchange rate endpoints"""
        self.log("\n=== TESTING EXCHANGE RATE ===")
        
        # Test get current rate
        success, response = self.run_test(
            "Get Current Exchange Rate",
            "GET",
            "exchange-rate/current",
            200
        )
        
        current_rate = None
        if success and 'rate' in response:
            current_rate = response['rate']
            self.log(f"   Current BCV rate: {current_rate} Bs/USD")
        
        # Test update rate
        success, response = self.run_test(
            "Update Exchange Rate",
            "POST",
            "exchange-rate/update",
            200
        )
        
        if success and 'rate' in response:
            new_rate = response['rate']
            self.log(f"   Updated BCV rate: {new_rate} Bs/USD")

    def test_clients_crud(self):
        """Test complete CRUD operations for clients"""
        self.log("\n=== TESTING CLIENTS CRUD ===")
        
        # Create client
        client_data = {
            "rif": "J-40123456-7",
            "legal_name": "Test Company Legal C.A.",
            "fantasy_name": "Test Company",
            "contact1": {
                "name": "Juan Pérez",
                "phone": "+58-212-1234567",
                "email": "juan.perez@testcompany.com"
            },
            "contact2": {
                "name": "María González",
                "phone": "+58-212-7654321", 
                "email": "maria.gonzalez@testcompany.com"
            }
        }
        
        success, response = self.run_test(
            "Create Client",
            "POST",
            "clients",
            201,
            client_data
        )
        
        client_id = None
        if success and 'client_id' in response:
            client_id = response['client_id']
            self.created_resources['clients'].append(client_id)
            self.log(f"   Created client ID: {client_id}")
        
        # Get all clients
        success, response = self.run_test(
            "Get All Clients",
            "GET",
            "clients",
            200
        )
        
        if success:
            self.log(f"   Retrieved {len(response)} clients")
        
        # Get specific client
        if client_id:
            success, response = self.run_test(
                "Get Client by ID",
                "GET",
                f"clients/{client_id}",
                200
            )
        
        # Update client
        if client_id:
            update_data = client_data.copy()
            update_data['fantasy_name'] = "Updated Test Company"
            
            success, response = self.run_test(
                "Update Client",
                "PUT",
                f"clients/{client_id}",
                200,
                update_data
            )

    def test_banks_crud(self):
        """Test complete CRUD operations for banks"""
        self.log("\n=== TESTING BANKS CRUD ===")
        
        # Create bank
        bank_data = {
            "name": "Banco Test Venezuela",
            "type": "Banco",
            "country": "Venezuela",
            "products": [
                {
                    "product_name": "Punto de Venta",
                    "description": "Terminal POS para pagos con tarjetas"
                },
                {
                    "product_name": "Transferencias",
                    "description": "Sistema de transferencias bancarias"
                }
            ]
        }
        
        success, response = self.run_test(
            "Create Bank",
            "POST",
            "banks",
            201,
            bank_data
        )
        
        bank_id = None
        if success and 'bank_id' in response:
            bank_id = response['bank_id']
            self.created_resources['banks'].append(bank_id)
            self.log(f"   Created bank ID: {bank_id}")
        
        # Get all banks
        success, response = self.run_test(
            "Get All Banks",
            "GET",
            "banks",
            200
        )
        
        if success:
            self.log(f"   Retrieved {len(response)} banks")
        
        # Update bank
        if bank_id:
            update_data = bank_data.copy()
            update_data['name'] = "Updated Banco Test Venezuela"
            
            success, response = self.run_test(
                "Update Bank",
                "PUT",
                f"banks/{bank_id}",
                200,
                update_data
            )

    def test_hardware_crud(self):
        """Test complete CRUD operations for hardware"""
        self.log("\n=== TESTING HARDWARE CRUD ===")
        
        # Create hardware
        hardware_data = {
            "name": "Pinpad Ingenico Move/5000",
            "type": "Pinpad",
            "price_usd": 150.00,
            "price_bs_usd": 165.00,
            "description": "Terminal móvil para pagos contactless"
        }
        
        success, response = self.run_test(
            "Create Hardware",
            "POST",
            "hardware",
            201,
            hardware_data
        )
        
        hardware_id = None
        if success and 'hardware_id' in response:
            hardware_id = response['hardware_id']
            self.created_resources['hardware'].append(hardware_id)
            self.log(f"   Created hardware ID: {hardware_id}")
        
        # Get all hardware
        success, response = self.run_test(
            "Get All Hardware",
            "GET",
            "hardware",
            200
        )
        
        if success:
            self.log(f"   Retrieved {len(response)} hardware items")
        
        # Update hardware
        if hardware_id:
            update_data = hardware_data.copy()
            update_data['price_usd'] = 155.00
            
            success, response = self.run_test(
                "Update Hardware",
                "PUT",
                f"hardware/{hardware_id}",
                200,
                update_data
            )

    def test_services_crud(self):
        """Test complete CRUD operations for services"""
        self.log("\n=== TESTING SERVICES CRUD ===")
        
        # Create service
        service_data = {
            "category": "Suscripciones y Configuración",
            "name": "Configuración Inicial POS",
            "setup_cost": 50.00,
            "monthly_cost": 15.00,
            "description": "Setup inicial del sistema POS"
        }
        
        success, response = self.run_test(
            "Create Service",
            "POST",
            "services",
            201,
            service_data
        )
        
        service_id = None
        if success and 'service_id' in response:
            service_id = response['service_id']
            self.created_resources['services'].append(service_id)
            self.log(f"   Created service ID: {service_id}")
        
        # Get all services
        success, response = self.run_test(
            "Get All Services",
            "GET",
            "services",
            200
        )
        
        if success:
            self.log(f"   Retrieved {len(response)} services")
        
        # Update service
        if service_id:
            update_data = service_data.copy()
            update_data['monthly_cost'] = 18.00
            
            success, response = self.run_test(
                "Update Service",
                "PUT",
                f"services/{service_id}",
                200,
                update_data
            )

    def test_quotes_workflow(self):
        """Test complete quotes workflow including PDF generation"""
        self.log("\n=== TESTING QUOTES WORKFLOW ===")
        
        # Ensure we have required data
        if not self.created_resources['clients']:
            self.log("❌ No clients available for quote testing")
            return
        
        client_id = self.created_resources['clients'][0]
        
        # Create quote with services and hardware
        quote_data = {
            "client_id": client_id,
            "services": [
                {
                    "item_type": "service",
                    "item_id": self.created_resources['services'][0] if self.created_resources['services'] else "srv_test123",
                    "item_name": "Configuración Inicial POS",
                    "quantity": 1,
                    "unit_price_usd": 65.00,
                    "total_usd": 65.00
                }
            ],
            "hardware": [
                {
                    "item_type": "hardware", 
                    "item_id": self.created_resources['hardware'][0] if self.created_resources['hardware'] else "hwr_test123",
                    "item_name": "Pinpad Ingenico",
                    "quantity": 2,
                    "unit_price_usd": 150.00,
                    "total_usd": 300.00
                }
            ],
            "notes": "Cotización de prueba para cliente test"
        }
        
        success, response = self.run_test(
            "Create Quote",
            "POST",
            "quotes",
            201,
            quote_data
        )
        
        quote_id = None
        if success and 'quote_id' in response:
            quote_id = response['quote_id']
            self.created_resources['quotes'].append(quote_id)
            self.log(f"   Created quote ID: {quote_id}")
            self.log(f"   Quote number: {response.get('quote_number', 'N/A')}")
            self.log(f"   Total USD: ${response.get('total_usd', 0):.2f}")
            self.log(f"   Total Bs: {response.get('total_bs', 0):.2f}")
        
        # Get all quotes
        success, response = self.run_test(
            "Get All Quotes",
            "GET", 
            "quotes",
            200
        )
        
        if success:
            self.log(f"   Retrieved {len(response)} quotes")
        
        # Get specific quote
        if quote_id:
            success, response = self.run_test(
                "Get Quote by ID",
                "GET",
                f"quotes/{quote_id}",
                200
            )
        
        # Test PDF generation
        if quote_id:
            success, response = self.run_test(
                "Generate Quote PDF",
                "GET",
                f"quotes/{quote_id}/pdf",
                200
            )
            
            if success:
                self.log("   ✅ PDF generation successful")

    def cleanup_resources(self):
        """Clean up created test resources"""
        self.log("\n=== CLEANING UP TEST RESOURCES ===")
        
        # Delete quotes
        for quote_id in self.created_resources['quotes']:
            # Note: Delete endpoint might not exist, skip for now
            pass
        
        # Delete clients
        for client_id in self.created_resources['clients']:
            success, _ = self.run_test(
                f"Delete Client {client_id}",
                "DELETE",
                f"clients/{client_id}",
                200
            )
        
        # Delete banks
        for bank_id in self.created_resources['banks']:
            success, _ = self.run_test(
                f"Delete Bank {bank_id}",
                "DELETE",
                f"banks/{bank_id}",
                200
            )
        
        # Delete hardware
        for hardware_id in self.created_resources['hardware']:
            success, _ = self.run_test(
                f"Delete Hardware {hardware_id}",
                "DELETE",
                f"hardware/{hardware_id}",
                200
            )
        
        # Delete services
        for service_id in self.created_resources['services']:
            success, _ = self.run_test(
                f"Delete Service {service_id}",
                "DELETE",
                f"services/{service_id}",
                200
            )

    def run_all_tests(self):
        """Run complete test suite"""
        self.log("🚀 Starting PagoFlow API Test Suite")
        self.log(f"🌐 Testing against: {self.base_url}")
        
        start_time = datetime.now()
        
        try:
            # Test authentication (mock for now)
            self.test_auth_mock_session()
            
            # Test exchange rate functionality
            self.test_exchange_rate()
            
            # Test CRUD operations
            self.test_clients_crud()
            self.test_banks_crud() 
            self.test_hardware_crud()
            self.test_services_crud()
            
            # Test quotes workflow
            self.test_quotes_workflow()
            
            # Cleanup
            self.cleanup_resources()
            
        except KeyboardInterrupt:
            self.log("\n⚠️  Tests interrupted by user")
        except Exception as e:
            self.log(f"\n💥 Unexpected error: {str(e)}")
        
        finally:
            end_time = datetime.now()
            duration = end_time - start_time
            
            self.log(f"\n📊 TEST SUMMARY")
            self.log(f"   Tests Run: {self.tests_run}")
            self.log(f"   Tests Passed: {self.tests_passed}")
            self.log(f"   Tests Failed: {self.tests_run - self.tests_passed}")
            self.log(f"   Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%" if self.tests_run > 0 else "   Success Rate: 0%")
            self.log(f"   Duration: {duration.total_seconds():.1f} seconds")
            
            if self.tests_passed == self.tests_run:
                self.log("🎉 ALL TESTS PASSED!")
                return 0
            else:
                self.log("❌ SOME TESTS FAILED")
                return 1

def main():
    tester = PagoFlowAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())
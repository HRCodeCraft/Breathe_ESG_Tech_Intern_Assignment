"""
Management command: seed emission factors, unit conversions, airport codes,
and create a demo organization + analyst user.

Run: python manage.py seed_reference_data
"""

import csv
import json
import os
from decimal import Decimal
from datetime import date
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.emissions.models import EmissionFactor, UnitConversion, AirportCode
from apps.organizations.models import Organization, User


EMISSION_FACTORS = [
    # Scope 1 — Stationary Combustion (DEFRA 2024, kgCO2e per litre unless noted)
    {'category': 'stationary_combustion', 'subcategory': 'diesel', 'fuel_type': 'diesel',
     'unit': 'litre', 'co2e': '2.53900', 'co2': '2.51636', 'ch4': '0.00109', 'n2o': '0.02155',
     'source': 'DEFRA_2024'},
    {'category': 'stationary_combustion', 'subcategory': 'petrol', 'fuel_type': 'petrol',
     'unit': 'litre', 'co2e': '2.19780', 'co2': '2.17420', 'ch4': '0.00081', 'n2o': '0.02279',
     'source': 'DEFRA_2024'},
    {'category': 'stationary_combustion', 'subcategory': 'natural_gas', 'fuel_type': 'natural_gas',
     'unit': 'kwh', 'co2e': '0.20200', 'co2': '0.18254', 'ch4': '0.00378', 'n2o': '0.00368',
     'source': 'DEFRA_2024'},
    {'category': 'stationary_combustion', 'subcategory': 'lpg', 'fuel_type': 'lpg',
     'unit': 'litre', 'co2e': '1.55500', 'co2': '1.54924', 'ch4': '0.00030', 'n2o': '0.00546',
     'source': 'DEFRA_2024'},
    {'category': 'stationary_combustion', 'subcategory': 'heating_oil', 'fuel_type': 'heating_oil',
     'unit': 'litre', 'co2e': '2.51574', 'co2': '2.49311', 'ch4': '0.00093', 'n2o': '0.02170',
     'source': 'DEFRA_2024'},
    {'category': 'stationary_combustion', 'subcategory': 'fuel_oil', 'fuel_type': 'fuel_oil',
     'unit': 'litre', 'co2e': '3.14930', 'co2': '3.11974', 'ch4': '0.00096', 'n2o': '0.02860',
     'source': 'DEFRA_2024'},
    {'category': 'stationary_combustion', 'subcategory': 'kerosene', 'fuel_type': 'kerosene',
     'unit': 'litre', 'co2e': '2.54164', 'co2': '2.51898', 'ch4': '0.00093', 'n2o': '0.02173',
     'source': 'DEFRA_2024'},
    # Scope 1 — Mobile Combustion
    {'category': 'mobile_combustion', 'subcategory': 'diesel', 'fuel_type': 'diesel',
     'unit': 'litre', 'co2e': '2.53900', 'co2': '2.51636', 'ch4': '0.00109', 'n2o': '0.02155',
     'source': 'DEFRA_2024'},
    {'category': 'mobile_combustion', 'subcategory': 'petrol', 'fuel_type': 'petrol',
     'unit': 'litre', 'co2e': '2.19780', 'co2': '2.17420', 'ch4': '0.00081', 'n2o': '0.02279',
     'source': 'DEFRA_2024'},
    # Scope 2 — Purchased Electricity (UK grid average, DEFRA 2024)
    {'category': 'purchased_electricity', 'subcategory': 'grid_electricity', 'fuel_type': '',
     'unit': 'kwh', 'co2e': '0.20705', 'co2': '0.19338', 'ch4': '0.00339', 'n2o': '0.00028',
     'source': 'DEFRA_2024'},
    # Scope 3 — Business Travel Flights (per km, DEFRA 2024, includes RFI)
    {'category': 'business_travel_air', 'subcategory': 'economy', 'fuel_type': '',
     'unit': 'km', 'co2e': '0.18861', 'co2': '0.15296', 'ch4': '0.00001', 'n2o': '0.00090',
     'source': 'DEFRA_2024'},
    {'category': 'business_travel_air', 'subcategory': 'premium economy', 'fuel_type': '',
     'unit': 'km', 'co2e': '0.23752', 'co2': '0.19253', 'ch4': '0.00001', 'n2o': '0.00113',
     'source': 'DEFRA_2024'},
    {'category': 'business_travel_air', 'subcategory': 'business', 'fuel_type': '',
     'unit': 'km', 'co2e': '0.45268', 'co2': '0.36711', 'ch4': '0.00002', 'n2o': '0.00215',
     'source': 'DEFRA_2024'},
    {'category': 'business_travel_air', 'subcategory': 'business class', 'fuel_type': '',
     'unit': 'km', 'co2e': '0.45268', 'co2': '0.36711', 'ch4': '0.00002', 'n2o': '0.00215',
     'source': 'DEFRA_2024'},
    {'category': 'business_travel_air', 'subcategory': 'first', 'fuel_type': '',
     'unit': 'km', 'co2e': '0.45268', 'co2': '0.36711', 'ch4': '0.00002', 'n2o': '0.00215',
     'source': 'DEFRA_2024'},
    # Hotels
    {'category': 'business_travel_hotel', 'subcategory': 'hotel_stay', 'fuel_type': '',
     'unit': 'nights', 'co2e': '16.10', 'co2': '15.80', 'ch4': '0.10', 'n2o': '0.20',
     'source': 'DEFRA_2024'},
    # Ground transport
    {'category': 'business_travel_ground', 'subcategory': 'car', 'fuel_type': '',
     'unit': 'km', 'co2e': '0.14549', 'co2': '0.14412', 'ch4': '0.00016', 'n2o': '0.00121',
     'source': 'DEFRA_2024'},
    {'category': 'business_travel_ground', 'subcategory': 'taxi', 'fuel_type': '',
     'unit': 'km', 'co2e': '0.14931', 'co2': '0.14788', 'ch4': '0.00016', 'n2o': '0.00127',
     'source': 'DEFRA_2024'},
    {'category': 'business_travel_ground', 'subcategory': 'trn', 'fuel_type': '',
     'unit': 'km', 'co2e': '0.03549', 'co2': '0.03281', 'ch4': '0.00018', 'n2o': '0.00250',
     'source': 'DEFRA_2024'},
    {'category': 'business_travel_ground', 'subcategory': 'train', 'fuel_type': '',
     'unit': 'km', 'co2e': '0.03549', 'co2': '0.03281', 'ch4': '0.00018', 'n2o': '0.00250',
     'source': 'DEFRA_2024'},
    {'category': 'business_travel_ground', 'subcategory': 'lim', 'fuel_type': '',
     'unit': 'km', 'co2e': '0.14931', 'co2': '0.14788', 'ch4': '0.00016', 'n2o': '0.00127',
     'source': 'DEFRA_2024'},
]

UNIT_CONVERSIONS = [
    ('gallon_us', 'litre', '3.78541', 'US liquid gallon'),
    ('gallon_uk', 'litre', '4.54609', 'Imperial gallon'),
    ('gal', 'litre', '3.78541', 'US gallon alias'),
    ('gl', 'litre', '3.78541', 'SAP GL unit code'),
    ('m3', 'litre', '1000', 'Cubic metres to litres'),
    ('nm3', 'kwh', '10.55', 'Normal cubic metres of natural gas (average calorific value)'),
    ('g', 'kg', '0.001', 'Grams to kg'),
    ('tonne', 'kg', '1000', 'Metric tonne to kg'),
    ('t', 'kg', '1000', 'Metric tonne alias'),
    ('lb', 'kg', '0.453592', 'Pounds to kg'),
    ('lbs', 'kg', '0.453592', 'Pounds plural alias'),
    ('mj', 'kwh', '0.277778', 'Megajoules to kWh'),
    ('gj', 'kwh', '277.778', 'Gigajoules to kWh'),
    ('mwh', 'kwh', '1000', 'MWh to kWh'),
    ('therm', 'kwh', '29.3001', 'Therms to kWh (US)'),
    ('therms', 'kwh', '29.3001', 'Therms plural'),
    ('mmbtu', 'kwh', '293.071', 'MMBtu to kWh'),
    ('btu', 'kwh', '0.000293071', 'BTU to kWh'),
    ('mile', 'km', '1.60934', 'Statute miles to km'),
    ('miles', 'km', '1.60934', 'Miles plural'),
    ('mi', 'km', '1.60934', 'Miles abbreviation'),
]

# Key airports for the sample data
AIRPORTS = [
    ('LHR', 'London Heathrow', 'London', 'GB', 51.477500, -0.461389),
    ('JFK', 'John F. Kennedy International', 'New York', 'US', 40.639722, -73.778889),
    ('CDG', 'Charles de Gaulle', 'Paris', 'FR', 49.009722, 2.547778),
    ('FRA', 'Frankfurt Airport', 'Frankfurt', 'DE', 50.033333, 8.570556),
    ('AMS', 'Amsterdam Schiphol', 'Amsterdam', 'NL', 52.308056, 4.764167),
    ('SIN', 'Singapore Changi', 'Singapore', 'SG', 1.359167, 103.989444),
    ('DXB', 'Dubai International', 'Dubai', 'AE', 25.252778, 55.364444),
    ('ORD', "Chicago O'Hare International", 'Chicago', 'US', 41.978603, -87.904842),
    ('LAX', 'Los Angeles International', 'Los Angeles', 'US', 33.942536, -118.408075),
    ('BOS', 'Logan International', 'Boston', 'US', 42.364347, -71.005181),
    ('SFO', 'San Francisco International', 'San Francisco', 'US', 37.618972, -122.374889),
    ('NRT', 'Narita International', 'Tokyo', 'JP', 35.764722, 140.386389),
    ('HKG', 'Hong Kong International', 'Hong Kong', 'HK', 22.308889, 113.914722),
    ('SYD', 'Sydney Kingsford Smith', 'Sydney', 'AU', -33.946111, 151.177222),
    ('MUC', 'Munich Airport', 'Munich', 'DE', 48.353889, 11.786111),
    ('MAD', 'Adolfo Suárez Madrid-Barajas', 'Madrid', 'ES', 40.471926, -3.56264),
    ('MAN', 'Manchester Airport', 'Manchester', 'GB', 53.353611, -2.275),
    ('BHX', 'Birmingham Airport', 'Birmingham', 'GB', 52.453889, -1.748056),
    ('EDI', 'Edinburgh Airport', 'Edinburgh', 'GB', 55.95, -3.3725),
    ('DUB', 'Dublin Airport', 'Dublin', 'IE', 53.421333, -6.270075),
    ('ZRH', 'Zurich Airport', 'Zurich', 'CH', 47.464722, 8.549167),
    ('BRU', 'Brussels Airport', 'Brussels', 'BE', 50.901389, 4.484444),
    ('MXP', 'Milan Malpensa', 'Milan', 'IT', 45.630556, 8.728056),
    ('BCN', 'Barcelona El Prat', 'Barcelona', 'ES', 41.297076, 2.078463),
    ('CPH', 'Copenhagen Airport', 'Copenhagen', 'DK', 55.617917, 12.655972),
    ('HEL', 'Helsinki-Vantaa Airport', 'Helsinki', 'FI', 60.317222, 24.963333),
    ('OSL', 'Oslo Gardermoen', 'Oslo', 'NO', 60.193917, 11.100361),
    ('WAW', 'Warsaw Chopin Airport', 'Warsaw', 'PL', 52.165833, 20.967222),
    ('PRG', 'Václav Havel Airport Prague', 'Prague', 'CZ', 50.100833, 14.26),
    ('BUD', 'Budapest Ferenc Liszt', 'Budapest', 'HU', 47.436667, 19.255556),
]


class Command(BaseCommand):
    help = 'Seed reference data: emission factors, unit conversions, airports, demo org'

    def handle(self, *args, **options):
        self.stdout.write('Seeding emission factors...')
        for ef_data in EMISSION_FACTORS:
            EmissionFactor.objects.update_or_create(
                category=ef_data['category'],
                subcategory=ef_data['subcategory'],
                unit=ef_data['unit'],
                factor_source=ef_data['source'],
                defaults={
                    'fuel_type': ef_data.get('fuel_type', ''),
                    'co2e_per_unit': Decimal(ef_data['co2e']),
                    'co2_per_unit': Decimal(ef_data['co2']),
                    'ch4_per_unit': Decimal(ef_data['ch4']),
                    'n2o_per_unit': Decimal(ef_data['n2o']),
                    'valid_from': date(2024, 1, 1),
                }
            )
        self.stdout.write(self.style.SUCCESS(f'  ✓ {len(EMISSION_FACTORS)} emission factors'))

        self.stdout.write('Seeding unit conversions...')
        for from_u, to_u, mult, notes in UNIT_CONVERSIONS:
            UnitConversion.objects.update_or_create(
                from_unit=from_u,
                defaults={'to_unit': to_u, 'multiplier': Decimal(mult), 'notes': notes}
            )
        self.stdout.write(self.style.SUCCESS(f'  ✓ {len(UNIT_CONVERSIONS)} unit conversions'))

        self.stdout.write('Seeding airport codes...')
        for iata, name, city, country, lat, lon in AIRPORTS:
            AirportCode.objects.update_or_create(
                iata=iata,
                defaults={'name': name, 'city': city, 'country': country,
                          'latitude': lat, 'longitude': lon}
            )
        self.stdout.write(self.style.SUCCESS(f'  ✓ {len(AIRPORTS)} airports'))

        self.stdout.write('Creating demo organization and users...')
        org, _ = Organization.objects.get_or_create(
            slug='acme-corp',
            defaults={
                'name': 'ACME Manufacturing Ltd.',
                'industry': 'Manufacturing',
                'reporting_year': 2024,
            }
        )

        # Demo analyst
        analyst, created = User.objects.get_or_create(
            username='analyst',
            defaults={
                'email': 'analyst@acme.example',
                'first_name': 'Alex',
                'last_name': 'Chen',
                'role': User.Role.ANALYST,
                'organization': org,
            }
        )
        if created:
            analyst.set_password('analyst123')
            analyst.save()

        # Demo admin
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@acme.example',
                'first_name': 'Sam',
                'last_name': 'Rivera',
                'role': User.Role.ADMIN,
                'organization': org,
                'is_staff': True,
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()

        self.stdout.write(self.style.SUCCESS(
            f'  ✓ Org: {org.name} | analyst / analyst123 | admin / admin123'
        ))
        self.stdout.write(self.style.SUCCESS('Reference data seeded successfully.'))

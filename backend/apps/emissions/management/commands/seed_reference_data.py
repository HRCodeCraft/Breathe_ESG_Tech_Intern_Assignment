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

# Major airports worldwide — covers ~90% of enterprise business travel routes.
# Source: ourairports.com open dataset (public domain), coordinates verified against
# OAG and IATA reference data. Expanded from initial 30 to 250+ to support
# Haversine distance calculation for Concur rows missing a distance field.
AIRPORTS = [
    # UK & Ireland
    ('LHR', 'London Heathrow', 'London', 'GB', 51.477500, -0.461389),
    ('LGW', 'London Gatwick', 'London', 'GB', 51.148056, -0.190278),
    ('STN', 'London Stansted', 'London', 'GB', 51.885000, 0.235000),
    ('LTN', 'London Luton', 'London', 'GB', 51.874722, -0.368333),
    ('LCY', 'London City Airport', 'London', 'GB', 51.505278, 0.055278),
    ('MAN', 'Manchester Airport', 'Manchester', 'GB', 53.353611, -2.275000),
    ('BHX', 'Birmingham Airport', 'Birmingham', 'GB', 52.453889, -1.748056),
    ('EDI', 'Edinburgh Airport', 'Edinburgh', 'GB', 55.950000, -3.372500),
    ('GLA', 'Glasgow International', 'Glasgow', 'GB', 55.871944, -4.433056),
    ('ABZ', 'Aberdeen Airport', 'Aberdeen', 'GB', 57.201944, -2.197778),
    ('NCL', 'Newcastle Airport', 'Newcastle', 'GB', 55.037222, -1.691667),
    ('BRS', 'Bristol Airport', 'Bristol', 'GB', 51.382498, -2.719089),
    ('BFS', 'Belfast International', 'Belfast', 'GB', 54.657500, -6.215833),
    ('DUB', 'Dublin Airport', 'Dublin', 'IE', 53.421333, -6.270075),
    ('SNN', 'Shannon Airport', 'Shannon', 'IE', 52.701944, -8.924722),
    # Western Europe
    ('CDG', 'Paris Charles de Gaulle', 'Paris', 'FR', 49.009722, 2.547778),
    ('ORY', 'Paris Orly', 'Paris', 'FR', 48.723333, 2.379444),
    ('LYS', 'Lyon Saint-Exupéry', 'Lyon', 'FR', 45.725556, 5.081111),
    ('MRS', 'Marseille Provence', 'Marseille', 'FR', 43.436667, 5.215000),
    ('NCE', 'Nice Côte d\'Azur', 'Nice', 'FR', 43.665278, 7.215000),
    ('TLS', 'Toulouse-Blagnac', 'Toulouse', 'FR', 43.629444, 1.363889),
    ('BOD', 'Bordeaux-Mérignac', 'Bordeaux', 'FR', 44.828333, -0.715556),
    ('NTE', 'Nantes Atlantique', 'Nantes', 'FR', 47.153194, -1.610819),
    ('FRA', 'Frankfurt Airport', 'Frankfurt', 'DE', 50.033333, 8.570556),
    ('MUC', 'Munich Airport', 'Munich', 'DE', 48.353889, 11.786111),
    ('BER', 'Berlin Brandenburg', 'Berlin', 'DE', 52.366667, 13.503333),
    ('HAM', 'Hamburg Airport', 'Hamburg', 'DE', 53.630278, 9.988333),
    ('DUS', 'Düsseldorf Airport', 'Düsseldorf', 'DE', 51.289444, 6.766667),
    ('CGN', 'Cologne Bonn Airport', 'Cologne', 'DE', 50.865833, 7.142778),
    ('STR', 'Stuttgart Airport', 'Stuttgart', 'DE', 48.689944, 9.221964),
    ('NUE', 'Nuremberg Airport', 'Nuremberg', 'DE', 49.498681, 11.078054),
    ('HAJ', 'Hannover Airport', 'Hannover', 'DE', 52.461111, 9.685000),
    ('BRE', 'Bremen Airport', 'Bremen', 'DE', 53.047778, 8.786944),
    ('AMS', 'Amsterdam Schiphol', 'Amsterdam', 'NL', 52.308056, 4.764167),
    ('EIN', 'Eindhoven Airport', 'Eindhoven', 'NL', 51.450139, 5.374528),
    ('BRU', 'Brussels Airport', 'Brussels', 'BE', 50.901389, 4.484444),
    ('CRL', 'Brussels South Charleroi', 'Charleroi', 'BE', 50.459197, 4.453783),
    ('ZRH', 'Zurich Airport', 'Zurich', 'CH', 47.464722, 8.549167),
    ('GVA', 'Geneva Airport', 'Geneva', 'CH', 46.238064, 6.108959),
    ('BSL', 'Basel-Mulhouse-Freiburg', 'Basel', 'CH', 47.589722, 7.529167),
    ('VIE', 'Vienna International', 'Vienna', 'AT', 48.110278, 16.569722),
    ('LIS', 'Lisbon Humberto Delgado', 'Lisbon', 'PT', 38.774167, -9.134167),
    ('OPO', 'Francisco de Sá Carneiro', 'Porto', 'PT', 41.248055, -8.681389),
    ('FAO', 'Faro Airport', 'Faro', 'PT', 37.014408, -7.965912),
    ('MAD', 'Madrid Barajas', 'Madrid', 'ES', 40.471926, -3.562640),
    ('BCN', 'Barcelona El Prat', 'Barcelona', 'ES', 41.297076, 2.078463),
    ('AGP', 'Málaga Airport', 'Málaga', 'ES', 36.674922, -4.499119),
    ('VLC', 'Valencia Airport', 'Valencia', 'ES', 39.489258, -0.481625),
    ('BIO', 'Bilbao Airport', 'Bilbao', 'ES', 43.300986, -2.910608),
    ('SVQ', 'Seville Airport', 'Seville', 'ES', 37.417900, -5.893108),
    ('PMI', 'Palma de Mallorca', 'Palma', 'ES', 39.551667, 2.738889),
    ('TFS', 'Tenerife South', 'Tenerife', 'ES', 28.044500, -16.572500),
    ('LPA', 'Gran Canaria Airport', 'Las Palmas', 'ES', 27.931886, -15.386581),
    ('FCO', 'Rome Fiumicino', 'Rome', 'IT', 41.804444, 12.250833),
    ('CIA', 'Rome Ciampino', 'Rome', 'IT', 41.799361, 12.594886),
    ('MXP', 'Milan Malpensa', 'Milan', 'IT', 45.630556, 8.728056),
    ('LIN', 'Milan Linate', 'Milan', 'IT', 45.445103, 9.276739),
    ('VCE', 'Venice Marco Polo', 'Venice', 'IT', 45.505278, 12.351944),
    ('NAP', 'Naples International', 'Naples', 'IT', 40.886111, 14.290833),
    ('CPH', 'Copenhagen Airport', 'Copenhagen', 'DK', 55.617917, 12.655972),
    ('OSL', 'Oslo Gardermoen', 'Oslo', 'NO', 60.193917, 11.100361),
    ('BGO', 'Bergen Airport Flesland', 'Bergen', 'NO', 60.293611, 5.218056),
    ('HEL', 'Helsinki-Vantaa Airport', 'Helsinki', 'FI', 60.317222, 24.963333),
    ('ARN', 'Stockholm Arlanda', 'Stockholm', 'SE', 59.651944, 17.918611),
    ('GOT', 'Gothenburg Landvetter', 'Gothenburg', 'SE', 57.668889, 12.292222),
    ('ATH', 'Athens Eleftherios Venizelos', 'Athens', 'GR', 37.936389, 23.944444),
    ('SKG', 'Thessaloniki Airport', 'Thessaloniki', 'GR', 40.519722, 22.971111),
    # Eastern Europe
    ('WAW', 'Warsaw Chopin Airport', 'Warsaw', 'PL', 52.165833, 20.967222),
    ('KRK', 'Krakow John Paul II', 'Krakow', 'PL', 50.077781, 19.784836),
    ('WRO', 'Wroclaw Airport', 'Wroclaw', 'PL', 51.102694, 16.885839),
    ('GDN', 'Gdansk Lech Walesa', 'Gdansk', 'PL', 54.377581, 18.466192),
    ('PRG', 'Václav Havel Airport Prague', 'Prague', 'CZ', 50.100833, 14.260000),
    ('BRQ', 'Brno-Tuřany Airport', 'Brno', 'CZ', 49.151269, 16.694433),
    ('BUD', 'Budapest Ferenc Liszt', 'Budapest', 'HU', 47.436667, 19.255556),
    ('OTP', 'Bucharest Henri Coandă', 'Bucharest', 'RO', 44.571111, 26.085000),
    ('SOF', 'Sofia Airport', 'Sofia', 'BG', 42.695000, 23.406389),
    ('BEG', 'Belgrade Nikola Tesla', 'Belgrade', 'RS', 44.818333, 20.309167),
    ('ZAG', 'Zagreb Airport', 'Zagreb', 'HR', 45.742931, 16.068778),
    ('LJU', 'Ljubljana Jože Pučnik', 'Ljubljana', 'SI', 46.223611, 14.457778),
    ('RIX', 'Riga International', 'Riga', 'LV', 56.923611, 23.971111),
    ('TLL', 'Tallinn Airport', 'Tallinn', 'EE', 59.413333, 24.832778),
    ('VNO', 'Vilnius Airport', 'Vilnius', 'LT', 54.634167, 25.285833),
    ('KBP', 'Kyiv Boryspil International', 'Kyiv', 'UA', 50.345000, 30.894722),
    ('LED', 'Saint Petersburg Pulkovo', 'St. Petersburg', 'RU', 59.800278, 30.262500),
    ('SVO', 'Moscow Sheremetyevo', 'Moscow', 'RU', 55.972642, 37.414589),
    ('DME', 'Moscow Domodedovo', 'Moscow', 'RU', 55.408611, 37.906111),
    # North America — United States
    ('JFK', 'John F. Kennedy International', 'New York', 'US', 40.639722, -73.778889),
    ('EWR', 'Newark Liberty International', 'Newark', 'US', 40.692444, -74.168667),
    ('LGA', 'LaGuardia Airport', 'New York', 'US', 40.777245, -73.872608),
    ('BOS', 'Logan International', 'Boston', 'US', 42.364347, -71.005181),
    ('ORD', "Chicago O'Hare International", 'Chicago', 'US', 41.978603, -87.904842),
    ('MDW', 'Chicago Midway International', 'Chicago', 'US', 41.785972, -87.752417),
    ('LAX', 'Los Angeles International', 'Los Angeles', 'US', 33.942536, -118.408075),
    ('SFO', 'San Francisco International', 'San Francisco', 'US', 37.618972, -122.374889),
    ('SJC', 'Norman Y. Mineta San Jose', 'San Jose', 'US', 37.362558, -121.929022),
    ('OAK', 'Oakland International', 'Oakland', 'US', 37.721278, -122.220722),
    ('SEA', 'Seattle-Tacoma International', 'Seattle', 'US', 47.449000, -122.309306),
    ('DEN', 'Denver International', 'Denver', 'US', 39.856093, -104.673756),
    ('ATL', 'Hartsfield-Jackson Atlanta', 'Atlanta', 'US', 33.636719, -84.428067),
    ('DFW', 'Dallas/Fort Worth International', 'Dallas', 'US', 32.896828, -97.037997),
    ('DAL', 'Dallas Love Field', 'Dallas', 'US', 32.847111, -96.851778),
    ('IAH', 'George Bush Intercontinental', 'Houston', 'US', 29.984433, -95.341442),
    ('HOU', 'William P. Hobby Airport', 'Houston', 'US', 29.645419, -95.278889),
    ('MIA', 'Miami International', 'Miami', 'US', 25.795306, -80.287806),
    ('FLL', 'Fort Lauderdale-Hollywood', 'Fort Lauderdale', 'US', 26.072583, -80.152722),
    ('MCO', 'Orlando International', 'Orlando', 'US', 28.429394, -81.309000),
    ('TPA', 'Tampa International', 'Tampa', 'US', 27.975472, -82.532083),
    ('IAD', 'Washington Dulles International', 'Washington DC', 'US', 38.944533, -77.455811),
    ('DCA', 'Ronald Reagan Washington National', 'Washington DC', 'US', 38.852083, -77.037722),
    ('BWI', 'Baltimore/Washington International', 'Baltimore', 'US', 39.175400, -76.668333),
    ('PHL', 'Philadelphia International', 'Philadelphia', 'US', 39.871944, -75.241139),
    ('CLT', 'Charlotte Douglas International', 'Charlotte', 'US', 35.214000, -80.943139),
    ('RDU', 'Raleigh-Durham International', 'Raleigh', 'US', 35.877639, -78.787472),
    ('DTW', 'Detroit Metropolitan Wayne County', 'Detroit', 'US', 42.212444, -83.353389),
    ('MSP', 'Minneapolis-Saint Paul International', 'Minneapolis', 'US', 44.882000, -93.221767),
    ('MKE', 'Milwaukee Mitchell International', 'Milwaukee', 'US', 42.947222, -87.896583),
    ('STL', 'St. Louis Lambert International', 'St. Louis', 'US', 38.748697, -90.370028),
    ('MCI', 'Kansas City International', 'Kansas City', 'US', 39.297600, -94.713889),
    ('LAS', 'Harry Reid International', 'Las Vegas', 'US', 36.080056, -115.152250),
    ('PHX', 'Phoenix Sky Harbor International', 'Phoenix', 'US', 33.434278, -112.011583),
    ('SLC', 'Salt Lake City International', 'Salt Lake City', 'US', 40.788389, -111.977772),
    ('PDX', 'Portland International', 'Portland', 'US', 45.588722, -122.597500),
    ('SAN', 'San Diego International', 'San Diego', 'US', 32.733556, -117.189667),
    ('SMF', 'Sacramento International', 'Sacramento', 'US', 38.695417, -121.590778),
    ('AUS', 'Austin-Bergstrom International', 'Austin', 'US', 30.197535, -97.666081),
    ('BNA', 'Nashville International', 'Nashville', 'US', 36.124472, -86.678194),
    ('MSY', 'Louis Armstrong New Orleans', 'New Orleans', 'US', 29.993389, -90.258028),
    ('MEM', 'Memphis International', 'Memphis', 'US', 35.042417, -89.976667),
    ('PIT', 'Pittsburgh International', 'Pittsburgh', 'US', 40.491467, -80.232872),
    ('CLE', 'Cleveland Hopkins International', 'Cleveland', 'US', 41.411689, -81.849794),
    ('CMH', 'John Glenn Columbus International', 'Columbus', 'US', 39.997972, -82.891889),
    ('IND', 'Indianapolis International', 'Indianapolis', 'US', 39.717331, -86.294383),
    ('HNL', 'Daniel K. Inouye International', 'Honolulu', 'US', 21.318681, -157.922428),
    # North America — Canada
    ('YYZ', 'Toronto Pearson International', 'Toronto', 'CA', 43.677222, -79.630556),
    ('YVR', 'Vancouver International', 'Vancouver', 'CA', 49.193889, -123.184167),
    ('YUL', 'Montréal-Trudeau International', 'Montreal', 'CA', 45.469722, -73.740556),
    ('YYC', 'Calgary International', 'Calgary', 'CA', 51.113889, -114.020278),
    ('YEG', 'Edmonton International', 'Edmonton', 'CA', 53.309723, -113.580278),
    ('YOW', 'Ottawa Macdonald-Cartier', 'Ottawa', 'CA', 45.322500, -75.669167),
    ('YWG', 'Winnipeg James Armstrong Richardson', 'Winnipeg', 'CA', 49.909722, -97.239722),
    ('YHZ', 'Halifax Stanfield International', 'Halifax', 'CA', 44.880833, -63.509167),
    ('YQB', 'Quebec City Jean Lesage', 'Quebec City', 'CA', 46.791111, -71.393056),
    # Middle East
    ('DXB', 'Dubai International', 'Dubai', 'AE', 25.252778, 55.364444),
    ('AUH', 'Abu Dhabi International', 'Abu Dhabi', 'AE', 24.432972, 54.651138),
    ('DWC', 'Al Maktoum International', 'Dubai', 'AE', 24.896356, 55.161389),
    ('DOH', 'Hamad International Airport', 'Doha', 'QA', 25.273056, 51.608056),
    ('BAH', 'Bahrain International', 'Manama', 'BH', 26.270834, 50.633331),
    ('KWI', 'Kuwait International', 'Kuwait City', 'KW', 29.226611, 47.968889),
    ('RUH', 'King Khalid International', 'Riyadh', 'SA', 24.957333, 46.698776),
    ('JED', 'King Abdulaziz International', 'Jeddah', 'SA', 21.679564, 39.156536),
    ('MCT', 'Muscat International', 'Muscat', 'OM', 23.593278, 58.284444),
    ('TLV', 'Ben Gurion International', 'Tel Aviv', 'IL', 32.011389, 34.886667),
    ('AMM', 'Queen Alia International', 'Amman', 'JO', 31.722778, 35.993333),
    ('BEY', 'Rafic Hariri International', 'Beirut', 'LB', 33.820931, 35.488389),
    ('IST', 'Istanbul Airport', 'Istanbul', 'TR', 41.275278, 28.751944),
    ('SAW', 'Istanbul Sabiha Gökçen', 'Istanbul', 'TR', 40.898553, 29.309219),
    ('ESB', 'Esenboğa International', 'Ankara', 'TR', 40.128082, 32.995083),
    # Asia — South Asia
    ('DEL', 'Indira Gandhi International', 'Delhi', 'IN', 28.556534, 77.100956),
    ('BOM', 'Chhatrapati Shivaji Maharaj', 'Mumbai', 'IN', 19.088686, 72.867919),
    ('BLR', 'Kempegowda International', 'Bangalore', 'IN', 13.198889, 77.705556),
    ('MAA', 'Chennai International', 'Chennai', 'IN', 12.990005, 80.169296),
    ('HYD', 'Rajiv Gandhi International', 'Hyderabad', 'IN', 17.231319, 78.429855),
    ('CCU', 'Netaji Subhas Chandra Bose', 'Kolkata', 'IN', 22.654658, 88.446777),
    ('AMD', 'Sardar Vallabhbhai Patel', 'Ahmedabad', 'IN', 23.077242, 72.634690),
    ('PNQ', 'Pune Airport', 'Pune', 'IN', 18.582000, 73.919717),
    ('COK', 'Cochin International', 'Kochi', 'IN', 10.152000, 76.401222),
    ('KHI', 'Jinnah International', 'Karachi', 'PK', 24.906500, 67.160797),
    ('LHE', 'Allama Iqbal International', 'Lahore', 'PK', 31.521564, 74.403594),
    ('ISB', 'Islamabad International', 'Islamabad', 'PK', 33.616722, 73.099167),
    ('CMB', 'Bandaranaike International', 'Colombo', 'LK', 7.180756, 79.884117),
    ('DAC', 'Hazrat Shahjalal International', 'Dhaka', 'BD', 23.843333, 90.397778),
    ('KTM', 'Tribhuvan International', 'Kathmandu', 'NP', 27.696583, 85.359140),
    # Asia — East & Southeast Asia
    ('HKG', 'Hong Kong International', 'Hong Kong', 'HK', 22.308889, 113.914722),
    ('NRT', 'Tokyo Narita International', 'Tokyo', 'JP', 35.764722, 140.386389),
    ('HND', 'Tokyo Haneda International', 'Tokyo', 'JP', 35.549167, 139.779833),
    ('KIX', 'Kansai International', 'Osaka', 'JP', 34.427222, 135.244167),
    ('NGO', 'Chubu Centrair International', 'Nagoya', 'JP', 34.858403, 136.804775),
    ('FUK', 'Fukuoka Airport', 'Fukuoka', 'JP', 33.585942, 130.451011),
    ('CTS', 'New Chitose Airport', 'Sapporo', 'JP', 42.774722, 141.692222),
    ('ICN', 'Incheon International', 'Seoul', 'KR', 37.469075, 126.450517),
    ('GMP', 'Seoul Gimpo International', 'Seoul', 'KR', 37.558333, 126.790556),
    ('PVG', 'Shanghai Pudong International', 'Shanghai', 'CN', 31.143378, 121.805214),
    ('SHA', 'Shanghai Hongqiao International', 'Shanghai', 'CN', 31.197875, 121.336161),
    ('PEK', 'Beijing Capital International', 'Beijing', 'CN', 40.080111, 116.584556),
    ('PKX', 'Beijing Daxing International', 'Beijing', 'CN', 39.509945, 116.410011),
    ('CAN', 'Guangzhou Baiyun International', 'Guangzhou', 'CN', 23.392436, 113.298786),
    ('SZX', 'Shenzhen Bao\'an International', 'Shenzhen', 'CN', 22.639258, 113.810664),
    ('CTU', 'Chengdu Shuangliu International', 'Chengdu', 'CN', 30.578333, 103.946944),
    ('WUH', 'Wuhan Tianhe International', 'Wuhan', 'CN', 30.777778, 114.208333),
    ('XIY', 'Xi\'an Xianyang International', 'Xi\'an', 'CN', 34.447119, 108.751592),
    ('HGH', 'Hangzhou Xiaoshan International', 'Hangzhou', 'CN', 30.229500, 120.434444),
    ('CKG', 'Chongqing Jiangbei International', 'Chongqing', 'CN', 29.719200, 106.641700),
    ('XMN', 'Xiamen Gaoqi International', 'Xiamen', 'CN', 24.544014, 118.127739),
    ('SIN', 'Singapore Changi Airport', 'Singapore', 'SG', 1.359167, 103.989444),
    ('KUL', 'Kuala Lumpur International', 'Kuala Lumpur', 'MY', 2.745578, 101.709917),
    ('BKK', 'Suvarnabhumi Airport', 'Bangkok', 'TH', 13.681108, 100.747283),
    ('DMK', 'Don Mueang International', 'Bangkok', 'TH', 13.912583, 100.606167),
    ('CNX', 'Chiang Mai International', 'Chiang Mai', 'TH', 18.766836, 98.962700),
    ('HAN', 'Noi Bai International', 'Hanoi', 'VN', 21.221192, 105.807178),
    ('SGN', 'Tan Son Nhat International', 'Ho Chi Minh City', 'VN', 10.818797, 106.651856),
    ('DAD', 'Da Nang International', 'Da Nang', 'VN', 16.043917, 108.199661),
    ('CGK', 'Soekarno-Hatta International', 'Jakarta', 'ID', -6.125567, 106.655897),
    ('DPS', 'Ngurah Rai International', 'Bali', 'ID', -8.748169, 115.167197),
    ('MNL', 'Ninoy Aquino International', 'Manila', 'PH', 14.508647, 121.019581),
    ('CEB', 'Mactan-Cebu International', 'Cebu', 'PH', 10.307500, 123.979444),
    ('RGN', 'Yangon International', 'Yangon', 'MM', 16.907278, 96.133222),
    ('REP', 'Siem Reap-Angkor International', 'Siem Reap', 'KH', 13.410666, 103.812817),
    ('MFM', 'Macau International', 'Macau', 'MO', 22.149600, 113.591600),
    ('TPE', 'Taiwan Taoyuan International', 'Taipei', 'TW', 25.077732, 121.232822),
    # Asia-Pacific — Oceania
    ('SYD', 'Sydney Kingsford Smith', 'Sydney', 'AU', -33.946111, 151.177222),
    ('MEL', 'Melbourne Airport', 'Melbourne', 'AU', -37.673333, 144.843333),
    ('BNE', 'Brisbane Airport', 'Brisbane', 'AU', -27.383333, 153.118056),
    ('PER', 'Perth Airport', 'Perth', 'AU', -31.940278, 115.966944),
    ('ADL', 'Adelaide Airport', 'Adelaide', 'AU', -34.945000, 138.530556),
    ('AKL', 'Auckland Airport', 'Auckland', 'NZ', -37.008056, 174.791667),
    ('WLG', 'Wellington Airport', 'Wellington', 'NZ', -41.327222, 174.805000),
    ('CHC', 'Christchurch Airport', 'Christchurch', 'NZ', -43.489722, 172.532222),
    # Africa
    ('JNB', 'O.R. Tambo International', 'Johannesburg', 'ZA', -26.133694, 28.242317),
    ('CPT', 'Cape Town International', 'Cape Town', 'ZA', -33.964806, 18.601667),
    ('DUR', 'King Shaka International', 'Durban', 'ZA', -29.618300, 31.117100),
    ('NBO', 'Jomo Kenyatta International', 'Nairobi', 'KE', -1.319167, 36.927500),
    ('ADD', 'Addis Ababa Bole International', 'Addis Ababa', 'ET', 8.977889, 38.799319),
    ('CAI', 'Cairo International', 'Cairo', 'EG', 30.121944, 31.405556),
    ('LOS', 'Murtala Muhammed International', 'Lagos', 'NG', 6.577222, 3.321111),
    ('ABV', 'Nnamdi Azikiwe International', 'Abuja', 'NG', 9.006792, 7.263172),
    ('ACC', 'Kotoka International', 'Accra', 'GH', 5.605186, -0.166786),
    ('CMN', 'Mohammed V International', 'Casablanca', 'MA', 33.367467, -7.589967),
    ('TUN', 'Tunis-Carthage International', 'Tunis', 'TN', 36.851019, 10.227217),
    ('ALG', 'Houari Boumediene Airport', 'Algiers', 'DZ', 36.691014, 3.215408),
    ('DAR', 'Julius Nyerere International', 'Dar es Salaam', 'TZ', -6.878000, 39.202556),
    ('KGL', 'Kigali International', 'Kigali', 'RW', -1.968636, 30.139444),
    ('EBB', 'Entebbe International', 'Entebbe', 'UG', 0.042386, 32.443161),
    ('MRU', 'Sir Seewoosagur Ramgoolam', 'Mauritius', 'MU', -20.430200, 57.683600),
    # Latin America
    ('GRU', 'São Paulo/Guarulhos International', 'São Paulo', 'BR', -23.432000, -46.469722),
    ('CGH', 'São Paulo/Congonhas Airport', 'São Paulo', 'BR', -23.626690, -46.655536),
    ('GIG', 'Rio de Janeiro/Galeão International', 'Rio de Janeiro', 'BR', -22.809917, -43.250556),
    ('SDU', 'Rio de Janeiro/Santos Dumont', 'Rio de Janeiro', 'BR', -22.910464, -43.163133),
    ('BSB', 'Brasília International', 'Brasília', 'BR', -15.871111, -47.917222),
    ('CNF', 'Belo Horizonte/Confins International', 'Belo Horizonte', 'BR', -19.633611, -43.971944),
    ('SSA', 'Deputado Luís Eduardo Magalhães', 'Salvador', 'BR', -12.908611, -38.322500),
    ('REC', 'Recife/Guararapes International', 'Recife', 'BR', -8.125944, -34.923167),
    ('EZE', 'Ministro Pistarini International', 'Buenos Aires', 'AR', -34.822222, -58.535833),
    ('AEP', 'Jorge Newbery Airfield', 'Buenos Aires', 'AR', -34.559167, -58.415556),
    ('SCL', 'Arturo Merino Benítez International', 'Santiago', 'CL', -33.393000, -70.785889),
    ('LIM', 'Jorge Chávez International', 'Lima', 'PE', -12.021889, -77.114319),
    ('BOG', 'El Dorado International', 'Bogotá', 'CO', 4.701594, -74.146942),
    ('MDE', 'José María Córdova International', 'Medellín', 'CO', 6.164000, -75.423111),
    ('UIO', 'Mariscal Sucre International', 'Quito', 'EC', -0.129167, -78.357500),
    ('GYE', 'José Joaquín de Olmedo International', 'Guayaquil', 'EC', -2.157333, -79.883667),
    ('PTY', 'Tocumen International', 'Panama City', 'PA', 9.071300, -79.383453),
    ('MEX', 'Mexico City International', 'Mexico City', 'MX', 19.436303, -99.072097),
    ('CUN', 'Cancún International', 'Cancún', 'MX', 21.036528, -86.876786),
    ('GDL', 'Miguel Hidalgo y Costilla', 'Guadalajara', 'MX', 20.521760, -103.310485),
    ('MTY', 'General Mariano Escobedo', 'Monterrey', 'MX', 25.778450, -100.107067),
    ('HAV', 'José Martí International', 'Havana', 'CU', 22.989153, -82.409086),
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

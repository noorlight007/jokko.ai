"""
Location Management System - CRUD operations for Country and City models
"""
from db_country import Country
from db_city import City
from db_airport import Airport
from db_gp_routes import GpRoutes
from db_user import User
from datetime import datetime, timezone
from typing import Optional, List, Tuple


def utcnow():
    # Mongo stores datetimes as UTC; keep your app consistent.
    # Use aware UTC datetime; MongoEngine/PyMongo will store it in UTC.
    return datetime.now(timezone.utc)


# ==================== COUNTRY OPERATIONS ====================

def create_country(name: str) -> Optional[Country]:
    """
    1. Create new Country
    
    Args:
        name: Name of the country
    
    Returns:
        Country object if successful, None otherwise
    """
    try:
        # Check if country already exists
        existing = Country.objects(name=name).first()
        if existing:
            print(f"❌ Country '{name}' already exists with ID: {existing.id}")
            return None
        
        country = Country(
            name=name,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        country.save()
        print(f"✅ Created country: {country.name} (ID: {country.id})")
        return country
    except Exception as e:
        print(f"❌ Error creating country: {e}")
        return None


def update_country(country_id: Optional[int] = None, country_name: Optional[str] = None, 
                   new_name: str = None) -> Optional[Country]:
    """
    2. Update a country
    
    Args:
        country_id: ID of the country to update
        country_name: Name of the country to update (alternative to ID)
        new_name: New name for the country
    
    Returns:
        Updated Country object if successful, None otherwise
    """
    try:
        # Find country by ID or name
        if country_id:
            country = Country.objects(id=country_id).first()
        elif country_name:
            country = Country.objects(name=country_name).first()
        else:
            print("❌ Please provide either country_id or country_name")
            return None
        
        if not country:
            print(f"❌ Country not found")
            return None
        
        old_name = country.name
        country.name = new_name
        country.updated_at = datetime.utcnow()
        country.save()
        print(f"✅ Updated country: '{old_name}' → '{country.name}'")
        return country
    except Exception as e:
        print(f"❌ Error updating country: {e}")
        return None


def delete_country(country_id: Optional[int] = None, country_name: Optional[str] = None) -> bool:
    """
    3. Delete a Country (will cascade delete all cities in that country)
    
    Args:
        country_id: ID of the country to delete
        country_name: Name of the country to delete (alternative to ID)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Find country by ID or name
        if country_id:
            country = Country.objects(id=country_id).first()
        elif country_name:
            country = Country.objects(name=country_name).first()
        else:
            print("❌ Please provide either country_id or country_name")
            return False
        
        if not country:
            print(f"❌ Country not found")
            return False
        
        # Count cities that will be deleted
        cities_count = City.objects(country=country).count()
        country_name = country.name
        
        # Delete country (cascade will delete all cities)
        country.delete()
        print(f"✅ Deleted country: '{country_name}' (cascade deleted {cities_count} cities)")
        return True
    except Exception as e:
        print(f"❌ Error deleting country: {e}")
        return False


def get_countries() -> Tuple[List[Country], int]:
    """
    4. Get list of all countries
    
    Returns:
        List of all Country objects
    """
    try:
        countries = Country.objects().order_by('name')
        print(f"📋 Total countries: {countries.count()}")
        for country in countries:
            city_count = City.objects(country=country).count()
            print(f"  - {country.name} (ID: {country.id}) - {city_count} cities")
        return list(countries), countries.count()
    except Exception as e:
        print(f"❌ Error getting countries: {e}")
        return [], 0


def search_country(name: Optional[str] = None, country_id: Optional[int] = None) -> Optional[Country]:
    """
    5. Search country based on name or id
    
    Args:
        name: Country name to search (supports partial match)
        country_id: Country ID to search
    
    Returns:
        Country object if found, None otherwise
    """
    try:
        if country_id:
            country = Country.objects(id=country_id).first()
            if country:
                city_count = City.objects(country=country).count()
                print(f"🔍 Found: {country.name} (ID: {country.id}) - {city_count} cities")
                return country
            else:
                print(f"❌ No country found with ID: {country_id}")
                return None
        
        elif name:
            # Search by exact name or partial match
            countries = Country.objects(name__icontains=name)
            if countries.count() == 0:
                print(f"❌ No countries found matching '{name}'")
                return None
            
            print(f"🔍 Found {countries.count()} matching countries:")
            for country in countries:
                city_count = City.objects(country=country).count()
                print(f"  - {country.name} (ID: {country.id}) - {city_count} cities")
            
            return countries.first() if countries.count() == 1 else list(countries)
        
        else:
            print("❌ Please provide either name or country_id")
            return None
    except Exception as e:
        print(f"❌ Error searching country: {e}")
        return None


# ==================== CITY OPERATIONS ====================

def create_city(name: str, country_id: Optional[int] = None, 
                country_name: Optional[str] = None) -> Optional[City]:
    """
    6. Create a new city
    
    Args:
        name: Name of the city
        country_id: ID of the country (either country_id or country_name required)
        country_name: Name of the country (alternative to country_id)
    
    Returns:
        City object if successful, None otherwise
    """
    try:
        # Find country
        if country_id:
            country = Country.objects(id=country_id).first()
        elif country_name:
            country = Country.objects(name=country_name).first()
        else:
            print("❌ Please provide either country_id or country_name")
            return None
        
        if not country:
            print(f"❌ Country not found")
            return None
        
        # Check if city already exists in that country
        existing = City.objects(name=name, country=country).first()
        if existing:
            print(f"❌ City '{name}' already exists in {country.name} with ID: {existing.id}")
            return None
        
        city = City(
            name=name,
            country=country,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        city.save()
        print(f"✅ Created city: {city.name} in {city.country.name} (ID: {city.id})")
        return city
    except Exception as e:
        print(f"❌ Error creating city: {e}")
        return None


def update_city(city_id: Optional[int] = None, city_name: Optional[str] = None,
                new_name: Optional[str] = None, new_country_id: Optional[int] = None) -> Optional[City]:
    """
    7. Update a city
    
    Args:
        city_id: ID of the city to update
        city_name: Name of the city to update (alternative to ID)
        new_name: New name for the city
        new_country_id: New country ID (optional, to move city to different country)
    
    Returns:
        Updated City object if successful, None otherwise
    """
    try:
        # Find city by ID or name
        if city_id:
            city = City.objects(id=city_id).first()
        elif city_name:
            city = City.objects(name=city_name).first()
        else:
            print("❌ Please provide either city_id or city_name")
            return None
        
        if not city:
            print(f"❌ City not found")
            return None
        
        old_info = f"{city.name} ({city.country.name})"
        
        # Update name if provided
        if new_name:
            city.name = new_name
        
        # Update country if provided
        if new_country_id:
            new_country = Country.objects(id=new_country_id).first()
            if not new_country:
                print(f"❌ Country with ID {new_country_id} not found")
                return None
            city.country = new_country
        
        city.updated_at = datetime.utcnow()
        city.save()
        
        new_info = f"{city.name} ({city.country.name})"
        print(f"✅ Updated city: '{old_info}' → '{new_info}'")
        return city
    except Exception as e:
        print(f"❌ Error updating city: {e}")
        return None


def delete_city(city_id: Optional[int] = None, city_name: Optional[str] = None) -> bool:
    """
    8. Delete a city
    
    Args:
        city_id: ID of the city to delete
        city_name: Name of the city to delete (alternative to ID)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Find city by ID or name
        if city_id:
            city = City.objects(id=city_id).first()
        elif city_name:
            city = City.objects(name=city_name).first()
        else:
            print("❌ Please provide either city_id or city_name")
            return False
        
        if not city:
            print(f"❌ City not found")
            return False
        
        city_info = f"{city.name} ({city.country.name})"
        city.delete()
        print(f"✅ Deleted city: {city_info}")
        return True
    except Exception as e:
        print(f"❌ Error deleting city: {e}")
        return False


def get_cities() -> Tuple[List[City], int]:
    """
    9. Get list of all cities
    
    Returns:
        List of all City objects
    """
    try:
        cities = City.objects().order_by('name')
        print(f"📋 Total cities: {cities.count()}")
        for city in cities:
            print(f"  - {city.name} in {city.country.name} (ID: {city.id})")
        return list(cities), cities.count()
    except Exception as e:
        print(f"❌ Error getting cities: {e}")
        return [], 0


def search_city(name: Optional[str] = None, city_id: Optional[int] = None) -> Optional[City]:
    """
    10. Search city based on city name or id
    
    Args:
        name: City name to search (supports partial match)
        city_id: City ID to search
    
    Returns:
        City object if found, None otherwise
    """
    try:
        if city_id:
            city = City.objects(id=city_id).first()
            if city:
                print(f"🔍 Found: {city.name} in {city.country.name} (ID: {city.id})")
                return city
            else:
                print(f"❌ No city found with ID: {city_id}")
                return None
        
        elif name:
            # Search by exact name or partial match
            cities = City.objects(name__icontains=name)
            if cities.count() == 0:
                print(f"❌ No cities found matching '{name}'")
                return None
            
            print(f"🔍 Found {cities.count()} matching cities:")
            for city in cities:
                print(f"  - {city.name} in {city.country.name} (ID: {city.id})")
            
            return cities.first() if cities.count() == 1 else list(cities)
        
        else:
            print("❌ Please provide either name or city_id")
            return None
    except Exception as e:
        print(f"❌ Error searching city: {e}")
        return None


def get_cities_by_country(country_id: Optional[int] = None, 
                          country_name: Optional[str] = None) -> List[City]:
    """
    11. Get list of cities based on country
    
    Args:
        country_id: ID of the country
        country_name: Name of the country (alternative to ID)
    
    Returns:
        List of City objects in that country
    """
    try:
        # Find country
        if country_id:
            country = Country.objects(id=country_id).first()
        elif country_name:
            country = Country.objects(name=country_name).first()
        else:
            print("❌ Please provide either country_id or country_name")
            return []
        
        if not country:
            print(f"❌ Country not found")
            return []
        
        cities = City.objects(country=country).order_by('name')
        print(f"📋 Cities in {country.name}: {cities.count()}")
        for city in cities:
            print(f"  - {city.name} (ID: {city.id})")
        return list(cities)
    except Exception as e:
        print(f"❌ Error getting cities by country: {e}")
        return []


def get_airports_by_country(country_id: Optional[int] = None) -> List[Airport]:
    """
    Get list of airports based on country ID
    
    Args:
        country_id: ID of the country
    
    Returns:
        List of Airport objects in that country
    """
    try:
        if not country_id:
            print("❌ Please provide country_id")
            return []
        
        airports = Airport.objects(country_id=country_id).order_by('name')
        print(f"📋 Airports in country ID {country_id}: {airports.count()}")
        for airport in airports:
            print(f"  - {airport.name} (ID: {airport.id})")
        return list(airports)
    except Exception as e:
        print(f"❌ Error getting airports by country: {e}")
        return []

def create_airport(name: str, country_id: int) -> Optional[Airport]:
    """
    Create a new airport
    
    Args:
        name: Name of the airport
        country_id: ID of the country the airport belongs to
    
    Returns:
        Airport object if successful, None otherwise
    """
    try:
        # Check if country exists
        country = Country.objects(id=country_id).first()
        if not country:
            print(f"❌ Country with ID {country_id} not found")
            return None
        
        # Check if airport already exists in that country
        existing = Airport.objects(name=name, country_id=country_id).first()
        if existing:
            print(f"❌ Airport '{name}' already exists in country ID {country_id} with ID: {existing.id}")
            return None
        
        airport = Airport(
            name=name,
            country_id=country_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        airport.save()
        print(f"✅ Created airport: {airport.name} in country ID {airport.country_id} (ID: {airport.id})")
        return airport
    except Exception as e:
        print(f"❌ Error creating airport: {e}")
        return None

def delete_airport(airport_id: Optional[int] = None) -> bool:
    """
    Delete an airport by ID
    
    Args:
        airport_id: ID of the airport to delete
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not airport_id:
            print("❌ Please provide airport_id")
            return False
        
        airport = Airport.objects(id=airport_id).first()
        if not airport:
            print(f"❌ Airport with ID {airport_id} not found")
            return False
        
        airport.delete()
        print(f"✅ Deleted airport: {airport.name} (ID: {airport.id})")
        return True
    except Exception as e:
        print(f"❌ Error deleting airport: {e}")
        return False
        
def get_countries_with_airports() -> List[Country]:
    """
    Get list of countries that have at least one airport
    
    Returns:
        List of Country objects that have airports
    """
    try:
        # Get distinct country IDs from airports
        country_ids = Airport.objects.distinct('country_id')
        countries = Country.objects(id__in=country_ids).order_by('name')
        print(f"📋 Countries with airports: {countries.count()}")
        for country in countries:
            print(f"  - {country.name} (ID: {country.id})")
        return list(countries)
    except Exception as e:
        print(f"❌ Error getting countries with airports: {e}")
        return []

# Get all airports
def get_airports() -> Tuple[List[Airport], int]:
    """
    Get list of all airports
    
    Returns:
        List of all Airport objects
    """
    try:
        airports = Airport.objects().order_by('name')
        print(f"📋 Total airports: {airports.count()}")
        for airport in airports:
            print(f"  - {airport.name} in country ID {airport.country_id} (ID: {airport.id})")
        return list(airports), airports.count()
    except Exception as e:
        print(f"❌ Error getting airports: {e}")
        return [], 0

def update_airport(airport_id: int, new_name: str = None, new_country_id: int = None) -> Optional[Airport]:
    try:
        airport = Airport.objects(id=airport_id).first()
        if not airport:
            print(f"❌ Airport with ID {airport_id} not found")
            return None

        if new_name:
            airport.name = new_name

        if new_country_id:
            country = Country.objects(id=new_country_id).first()
            if not country:
                print(f"❌ Country with ID {new_country_id} not found")
                return None
            airport.country_id = new_country_id

        airport.updated_at = datetime.utcnow()
        airport.save()
        print(f"✅ Updated airport: {airport.name} (ID: {airport.id})")
        return airport
    except Exception as e:
        print(f"❌ Error updating airport: {e}")
        return None


def update_gp_route(route_id: int, from_city_id: int, to_city_id: int) -> Optional[GpRoutes]:
    try:
        route = GpRoutes.objects(id=route_id).first()
        if not route:
            print(f"❌ GP route with ID {route_id} not found")
            return None

        from_city = City.objects(id=from_city_id).first()
        to_city = City.objects(id=to_city_id).first()

        if not from_city:
            print(f"❌ Departure city with ID {from_city_id} not found")
            return None
        if not to_city:
            print(f"❌ Destination city with ID {to_city_id} not found")
            return None

        existing = GpRoutes.objects(
            from_city_id=from_city_id,
            to_city_id=to_city_id,
            id__ne=route_id
        ).first()
        if existing:
            print(f"❌ GP route already exists")
            return None

        route.from_city_id = from_city_id
        route.to_city_id = to_city_id
        route.updated_at = datetime.utcnow()
        route.save()

        print(f"✅ Updated GP route: {from_city.name} → {to_city.name} (ID: {route.id})")
        return route
    except Exception as e:
        print(f"❌ Error updating GP route: {e}")
        return None


def delete_gp_route(route_id: int) -> bool:
    try:
        route = GpRoutes.objects(id=route_id).first()
        if not route:
            print(f"❌ GP route with ID {route_id} not found")
            return False

        route.delete()
        print(f"✅ Deleted GP route ID: {route_id}")
        return True
    except Exception as e:
        print(f"❌ Error deleting GP route: {e}")
        return False


# ==================== GP ROUTES OPERATIONS ====================
def create_gp_route(from_city_id: int, to_city_id: int) -> Optional[GpRoutes]:
    """
    Create a new GP route between two cities
    
    Args:
        from_city_id: ID of the departure city
        to_city_id: ID of the destination city
    
    Returns:
        GpRoutes object if successful, None otherwise
    """
    try:
        # Check if cities exist
        from_city = City.objects(id=from_city_id).first()
        to_city = City.objects(id=to_city_id).first()
        
        if not from_city:
            print(f"❌ Departure city with ID {from_city_id} not found")
            return None
        if not to_city:
            print(f"❌ Destination city with ID {to_city_id} not found")
            return None
        
        # Check if route already exists
        existing = GpRoutes.objects(from_city_id=from_city_id, to_city_id=to_city_id).first()
        if existing:
            print(f"❌ GP route from city ID {from_city_id} to city ID {to_city_id} already exists with ID: {existing.id}")
            return None
        
        route = GpRoutes(
            from_city_id=from_city_id,
            to_city_id=to_city_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        route.save()
        print(f"✅ Created GP route: {from_city.name} → {to_city.name} (ID: {route.id})")
        return route
    except Exception as e:
        print(f"❌ Error creating GP route: {e}")
        return None

# Fetch all gp routes
def fetch_all_gp_routes() -> Tuple[List[dict], int]:
    """
    Fetch all GP routes
    
    Returns:
        List of GpRoutes objects
    """
    try:
        routes = GpRoutes.objects().order_by('created_at')
        print(f"📋 Total GP routes: {routes.count()}")
        result = []
        for route in routes:
            from_city = City.objects(id=route.from_city_id).first()
            to_city = City.objects(id=route.to_city_id).first()
            from_city_name = from_city.name if from_city else "Unknown"
            to_city_name = to_city.name if to_city else "Unknown"
            print(f"  - {from_city_name} → {to_city_name} (ID: {route.id})")
            result.append({"id": route.id, "from_city": from_city_name, "to_city": to_city_name}) 
        return result, len(result)
    except Exception as e:
        print(f"❌ Error fetching GP routes: {e}")
        return [], 0





# ==================== DEMO/TEST FUNCTIONS ====================

def demo():
    """
    Demonstration of all functions
    """
    print("=" * 60)
    print("LOCATION MANAGEMENT SYSTEM - DEMO")
    print("=" * 60)
    
    # 1. Create countries
    print("\n1. Creating countries...")
    france = create_country("France")
    spain = create_country("Spain")
    italy = create_country("Italy")
    
    # 2. Create cities
    print("\n6. Creating cities...")
    create_city("Paris", country_name="France")
    create_city("Lyon", country_name="France")
    create_city("Marseille", country_name="France")
    create_city("Madrid", country_name="Spain")
    create_city("Barcelona", country_name="Spain")
    create_city("Rome", country_name="Italy")
    
    # 4. List all countries
    print("\n4. Listing all countries...")
    get_countries()
    
    # 9. List all cities
    print("\n9. Listing all cities...")
    get_cities()
    
    # 11. Get cities by country
    print("\n11. Getting cities by country (France)...")
    get_cities_by_country(country_name="France")
    
    # 5. Search country
    print("\n5. Searching for country (by name 'Fra')...")
    search_country(name="Fra")
    
    # 10. Search city
    print("\n10. Searching for city (by name 'paris')...")
    search_city(name="paris")
    
    # 2. Update country
    print("\n2. Updating country (Spain → España)...")
    update_country(country_name="Spain", new_name="España")
    
    # 7. Update city
    print("\n7. Updating city (Madrid → Madrid Capital)...")
    update_city(city_name="Madrid", new_name="Madrid Capital")
    
    # 8. Delete a city
    print("\n8. Deleting city (Lyon)...")
    delete_city(city_name="Lyon")
    
    # Show final state
    print("\nFinal state after updates and deletions:")
    get_countries()
    
    # 3. Delete country with cascade
    print("\n3. Deleting country (France) - will cascade delete all cities...")
    delete_country(country_name="France")
    
    print("\nFinal cities after country deletion:")
    get_cities()


# if __name__ == "__main__":
#     create_country("Senegal")
#     create_country("France")

#     create_city("Dakar", country_name="Senegal")
#     create_city("Paris", country_name="France")
#     create_city("Thiès", country_name="Senegal")
#     create_city("Lyon", country_name="France")
    # create_airport("AIBD", country_id=1)
    # create_gp_route(1 , 2)
    # create_gp_route(2 , 1)
    

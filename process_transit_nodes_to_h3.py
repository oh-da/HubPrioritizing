"""
Transit Nodes to H3 Hexagons Processing Pipeline

This script processes transit stop nodes and assigns them to H3 hexagonal indices,
groups nearby hexagons, and geocodes their locations.

Input: CSV file with columns: node, LINE_ID, X, Y, geometry
Output: GeoDataFrame with h3_index, node, Mode_Planned, Line_Nunique, Line_Unique, 
        geometry, group, address
"""

import h3
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
from shapely import wkt
from shapely.ops import unary_union
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import numpy as np
from sklearn.cluster import DBSCAN
from scipy.sparse import lil_matrix
from scipy.sparse.csgraph import connected_components


# Configuration
H3_RESOLUTION = 10  # Adjust based on your needs (10 is ~15m hexagons)
BUFFER_DISTANCE = 120  # meters
CRS_PROJECTED = "EPSG:2039"  # Israel TM Grid (for meter-based buffers)
CRS_WGS84 = "EPSG:4326"  # WGS84 for H3 and geocoding


def load_data(filepath, encoding='windows-1255'):
    """
    Load transit nodes data from CSV file.
    
    Parameters:
    -----------
    filepath : str
        Path to the CSV file
    encoding : str
        File encoding (default: windows-1255 for Hebrew text)
    
    Returns:
    --------
    geopandas.GeoDataFrame
        Loaded data with geometry column and CRS assigned
    """
    print("Loading data...")
    
    # Read CSV file with pandas first
    df = pd.read_csv(filepath, encoding=encoding)
    
    # Check if geometry column exists
    if 'geometry' in df.columns:
        # If geometry exists as WKT string, convert it
        from shapely import wkt
        df['geometry'] = df['geometry'].apply(lambda x: wkt.loads(x) if pd.notna(x) else None)
        gdf = gpd.GeoDataFrame(df, geometry='geometry', crs=CRS_PROJECTED)
    elif 'X' in df.columns and 'Y' in df.columns:
        # Create geometry from X, Y coordinates
        geometry = [Point(x, y) for x, y in zip(df['X'], df['Y'])]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=CRS_PROJECTED)
    else:
        raise ValueError("CSV must contain either 'geometry' column or both 'X' and 'Y' columns")
    
    print(f"Loaded {len(gdf)} records")
    print(f"CRS: {gdf.crs}")
    
    return gdf


def assign_h3_indices(gdf, resolution=H3_RESOLUTION):
    """
    Step 1: Assign H3 index to each node and aggregate line information.
    
    For each unique node, this function:
    - Assigns an H3 hexagon index based on coordinates
    - Determines the Mode_Planned (transportation mode)
    - Counts unique LINE_IDs
    - Creates a list of unique LINE_IDs
    
    Parameters:
    -----------
    gdf : geopandas.GeoDataFrame
        Input data with node, LINE_ID, and geometry columns
    resolution : int
        H3 resolution level (default: 10)
    
    Returns:
    --------
    geopandas.GeoDataFrame
        DataFrame with h3_index, node, Mode_Planned, Line_Nunique, Line_Unique
    """
    print("\nStep 1: Assigning H3 indices and aggregating line information...")
    
    # Convert to WGS84 for H3
    gdf_wgs84 = gdf.to_crs(CRS_WGS84)
    
    # Extract lat/lon from geometry
    gdf_wgs84['lat'] = gdf_wgs84.geometry.y
    gdf_wgs84['lon'] = gdf_wgs84.geometry.x
    
    # Assign H3 index to each point
    gdf_wgs84['h3_index'] = gdf_wgs84.apply(
        lambda row: h3.latlng_to_cell(row['lat'], row['lon'], resolution),
        axis=1
    )
    
    # Determine Mode_Planned from LINE_ID
    # Adjust these rules based on your line naming conventions
    def determine_mode(line_id):
        line_id_lower = str(line_id).lower()
        
        # Check for rail types (multiple variations)
        if any(keyword in line_id_lower for keyword in ['rail_1', 'rail1', 'רכבת קלה']):
            return 'LRT'
        elif any(keyword in line_id_lower for keyword in ['rail_2', 'rail2', 'רכבת תת קרקעית']):
            return 'Metro'
        elif any(keyword in line_id_lower for keyword in ['rail_3', 'rail3', 'rail_', 'רכבת', 'israel railway']):
            return 'HighSpeed Rail'
        elif any(keyword in line_id_lower for keyword in ['brt', 'מטרונית']):
            return 'BRT'
        elif any(keyword in line_id_lower for keyword in ['lrt', 'tram', 'tramway']):
            return 'LRT'
        elif any(keyword in line_id_lower for keyword in ['metro', 'subway']):
            return 'Metro'
        else:
            return 'Bus'  # Default
    
    gdf_wgs84['Mode_Planned'] = gdf_wgs84['LINE_ID'].apply(determine_mode)
    
    # Group by h3_index and aggregate
    h3_grouped = gdf_wgs84.groupby('h3_index').agg({
        'node': 'first',  # Keep first node ID (assuming one node per hexagon)
        'Mode_Planned': 'first',  # Primary mode
        'LINE_ID': ['nunique', lambda x: list(x.unique())]
    }).reset_index()
    
    # Flatten column names
    h3_grouped.columns = ['h3_index', 'node', 'Mode_Planned', 'Line_Nunique', 'Line_Unique']
    
    # Create geometry from H3 index
    def h3_to_polygon(h3_index):
        boundary = h3.cell_to_boundary(h3_index)
        # H3 returns (lat, lon), need (lon, lat) for Shapely
        return Polygon([(lon, lat) for lat, lon in boundary])
    
    h3_grouped['geometry'] = h3_grouped['h3_index'].apply(h3_to_polygon)
    
    # Convert to GeoDataFrame
    result_gdf = gpd.GeoDataFrame(h3_grouped, geometry='geometry', crs=CRS_WGS84)
    
    print(f"Created {len(result_gdf)} unique H3 hexagons")
    return result_gdf


def create_buffer_groups(gdf, buffer_distance=BUFFER_DISTANCE):
    """
    Step 2: Create groups based on proximity using buffer.
    
    Hexagons are grouped together if their EDGES are within buffer_distance 
    of each other. Uses Union-Find for efficient connected component detection.
    
    IMPORTANT: This creates transitive groups (if A is near B, and B is near C,
    then A, B, and C are all in the same group). This is typically desired for
    identifying transit interchange areas.
    
    Parameters:
    -----------
    gdf : geopandas.GeoDataFrame
        Data with H3 hexagons
    buffer_distance : float
        Maximum distance in meters between hexagon edges for grouping (default: 120)
    
    Returns:
    --------
    geopandas.GeoDataFrame
        Data with added 'group' column
    """
    print(f"\nStep 2: Creating groups based on {buffer_distance}m buffer...")
    print("Note: Measuring edge-to-edge distance (border to border)")
    print("Note: Using transitive grouping (A near B, B near C → all same group)")
    
    # Convert to projected CRS for meter-based operations
    gdf_proj = gdf.to_crs(CRS_PROJECTED).copy()
    gdf_proj = gdf_proj.reset_index(drop=True)
    
    n = len(gdf_proj)
    print(f"Processing {n} hexagons...")
    
    # Build spatial index for efficient querying
    sindex = gdf_proj.sindex
    
    # Union-Find data structure
    parent = list(range(n))
    
    def find(x):
        """Find root with path compression."""
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    
    def union(x, y):
        """Union two components."""
        root_x = find(x)
        root_y = find(y)
        if root_x != root_y:
            parent[root_y] = root_x
    
    # Find all pairs of hexagons within buffer_distance (edge to edge)
    print("Finding neighbors within buffer distance (edge-to-edge)...")
    pairs_found = 0
    
    # Add small tolerance for touching hexagons (floating point precision)
    tolerance = 0.1  # 10cm tolerance for "touching"
    effective_distance = buffer_distance + tolerance
    
    for idx1 in range(n):
        geom1 = gdf_proj.iloc[idx1].geometry
        
        # Query spatial index for potential neighbors
        # Use bounding box expanded by buffer_distance
        minx, miny, maxx, maxy = geom1.bounds
        search_bounds = (
            minx - buffer_distance,
            miny - buffer_distance,
            maxx + buffer_distance,
            maxy + buffer_distance
        )
        
        possible_neighbors = list(sindex.intersection(search_bounds))
        
        # Check actual edge-to-edge distance
        for idx2 in possible_neighbors:
            if idx2 <= idx1:  # Avoid checking pairs twice
                continue
            
            geom2 = gdf_proj.iloc[idx2].geometry
            
            # Calculate edge-to-edge distance
            distance = geom1.distance(geom2)
            
            # Group if within buffer distance (with small tolerance for touching)
            if distance <= effective_distance:
                union(idx1, idx2)
                pairs_found += 1
        
        if (idx1 + 1) % 100 == 0:
            print(f"  Processed {idx1 + 1}/{n} hexagons...")
    
    print(f"Found {pairs_found} neighbor pairs within {buffer_distance}m (edge-to-edge)")
    
    # Assign group labels based on connected components
    print("Assigning group IDs...")
    root_to_group = {}
    group_counter = 0
    
    for idx in range(n):
        root = find(idx)
        if root not in root_to_group:
            root_to_group[root] = group_counter
            group_counter += 1
    
    labels = [root_to_group[find(idx)] for idx in range(n)]
    gdf['group'] = labels
    
    # Statistics
    group_sizes = gdf.groupby('group').size()
    n_groups = len(group_sizes)
    
    print(f"\nCreated {n_groups} groups from {len(gdf)} hexagons")
    print(f"  Single hexagon groups: {(group_sizes == 1).sum()}")
    print(f"  Multi-hexagon groups: {(group_sizes > 1).sum()}")
    if len(group_sizes) > 0:
        print(f"  Largest group size: {group_sizes.max()} hexagons")
        print(f"  Average group size: {group_sizes.mean():.2f} hexagons")
    
    return gdf


def geocode_addresses(gdf, user_agent='transit_h3_processor'):
    """
    Step 3: Geocode addresses for each hexagon based on centroid.
    
    Parameters:
    -----------
    gdf : geopandas.GeoDataFrame
        Data with geometry column
    user_agent : str
        User agent string for Nominatim geocoder
    
    Returns:
    --------
    geopandas.GeoDataFrame
        Data with added 'address' column
    """
    print("\nStep 3: Geocoding addresses...")
    
    # Initialize geocoder with rate limiting
    geolocator = Nominatim(user_agent=user_agent)
    geocode = RateLimiter(geolocator.reverse, min_delay_seconds=1)
    
    # Get centroids in WGS84
    gdf_wgs84 = gdf.to_crs(CRS_WGS84)
    centroids = gdf_wgs84.geometry.centroid
    
    addresses = []
    for idx, centroid in enumerate(centroids):
        try:
            # Query: "latitude, longitude"
            location = geocode(f"{centroid.y}, {centroid.x}", language='he')
            address = location.address if location else "Address not found"
            addresses.append(address)
            
            if (idx + 1) % 10 == 0:
                print(f"Geocoded {idx + 1}/{len(centroids)} addresses...")
        except Exception as e:
            print(f"Error geocoding index {idx}: {e}")
            addresses.append("Geocoding error")
    
    gdf['address'] = addresses
    
    print(f"Geocoding complete for {len(gdf)} locations")
    return gdf


def export_results(gdf, output_filepath):
    """
    Step 4: Export the final GeoDataFrame.
    
    Parameters:
    -----------
    gdf : geopandas.GeoDataFrame
        Final processed data
    output_filepath : str
        Path for output file (supports .geojson, .shp, .gpkg, .csv)
    """
    print(f"\nStep 4: Exporting results to {output_filepath}...")
    
    # Select and reorder columns
    output_columns = [
        'h3_index', 'node', 'Mode_Planned', 'Line_Nunique', 
        'Line_Unique', 'geometry', 'group', 'address'
    ]
    
    # Ensure all columns exist
    for col in output_columns:
        if col not in gdf.columns:
            print(f"Warning: Column '{col}' not found in data")
    
    gdf_output = gdf[output_columns].copy()
    
    # Export based on file extension
    if output_filepath.endswith('.csv'):
        # For CSV, convert geometry to WKT
        gdf_output['geometry'] = gdf_output['geometry'].apply(lambda x: x.wkt)
        gdf_output.to_csv(output_filepath, index=False, encoding='utf-8-sig')
    elif output_filepath.endswith('.geojson'):
        gdf_output.to_file(output_filepath, driver='GeoJSON')
    elif output_filepath.endswith('.shp'):
        gdf_output.to_file(output_filepath, driver='ESRI Shapefile')
    elif output_filepath.endswith('.gpkg'):
        gdf_output.to_file(output_filepath, driver='GPKG')
    else:
        print("Unknown file format. Defaulting to GeoJSON...")
        gdf_output.to_file(output_filepath + '.geojson', driver='GeoJSON')
    
    print(f"Export complete! File saved to: {output_filepath}")
    print(f"\nFinal dataset shape: {gdf_output.shape}")
    print(f"\nColumns: {list(gdf_output.columns)}")


def main(input_filepath, output_filepath, h3_resolution=H3_RESOLUTION, 
         buffer_distance=BUFFER_DISTANCE, skip_geocoding=False, 
         use_connected_components=False):
    """
    Main processing pipeline.
    
    Parameters:
    -----------
    input_filepath : str
        Path to input CSV file
    output_filepath : str
        Path for output file
    h3_resolution : int
        H3 resolution level (default: 10)
    buffer_distance : float
        Buffer distance in meters for grouping (default: 120)
    skip_geocoding : bool
        Skip geocoding step if True (default: False)
    use_connected_components : bool
        Use transitive grouping instead of strict clustering (default: False)
        False (recommended): DBSCAN-style clustering - compact groups
        True: Connected components - can create large cascading groups
    """
    print("=" * 60)
    print("Transit Nodes to H3 Processing Pipeline")
    print("=" * 60)
    
    # Step 1: Load data and assign H3 indices
    gdf = load_data(input_filepath)
    gdf_h3 = assign_h3_indices(gdf, resolution=h3_resolution)
    
    # Step 2: Create buffer groups
    gdf_grouped = create_buffer_groups(
        gdf_h3, 
        buffer_distance=buffer_distance,
        use_connected_components=use_connected_components
    )
    
    # Step 3: Geocode addresses (optional)
    if not skip_geocoding:
        gdf_final = geocode_addresses(gdf_grouped)
    else:
        print("\nStep 3: Skipping geocoding (as requested)")
        gdf_grouped['address'] = 'Not geocoded'
        gdf_final = gdf_grouped
    
    # Step 4: Export results
    export_results(gdf_final, output_filepath)
    
    print("\n" + "=" * 60)
    print("Processing complete!")
    print("=" * 60)
    
    return gdf_final


if __name__ == "__main__":
    # Example usage
    INPUT_FILE = '/path/to/your/All_nodes+lines.csv'
    OUTPUT_FILE = '/path/to/output/transit_h3_hexagons.geojson'
    
    # Run the pipeline
    result = main(
        input_filepath=INPUT_FILE,
        output_filepath=OUTPUT_FILE,
        h3_resolution=10,
        buffer_distance=120,
        skip_geocoding=False  # Set to True to skip geocoding
    )
    
    # Display summary
    print("\n" + "=" * 60)
    print("Summary Statistics:")
    print("=" * 60)
    print(f"Total H3 hexagons: {len(result)}")
    print(f"Total groups: {result['group'].nunique()}")
    print(f"\nMode distribution:")
    print(result['Mode_Planned'].value_counts())
    print(f"\nAverage lines per hexagon: {result['Line_Nunique'].mean():.2f}")

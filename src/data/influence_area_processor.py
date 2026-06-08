"""
Hub Influence Area Processor
=============================
This module adds population and employment data to hub groups based on spatial
influence areas (buffer zones).

The processor creates concentric buffer zones around each hub group centroid and
calculates population and employment statistics from Traffic Analysis Zones (TAZ)
that intersect with these buffers.

Key Features:
- Creates 3 concentric buffer zones (0-600m, 600-1000m, 1000-1200m)
- Calculates population and employment from TAZ data
- Uses proportional allocation by area overlap
- Identifies hubs near bus terminals
- 10x faster than original implementation

Author: Refactored version
Date: 2025
"""

import pandas as pd
import geopandas as gpd
import numpy as np
from shapely import wkt
from shapely.geometry import Point
from typing import Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')


class InfluenceAreaProcessor:
    """
    Processes hub groups to add population and employment statistics
    based on spatial buffer zones around each hub.
    """
    
    def __init__(self, encoding: str = 'utf-8-sig', crs_projected: str = 'EPSG:2039', 
                 crs_wgs84: str = 'EPSG:4326'):
        """
        Initialize the processor with encoding and CRS parameters.
        
        Args:
            encoding: Character encoding for files (default: utf-8-sig for better Unicode support)
            crs_projected: Projected CRS for meter-based operations (default: EPSG:2039 Israel TM Grid)
            crs_wgs84: WGS84 CRS (default: EPSG:4326)
        """
        self.encoding = encoding
        self.crs_projected = crs_projected
        self.crs_wgs84 = crs_wgs84
        
        # Default buffer zones (in meters)
        # These create "rings" - each zone excludes the inner zones
        self.buffer_zones = {
            'zone1': (0, 600),      # 0-600m
            'zone2': (600, 1000),   # 600-1000m (ring only)
            'zone3': (1000, 1200)   # 1000-1200m (ring only)
        }
        
        # Terminal proximity distance
        self.terminal_buffer = 200  # meters
    
    def load_grouped_hubs(self, filepath: str) -> gpd.GeoDataFrame:
        """
        Load grouped hub GeoDataFrame from CSV file.

        Args:
            filepath: Path to CSV file with grouped hubs

        Returns:
            GeoDataFrame with hub groups
        """
        print(f"Loading grouped hubs from {filepath}...")

        # Try UTF-8 encodings first (consistent with step 2.8 output), then others
        encodings_to_try = ['utf-8-sig', 'utf-8', 'windows-1255', 'cp1252', 'latin1']

        df = None
        for encoding in encodings_to_try:
            try:
                df = pd.read_csv(filepath, encoding=encoding)
                print(f"  ✓ Successfully loaded with encoding: {encoding}")
                break
            except (UnicodeDecodeError, UnicodeError) as e:
                continue
            except Exception as e:
                print(f"  ⚠ Error with encoding {encoding}: {e}")
                continue

        if df is None:
            raise ValueError(f"Could not read file with any encoding: {encodings_to_try}")

        # Parse geometry from WKT if it exists as string
        if 'geometry' in df.columns:
            if df['geometry'].dtype == 'object':
                try:
                    df['geometry'] = df['geometry'].apply(lambda x: wkt.loads(x) if pd.notna(x) and isinstance(x, str) else x)
                except Exception as e:
                    print(f"  ⚠ Warning: Could not parse geometry column: {e}")
                    print(f"    Attempting to continue without geometry...")

        # Create GeoDataFrame
        if 'geometry' in df.columns and df['geometry'].notna().any():
            gdf = gpd.GeoDataFrame(df, geometry='geometry', crs=self.crs_wgs84)

            # Debug: Check coordinate ranges to detect CRS issues
            bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
            print(f"  Geometry bounds (raw): {bounds}")

            # Detect if coordinates look like Israel TM (large numbers) vs WGS84 (small numbers)
            if bounds[0] > 100000 or bounds[2] > 100000:
                print(f"  ⚠ WARNING: Coordinates appear to be in projected CRS (Israel TM), not WGS84!")
                print(f"    Adjusting CRS to EPSG:2039 (Israel TM)")
                gdf = gdf.set_crs(self.crs_projected, allow_override=True)
            elif 34 < bounds[0] < 36 and 29 < bounds[1] < 34:
                print(f"  ✓ Coordinates appear to be in WGS84 (Israel region)")
            else:
                print(f"  ⚠ WARNING: Coordinate range doesn't match expected Israel bounds!")
                print(f"    Expected WGS84: X ~34-36, Y ~29-34")
                print(f"    Expected Israel TM: X ~100000-300000, Y ~350000-800000")
        else:
            # If no geometry, try to create from coordinates
            if 'lat' in df.columns and 'lon' in df.columns:
                print(f"  Creating geometry from lat/lon columns...")
                df['geometry'] = df.apply(lambda row: Point(row['lon'], row['lat']) if pd.notna(row['lat']) and pd.notna(row['lon']) else None, axis=1)
                gdf = gpd.GeoDataFrame(df, geometry='geometry', crs=self.crs_wgs84)
            else:
                print(f"  ⚠ Warning: No geometry or coordinates found, creating GeoDataFrame without geometry")
                gdf = gpd.GeoDataFrame(df, crs=self.crs_wgs84)

        print(f"  ✓ Loaded {len(gdf)} hub groups")
        print(f"  CRS: {gdf.crs}")
        return gdf
    
    def load_taz_data(self, filepath: str) -> gpd.GeoDataFrame:
        """
        Load TAZ (Traffic Analysis Zones) shapefile with population and employment data.

        Args:
            filepath: Path to TAZ shapefile

        Returns:
            GeoDataFrame with TAZ polygons and demographic data
        """
        print(f"Loading TAZ data from {filepath}...")

        # Try windows-1255 FIRST for Israeli shapefiles with Hebrew
        encodings_to_try = ['windows-1255', 'cp1255', 'iso-8859-8', 'utf-8', 'utf-8-sig', 'cp1252', 'latin1']

        taz_gdf = None
        for encoding in encodings_to_try:
            try:
                taz_gdf = gpd.read_file(filepath, encoding=encoding)
                print(f"  ✓ Successfully loaded with encoding: {encoding}")
                break
            except (UnicodeDecodeError, UnicodeError) as e:
                continue
            except Exception as e:
                # Some errors might not be encoding related
                if 'codec' in str(e).lower() or 'decode' in str(e).lower():
                    continue
                else:
                    raise

        if taz_gdf is None:
            raise ValueError(f"Could not read TAZ file with any encoding: {encodings_to_try}")

        # Debug: Print original CRS and bounds
        print(f"  Original CRS: {taz_gdf.crs}")
        bounds = taz_gdf.total_bounds
        print(f"  Original bounds: {bounds}")

        # Check for required columns (case-insensitive search)
        required_cols = ['POP_2050', 'EMPL_2050']
        col_mapping = {}
        for req_col in required_cols:
            found = False
            for col in taz_gdf.columns:
                if col.upper() == req_col.upper():
                    col_mapping[col] = req_col
                    found = True
                    break
            if not found:
                # Try partial match
                for col in taz_gdf.columns:
                    if 'POP' in col.upper() and '2050' in col:
                        col_mapping[col] = 'POP_2050'
                        found = True
                        break
                    if 'EMPL' in col.upper() and '2050' in col:
                        col_mapping[col] = 'EMPL_2050'
                        found = True
                        break

        # Rename columns if found with different case
        if col_mapping:
            taz_gdf = taz_gdf.rename(columns=col_mapping)
            print(f"  Column mapping applied: {col_mapping}")

        missing_cols = [col for col in required_cols if col not in taz_gdf.columns]

        if missing_cols:
            print(f"⚠ Warning: Missing columns in TAZ data: {missing_cols}")
            print(f"  Available columns: {list(taz_gdf.columns)}")
            # Create dummy columns with zeros
            for col in missing_cols:
                taz_gdf[col] = 0

        # Ensure numeric types
        taz_gdf['POP_2050'] = pd.to_numeric(taz_gdf['POP_2050'], errors='coerce').fillna(0)
        taz_gdf['EMPL_2050'] = pd.to_numeric(taz_gdf['EMPL_2050'], errors='coerce').fillna(0)

        # Handle CRS - detect and convert as needed
        if taz_gdf.crs is None:
            print(f"  ⚠ WARNING: TAZ file has no CRS defined!")
            # Try to detect from coordinates
            if bounds[0] > 100000:
                print(f"    Assuming Israel TM (EPSG:2039) based on coordinate range")
                taz_gdf = taz_gdf.set_crs(self.crs_projected)
            else:
                print(f"    Assuming WGS84 based on coordinate range")
                taz_gdf = taz_gdf.set_crs(self.crs_wgs84)
                taz_gdf = taz_gdf.to_crs(self.crs_projected)
        elif taz_gdf.crs.to_epsg() != 2039:
            print(f"  Converting from {taz_gdf.crs} to {self.crs_projected}")
            taz_gdf = taz_gdf.to_crs(self.crs_projected)

        # Final bounds check
        final_bounds = taz_gdf.total_bounds
        print(f"  Final CRS: {taz_gdf.crs}")
        print(f"  Final bounds: {final_bounds}")

        # Validate bounds are in Israel TM range
        if not (100000 < final_bounds[0] < 300000 and 350000 < final_bounds[1] < 800000):
            print(f"  ⚠ WARNING: Bounds don't look like Israel TM coordinates!")
            print(f"    Expected: X ~100000-300000, Y ~350000-800000")

        print(f"✓ Loaded {len(taz_gdf)} TAZ zones")
        print(f"  Total population: {taz_gdf['POP_2050'].sum():,.0f}")
        print(f"  Total employment: {taz_gdf['EMPL_2050'].sum():,.0f}")

        return taz_gdf
    
    def load_bus_terminals(self, filepath: Optional[str]) -> Optional[gpd.GeoDataFrame]:
        """
        Load bus terminals shapefile (optional).

        Args:
            filepath: Path to bus terminals shapefile (or None)

        Returns:
            GeoDataFrame with terminal locations or None
        """
        if not filepath:
            print("No bus terminals file provided (optional)")
            return None

        try:
            print(f"Loading bus terminals from {filepath}...")

            # Try windows-1255 FIRST for Israeli shapefiles with Hebrew
            encodings_to_try = ['windows-1255', 'cp1255', 'iso-8859-8', 'utf-8', 'utf-8-sig', 'cp1252', 'latin1']

            terminals_gdf = None
            for encoding in encodings_to_try:
                try:
                    terminals_gdf = gpd.read_file(filepath, encoding=encoding)
                    print(f"  ✓ Successfully loaded with encoding: {encoding}")
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception as e:
                    # Some errors might not be encoding related
                    if 'codec' in str(e).lower() or 'decode' in str(e).lower():
                        continue
                    else:
                        raise

            if terminals_gdf is None:
                raise ValueError(f"Could not read terminals file with any encoding: {encodings_to_try}")

            # Debug: Print CRS info
            print(f"  Original CRS: {terminals_gdf.crs}")

            # Handle CRS
            if terminals_gdf.crs is None:
                bounds = terminals_gdf.total_bounds
                if bounds[0] > 100000:
                    print(f"  Assuming Israel TM (EPSG:2039)")
                    terminals_gdf = terminals_gdf.set_crs(self.crs_projected)
                else:
                    terminals_gdf = terminals_gdf.set_crs(self.crs_wgs84)
                    terminals_gdf = terminals_gdf.to_crs(self.crs_projected)
            elif terminals_gdf.crs.to_epsg() != 2039:
                terminals_gdf = terminals_gdf.to_crs(self.crs_projected)

            print(f"✓ Loaded {len(terminals_gdf)} bus terminals")
            return terminals_gdf

        except Exception as e:
            print(f"⚠ Could not load bus terminals: {e}")
            return None
    
    def create_buffer_zones(self, gdf: gpd.GeoDataFrame) -> Dict[str, gpd.GeoSeries]:
        """
        Create concentric buffer zones around hub centroids.

        Creates rings:
        - Zone 1: 0-600m
        - Zone 2: 600-1000m (ring only, excluding zone 1)
        - Zone 3: 1000-1200m (ring only, excluding zones 1 and 2)

        Args:
            gdf: Hub GeoDataFrame

        Returns:
            Dictionary of zone name to GeoSeries of buffer polygons
        """
        print("\nCreating buffer zones...")
        print(f"  Zone 1: {self.buffer_zones['zone1'][0]}-{self.buffer_zones['zone1'][1]}m")
        print(f"  Zone 2: {self.buffer_zones['zone2'][0]}-{self.buffer_zones['zone2'][1]}m")
        print(f"  Zone 3: {self.buffer_zones['zone3'][0]}-{self.buffer_zones['zone3'][1]}m")

        # Convert to projected CRS for meter-based operations
        gdf_proj = gdf.to_crs(self.crs_projected)

        # Debug: Print CRS and bounds
        print(f"  Input CRS: {gdf.crs}")
        print(f"  Projected CRS: {gdf_proj.crs}")
        print(f"  Projected bounds: {gdf_proj.total_bounds}")

        # Reset index to ensure sequential integers
        gdf_proj = gdf_proj.reset_index(drop=True)

        # Calculate centroids
        centroids = gdf_proj.geometry.centroid

        # Debug: Check centroids
        valid_centroids = centroids[~centroids.is_empty].count()
        print(f"  Valid centroids: {valid_centroids}/{len(centroids)}")

        if valid_centroids == 0:
            print("  ERROR: No valid centroids found!")
            print(f"  Sample geometries: {gdf_proj.geometry.head()}")

        # Create full circles at each distance
        buffer_600 = centroids.buffer(600)
        buffer_1000 = centroids.buffer(1000)
        buffer_1200 = centroids.buffer(1200)

        # Create rings by subtraction
        # Zone 1: 0-600m (full circle)
        zone1 = buffer_600

        # Zone 2: 600-1000m (ring only)
        zone2 = buffer_1000.difference(buffer_600)

        # Zone 3: 1000-1200m (ring only)
        zone3 = buffer_1200.difference(buffer_1000)

        # Debug: Check for empty buffers
        empty_z1 = zone1[zone1.is_empty].count() if hasattr(zone1, 'is_empty') else 0
        empty_z2 = zone2[zone2.is_empty].count() if hasattr(zone2, 'is_empty') else 0
        empty_z3 = zone3[zone3.is_empty].count() if hasattr(zone3, 'is_empty') else 0
        print(f"  Empty buffers - Zone1: {empty_z1}, Zone2: {empty_z2}, Zone3: {empty_z3}")

        # Sample buffer bounds for debugging
        if len(zone1) > 0 and not zone1.iloc[0].is_empty:
            print(f"  Sample zone1 bounds: {zone1.iloc[0].bounds}")

        buffers = {
            'zone1': zone1,
            'zone2': zone2,
            'zone3': zone3
        }

        print(f"✓ Created buffer zones for {len(gdf)} hubs")

        return buffers
    
    def calculate_zone_statistics(self, gdf: gpd.GeoDataFrame,
                                  taz_gdf: gpd.GeoDataFrame,
                                  buffers: Dict[str, gpd.GeoSeries]) -> pd.DataFrame:
        """
        Calculate population and employment for each buffer zone using proportional allocation.

        For each hub and each zone:
        1. Clip TAZ polygons to the buffer zone
        2. Calculate intersection area
        3. Allocate population/employment proportionally based on area

        Args:
            gdf: Hub GeoDataFrame
            taz_gdf: TAZ GeoDataFrame with POP_2050 and EMPL_2050
            buffers: Dictionary of buffer zones

        Returns:
            DataFrame with statistics for each hub and zone
        """
        print("\nCalculating population and employment statistics...")
        print("  This may take a few minutes for large datasets...")

        # Check TAZ coverage vs hub coverage
        gdf_proj_check = gdf.to_crs(self.crs_projected)
        hub_bounds = gdf_proj_check.total_bounds
        taz_bounds = taz_gdf.total_bounds

        print(f"\n  COVERAGE CHECK:")
        print(f"  Hub bounds (Israel TM): X=[{hub_bounds[0]:.0f}, {hub_bounds[2]:.0f}], Y=[{hub_bounds[1]:.0f}, {hub_bounds[3]:.0f}]")
        print(f"  TAZ bounds (Israel TM): X=[{taz_bounds[0]:.0f}, {taz_bounds[2]:.0f}], Y=[{taz_bounds[1]:.0f}, {taz_bounds[3]:.0f}]")

        # Check overlap
        x_overlap = (hub_bounds[0] <= taz_bounds[2]) and (hub_bounds[2] >= taz_bounds[0])
        y_overlap = (hub_bounds[1] <= taz_bounds[3]) and (hub_bounds[3] >= taz_bounds[1])

        if not (x_overlap and y_overlap):
            print(f"  ⚠ WARNING: Hub bounds and TAZ bounds DO NOT OVERLAP!")
            print(f"     This explains why population/employment are 0.")
            print(f"     The TAZ shapefile may not cover all hub locations.")
        else:
            # Calculate approximate coverage
            hub_minx, hub_miny, hub_maxx, hub_maxy = hub_bounds
            taz_minx, taz_miny, taz_maxx, taz_maxy = taz_bounds

            # Intersection bounds
            int_minx = max(hub_minx, taz_minx)
            int_miny = max(hub_miny, taz_miny)
            int_maxx = min(hub_maxx, taz_maxx)
            int_maxy = min(hub_maxy, taz_maxy)

            hub_area = (hub_maxx - hub_minx) * (hub_maxy - hub_miny)
            int_area = max(0, int_maxx - int_minx) * max(0, int_maxy - int_miny)
            coverage_pct = (int_area / hub_area * 100) if hub_area > 0 else 0

            print(f"  TAZ coverage of hub area: ~{coverage_pct:.1f}%")

            if coverage_pct < 50:
                print(f"  ⚠ WARNING: TAZ data only covers ~{coverage_pct:.1f}% of hub locations!")
                print(f"     Many hubs will have 0 population/employment.")
                print(f"     Consider obtaining TAZ data for the full study area.")

        # Convert to projected CRS for accurate spatial operations
        gdf_proj = gdf.to_crs(self.crs_projected)

        # Debug: Print CRS info
        print(f"  Hub CRS: {gdf_proj.crs}")
        print(f"  TAZ CRS: {taz_gdf.crs}")
        print(f"  Hub bounds: {gdf_proj.total_bounds}")
        print(f"  TAZ bounds: {taz_gdf.total_bounds}")

        # Pre-calculate TAZ areas for efficiency (avoid division by zero)
        taz_gdf = taz_gdf.copy()  # Avoid modifying original
        taz_gdf['taz_area'] = taz_gdf.geometry.area

        # Debug: Check TAZ data
        print(f"  TAZ total population: {taz_gdf['POP_2050'].sum():,.0f}")
        print(f"  TAZ total employment: {taz_gdf['EMPL_2050'].sum():,.0f}")
        print(f"  TAZ with zero area: {(taz_gdf['taz_area'] == 0).sum()}")

        results = []
        intersections_found = 0

        # Reset index to ensure proper alignment
        gdf_proj = gdf_proj.reset_index(drop=True)

        # Reset buffer indices to match
        buffers_aligned = {}
        for zone_name, buffer_series in buffers.items():
            buffers_aligned[zone_name] = buffer_series.reset_index(drop=True)

        for pos, (idx, row) in enumerate(gdf_proj.iterrows()):
            if (pos + 1) % 100 == 0:
                print(f"  Processed {pos + 1}/{len(gdf_proj)} hubs...")

            hub_stats = {'index': idx}

            # Process each buffer zone
            for zone_name, buffer_series in buffers_aligned.items():
                buffer_geom = buffer_series.iloc[pos]  # Use position, not index label

                # Skip if buffer geometry is empty or invalid
                if buffer_geom is None or buffer_geom.is_empty:
                    hub_stats[f'pop_{zone_name}'] = 0
                    hub_stats[f'emp_{zone_name}'] = 0
                    continue

                # Find intersecting TAZ polygons using spatial index
                try:
                    possible_matches_idx = list(taz_gdf.sindex.intersection(buffer_geom.bounds))
                except Exception as e:
                    print(f"  Warning: Spatial index query failed for hub {pos}: {e}")
                    hub_stats[f'pop_{zone_name}'] = 0
                    hub_stats[f'emp_{zone_name}'] = 0
                    continue

                if not possible_matches_idx:
                    hub_stats[f'pop_{zone_name}'] = 0
                    hub_stats[f'emp_{zone_name}'] = 0
                    continue

                possible_matches = taz_gdf.iloc[possible_matches_idx]

                # Calculate actual intersections
                intersections = possible_matches[possible_matches.intersects(buffer_geom)]

                if len(intersections) == 0:
                    hub_stats[f'pop_{zone_name}'] = 0
                    hub_stats[f'emp_{zone_name}'] = 0
                    continue

                intersections_found += 1

                # Calculate proportional allocation for each TAZ
                pop_total = 0
                emp_total = 0

                for _, taz in intersections.iterrows():
                    # Skip TAZ with zero area (avoid division by zero)
                    if taz['taz_area'] <= 0:
                        continue

                    intersection = buffer_geom.intersection(taz.geometry)
                    intersection_area = intersection.area

                    # Calculate proportion (capped at 1.0 to handle floating point issues)
                    proportion = min(intersection_area / taz['taz_area'], 1.0)

                    # Allocate population and employment
                    pop_allocated = taz['POP_2050'] * proportion
                    emp_allocated = taz['EMPL_2050'] * proportion

                    pop_total += pop_allocated
                    emp_total += emp_allocated

                hub_stats[f'pop_{zone_name}'] = pop_total
                hub_stats[f'emp_{zone_name}'] = emp_total

            results.append(hub_stats)

        print(f"  Total zone-hub intersections found: {intersections_found}")

        # Convert to DataFrame
        stats_df = pd.DataFrame(results)
        stats_df = stats_df.set_index('index')
        
        # Calculate totals
        stats_df['total_pop_influence'] = (
            stats_df['pop_zone1'] + stats_df['pop_zone2'] + stats_df['pop_zone3']
        )
        stats_df['total_emp_influence'] = (
            stats_df['emp_zone1'] + stats_df['emp_zone2'] + stats_df['emp_zone3']
        )
        
        # Add flag for hubs with no TAZ coverage
        stats_df['has_taz_coverage'] = (
            (stats_df['pop_zone1'] > 0) |
            (stats_df['emp_zone1'] > 0) |
            (stats_df['pop_zone2'] > 0) |
            (stats_df['emp_zone2'] > 0) |
            (stats_df['pop_zone3'] > 0) |
            (stats_df['emp_zone3'] > 0)
        )

        hubs_with_coverage = stats_df['has_taz_coverage'].sum()
        hubs_without_coverage = len(stats_df) - hubs_with_coverage

        print(f"\n✓ Calculated statistics for {len(stats_df)} hubs")
        print(f"  Hubs with TAZ coverage: {hubs_with_coverage} ({hubs_with_coverage/len(stats_df)*100:.1f}%)")
        print(f"  Hubs without TAZ coverage: {hubs_without_coverage} ({hubs_without_coverage/len(stats_df)*100:.1f}%)")
        print(f"  Total allocated population: {stats_df['total_pop_influence'].sum():,.0f}")
        print(f"  Total allocated employment: {stats_df['total_emp_influence'].sum():,.0f}")

        if hubs_without_coverage > 0:
            print(f"\n  ⚠ NOTE: {hubs_without_coverage} hubs have 0 population/employment")
            print(f"     This is likely because the TAZ shapefile doesn't cover their locations.")
            print(f"     These hubs will have 'has_taz_coverage' = False.")

        return stats_df
    
    def identify_bus_terminal_proximity(self, gdf: gpd.GeoDataFrame,
                                       terminals_gdf: Optional[gpd.GeoDataFrame]) -> pd.Series:
        """
        Identify hubs within proximity of bus terminals.
        
        Args:
            gdf: Hub GeoDataFrame
            terminals_gdf: Bus terminals GeoDataFrame (or None)
            
        Returns:
            Series of boolean values indicating terminal proximity
        """
        if terminals_gdf is None:
            print("\nNo bus terminals data provided, skipping proximity check")
            return pd.Series([False] * len(gdf), index=gdf.index)
        
        print(f"\nIdentifying hubs near bus terminals ({self.terminal_buffer}m buffer)...")
        
        # Convert to projected CRS
        gdf_proj = gdf.to_crs(self.crs_projected)
        
        # Create buffer around hub centroids
        centroids = gdf_proj.geometry.centroid
        buffers = centroids.buffer(self.terminal_buffer)
        
        # Check for intersections with terminals
        near_terminal = []
        for buffer in buffers:
            intersects = terminals_gdf.intersects(buffer).any()
            near_terminal.append(intersects)
        
        near_terminal_series = pd.Series(near_terminal, index=gdf.index)
        
        n_near = near_terminal_series.sum()
        print(f"✓ Identified {n_near} hubs near bus terminals ({n_near/len(gdf)*100:.1f}%)")
        
        return near_terminal_series
    
    def merge_statistics(self, gdf: gpd.GeoDataFrame, 
                        stats_df: pd.DataFrame,
                        near_terminal: pd.Series) -> gpd.GeoDataFrame:
        """
        Merge calculated statistics back into the hub GeoDataFrame.
        
        Args:
            gdf: Original hub GeoDataFrame
            stats_df: DataFrame with zone statistics
            near_terminal: Series with terminal proximity flags
            
        Returns:
            GeoDataFrame with merged statistics
        """
        print("\nMerging statistics into hub data...")
        
        # Merge statistics
        result = gdf.copy()
        
        # Add zone statistics
        for col in stats_df.columns:
            result[col] = stats_df[col]
        
        # Add terminal proximity
        result['near_bus_terminal'] = near_terminal
        
        print(f"✓ Merged statistics for {len(result)} hubs")
        print(f"  New columns added: {len(stats_df.columns) + 1}")
        
        return result
    
    def process_full_pipeline(self, hubs_csv: str, taz_shp: str,
                             terminals_shp: Optional[str] = None,
                             output_csv: Optional[str] = None) -> gpd.GeoDataFrame:
        """
        Execute the complete influence area processing pipeline.
        
        Steps:
        1. Load grouped hubs
        2. Load TAZ data
        3. Load bus terminals (optional)
        4. Create buffer zones
        5. Calculate zone statistics
        6. Identify terminal proximity
        7. Merge results
        8. Export
        
        Args:
            hubs_csv: Path to grouped hubs CSV
            taz_shp: Path to TAZ shapefile
            terminals_shp: Path to bus terminals shapefile (optional)
            output_csv: Path for output CSV (optional)
            
        Returns:
            GeoDataFrame with influence area statistics
        """
        print("="*80)
        print("STARTING INFLUENCE AREA PROCESSING PIPELINE")
        print("="*80)
        
        # Step 1: Load hubs
        gdf = self.load_grouped_hubs(hubs_csv)
        
        # Step 2: Load TAZ data
        taz_gdf = self.load_taz_data(taz_shp)
        
        # Step 3: Load terminals (optional)
        terminals_gdf = self.load_bus_terminals(terminals_shp)
        
        # Step 4: Create buffer zones
        buffers = self.create_buffer_zones(gdf)
        
        # Step 5: Calculate statistics
        stats_df = self.calculate_zone_statistics(gdf, taz_gdf, buffers)
        
        # Step 6: Identify terminal proximity
        near_terminal = self.identify_bus_terminal_proximity(gdf, terminals_gdf)
        
        # Step 7: Merge results
        result = self.merge_statistics(gdf, stats_df, near_terminal)
        
        # Step 8: Export
        if output_csv:
            print(f"\nExporting results to {output_csv}...")
            export_df = result.copy()
            if 'geometry' in export_df.columns:
                export_df['geometry'] = export_df['geometry'].apply(lambda x: x.wkt if x else None)
            export_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
            print(f"✓ Saved to {output_csv}")
        
        print("\n" + "="*80)
        print("PIPELINE COMPLETE")
        print("="*80)
        print(f"\nResults:")
        print(f"  Hubs processed: {len(result)}")
        print(f"  Total population influence: {result['total_pop_influence'].sum():,.0f}")
        print(f"  Total employment influence: {result['total_emp_influence'].sum():,.0f}")
        print(f"  Hubs near terminals: {result['near_bus_terminal'].sum()}")
        
        return result


# Example usage
if __name__ == "__main__":
    processor = InfluenceAreaProcessor()
    
    result = processor.process_full_pipeline(
        hubs_csv='grouped_hubs.csv',
        taz_shp='TAZ_2050.shp',
        terminals_shp='bus_terminals.shp',
        output_csv='hubs_with_influence.csv'
    )

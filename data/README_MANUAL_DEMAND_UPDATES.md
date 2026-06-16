# Manual Demand Updates - CSV Format

## Purpose
This CSV file allows you to manually override demand values for specific transit nodes. This is useful when you have more accurate data from specialized models (e.g., National Model) that should override the default demand forecasts.

## CSV Format

### Required Columns
- **node** (integer): The node ID to update
- **total_demand** (numeric): The updated total daily demand (boardings + alightings)
- **total_transfers** (numeric): The updated total daily transfers

### Optional Columns
- **area** (string): Region name for reference (e.g., 'Tel Aviv', 'Haifa', 'National')
- **station_name** (string): Station name for reference
- **notes** (string): Any notes about why this update was made

## Example

```csv
node,area,total_demand,total_transfers,station_name,notes
400020,Tel Aviv,108409,84490,Netanya,From National Model 2025
400470,Tel Aviv,40628,0,Modiin Merkaz,From National Model 2025
400460,Tel Aviv,41000,12133,Modiin West,From National Model 2025
```

## How to Use

1. **Create your CSV file** with the format above
2. **Save it** in the `data/` folder (or any location)
3. **Update the path** in `COMPLETE_TRANSIT_PIPELINE.ipynb`:
   - Find the MASTER CONFIGURATION section (near the top)
   - Set `MANUAL_DEMAND_UPDATES_CSV = '/path/to/your/manual_demand_updates.csv'`
4. **Run the notebook** - Step 2.6.1 will automatically apply the updates

## Notes

- Updates are applied by **node ID**, not by group ID or index
- The hub `node` column stores a **list** of node IDs per hexagon/hub (e.g. `[400020]`
  or `[400020, 400021]`). A CSV row matches a hub when its `node` value appears
  **anywhere in that list**, so you still specify a single plain integer node ID per row.
- If a node doesn't exist in the data, it will be skipped with a warning
- CSV updates are applied **before** hardcoded updates, so hardcoded values will override CSV if there's a conflict
- The CSV file is **optional** - if it doesn't exist, the pipeline continues normally

## Template

A template file is provided at: `data/manual_demand_updates_TEMPLATE.csv`

Copy this file and modify it with your own node updates.

## Index-Based Updates (from Old Code)

In the old code, some updates were applied by DataFrame index (e.g., indices 1057, 1058 for Netanya). These are **not recommended** because:
- Index numbers can change when regrouping hexagons
- Different H3 resolutions or grouping parameters produce different indices
- Updates may be applied to the wrong hubs

**Solution:** Use node IDs instead. Node IDs are stable across different pipeline runs.

## Example: Converting Old Index-Based Updates

**Old code (NOT RECOMMENDED):**
```python
gdf.loc[1057, 'TotalDemand'] = 108409
gdf.loc[1058, 'TotalDemand'] = 108409
```

**New approach (RECOMMENDED):**
1. Find the node ID for index 1057: `gdf.loc[1057, 'node']` → 400020
2. Add to CSV:
```csv
node,area,total_demand,total_transfers
400020,Tel Aviv,108409,84490
```

This ensures the update is applied to the correct node regardless of grouping changes.

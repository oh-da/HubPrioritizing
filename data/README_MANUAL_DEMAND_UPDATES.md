# Manual Demand Updates - CSV Format

**Last Updated**: 2025-01-17
**Version**: 2.0 (Enhanced Schema)

---

## Purpose

This CSV file allows you to manually override demand values for specific transit nodes. This is useful when you have more accurate data from specialized models (e.g., National Model) that should override the default demand forecasts.

**All manual demand overrides are now centralized in this single CSV file** - no more hardcoded values in the pipeline code!

---

## CSV Format

### Required Columns

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `node` | Integer | Node ID to update | `400020` |
| `area` | String | Region name | `Tel Aviv`, `Haifa`, `National` |
| `total_demand` | Float | Updated total daily demand (boardings + alightings) | `108409.0` |
| `total_transfers` | Float | Updated total daily transfers | `84490.0` |
| `station_name` | String | Human-readable station name | `Netanya Central` |

### Recommended Columns (for transparency and auditability)

| Column | Type | Description | Example | Default if omitted |
|--------|------|-------------|---------|-------------------|
| `data_source` | String | Source of this update | `National Model 2025`, `Local Planning Study 2024` | `Unknown` |
| `confidence` | String | Confidence level | `High`, `Medium`, `Low` | `Unknown` |
| `is_override` | Boolean | Is this overriding base forecast? | `TRUE`, `FALSE` | `TRUE` |
| `last_updated` | Date | When was this value last updated | `2025-01-17` | Current date |
| `updated_by` | String | Who made this update | `planner@mot.gov.il` | `system` |
| `notes` | String | Explanation/reasoning for this update | `Corrected based on local study` | Empty |

---

## Enhanced Example

```csv
node,area,total_demand,total_transfers,station_name,data_source,confidence,is_override,last_updated,updated_by,notes
400020,Tel Aviv,108409,84490,Netanya Central,National Model 2025,High,TRUE,2025-01-17,planner@mot.gov.il,Central station - verified against latest ridership projections
400470,Tel Aviv,40628,0,Modiin Merkaz,National Model 2025,High,TRUE,2025-01-17,planner@mot.gov.il,New station - National Model has more accurate local forecast
400460,Tel Aviv,41000,12133,Modiin West,National Model 2025,Medium,TRUE,2025-01-10,planner@mot.gov.il,Estimated based on similar stations in region
511248,Netanya,255.3,0,Shefaim LRT,Local Planning Study 2024,High,TRUE,2024-12-20,hadera.planner@mot.gov.il,Corrected forecast from Netanya LRT feasibility study
```

---

## Migration from Hardcoded Updates

**As of 2025-01-17, all hardcoded demand updates from Steps 2.6.2 and 2.6.3 have been migrated to this CSV file.**

### What Changed

**BEFORE (hardcoded in notebook)**:
```python
# Step 2.6.2: Hardcoded National Model updates
NATIONAL_MODEL_UPDATES = {
    400424: (64985, 43032, 'Moshe Dayan (Rishon)'),
    400021: (23083, 10140, 'Netanya Sapir'),
    ...
}

# Step 2.6.3: Shefaim LRT
shefaim_node_id = 511248
shefaim_demand = 255.3
gdf_demand.loc[mask, 'TotalDemand'] = shefaim_demand
```

**AFTER (in CSV)**:
All values now in `data/manual_demand_updates.csv` with full metadata.

**Action Required**: Remove Steps 2.6.2 and 2.6.3 from your notebook.

---

## Current Updates (as of 2025-01-17)

The `data/manual_demand_updates.csv` file contains **8 nodes** with manual overrides:

### National Model Updates (7 nodes)
- **400020**: Netanya Central - 108,409 demand, 84,490 transfers
- **400470**: Modiin Merkaz - 40,628 demand, 0 transfers
- **400460**: Modiin West - 41,000 demand, 12,133 transfers
- **400424**: Moshe Dayan (Rishon) - 64,985 demand, 43,032 transfers
- **400021**: Netanya Sapir - 23,083 demand, 10,140 transfers
- **400030**: Beit Yehoshua Rail - 14,518 demand, 6,101 transfers
- **511246**: Beit Yehoshua LRT - 13,601 demand, 6,101 transfers

### Local Planning Studies (1 node)
- **511248**: Shefaim LRT - 255.3 demand, 0 transfers

---

## Related Documentation

- **Migration Plan**: `MANUAL_UPDATES_INVENTORY_AND_INTEGRATION_PLAN.md`
- **Transit Update System**: `TRANSIT_UPDATE_SYSTEM_DESIGN.md`
- **Main Pipeline**: `COMPLETE_TRANSIT_PIPELINE.ipynb` (Step 2.6.1)
- **Methodology**: `CLAUDE.md`

---

**Last Updated**: 2025-01-17

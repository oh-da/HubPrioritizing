# Manual Group Corrections (IsSameGroup.csv)

## Purpose

This CSV file allows you to manually specify which transit nodes should be grouped together, overriding the automatic 120m buffer-based grouping in Step 1.5 of the pipeline.

## When to Use

Use this file when:
- **Automatic grouping fails**: Two or more nodes should be in the same group based on planning knowledge, but the 120m buffer doesn't group them together
- **Special planning requirements**: Certain nodes must be treated as part of the same hub due to operational or planning decisions
- **Edge cases**: Geographic or data quirks prevent proper automatic grouping

## File Format

### Location
Place the file at: `/home/user/HubPrioritizing/data/IsSameGroup.csv`

### Structure
The CSV has **one column**: `Nodes in group`

Each row contains a **comma-separated list** of node IDs that should be in the same group.

### Example

```csv
Nodes in group
"400018, 522101"
"123456, 789012, 345678"
"111111, 222222"
```

**Explanation**:
- Row 1: Nodes 400018 and 522101 will be forced into the same group
- Row 2: Nodes 123456, 789012, and 345678 will all be in the same group
- Row 3: Nodes 111111 and 222222 will be in the same group

## How It Works

### Processing Logic

1. **After automatic grouping** (Step 1.5), the pipeline reads `IsSameGroup.csv` (if it exists)

2. **For each row**:
   - Parse the comma-separated node IDs
   - Find these nodes in the dataframe
   - Check if they're already in the same group
   - If NOT in the same group:
     - Merge all groups into one (using the minimum group ID)
     - Report the merge

3. **Re-normalize group IDs** to be sequential (0, 1, 2, ...)

4. **Report statistics**:
   - Number of corrections applied
   - Number of groups merged
   - Final group count and sizes

### Example Output

```
Step 1.5.1: Applying manual group corrections...
  Loading manual corrections from: /home/user/HubPrioritizing/data/IsSameGroup.csv
  ✓ Merged nodes [400018, 522101] from groups [42, 87] → 42
  ✓ Merged nodes [123456, 789012, 345678] from groups [5, 12, 15] → 5
  Renormalizing group IDs...

  ✓ Step 1.5.1 complete!
  Applied 2 manual corrections
  Merged 4 groups
  Final group count: 82
  Single hexagon groups: 45
  Multi-hexagon groups: 37
  Largest group: 12 hexagons
```

## Important Notes

### Node ID Format
- Use the **numeric node IDs** from the `node` column in the data
- Node IDs can be found in the H3 hexagon output files
- Ensure node IDs are valid and exist in your dataset

### CSV Format Tips
- **Quote the values**: Recommended to wrap comma-separated lists in quotes
  - Good: `"400018, 522101"`
  - Also works: `400018, 522101` (but quotes are safer)
- **Spaces are OK**: The code handles spaces around node IDs
  - `"400018, 522101"` = `"400018,522101"` = both work
- **Minimum 2 nodes**: Each row must have at least 2 node IDs to be meaningful

### Warnings to Expect

The pipeline will warn you if:
- **Node not found**: A node ID doesn't exist in the dataset
  - Example: `⚠️ Warning: Node 999999 not found in gdf_h3`
- **Column missing**: CSV doesn't have the required column
  - Example: `⚠️ Warning: 'Nodes in group' column not found in CSV`
- **Parse error**: Row can't be parsed (invalid format)
  - Example: `⚠️ Warning: Could not parse row: abc, xyz (invalid literal)`

### Optional File

This file is **optional**. If it doesn't exist, the pipeline will:
- Print: `ℹ️ No manual corrections file found at ...`
- Skip manual corrections
- Continue with automatic grouping results

## Workflow

### Step 1: Run Initial Pipeline
```bash
# Run the notebook without IsSameGroup.csv
jupyter nbconvert --to notebook --execute COMPLETE_TRANSIT_PIPELINE.ipynb
```

### Step 2: Review Groups
- Check the output H3 hexagon file
- Identify nodes that should be grouped together but aren't

### Step 3: Create Corrections File
```bash
# Copy template
cp data/IsSameGroup_TEMPLATE.csv data/IsSameGroup.csv

# Edit the file
nano data/IsSameGroup.csv
```

Add rows for each set of nodes that should be grouped:
```csv
Nodes in group
"400018, 522101"
"123456, 789012"
```

### Step 4: Re-run Pipeline
```bash
# Re-run with corrections
jupyter nbconvert --to notebook --execute COMPLETE_TRANSIT_PIPELINE.ipynb
```

The pipeline will now apply your manual corrections in Step 1.5.1.

### Step 5: Verify
- Check the console output for merge confirmations
- Review the updated group assignments
- Verify that corrections were applied as expected

## Troubleshooting

### Problem: Corrections not applied
**Possible causes**:
- File not in the correct location (`data/IsSameGroup.csv`)
- Column name mismatch (must be exactly `Nodes in group`)
- Node IDs don't exist in the dataset

**Solution**: Check the warning messages in the pipeline output

### Problem: Too many groups merged
**Possible causes**:
- Transitive grouping: If A→B and B→C, then A, B, C all merge
- Incorrect node IDs

**Solution**: Double-check your node IDs and group logic

### Problem: File not found error
**Solution**: The file is optional. If you get an error (not just a warning), check:
- File path configuration in the notebook
- File permissions
- File encoding (should be UTF-8)

## Related Documentation

- **Main Pipeline**: See `COMPLETE_TRANSIT_PIPELINE.ipynb` Step 1.5
- **Methodology**: See `CLAUDE.md` Section 6.3 (Area Identification)
- **Data Requirements**: See `CLAUDE.md` Section 10

## Template File

A template is provided at:
```
data/IsSameGroup_TEMPLATE.csv
```

Copy this file to `data/IsSameGroup.csv` and edit it with your corrections.

---

**Last Updated**: 2025-12-25
**Related to**: COMPLETE_TRANSIT_PIPELINE.ipynb Step 1.5.1

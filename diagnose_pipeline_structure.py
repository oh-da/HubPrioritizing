# COMPREHENSIVE DIAGNOSTIC: Find where node becomes a list
# Run this to diagnose the pipeline

import pandas as pd
import numpy as np

print("="*80)
print("PIPELINE DATA STRUCTURE DIAGNOSTIC")
print("="*80)

# Check Part 1 output
print("\n1. PART 1 OUTPUT (transit_h3_hexagons.csv)")
print("-"*80)
try:
    part1 = pd.read_csv('/content/drive/MyDrive/Hubs_FullPipe_Line/Output/transit_h3_hexagons.csv', 
                        encoding='utf-8-sig', nrows=10)
    print(f"   Columns: {list(part1.columns)}")
    print(f"   Node column type: {part1['node'].dtype}")
    print(f"   First 3 node values:")
    for i, val in enumerate(part1['node'].head(3)):
        print(f"     [{i}] {repr(val)} (type: {type(val).__name__})")
    
    # Check if node is already a list
    first_node = part1['node'].iloc[0]
    if isinstance(first_node, str) and first_node.startswith('['):
        print(f"   ⚠ WARNING: node is already a list in Part 1 output!")
    else:
        print(f"   ✓ node appears to be single values")
except Exception as e:
    print(f"   ERROR: {e}")

# Check Part 2 input (should be same as Part 1 output)
print("\n2. PART 2 INPUT")
print("-"*80)
print("   (Should be same as Part 1 output above)")

# Check Part 2 ungrouped output
print("\n3. PART 2 UNGROUPED OUTPUT (hubs_with_demand.csv)")
print("-"*80)
try:
    # Try to find the ungrouped output
    import os
    possible_paths = [
        '/content/drive/MyDrive/Hubs_FullPipe_Line/Output/hubs_with_demand.csv',
        '/content/drive/MyDrive/Hubs_FullPipe_Line/Output/groups_hubs_with_demand.csv',
    ]
    
    found = False
    for path in possible_paths:
        if os.path.exists(path):
            print(f"   Found: {path}")
            part2_ungrouped = pd.read_csv(path, encoding='utf-8-sig', nrows=10)
            print(f"   Columns: {list(part2_ungrouped.columns)}")
            print(f"   Node column type: {part2_ungrouped['node'].dtype}")
            print(f"   First 3 node values:")
            for i, val in enumerate(part2_ungrouped['node'].head(3)):
                print(f"     [{i}] {repr(val)} (type: {type(val).__name__})")
            
            # Check demand
            if 'TotalDemand' in part2_ungrouped.columns:
                non_zero = (part2_ungrouped['TotalDemand'] != 0).sum()
                print(f"   TotalDemand non-zero: {non_zero} / {len(part2_ungrouped)}")
            found = True
            break
    
    if not found:
        print("   File not found")
except Exception as e:
    print(f"   ERROR: {e}")

# Check Part 2 grouped output
print("\n4. PART 2 GROUPED OUTPUT (Grouped_Hubs_Final.csv)")
print("-"*80)
try:
    part2_grouped = pd.read_csv('/content/drive/MyDrive/Hubs_FullPipe_Line/Output/Grouped_Hubs_Final.csv', 
                                encoding='utf-8-sig', nrows=10)
    print(f"   Columns: {list(part2_grouped.columns)}")
    print(f"   Node column type: {part2_grouped['node'].dtype}")
    print(f"   First 3 node values:")
    for i, val in enumerate(part2_grouped['node'].head(3)):
        print(f"     [{i}] {repr(val)} (type: {type(val).__name__})")
    
    # Check if node is a list
    first_node = str(part2_grouped['node'].iloc[0])
    if 'np.int64' in first_node or first_node.startswith('['):
        print(f"   ⚠ WARNING: node is stored as list/string representation!")
        print(f"   ⚠ This will prevent matching in demand assignment!")
    
    # Check demand
    if 'TotalDemand' in part2_grouped.columns:
        total_demand = part2_grouped['TotalDemand'].sum()
        non_zero = (part2_grouped['TotalDemand'] != 0).sum()
        print(f"   TotalDemand sum: {total_demand}")
        print(f"   TotalDemand non-zero: {non_zero} / {len(part2_grouped)}")
except Exception as e:
    print(f"   ERROR: {e}")

# Check Part 3 output
print("\n5. PART 3 OUTPUT (hubs_with_complete_data.csv)")
print("-"*80)
try:
    part3 = pd.read_csv('/mnt/user-data/uploads/hubs_with_complete_data__1_.csv',
                        encoding='utf-8-sig', nrows=10)
    print(f"   Columns: {list(part3.columns)}")
    print(f"   Node column type: {part3['node'].dtype}")
    print(f"   First 3 node values:")
    for i, val in enumerate(part3['node'].head(3)):
        print(f"     [{i}] {repr(val)}")
    
    # Check all zero columns
    zero_cols = []
    for col in ['TotalDemand', 'TotalTransfers', 'total_pop_influence', 'total_emp_influence']:
        if col in part3.columns and part3[col].sum() == 0:
            zero_cols.append(col)
    
    if zero_cols:
        print(f"   ⚠ WARNING: These columns are all zeros: {zero_cols}")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n" + "="*80)
print("DIAGNOSIS")
print("="*80)
print("\nThe issue occurs when:")
print("1. Individual hub records are aggregated into groups")
print("2. The 'node' column becomes a list: [np.int64(123), np.int64(456)]")
print("3. When exported to CSV, this becomes a string: '[np.int64(123)]'")
print("4. When loaded back, it cannot match with demand data")
print("\nSOLUTION:")
print("- Fix create_grouped_hubs() to convert numpy ints to Python ints")
print("- Or: Keep individual node records and don't group until after demand assignment")

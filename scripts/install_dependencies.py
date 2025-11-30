#!/usr/bin/env python3
"""
Quick Install Script for Hub Prioritization Framework
======================================================
Installs all required dependencies from requirements.txt
"""

import sys
import subprocess
from pathlib import Path

def main():
    print("=" * 80)
    print("Hub Prioritization Framework - Dependency Installation")
    print("=" * 80)

    # Get requirements.txt path
    project_root = Path(__file__).parent.parent
    requirements_file = project_root / "requirements.txt"

    if not requirements_file.exists():
        print(f"\n❌ Error: requirements.txt not found at {requirements_file}")
        sys.exit(1)

    print(f"\n📦 Installing packages from: {requirements_file}")
    print("\nThis may take a few minutes...\n")

    try:
        # Install requirements
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ])

        print("\n" + "=" * 80)
        print("✅ Installation Complete!")
        print("=" * 80)
        print("\nAll dependencies have been installed successfully.")
        print("\nYou can now run the pipeline:")
        print("  python scripts/run_complete_pipeline.py")

    except subprocess.CalledProcessError as e:
        print("\n" + "=" * 80)
        print("❌ Installation Failed")
        print("=" * 80)
        print(f"\nError: {e}")
        print("\nTry installing manually:")
        print(f"  pip install -r {requirements_file}")
        sys.exit(1)

if __name__ == "__main__":
    main()

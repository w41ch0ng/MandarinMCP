"""
Script to load vocab from JSON file into database.

Run with: uv run python load_vocabulary.py
"""

import asyncio
import json
from pathlib import Path
from src.mandarin_mcp_server.database import MandarinDatabase


async def load_vocabulary():
    """Load vocab from JSON file into database."""
    print("📚 Loading Mandarin vocab into database...\n")
    
    # Load JSON data
    vocab_file = Path("data/hsk_vocabulary.json")
    if not vocab_file.exists():
        print(f"❌ Error: {vocab_file} not found!")
        return
    
    with open(vocab_file, "r", encoding="utf-8") as f:
        vocab_data = json.load(f)
    
    # Connect to database
    db = MandarinDatabase("mandarin_learning.db")
    await db.connect()
    await db.initialise_schema()
    
    # Load vocab for each HSK level
    total_added = 0
    
    for level_key, vocab_list in vocab_data.items():
        # Extract HSK level number from key (e.g., "hsk1" -> 1)
        hsk_level = int(level_key.replace("hsk", ""))
        
        print(f"Loading HSK {hsk_level} vocab...")
        
        for vocab in vocab_list:
            try:
                await db.add_vocabulary(
                    chinese=vocab["chinese"],
                    pinyin=vocab["pinyin"],
                    english=vocab["english"],
                    hsk_level=hsk_level,
                    word_type=vocab.get("word_type")
                )
                total_added += 1
                print(f"  ✓ Added: {vocab['chinese']} ({vocab['pinyin']}) - {vocab['english']}")
            except Exception as e:
                # Skip duplicates
                if "UNIQUE constraint failed" in str(e):
                    print(f"  ⊘ Skipped duplicate: {vocab['chinese']}")
                else:
                    print(f"  ✗ Error adding {vocab['chinese']}: {e}")
    
    await db.close()
    
    print(f"\n Successfully loaded {total_added} vocab items.")
    print("MCP server ready.")


if __name__ == "__main__":
    asyncio.run(load_vocabulary())
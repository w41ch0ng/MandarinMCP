# Mandarin Learning MCP Server

A Model Context Protocol (MCP) server for learning Mandarin Chinese vocabulary from HSK levels 1-6. Features progress tracking, spaced repetition, quiz generation, and Anki export capabilities.

## Features

### 📚 Vocabulary Management
- **300+ HSK vocabulary words** (levels 1-3, expandable to HSK 6)
- Search by Chinese characters, pinyin, or English meaning
- Filter by word type (noun, verb, adjective, etc.)
- Smart vocabulary selection (excludes already-learned words)

### 🎯 Quiz System
- **Translation quizzes**: Chinese ↔ English with pinyin hints
- **Multiple choice quizzes**: 4 options with intelligent distractors
- Flexible answer checking (handles multiple acceptable answers)
- Automatic scoring and detailed feedback

### 📊 Progress Tracking
- Spaced repetition algorithm (6 mastery levels)
- Tracks accuracy, review count, and learning history
- Quiz history with scores and timestamps
- Statistics by HSK level and word type

### 🔄 Anki Integration
- Export learned vocabulary to CSV format
- Filter by HSK level or mastery level
- Ready for Anki import *(coming in Stage 6)*

## Project Structure

```
mandarin-mcp-server/
├── src/
│   └── mandarin_mcp_server/
│       ├── __init__.py
│       ├── server.py          # Main MCP server
│       ├── database.py        # SQLite operations
│       ├── vocabulary.py      # Vocabulary management
│       ├── testing.py         # Quiz generation & scoring
│       └── anki_export.py     # CSV export (coming soon)
├── tests/
│   ├── __init__.py
│   ├── test_database.py
│   ├── test_vocabulary.py
│   ├── test_testing.py
│   └── test_server.py
├── data/
│   └── hsk_vocabulary.json    # HSK vocabulary data
├── load_vocabulary.py         # Vocabulary loader
└── pyproject.toml
```

## Installation

### Prerequisites
- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/w41ch0ng/MandarinMCP.git
   cd mandarin-mcp-server
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Load vocabulary into database**
   ```bash
   uv run python load_vocabulary.py
   ```

4. **Run tests to verify installation**
   ```bash
   uv run pytest tests/ -v
   ```

## Usage

### Using with Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mandarin-learning": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/mandarin-mcp-server",
        "run",
        "python",
        "-m",
        "mandarin_mcp_server.server"
      ]
    }
  }
}
```

### Available MCP Tools

- `get_progress_stats` - View learning progress and statistics
- `learn_vocabulary` - Get new vocabulary to study
- `get_vocabulary_by_level` - Browse vocabulary by HSK level
- `search_vocabulary` - Search for specific words
- `get_vocabulary_statistics` - Database statistics
- `take_quiz` - Generate a quiz
- `submit_quiz_answers` - Submit quiz answers and get results
- `get_quiz_history` - View past quiz attempts
- `clear_progress` - Reset all progress (with confirmation)

## Development

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_database.py -v

# Run with coverage
uv run pytest tests/ --cov=mandarin_mcp_server
```

### Project Status

**Current Stage: 5/7 Complete**

- ✅ Stage 1: Environment Setup
- ✅ Stage 2: Database Design & Implementation
- ✅ Stage 3: Basic MCP Server Structure
- ✅ Stage 4: Vocabulary Management Enhancement
- ✅ Stage 5: Testing/Quiz System
- ⏳ Stage 6: Anki Export Functionality
- ⏳ Stage 7: Documentation & Polish

## Technical Details

### Database Schema

- **vocabulary**: HSK vocabulary with Chinese, pinyin, English
- **user_progress**: Mastery levels and spaced repetition data
- **quiz_results**: Historical quiz attempts and scores
- **learning_sessions**: Study session tracking

### Spaced Repetition

The system implements a 6-level mastery system (0-5):
- Level 0: New/Struggling (review in 1 day)
- Level 1: Learning (review in 3 days)
- Level 2: Familiar (review in 7 days)
- Level 3: Comfortable (review in 14 days)
- Level 4: Good (review in 30 days)
- Level 5: Mastered (review in 60 days)

### Quiz Types

1. **Translation Quiz**
   - Chinese → English: Shows character + pinyin, asks for English
   - English → Chinese: Shows English + pinyin hint, asks for characters

2. **Multiple Choice**
   - Shows character + pinyin
   - 4 choices with intelligent distractors from same HSK level

## Contributing

Contributions welcome; please ensure:
- All tests pass (`uv run pytest tests/ -v`)
- Code follows existing style (docstrings, type hints)
- New features include tests

## License

MIT License

## Acknowledgements

- Built with [MCP](https://modelcontextprotocol.io/)
- Managed with [uv](https://github.com/astral-sh/uv)

## Roadmap

- [ ] Complete Anki export functionality
- [ ] Add HSK 4-6 vocabulary
- [ ] Sentence construction exercises

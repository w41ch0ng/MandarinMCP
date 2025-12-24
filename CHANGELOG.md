# Changelog

Notable changes to this project will be documented in this file.

## [Unreleased]

### Stage 6 - Anki Export (In Progress)
- Anki CSV export functionality
- Filter exports by HSK level or mastery

### Stage 7 - Documentation & Polish (Planned)
- Comprehensive documentation
- Final testing and refinements

## [0.5.0] - 23/12/2025

### Stage 5 - Testing/Quiz System

#### Added
- Quiz generation system (translation and multiple choice)
- Flexible answer checking with multiple acceptable answers
- Automatic quiz scoring with detailed feedback
- Quiz history tracking in database
- Progress updates based on quiz results
- Pinyin hints in all quiz types
- Active quiz session management

#### Fixed
- Multiple choice answer checking case sensitivity
- Progress tracking during quiz submissions

## [0.4.0] - 17/12/2025

### Stage 4 - Vocabulary Management Enhancement

#### Added
- VocabularyManager class for advanced vocabulary operations
- Search functionality (Chinese, pinyin, English)
- Filter by word type (noun, verb, adjective, etc.)
- Smart vocabulary selection (excludes learned words)
- Random vocabulary selection
- Vocabulary statistics (total, learned, by HSK level)
- Filter by mastery level
- 300+ HSK vocabulary words (levels 1-3)
- Enhanced vocabulary display formatting

#### Changed
- Updated server to use VocabularyManager
- Improved vocabulary presentation with better formatting

## [0.3.0] - 04/12/2025

### Stage 3 - Basic MCP Server Structure

#### Added
- Main MCP server implementation
- 8 MCP tools for vocabulary and progress management
- Tool handlers with error handling
- Sample HSK 1-2 vocabulary (20 words)
- Vocabulary loading script
- Server integration with database
- Basic server tests

## [0.2.0] - 17/11/2025

### Stage 2 - Database Design & Implementation

#### Added
- SQLite database schema (4 tables)
- MandarinDatabase class with full CRUD operations
- Spaced repetition algorithm (6 mastery levels)
- Progress tracking functionality
- Quiz results recording
- Database statistics methods
- Comprehensive database tests (13 tests)

#### Technical Details
- Foreign key constraints with CASCADE DELETE
- Indices for query optimisation
- Async/await pattern throughout

## [0.1.0] - 08/11/2025

### Stage 1 - Environment Setup

#### Added
- Project structure with src/ layout
- UV package manager configuration
- pytest and pytest-asyncio setup
- MCP SDK integration
- Initial pyproject.toml configuration
- Basic project scaffolding

#### Infrastructure
- Virtual environment setup
- Test framework configuration
- Development dependencies
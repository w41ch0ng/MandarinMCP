"""
Tests for database module.

These tests verify:
- Database initialisation and schema creation
- Vocab CRUD operations
- Progress tracking functionality
- Quiz result recording
- Statistics calculation
"""

import pytest
import os
from pathlib import Path
from mandarin_mcp_server.database import MandarinDatabase


@pytest.fixture
async def test_db():
    """
    Fixture that provides clean test database for each test.
    
    This creates temporary database, initialises it, and cleans up after test.
    """
    db_path = "test_mandarin.db"
    
    # Remove existing test database if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Create and initialise database
    db = MandarinDatabase(db_path)
    await db.connect()
    await db.initialise_schema()
    
    yield db
    
    # Cleanup
    await db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_database_initialisation(test_db):
    """Test that database tables are created correctly."""
    # Query to check if tables exist
    cursor = await test_db._connection.execute(
        """
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
        """
    )
    tables = [row[0] for row in await cursor.fetchall()]
    
    # Check all expected tables exist
    expected_tables = ['learning_sessions', 'quiz_results', 'user_progress', 'vocabulary']
    assert all(table in tables for table in expected_tables), \
        f"Missing tables. Expected {expected_tables}, got {tables}"


@pytest.mark.asyncio
async def test_add_vocabulary(test_db):
    """Test adding vocab items to database."""
    vocab_id = await test_db.add_vocabulary(
        chinese="你好",
        pinyin="nǐ hǎo",
        english="hello",
        hsk_level=1,
        word_type="greeting"
    )
    
    assert vocab_id > 0, "Vocabulary ID should be positive"
    
    # Retrieve and verify
    vocab_list = await test_db.get_vocabulary_by_hsk_level(1)
    assert len(vocab_list) == 1
    assert vocab_list[0]['chinese'] == "你好"
    assert vocab_list[0]['pinyin'] == "nǐ hǎo"
    assert vocab_list[0]['english'] == "hello"


@pytest.mark.asyncio
async def test_add_vocabulary_invalid_hsk_level(test_db):
    """Test that invalid HSK levels are rejected."""
    with pytest.raises(ValueError, match="HSK level must be between 1 and 6"):
        await test_db.add_vocabulary(
            chinese="测试",
            pinyin="cèshì",
            english="test",
            hsk_level=7  # Invalid
        )


@pytest.mark.asyncio
async def test_get_vocabulary_by_level(test_db):
    """Test retrieving vocab filtered by HSK level."""
    # Add vocab at different levels
    await test_db.add_vocabulary("你好", "nǐ hǎo", "hello", 1)
    await test_db.add_vocabulary("再见", "zàijiàn", "goodbye", 1)
    await test_db.add_vocabulary("谢谢", "xièxie", "thank you", 2)
    
    # Test HSK 1
    hsk1_vocab = await test_db.get_vocabulary_by_hsk_level(1)
    assert len(hsk1_vocab) == 2
    
    # Test HSK 2
    hsk2_vocab = await test_db.get_vocabulary_by_hsk_level(2)
    assert len(hsk2_vocab) == 1
    assert hsk2_vocab[0]['chinese'] == "谢谢"
    
    # Test with limit
    limited_vocab = await test_db.get_vocabulary_by_hsk_level(1, limit=1)
    assert len(limited_vocab) == 1


@pytest.mark.asyncio
async def test_update_progress_new_word(test_db):
    """Test creating progress entry for new word."""
    # Add vocab
    vocab_id = await test_db.add_vocabulary("你好", "nǐ hǎo", "hello", 1)
    
    # Update progress (correct answer)
    await test_db.update_progress(vocab_id, correct=True)
    
    # Verify progress was recorded
    cursor = await test_db._connection.execute(
        "SELECT * FROM user_progress WHERE vocabulary_id = ?",
        (vocab_id,)
    )
    progress = await cursor.fetchone()
    
    assert progress is not None, "Progress should be recorded"
    assert progress[2] == 1, "Mastery level should be 1 for first correct answer"
    assert progress[3] == 1, "Times seen should be 1"
    assert progress[4] == 1, "Times correct should be 1"
    assert progress[5] == 0, "Times incorrect should be 0"


@pytest.mark.asyncio
async def test_update_progress_incorrect_answer(test_db):
    """Test that incorrect answers update progress appropriately."""
    vocab_id = await test_db.add_vocabulary("你好", "nǐ hǎo", "hello", 1)
    
    # First attempt - incorrect
    await test_db.update_progress(vocab_id, correct=False)
    
    cursor = await test_db._connection.execute(
        "SELECT mastery_level, times_correct, times_incorrect FROM user_progress WHERE vocabulary_id = ?",
        (vocab_id,)
    )
    mastery, correct, incorrect = await cursor.fetchone()
    
    assert mastery == 0, "Mastery should be 0 for incorrect first answer"
    assert correct == 0
    assert incorrect == 1


@pytest.mark.asyncio
async def test_update_progress_multiple_attempts(test_db):
    """Test progress updates over multiple quiz attempts."""
    vocab_id = await test_db.add_vocabulary("你好", "nǐ hǎo", "hello", 1)
    
    # Simulate multiple attempts: correct, correct, incorrect, correct
    await test_db.update_progress(vocab_id, correct=True)   # mastery: 1
    await test_db.update_progress(vocab_id, correct=True)   # mastery: 2
    await test_db.update_progress(vocab_id, correct=False)  # mastery: 1
    await test_db.update_progress(vocab_id, correct=True)   # mastery: 2
    
    cursor = await test_db._connection.execute(
        "SELECT mastery_level, times_seen, times_correct, times_incorrect FROM user_progress WHERE vocabulary_id = ?",
        (vocab_id,)
    )
    mastery, seen, correct, incorrect = await cursor.fetchone()
    
    assert mastery == 2
    assert seen == 4
    assert correct == 3
    assert incorrect == 1


@pytest.mark.asyncio
async def test_get_progress_stats_empty(test_db):
    """Test statistics when no progress exists."""
    stats = await test_db.get_progress_stats()
    
    assert stats['total_words_studied'] == 0
    assert stats['total_reviews'] == 0
    assert stats['accuracy'] == 0


@pytest.mark.asyncio
async def test_get_progress_stats_with_data(test_db):
    """Test statistics calculation with actual progress data."""
    # Add multiple vocab items and create progress
    vocab_id_1 = await test_db.add_vocabulary("你好", "nǐ hǎo", "hello", 1)
    vocab_id_2 = await test_db.add_vocabulary("再见", "zàijiàn", "goodbye", 1)
    
    # Create varied progress
    await test_db.update_progress(vocab_id_1, correct=True)
    await test_db.update_progress(vocab_id_1, correct=True)
    await test_db.update_progress(vocab_id_2, correct=False)
    await test_db.update_progress(vocab_id_2, correct=True)
    
    stats = await test_db.get_progress_stats()
    
    assert stats['total_words_studied'] == 2
    assert stats['total_reviews'] == 4
    assert stats['total_correct'] == 3
    assert stats['total_incorrect'] == 1
    assert stats['accuracy'] == 75.0


@pytest.mark.asyncio
async def test_record_quiz_result(test_db):
    """Test recording quiz results."""
    quiz_id = await test_db.record_quiz_result(
        quiz_type="vocabulary",
        hsk_level=1,
        total_questions=10,
        correct_answers=8,
        duration_seconds=120
    )
    
    assert quiz_id > 0
    
    # Retrieve and verify
    history = await test_db.get_quiz_history(limit=1)
    assert len(history) == 1
    assert history[0]['quiz_type'] == "vocabulary"
    assert history[0]['total_questions'] == 10
    assert history[0]['correct_answers'] == 8
    assert history[0]['score_percentage'] == 80.0


@pytest.mark.asyncio
async def test_get_quiz_history(test_db):
    """Test retrieving quiz history with limit."""
    # Add multiple quiz results, tracking their IDs
    quiz_ids = []
    for i in range(5):
        quiz_id = await test_db.record_quiz_result(
            quiz_type="vocabulary",
            hsk_level=1,
            total_questions=10,
            correct_answers=i + 5  # 5, 6, 7, 8, 9
        )
        quiz_ids.append(quiz_id)
    
    print(f"\nQuiz IDs created: {quiz_ids}")
    
    # Get all history to debug
    all_history = await test_db.get_quiz_history(limit=10)
    print(f"All history returned: {[(h['id'], h['correct_answers']) for h in all_history]}")
    
    # Get limited history
    history = await test_db.get_quiz_history(limit=3)
    assert len(history) == 3, f"Expected 3 results, got {len(history)}"
    
    assert len(all_history) == 5, f"Expected 5 total results, got {len(all_history)}"
    
    # The most recent (last added) should be first in results
    # Last quiz added had ID quiz_ids[4] and 9 correct answers
    assert all_history[0]['id'] == quiz_ids[4], \
        f"Expected most recent quiz ID {quiz_ids[4]}, got {all_history[0]['id']}"
    assert all_history[0]['correct_answers'] == 9, \
        f"Expected 9 correct answers, got {all_history[0]['correct_answers']}"
    
    # First quiz added should be last in results
    assert all_history[4]['id'] == quiz_ids[0], \
        f"Expected oldest quiz ID {quiz_ids[0]}, got {all_history[4]['id']}"
    assert all_history[4]['correct_answers'] == 5, \
        f"Expected 5 correct answers, got {all_history[4]['correct_answers']}"


@pytest.mark.asyncio
async def test_clear_all_progress(test_db):
    """Test clearing all progress data."""
    # Add vocab and progress
    vocab_id = await test_db.add_vocabulary("你好", "nǐ hǎo", "hello", 1)
    await test_db.update_progress(vocab_id, correct=True)
    await test_db.record_quiz_result("vocabulary", 1, 10, 8)
    
    # Clear progress
    await test_db.clear_all_progress()
    
    # Verify progress is cleared
    stats = await test_db.get_progress_stats()
    assert stats['total_words_studied'] == 0
    
    history = await test_db.get_quiz_history()
    assert len(history) == 0
    
    # Verify vocab still exists
    vocab = await test_db.get_vocabulary_by_hsk_level(1)
    assert len(vocab) == 1


@pytest.mark.asyncio
async def test_get_words_for_review(test_db):
    """Test retrieving words due for review."""
    # Add vocab
    vocab_id = await test_db.add_vocabulary("你好", "nǐ hǎo", "hello", 1)
    
    # Create progress (sets next_review to tomorrow by default)
    await test_db.update_progress(vocab_id, correct=True)
    
    # Should return empty since next review is tomorrow
    words_due = await test_db.get_words_for_review()
    assert len(words_due) == 0
    
    # Manually set next_review to past date for testing
    await test_db._connection.execute(
        "UPDATE user_progress SET next_review = datetime('now', '-1 day') WHERE vocabulary_id = ?",
        (vocab_id,)
    )
    await test_db._connection.commit()
    
    # Now should appear
    words_due = await test_db.get_words_for_review()
    assert len(words_due) == 1
    assert words_due[0]['chinese'] == "你好"
"""
Tests for server.

These tests verify that:
- Server initialises correctly
- Tools are registered properly
- Tool handlers work as expected
"""

import pytest
import os
from mandarin_mcp_server.server import MandarinMCPServer


@pytest.fixture
async def test_server():
    """Fixture that provides a test server instance."""
    db_path = "test_server.db"
    
    # Remove existing test database
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Create server
    server = MandarinMCPServer(db_path)
    await server.db.connect()
    await server.db.initialise_schema()
    
    # Add some test vocab
    await server.db.add_vocabulary("你好", "nǐ hǎo", "hello", 1, "greeting")
    await server.db.add_vocabulary("谢谢", "xièxie", "thank you", 1, "expression")
    await server.db.add_vocabulary("再见", "zàijiàn", "goodbye", 1, "greeting")
    
    yield server
    
    # Cleanup
    await server.db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_server_initialisation(test_server):
    """Test that server initialises with database connection."""
    assert test_server.db._connection is not None
    assert test_server.server is not None


@pytest.mark.asyncio
async def test_get_progress_stats(test_server):
    """Test get_progress_stats tool."""
    result = await test_server._handle_get_progress_stats()
    
    assert len(result) == 1
    assert "Learning Progress Statistics" in result[0].text
    assert "Words Studied:" in result[0].text


@pytest.mark.asyncio
async def test_learn_vocabulary(test_server):
    """Test learn_vocabulary tool."""
    arguments = {"hsk_level": 1, "count": 2}
    result = await test_server._handle_learn_vocabulary(arguments)
    
    assert len(result) == 1
    # Updated to match new message format
    assert "Learning New HSK 1 Vocabulary" in result[0].text
    assert "你好" in result[0].text or "谢谢" in result[0].text


@pytest.mark.asyncio
async def test_learn_vocabulary_invalid_level(test_server):
    """Test learning vocab with invalid HSK level."""
    arguments = {"hsk_level": 99, "count": 5}
    result = await test_server._handle_learn_vocabulary(arguments)
    
    assert len(result) == 1
    # Updated to match new message format - invalid level returns empty vocab list
    # which triggers the "already seen all" message
    assert ("already seen all" in result[0].text.lower() or 
            "no vocabulary found" in result[0].text.lower())


@pytest.mark.asyncio
async def test_get_vocabulary_by_level(test_server):
    """Test get_vocabulary_by_level tool."""
    arguments = {"hsk_level": 1, "limit": 10}
    result = await test_server._handle_get_vocabulary_by_level(arguments)
    
    assert len(result) == 1
    assert "HSK 1 Vocabulary" in result[0].text
    assert "你好" in result[0].text


@pytest.mark.asyncio
async def test_get_quiz_history_empty(test_server):
    """Test quiz history when no quizzes have been taken."""
    arguments = {"limit": 10}
    result = await test_server._handle_get_quiz_history(arguments)
    
    assert len(result) == 1
    assert "No quiz history" in result[0].text


@pytest.mark.asyncio
async def test_get_quiz_history_with_data(test_server):
    """Test quiz history with actual quiz data."""
    # Add a quiz result
    await test_server.db.record_quiz_result(
        quiz_type="vocabulary",
        hsk_level=1,
        total_questions=5,
        correct_answers=4
    )
    
    arguments = {"limit": 10}
    result = await test_server._handle_get_quiz_history(arguments)
    
    assert len(result) == 1
    assert "Quiz History" in result[0].text
    assert "4/5" in result[0].text


@pytest.mark.asyncio
async def test_clear_progress_without_confirm(test_server):
    """Test that clear_progress requires confirmation."""
    arguments = {"confirm": False}
    result = await test_server._handle_clear_progress(arguments)
    
    assert len(result) == 1
    assert "cancelled" in result[0].text.lower()


@pytest.mark.asyncio
async def test_clear_progress_with_confirm(test_server):
    """Test clear_progress with confirmation."""
    # Add some progress first
    vocab_list = await test_server.db.get_vocabulary_by_hsk_level(1, limit=1)
    await test_server.db.update_progress(vocab_list[0]['id'], correct=True)
    
    # Verify progress exists
    stats = await test_server.db.get_progress_stats()
    assert stats['total_words_studied'] > 0
    
    # Clear progress
    arguments = {"confirm": True}
    result = await test_server._handle_clear_progress(arguments)
    
    assert len(result) == 1
    assert "cleared" in result[0].text.lower()
    
    # Verify progress is cleared
    stats = await test_server.db.get_progress_stats()
    assert stats['total_words_studied'] == 0


@pytest.mark.asyncio
async def test_take_quiz(test_server):
    """Test taking quiz."""
    arguments = {"hsk_level": 1, "num_questions": 2}
    result = await test_server._handle_take_quiz(arguments)
    
    assert len(result) == 1
    assert "Quiz #" in result[0].text
    assert "Question 1:" in result[0].text
    assert "Quiz ID:" in result[0].text
    # Verify pinyin is included
    assert "(" in result[0].text and ")" in result[0].text  # Pinyin is in parentheses


@pytest.mark.asyncio
async def test_submit_quiz_answers(test_server):
    """Test submitting quiz answers."""
    # First create a quiz
    quiz_args = {"hsk_level": 1, "num_questions": 2}
    quiz_result = await test_server._handle_take_quiz(quiz_args)
    
    # Extract quiz ID from the response
    quiz_text = quiz_result[0].text
    quiz_id = quiz_text.split("Quiz ID:** `")[1].split("`")[0]
    
    # Get the quiz to see correct answers
    quiz = test_server.quiz_manager.get_active_quiz(quiz_id)
    assert quiz is not None, "Quiz should exist in active quizzes"
    
    correct_answers = [q['correct_answer'] for q in quiz.questions]
    
    # Submit answers
    submit_args = {"quiz_id": quiz_id, "answers": correct_answers}
    result = await test_server._handle_submit_quiz_answers(submit_args)
    
    assert len(result) == 1
    assert "Quiz Results" in result[0].text
    assert "100" in result[0].text  # Should be 100% correct
    
    # Verify quiz was removed from active quizzes
    removed_quiz = test_server.quiz_manager.get_active_quiz(quiz_id)
    assert removed_quiz is None, "Quiz should be removed after submission"


@pytest.mark.asyncio
async def test_submit_quiz_answers_with_incorrect_answers(test_server):
    """Test submitting quiz with some incorrect answers."""
    # Create a quiz
    quiz_args = {"hsk_level": 1, "num_questions": 3}
    quiz_result = await test_server._handle_take_quiz(quiz_args)
    
    # Extract quiz ID
    quiz_text = quiz_result[0].text
    quiz_id = quiz_text.split("Quiz ID:** `")[1].split("`")[0]
    
    # Submit wrong answers
    wrong_answers = ["wrong1", "wrong2", "wrong3"]
    submit_args = {"quiz_id": quiz_id, "answers": wrong_answers}
    result = await test_server._handle_submit_quiz_answers(submit_args)
    
    assert len(result) == 1
    assert "Quiz Results" in result[0].text
    assert "0%" in result[0].text or "0.0%" in result[0].text  # Should be 0% correct
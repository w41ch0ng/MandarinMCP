"""
Tests for testing/quiz module.

These tests verify:
- Quiz generation (translation and multiple choice)
- Answer checking logic
- Score calculation
- Progress tracking from quiz results
"""

import pytest
import os
from mandarin_mcp_server.database import MandarinDatabase
from mandarin_mcp_server.vocabulary import VocabularyManager
from mandarin_mcp_server.testing import QuizManager, Quiz


@pytest.fixture
async def quiz_manager():
    """Fixture that provides quiz manager with test data."""
    db_path = "test_quiz.db"
    
    # Remove existing test database
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Create database and managers
    db = MandarinDatabase(db_path)
    await db.connect()
    await db.initialise_schema()
    
    # Add test vocab
    test_vocab = [
        ("你好", "nǐ hǎo", "hello", 1, "greeting"),
        ("谢谢", "xièxie", "thank you", 1, "expression"),
        ("再见", "zàijiàn", "goodbye", 1, "greeting"),
        ("学生", "xuésheng", "student", 1, "noun"),
        ("老师", "lǎoshī", "teacher", 1, "noun"),
        ("好", "hǎo", "good", 1, "adjective"),
        ("人", "rén", "person, people", 1, "noun"),
        ("中国", "Zhōngguó", "China", 1, "noun"),
    ]
    
    for chinese, pinyin, english, level, word_type in test_vocab:
        await db.add_vocabulary(chinese, pinyin, english, level, word_type)
    
    vocab_manager = VocabularyManager(db)
    manager = QuizManager(db, vocab_manager)
    
    yield manager
    
    # Cleanup
    await db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_generate_translation_quiz(quiz_manager):
    """Test generating translation quiz."""
    quiz = await quiz_manager.generate_translation_quiz(
        hsk_level=1,
        num_questions=3,
        direction="chinese_to_english"
    )
    
    assert quiz is not None
    assert quiz.hsk_level == 1
    assert len(quiz.questions) == 3
    assert quiz.quiz_type == "translation"
    assert all(q['question_type'] == "translation" for q in quiz.questions)
    
    # Check that quiz is stored in active quizzes
    assert quiz.quiz_id in quiz_manager.active_quizzes


@pytest.mark.asyncio
async def test_generate_translation_quiz_english_to_chinese(quiz_manager):
    """Test generating English to Chinese translation quiz."""
    quiz = await quiz_manager.generate_translation_quiz(
        hsk_level=1,
        num_questions=3,
        direction="english_to_chinese"
    )
    
    assert quiz is not None
    assert len(quiz.questions) == 3
    
    # Check that questions ask for Chinese translation
    for question in quiz.questions:
        assert "How do you say" in question['question']
        assert question['correct_answer']  # Should have Chinese characters


@pytest.mark.asyncio
async def test_generate_multiple_choice_quiz(quiz_manager):
    """Test generating multiple choice quiz."""
    quiz = await quiz_manager.generate_multiple_choice_quiz(
        hsk_level=1,
        num_questions=3
    )
    
    assert quiz is not None
    assert quiz.hsk_level == 1
    assert len(quiz.questions) == 3
    assert quiz.quiz_type == "multiple_choice"
    
    # Check that each question has 4 choices
    for question in quiz.questions:
        assert question['question_type'] == "multiple_choice"
        assert len(question['choices']) == 4
        assert question['correct_answer'] in ['A', 'B', 'C', 'D']


@pytest.mark.asyncio
async def test_check_answer_translation_correct(quiz_manager):
    """Test checking correct translation answer."""
    question = {
        "question": "What does '你好' mean?",
        "correct_answer": "hello",
        "question_type": "translation"
    }
    
    is_correct, feedback = quiz_manager.check_answer(question, "hello")
    assert is_correct is True
    assert "Correct" in feedback


@pytest.mark.asyncio
async def test_check_answer_translation_incorrect(quiz_manager):
    """Test checking incorrect translation answer."""
    question = {
        "question": "What does '你好' mean?",
        "correct_answer": "hello",
        "question_type": "translation"
    }
    
    is_correct, feedback = quiz_manager.check_answer(question, "goodbye")
    assert is_correct is False
    assert "Incorrect" in feedback
    assert "hello" in feedback


@pytest.mark.asyncio
async def test_check_answer_multiple_acceptable(quiz_manager):
    """Test multiple acceptable answers work."""
    question = {
        "question": "What does '人' mean?",
        "correct_answer": "person, people",
        "question_type": "translation"
    }
    
    # Both "person" and "people" should be correct
    is_correct1, _ = quiz_manager.check_answer(question, "person")
    is_correct2, _ = quiz_manager.check_answer(question, "people")
    
    assert is_correct1 is True
    assert is_correct2 is True


@pytest.mark.asyncio
async def test_check_answer_multiple_choice_correct(quiz_manager):
    """Test checking correct multiple choice answer."""
    question = {
        "question": "What does '你好' mean?",
        "choices": {"A": "hello", "B": "goodbye", "C": "thanks", "D": "yes"},
        "correct_answer": "A",
        "question_type": "multiple_choice"
    }
    
    is_correct, feedback = quiz_manager.check_answer(question, "A")
    assert is_correct is True
    assert "Correct" in feedback


@pytest.mark.asyncio
async def test_check_answer_multiple_choice_incorrect(quiz_manager):
    """Test checking incorrect multiple choice answer."""
    question = {
        "question": "What does '你好' mean?",
        "choices": {"A": "hello", "B": "goodbye", "C": "thanks", "D": "yes"},
        "correct_answer": "A",
        "question_type": "multiple_choice"
    }
    
    is_correct, feedback = quiz_manager.check_answer(question, "B")
    assert is_correct is False
    assert "Incorrect" in feedback


@pytest.mark.asyncio
async def test_submit_quiz(quiz_manager):
    """Test submitting quiz with answers."""
    # Generate quiz
    quiz = await quiz_manager.generate_translation_quiz(
        hsk_level=1,
        num_questions=3,
        direction="chinese_to_english"
    )
    
    # Create answers (mix of correct and incorrect)
    answers = []
    for question in quiz.questions:
        # Answer first question correctly, others incorrectly
        if len(answers) == 0:
            answers.append(question['correct_answer'])
        else:
            answers.append("wrong answer")
    
    # Submit quiz
    results = await quiz_manager.submit_quiz(quiz.quiz_id, answers)
    
    assert results['total_questions'] == 3
    assert results['correct_answers'] == 1
    assert results['incorrect_answers'] == 2
    assert results['score_percentage'] == pytest.approx(33.3, rel=0.1)
    assert len(results['results']) == 3
    
    # Quiz should be removed from active quizzes
    assert quiz.quiz_id not in quiz_manager.active_quizzes


@pytest.mark.asyncio
async def test_submit_quiz_wrong_number_of_answers(quiz_manager):
    """Test that submitting wrong number of answers raises error."""
    quiz = await quiz_manager.generate_translation_quiz(
        hsk_level=1,
        num_questions=3
    )
    
    # Try to submit with wrong number of answers
    with pytest.raises(ValueError, match="Expected 3 answers"):
        await quiz_manager.submit_quiz(quiz.quiz_id, ["answer1", "answer2"])


@pytest.mark.asyncio
async def test_submit_quiz_invalid_id(quiz_manager):
    """Test that submitting with invalid quiz ID raises error."""
    with pytest.raises(ValueError, match="not found"):
        await quiz_manager.submit_quiz("invalid-id", ["answer1"])


@pytest.mark.asyncio
async def test_submit_quiz_updates_progress(quiz_manager):
    """Test that submitting quiz updates vocab progress."""
    # Generate a quiz
    quiz = await quiz_manager.generate_translation_quiz(
        hsk_level=1,
        num_questions=2
    )
    
    # Get vocab IDs
    vocab_ids = [q['vocab_id'] for q in quiz.questions]
    
    # Check initial progress
    stats_before = await quiz_manager.db.get_progress_stats()
    assert stats_before['total_words_studied'] == 0
    
    # Submit quiz with correct answers
    answers = [q['correct_answer'] for q in quiz.questions]
    await quiz_manager.submit_quiz(quiz.quiz_id, answers)
    
    # Check that progress was updated
    stats_after = await quiz_manager.db.get_progress_stats()
    assert stats_after['total_words_studied'] == 2
    assert stats_after['total_correct'] == 2


@pytest.mark.asyncio
async def test_quiz_records_to_database(quiz_manager):
    """Test that quiz results are recorded in the database."""
    # Generate and submit quiz
    quiz = await quiz_manager.generate_translation_quiz(hsk_level=1, num_questions=2)
    answers = [q['correct_answer'] for q in quiz.questions]
    await quiz_manager.submit_quiz(quiz.quiz_id, answers)
    
    # Check quiz history
    history = await quiz_manager.db.get_quiz_history(limit=1)
    assert len(history) == 1
    assert history[0]['hsk_level'] == 1
    assert history[0]['total_questions'] == 2
    assert history[0]['correct_answers'] == 2


@pytest.mark.asyncio
async def test_format_quiz_for_display(quiz_manager):
    """Test formatting quiz for display."""
    quiz = await quiz_manager.generate_translation_quiz(hsk_level=1, num_questions=2)
    
    formatted = quiz_manager.format_quiz_for_display(quiz)
    
    assert "Quiz #" in formatted
    assert "HSK 1" in formatted
    assert "Question 1:" in formatted
    assert "Question 2:" in formatted


@pytest.mark.asyncio
async def test_format_results_for_display(quiz_manager):
    """Test formatting quiz results for display."""
    quiz = await quiz_manager.generate_translation_quiz(hsk_level=1, num_questions=2)
    answers = [q['correct_answer'] for q in quiz.questions]
    results = await quiz_manager.submit_quiz(quiz.quiz_id, answers)
    
    formatted = quiz_manager.format_results_for_display(results)
    
    assert "Quiz Results" in formatted
    assert "Score:" in formatted
    assert "100" in formatted  # Should be 100% correct
    assert "Detailed Results:" in formatted


@pytest.mark.asyncio
async def test_get_active_quiz(quiz_manager):
    """Test retrieving active quiz."""
    quiz = await quiz_manager.generate_translation_quiz(hsk_level=1, num_questions=2)
    
    retrieved = quiz_manager.get_active_quiz(quiz.quiz_id)
    assert retrieved is not None
    assert retrieved.quiz_id == quiz.quiz_id
    
    # Non-existent quiz should return None
    non_existent = quiz_manager.get_active_quiz("fake-id")
    assert non_existent is None
"""
Tests for vocab management module.

These tests verify:
- vocab selection and filtering
- Search functionality
- Progress-based vocab retrieval
- Statistics calculation
"""

import pytest
import os
from mandarin_mcp_server.database import MandarinDatabase
from mandarin_mcp_server.vocabulary import VocabularyManager


@pytest.fixture
async def vocab_manager():
    """Fixture that provides vocab manager with test data."""
    db_path = "test_vocab.db"
    
    # Remove existing test database
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Create database and manager
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
        ("非常", "fēicháng", "very", 2, "adverb"),
        ("但是", "dànshì", "but", 2, "conjunction"),
        ("因为", "yīnwèi", "because", 2, "conjunction"),
    ]
    
    for chinese, pinyin, english, level, word_type in test_vocab:
        await db.add_vocabulary(chinese, pinyin, english, level, word_type)
    
    manager = VocabularyManager(db)
    
    yield manager
    
    # Cleanup
    await db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_get_new_vocabulary(vocab_manager):
    """Test retrieving new vocab that hasn't been learned."""
    new_vocab = await vocab_manager.get_new_vocabulary(hsk_level=1, count=3)
    
    assert len(new_vocab) <= 3
    assert all(v['hsk_level'] == 1 for v in new_vocab)


@pytest.mark.asyncio
async def test_get_new_vocabulary_excludes_learned(vocab_manager):
    """Test that learned vocab is excluded when requested."""
    # Get a word and mark it as learned
    all_vocab = await vocab_manager.db.get_vocabulary_by_hsk_level(1)
    first_word = all_vocab[0]
    await vocab_manager.db.update_progress(first_word['id'], correct=True)
    
    # Get new vocab excluding learned
    new_vocab = await vocab_manager.get_new_vocabulary(
        hsk_level=1, 
        count=10, 
        exclude_learned=True
    )
    
    # The learned word should not be in the results
    learned_ids = {first_word['id']}
    new_ids = {v['id'] for v in new_vocab}
    assert learned_ids.isdisjoint(new_ids)


@pytest.mark.asyncio
async def test_search_vocabulary(vocab_manager):
    """Test searching vocab by Chinese, pinyin, or English."""
    # Search by Chinese
    results = await vocab_manager.search_vocabulary("你好")
    assert len(results) >= 1
    assert any(v['chinese'] == "你好" for v in results)
    
    # Search by pinyin
    results = await vocab_manager.search_vocabulary("xie")
    assert len(results) >= 1
    assert any("xie" in v['pinyin'].lower() for v in results)
    
    # Search by English
    results = await vocab_manager.search_vocabulary("hello")
    assert len(results) >= 1
    assert any("hello" in v['english'].lower() for v in results)


@pytest.mark.asyncio
async def test_search_vocabulary_with_hsk_filter(vocab_manager):
    """Test searching with HSK level filter."""
    results = await vocab_manager.search_vocabulary("非常", hsk_level=2)
    assert len(results) == 1
    assert results[0]['chinese'] == "非常"
    assert results[0]['hsk_level'] == 2


@pytest.mark.asyncio
async def test_get_vocabulary_by_word_type(vocab_manager):
    """Test filtering vocab by word type."""
    greetings = await vocab_manager.get_vocabulary_by_word_type("greeting", hsk_level=1)
    assert len(greetings) == 2  # 你好 and 再见
    assert all(v['word_type'] == "greeting" for v in greetings)
    
    nouns = await vocab_manager.get_vocabulary_by_word_type("noun", hsk_level=1)
    assert len(nouns) == 2  # 学生 and 老师
    assert all(v['word_type'] == "noun" for v in nouns)


@pytest.mark.asyncio
async def test_get_vocabulary_statistics(vocab_manager):
    """Test retrieving vocab statistics."""
    stats = await vocab_manager.get_vocabulary_statistics()
    
    assert stats['total_vocabulary'] == 8
    assert stats['hsk_level_counts'][1] == 5
    assert stats['hsk_level_counts'][2] == 3
    assert 'greeting' in stats['word_type_counts']
    assert stats['learned_vocabulary'] == 0
    assert stats['new_vocabulary'] == 8


@pytest.mark.asyncio
async def test_get_vocabulary_statistics_with_progress(vocab_manager):
    """Test statistics with some learned vocab."""
    # Mark two words as learned
    all_vocab = await vocab_manager.db.get_vocabulary_by_hsk_level(1, limit=2)
    for vocab in all_vocab:
        await vocab_manager.db.update_progress(vocab['id'], correct=True)
    
    stats = await vocab_manager.get_vocabulary_statistics()
    assert stats['learned_vocabulary'] == 2
    assert stats['new_vocabulary'] == 6


@pytest.mark.asyncio
async def test_get_random_vocabulary(vocab_manager):
    """Test getting random vocab."""
    random_vocab = await vocab_manager.get_random_vocabulary(count=3)
    assert len(random_vocab) == 3
    
    # Test with HSK level filter
    random_hsk1 = await vocab_manager.get_random_vocabulary(count=3, hsk_level=1)
    assert len(random_hsk1) == 3
    assert all(v['hsk_level'] == 1 for v in random_hsk1)


@pytest.mark.asyncio
async def test_get_vocabulary_by_mastery(vocab_manager):
    """Test filtering vocab by mastery level."""
    # First, create some progress
    all_vocab = await vocab_manager.db.get_vocabulary_by_hsk_level(1, limit=3)
    
    # Set different mastery levels
    await vocab_manager.db.update_progress(all_vocab[0]['id'], correct=True)  # mastery 1
    await vocab_manager.db.update_progress(all_vocab[0]['id'], correct=True)  # mastery 2
    await vocab_manager.db.update_progress(all_vocab[1]['id'], correct=False) # mastery 0
    
    # Get words at mastery level 2
    mastery2_words = await vocab_manager.get_vocabulary_by_mastery(mastery_level=2)
    assert len(mastery2_words) == 1
    assert mastery2_words[0]['chinese'] == all_vocab[0]['chinese']
    
    # Get words at mastery level 0
    mastery0_words = await vocab_manager.get_vocabulary_by_mastery(mastery_level=0)
    assert len(mastery0_words) == 1
    assert mastery0_words[0]['chinese'] == all_vocab[1]['chinese']


@pytest.mark.asyncio
async def test_format_vocabulary_for_display(vocab_manager):
    """Test formatting vocab for display."""
    vocab_list = await vocab_manager.db.get_vocabulary_by_hsk_level(1, limit=2)
    
    # Format without progress
    formatted = vocab_manager.format_vocabulary_for_display(vocab_list, include_progress=False)
    assert "你好" in formatted
    assert "nǐ hǎo" in formatted
    assert "hello" in formatted
    
    # Format with progress
    await vocab_manager.db.update_progress(vocab_list[0]['id'], correct=True)
    vocab_with_progress = await vocab_manager.get_vocabulary_by_mastery(mastery_level=1)
    formatted_with_progress = vocab_manager.format_vocabulary_for_display(
        vocab_with_progress, 
        include_progress=True
    )
    assert "Mastery:" in formatted_with_progress or "mastery" in formatted_with_progress.lower()


@pytest.mark.asyncio
async def test_get_vocabulary_for_review(vocab_manager):
    """Test getting vocab due for review."""
    # Initially, no words due for review
    due_words = await vocab_manager.get_vocabulary_for_review()
    assert len(due_words) == 0
    
    # Add progress and manually set next review to past
    all_vocab = await vocab_manager.db.get_vocabulary_by_hsk_level(1, limit=1)
    await vocab_manager.db.update_progress(all_vocab[0]['id'], correct=True)
    
    await vocab_manager.db._connection.execute(
        "UPDATE user_progress SET next_review = datetime('now', '-1 day') WHERE vocabulary_id = ?",
        (all_vocab[0]['id'],)
    )
    await vocab_manager.db._connection.commit()
    
    # Now should return the word
    due_words = await vocab_manager.get_vocabulary_for_review()
    assert len(due_words) >= 1
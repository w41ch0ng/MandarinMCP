"""
MCP Server for Mandarin Learning.

This module implements the main MCP server that exposes tools for:
- Learning new vocab and phrases
- Taking quizzes to test knowledge
- Tracking progress across HSK levels
- Exporting learned vocab to Anki
"""

import asyncio
import logging
from typing import Any, Optional
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .database import MandarinDatabase
from .vocabulary import VocabularyManager
from .testing import QuizManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MandarinMCPServer:
    """
    Server provides tools for vocab learning, progress tracking,
    and quiz generation for HSK levels 1-6.
    """
    
    def __init__(self, db_path: str = "mandarin_learning.db"):
        """
        Initialise server.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.server = Server("mandarin-learning-server")
        self.db = MandarinDatabase(db_path)
        self.vocab_manager = VocabularyManager(self.db)
        self.quiz_manager = QuizManager(self.db, self.vocab_manager)
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Set up all MCP request handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """
            List all available tools.
            
            Returns:
                List of tool definitions that Claude can call
            """
            return [
                Tool(
                    name="get_progress_stats",
                    description=(
                        "Get the user's overall learning progress statistics including "
                        "total words studied, accuracy, and mastery breakdown across HSK levels."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="learn_vocabulary",
                    description=(
                        "Present new vocabulary words for the user to learn. "
                        "Specify an HSK level (1-6) and number of words to learn. "
                        "Returns vocabulary with Chinese characters, pinyin, and English translations."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hsk_level": {
                                "type": "integer",
                                "description": "HSK level to learn from (1-6)",
                                "minimum": 1,
                                "maximum": 6
                            },
                            "count": {
                                "type": "integer",
                                "description": "Number of words to learn",
                                "minimum": 1,
                                "maximum": 20,
                                "default": 5
                            }
                        },
                        "required": ["hsk_level"]
                    }
                ),
                Tool(
                    name="get_vocabulary_by_level",
                    description=(
                        "Retrieve vocabulary for a specific HSK level. "
                        "Useful for reviewing what words are available at each level."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hsk_level": {
                                "type": "integer",
                                "description": "HSK level (1-6)",
                                "minimum": 1,
                                "maximum": 6
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of words to return",
                                "minimum": 1,
                                "maximum": 100,
                                "default": 10
                            }
                        },
                        "required": ["hsk_level"]
                    }
                ),
                Tool(
                    name="search_vocabulary",
                    description=(
                        "Search for vocabulary by Chinese characters, pinyin, or English meaning. "
                        "Can optionally filter by HSK level."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search_term": {
                                "type": "string",
                                "description": "Search query (Chinese, pinyin, or English)"
                            },
                            "hsk_level": {
                                "type": "integer",
                                "description": "Optional HSK level filter (1-6)",
                                "minimum": 1,
                                "maximum": 6
                            }
                        },
                        "required": ["search_term"]
                    }
                ),
                Tool(
                    name="get_vocabulary_statistics",
                    description=(
                        "Get detailed statistics about vocabulary in the database, "
                        "including total counts, HSK distribution, and learning progress."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="take_quiz",
                    description=(
                        "Generate and take a quiz to test vocabulary knowledge. "
                        "Specify HSK level and number of questions. The quiz will test "
                        "Chinese-to-English translation."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hsk_level": {
                                "type": "integer",
                                "description": "HSK level to quiz on (1-6)",
                                "minimum": 1,
                                "maximum": 6
                            },
                            "num_questions": {
                                "type": "integer",
                                "description": "Number of quiz questions",
                                "minimum": 1,
                                "maximum": 20,
                                "default": 5
                            }
                        },
                        "required": ["hsk_level"]
                    }
                ),
                Tool(
                    name="submit_quiz_answers",
                    description=(
                        "Submit answers to a quiz and get results. "
                        "Provide the quiz ID and a list of answers."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "quiz_id": {
                                "type": "string",
                                "description": "ID of the quiz being answered"
                            },
                            "answers": {
                                "type": "array",
                                "description": "List of user's answers",
                                "items": {
                                    "type": "string"
                                }
                            }
                        },
                        "required": ["quiz_id", "answers"]
                    }
                ),
                Tool(
                    name="get_quiz_history",
                    description=(
                        "Get the history of past quiz attempts with scores and dates."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "minimum": 1,
                                "maximum": 50,
                                "default": 10
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="export_to_anki",
                    description=(
                        "Export learned vocabulary to a CSV file suitable for importing into Anki. "
                        "Can filter by HSK level or export all learned vocabulary."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "hsk_level": {
                                "type": "integer",
                                "description": "HSK level to export (optional, exports all if not specified)",
                                "minimum": 1,
                                "maximum": 6
                            },
                            "filename": {
                                "type": "string",
                                "description": "Output filename for the CSV",
                                "default": "mandarin_vocabulary.csv"
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="clear_progress",
                    description=(
                        "Clear all learning progress and start fresh. "
                        "WARNING: This deletes all progress tracking data but keeps vocabulary intact."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "confirm": {
                                "type": "boolean",
                                "description": "Must be true to confirm deletion"
                            }
                        },
                        "required": ["confirm"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            """
            Handle tool calls from Claude.
            
            Args:
                name: Tool name
                arguments: Dictionary of arguments for the tool
            
            Returns:
                List of text content responses
            """
            try:
                if name == "get_progress_stats":
                    return await self._handle_get_progress_stats()
                
                elif name == "learn_vocabulary":
                    return await self._handle_learn_vocabulary(arguments)
                
                elif name == "get_vocabulary_by_level":
                    return await self._handle_get_vocabulary_by_level(arguments)
                
                elif name == "search_vocabulary":
                    return await self._handle_search_vocabulary(arguments)
                
                elif name == "get_vocabulary_statistics":
                    return await self._handle_get_vocabulary_statistics()
                
                elif name == "take_quiz":
                    return await self._handle_take_quiz(arguments)
                
                elif name == "submit_quiz_answers":
                    return await self._handle_submit_quiz_answers(arguments)
                
                elif name == "get_quiz_history":
                    return await self._handle_get_quiz_history(arguments)
                
                elif name == "export_to_anki":
                    return await self._handle_export_to_anki(arguments)
                
                elif name == "clear_progress":
                    return await self._handle_clear_progress(arguments)
                
                else:
                    return [TextContent(
                        type="text",
                        text=f"Unknown tool: {name}"
                    )]
            
            except Exception as e:
                logger.error(f"Error handling tool {name}: {e}", exc_info=True)
                return [TextContent(
                    type="text",
                    text=f"Error: {str(e)}"
                )]
    
    async def _handle_get_progress_stats(self) -> list[TextContent]:
        """Handle get_progress_stats tool call."""
        stats = await self.db.get_progress_stats()
        
        response = f"""📊 **Learning Progress Statistics**

📚 **Words Studied:** {stats['total_words_studied']}
📝 **Total Reviews:** {stats['total_reviews']}
✅ **Accuracy:** {stats['accuracy']}%
✓ **Correct Answers:** {stats['total_correct']}
✗ **Incorrect Answers:** {stats['total_incorrect']}

🎯 **Mastery Breakdown:**
"""
        
        mastery_labels = {
            0: "New/Struggling",
            1: "Learning", 
            2: "Familiar",
            3: "Comfortable",
            4: "Good",
            5: "Mastered"
        }
        
        for level, count in sorted(stats['mastery_breakdown'].items()):
            label = mastery_labels.get(level, f"Level {level}")
            response += f"  {label}: {count} words\n"
        
        return [TextContent(type="text", text=response)]
    
    async def _handle_learn_vocabulary(self, arguments: dict) -> list[TextContent]:
        """Handle learn_vocabulary tool call."""
        hsk_level = arguments.get("hsk_level")
        count = arguments.get("count", 5)
        
        # Get new vocabulary that the user hasn't seen yet
        vocab_list = await self.vocab_manager.get_new_vocabulary(
            hsk_level=hsk_level, 
            count=count,
            exclude_learned=True
        )
        
        if not vocab_list:
            return [TextContent(
                type="text",
                text=f"Great! You've already seen all HSK {hsk_level} vocabulary. Try a higher level or review existing words."
            )]
        
        response = f"📖 **Learning New HSK {hsk_level} Vocabulary** ({len(vocab_list)} words)\n\n"
        response += self.vocab_manager.format_vocabulary_for_display(vocab_list, include_progress=False)
        response += "\n\n💡 **Tip:** Practice these words and then take a quiz to test your knowledge!"
        
        return [TextContent(type="text", text=response)]
    
    async def _handle_get_vocabulary_by_level(self, arguments: dict) -> list[TextContent]:
        """Handle get_vocabulary_by_level tool call."""
        hsk_level = arguments.get("hsk_level")
        limit = arguments.get("limit", 10)
        
        vocab_list = await self.db.get_vocabulary_by_hsk_level(hsk_level, limit=limit)
        
        if not vocab_list:
            return [TextContent(
                type="text",
                text=f"No vocabulary found for HSK {hsk_level}."
            )]
        
        response = f"📚 **HSK {hsk_level} Vocabulary** (showing {len(vocab_list)} words)\n\n"
        response += self.vocab_manager.format_vocabulary_for_display(vocab_list, include_progress=False)
        
        return [TextContent(type="text", text=response)]
    
    async def _handle_search_vocabulary(self, arguments: dict) -> list[TextContent]:
        """Handle search_vocabulary tool call."""
        search_term = arguments.get("search_term")
        hsk_level = arguments.get("hsk_level")
        
        results = await self.vocab_manager.search_vocabulary(search_term, hsk_level)
        
        if not results:
            return [TextContent(
                type="text",
                text=f"No vocabulary found matching '{search_term}'."
            )]
        
        hsk_filter = f" (HSK {hsk_level})" if hsk_level else ""
        response = f"🔍 **Search Results for '{search_term}'{hsk_filter}** ({len(results)} words)\n\n"
        response += self.vocab_manager.format_vocabulary_for_display(results, include_progress=False)
        
        return [TextContent(type="text", text=response)]
    
    async def _handle_get_vocabulary_statistics(self) -> list[TextContent]:
        """Handle get_vocabulary_statistics tool call."""
        stats = await self.vocab_manager.get_vocabulary_statistics()
        
        response = f"""📊 **Vocabulary Database Statistics**

📚 **Total Vocabulary:** {stats['total_vocabulary']} words
✅ **Learned:** {stats['learned_vocabulary']} words
🆕 **New/Unseen:** {stats['new_vocabulary']} words

**HSK Level Distribution:**
"""
        
        for level in range(1, 7):
            count = stats['hsk_level_counts'].get(level, 0)
            if count > 0:
                bar = "█" * min(count // 10, 50)  # Visual bar
                response += f"  HSK {level}: {count} words {bar}\n"
        
        response += "\n**Word Types:**\n"
        for word_type, count in sorted(stats['word_type_counts'].items(), key=lambda x: x[1], reverse=True)[:10]:
            response += f"  {word_type.capitalize()}: {count}\n"
        
        return [TextContent(type="text", text=response)]
    
    async def _handle_take_quiz(self, arguments: dict) -> list[TextContent]:
        """Handle take_quiz tool call."""
        hsk_level = arguments.get("hsk_level")
        num_questions = arguments.get("num_questions", 5)
        
        try:
            # Generate a translation quiz (Chinese to English)
            quiz = await self.quiz_manager.generate_translation_quiz(
                hsk_level=hsk_level,
                num_questions=num_questions,
                direction="chinese_to_english"
            )
            
            response = self.quiz_manager.format_quiz_for_display(quiz)
            response += f"\n\n**Quiz ID:** `{quiz.quiz_id}`"
            response += "\n\n📝 **To submit:** Use the `submit_quiz_answers` tool with this quiz ID and your answers as a list."
            response += f"\n\n💡 **Note:** All questions include pinyin to help with pronunciation."
            
            return [TextContent(type="text", text=response)]
        
        except Exception as e:
            logger.error(f"Error generating quiz: {e}", exc_info=True)
            return [TextContent(
                type="text",
                text=f"Error generating quiz: {str(e)}"
            )]
    
    async def _handle_submit_quiz_answers(self, arguments: dict) -> list[TextContent]:
        """Handle submit_quiz_answers tool call."""
        quiz_id = arguments.get("quiz_id")
        answers = arguments.get("answers")
        
        try:
            results = await self.quiz_manager.submit_quiz(quiz_id, answers)
            response = self.quiz_manager.format_results_for_display(results)
            
            return [TextContent(type="text", text=response)]
        
        except ValueError as e:
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {str(e)}"
            )]
    
    async def _handle_get_quiz_history(self, arguments: dict) -> list[TextContent]:
        """Handle get_quiz_history tool call."""
        limit = arguments.get("limit", 10)
        history = await self.db.get_quiz_history(limit=limit)
        
        if not history:
            return [TextContent(
                type="text",
                text="No quiz history found. Take a quiz to get started!"
            )]
        
        response = f"📜 **Quiz History** (last {len(history)} quizzes)\n\n"
        
        for quiz in history:
            hsk_info = f"HSK {quiz['hsk_level']}" if quiz['hsk_level'] else "Mixed"
            score = quiz['score_percentage']
            
            # Add emoji based on score
            if score >= 90:
                emoji = "🌟"
            elif score >= 70:
                emoji = "✅"
            elif score >= 50:
                emoji = "📝"
            else:
                emoji = "📚"
            
            response += f"{emoji} **{hsk_info}** - {quiz['correct_answers']}/{quiz['total_questions']} ({score}%)\n"
            response += f"   Type: {quiz['quiz_type']} | Date: {quiz['created_at']}\n\n"
        
        return [TextContent(type="text", text=response)]
    
    async def _handle_export_to_anki(self, arguments: dict) -> list[TextContent]:
        """Handle export_to_anki tool call."""
        # This will be implemented in Stage 6 with the anki_export module
        return [TextContent(
            type="text",
            text="Anki export functionality will be implemented in the next stage."
        )]
    
    async def _handle_clear_progress(self, arguments: dict) -> list[TextContent]:
        """Handle clear_progress tool call."""
        confirm = arguments.get("confirm", False)
        
        if not confirm:
            return [TextContent(
                type="text",
                text="⚠️  Progress clearing cancelled. Set 'confirm' to true to proceed."
            )]
        
        await self.db.clear_all_progress()
        
        return [TextContent(
            type="text",
            text="✅ All learning progress has been cleared. Vocabulary remains intact. You can start fresh!"
        )]
    
    async def run(self) -> None:
        """Run server."""
        # Connect to database
        await self.db.connect()
        await self.db.initialise_schema()
        logger.info("Database connected and initialised")
        
        # Run server using stdio transport
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server starting...")
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point for server."""
    server = MandarinMCPServer()
    await server.run()


# Allow running directly with: python -m mandarin_mcp_server.server
if __name__ == "__main__":
    asyncio.run(main())
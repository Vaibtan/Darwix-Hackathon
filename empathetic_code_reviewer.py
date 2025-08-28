# DSPy-powered solution that transforms critical code review feedback into constructive, educational guidance
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import dspy
from dotenv import load_dotenv

load_dotenv()

LM_TEMPERATURE = float(os.getenv("LM_TEMPERATURE", "0.4"))
MAX_TOKENS = int(os.getenv("LM_MAX_TOKENS", "2048"))

logging.basicConfig(level = logging.INFO, \
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers = \
        [logging.FileHandler('empathetic_reviewer.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

@dataclass
class ReviewComment:
    original: str
    positive_rephrasing: str
    why_explanation: str
    suggested_improvement: str
    severity: str
    resources: Optional[List[str]] = None
    
class LanguageDetector:    
    LANGUAGE_PATTERNS = {
        "Python": [
            r'\bdef\s+\w+\s*\(',
            r'\bimport\s+\w+',
            r'\bfrom\s+\w+\s+import',
            r'\bclass\s+\w+',
            r'\bif\s+.*:',
            r'\bfor\s+.*\s+in\s+',
            r'\bwhile\s+.*:',
            r'@\w+', 
            r'\bprint\s*\(',
            r'\.py\b',
        ],
        "JavaScript": [
            r'\bfunction\s+\w+\s*\(',
            r'\bconst\s+\w+\s*=',
            r'\blet\s+\w+\s*=',
            r'\bvar\s+\w+\s*=',
            r'\b=>\s*{',
            r'\bconsole\.log',
            r'\bdocument\.getElementById',
            r'\brequire\s*\(',
            r'\.js\b',
        ],
        "Java": [
            r'\bpublic\s+class\s+\w+',
            r'\bprivate\s+\w+\s+\w+',
            r'\bpublic\s+static\s+void\s+main',
            r'\bSystem\.out\.println',
            r'\bimport\s+java\.',
            r'\bextends\s+\w+',
            r'\bimplements\s+\w+',
            r'@Override',
            r'\.java\b',
        ],
        "C++": [
            r'#include\s*<.*>',
            r'\bint\s+main\s*\(',
            r'\bstd::',
            r'\bcout\s*<<',
            r'\bcin\s*>>',
            r'\bnamespace\s+\w+',
            r'\.cpp\b|\.hpp\b',
        ],
        "C#": [
            r'\busing\s+\w+;',
            r'\bnamespace\s+\w+',
            r'\bpublic\s+class\s+\w+',
            r'\bConsole\.WriteLine',
            r'\bstring\s*\[',
            r'\.cs\b',
        ],
        "TypeScript": [
            r'\binterface\s+\w+',
            r'\btype\s+\w+\s*=',
            r':\s*\w+\s*=',
            r'\bexport\s+interface',
            r'\.ts\b|\.tsx\b',
        ],
        "Go": [
            r'\bpackage\s+\w+',
            r'\bfunc\s+\w+\s*\(',
            r'\bimport\s+\(',
            r'\bvar\s+\w+\s+\w+',
            r'\.go\b',
        ],
        "Rust": [
            r'\bfn\s+\w+\s*\(',
            r'\blet\s+mut\s+\w+',
            r'\buse\s+\w+',
            r'\bimpl\s+\w+',
            r'\.rs\b',
        ]
    }
    
    def __init__(self, lm_instance = None) -> None:
        # Initialize with optional LM instance for fallback detection
        self.lm = lm_instance
    
    @classmethod
    def detect_language_regex(self, code: str) -> str:
        if not code or not code.strip(): return "Unknown"
        scores = {}
        for language, patterns in self.LANGUAGE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = re.findall(pattern, code, re.IGNORECASE | re.MULTILINE)
                score += len(matches)
            scores[language] = score
        # return language with highest score, or "Unknown" if no matches
        if not scores or max(scores.values()) == 0: return "Unknown"
        best_language = max(scores, key = scores.get)
        return best_language
    
    @classmethod
    def detect_language_llm(self, code: str) -> str:
        if not self.lm: return "Unknown"
        try:
            prompt = f"""
            Analyze the following code snippet and identify the programming language.
            Respond with only the language name (e.g., "Python", "JavaScript", "Java", "C++", "C#", "TypeScript", "Go", "Rust").
            If you cannot determine the language, respond with "Unknown".
            Code:
            ```
            {code}
            ```
            """ 
            response = self.lm(prompt)
            language = response.strip()
            known_languages = list(self.LANGUAGE_PATTERNS.keys()) + ["Unknown"]
            if language in known_languages: return language
            else: return "Unknown"  
        except Exception as e:
            logger.warning(f"LLM language detection failed: {e}")
            return "Unknown"

    def detect_language(self, code: str) -> str:
        # Detect programming language with regex first, LLM fallback.        
        language = self.detect_language_regex(code)
        if language == "Unknown" and self.lm:
            logger.info("Regex detection failed, falling back to LLM")
            language = self.detect_language_llm(code)
        return language
    
class EmpathySignature(dspy.Signature):
    # transforming harsh feedback into empathetic guidance
    code_snippet = dspy.InputField(desc = "The code being reviewed")
    harsh_comment = dspy.InputField(desc = "The original critical comment")
    context = dspy.InputField(desc = "Programming language and context")
    positive_rephrasing = dspy.OutputField(desc = "Gentle, encouraging version that acknowledges effort and guides improvement")
    why_explanation = dspy.OutputField(desc = "Clear explanation of the underlying principle (performance, readability, etc.)")
    suggested_improvement = dspy.OutputField(desc = "Concrete code example demonstrating the fix")
    severity_level = dspy.OutputField(desc = "LOW, MEDIUM, or HIGH based on impact")

class ResourceFinderSignature(dspy.Signature):
    # finding relevant learning resources
    topic = dspy.InputField(desc = "The programming concept or issue")
    language = dspy.InputField(desc = "Programming language")
    resources = dspy.OutputField(desc = "List of 2-3 relevant documentation links or articles")

class HolisticSummarySignature(dspy.Signature):
    # creating an encouraging overall summary
    code_snippet = dspy.InputField(desc = "The original code")
    all_feedback = dspy.InputField(desc = "All the transformed feedback points")
    language = dspy.InputField(desc="Programming language")
    summary = dspy.OutputField(desc = "Encouraging paragraph that synthesizes feedback and motivates growth")

class EmpathyAnalyzer(dspy.Module):
    # Analyzes code review comments and transforms them empathetically
    def __init__(self):
        super().__init__()
        self.empathy_transformer = dspy.ChainOfThought(EmpathySignature)
        self.resource_finder = dspy.ChainOfThought(ResourceFinderSignature)
        self.summary_generator = dspy.ChainOfThought(HolisticSummarySignature)

    def forward(self, code_snippet: str, comment: str, language: str = "Python"):
        # Transform a single comment into empathetic feedback
        try:
            result = self.empathy_transformer(code_snippet = code_snippet, \
                harsh_comment = comment, context = f"{language} best practices and clean code principles")
            resources = self.resource_finder(topic = result.why_explanation[:100], language = language)
            return { "positive_rephrasing": result.positive_rephrasing, \
                "explanation": result.why_explanation, "suggested_improvement": result.suggested_improvement, \
                    "severity": result.severity_level, "resources": resources.resources }
        except Exception as e:
            logger.error(f"Error in empathy analysis: {e}")


class EmpatheticCodeReviewer:
    def __init__(self):
        try:
            self.lm = dspy.LM(model = "openrouter/google/gemini-2.0-flash-001", \
                api_base="https://openrouter.ai/api/v1", \
                    api_key = os.getenv("OPENROUTER_API_KEY"), \
                        temperature = LM_TEMPERATURE, max_tokens = MAX_TOKENS)
            dspy.settings.configure(lm = self.lm)
            logger.info("Successfully initialized language model")
        except Exception as e:
            logger.error(f"Failed to initialize language model: {e}")
            raise
        self.analyzer = EmpathyAnalyzer()
        self.language_detector = LanguageDetector(self.lm)

    def process_review(self, input_data: Dict[str, Any]) -> str:
        code_snippet = input_data["code_snippet"]
        review_comments = input_data["review_comments"]
        language = self.language_detector.detect_language(code_snippet)
        logger.info(f"Detected language: {language}")
        # Process each comment
        transformed_comments = []
        for i, comment in enumerate(review_comments):
            logger.info(f"Processing comment {i + 1}/{len(review_comments)}")
            try:
                result = self.analyzer.forward(code_snippet, comment, language)
                transformed_comments.append({ "original": comment, **result })
            except Exception as e:
                logger.error(f"Error processing comment '{comment}': {e}")
                transformed_comments.append({
                    "original": comment,
                    "positive_rephrasing": f"Let's look at improving this aspect: {comment}",
                    "explanation": "This change will improve code quality.",
                    "suggested_improvement": "# See suggested improvement in code",
                    "severity": "MEDIUM",
                    "resources": []
                })
        all_feedback = "\n".join([f"- {tc['positive_rephrasing']}" for tc in transformed_comments])
        try:
            summary_result = self.analyzer.summary_generator(code_snippet=code_snippet, \
                all_feedback = all_feedback, language = language)
            summary = summary_result.summary
        except Exception as e:
            logger.error(f"Error generating summary: {e}")            
        report = self.generate_markdown_report(code_snippet, \
            transformed_comments, summary, language)  
        logger.info("Successfully generated empathetic review report")
        return report
            
    def generate_markdown_report(self, code_snippet: str, \
        comments: List[Dict], summary: str, language: str) -> str:
        # Generate a well-formatted markdown report
        report = "# 🌟 Code Review Feedback Report\n\n"
        report += f"**Programming Language Detected:** {language}\n\n"
        report += "## 📝 Original Code\n\n"        
        lang_map = {
            "Python": "python",
            "JavaScript": "javascript", 
            "Java": "java",
            "C++": "cpp",
            "C#": "csharp",
            "TypeScript": "typescript",
            "Go": "go",
            "Rust": "rust",
            "Unknown": "text"
        }
        code_lang = lang_map.get(language, "text")
        report += f"```{code_lang}\n{code_snippet}\n```\n\n"
        report += "## 💡 Detailed Feedback\n\n"  
        # Sort comments by severity for better organization
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        comments.sort(key=lambda x: severity_order.get(x.get("severity", "MEDIUM"), 1))
        
        for i, comment in enumerate(comments, 1):
            severity_emoji = {
                "HIGH": "🔴",
                "MEDIUM": "🟡", 
                "LOW": "🟢"
            }.get(comment.get("severity", "MEDIUM"), "🟡")
            
            report += "---\n\n"
            report += f"### {severity_emoji} Analysis of Comment #{i}: \"{comment['original']}\"\n\n"
            report += f"**✨ Positive Rephrasing:**\n{comment['positive_rephrasing']}\n\n"
            report += f"**📚 The 'Why':**\n{comment['explanation']}\n\n"
            report += f"**🔧 Suggested Improvement:**\n```{code_lang}\n{comment['suggested_improvement']}\n```\n\n"
            
            # Handle resources more robustly
            resources = comment.get("resources", [])
            if resources:
                report += "**📖 Learning Resources:**\n"
                if isinstance(resources, str):
                    # Parse resource links from string
                    resource_lines = [line.strip() for line in resources.split('\n') if line.strip()]
                    for line in resource_lines:
                        report += f"- {line}\n"
                elif isinstance(resources, list):
                    for resource in resources:
                        if resource and resource.strip():
                            report += f"- {resource.strip()}\n"
                report += "\n"
        
        report += "---\n\n"
        report += "## 🎯 Overall Summary\n\n"
        report += f"{summary}\n\n"
        report += "---\n\n"
        report += "*Remember: Every expert was once a beginner. Keep coding, keep learning, and keep growing! 🚀*\n"
        return report

def main():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Please set OPENROUTER_API_KEY environment variable")
        sys.exit(1)
    example_input = {
        "code_snippet": """def get_active_users(users):
    results = []
    for u in users:
        if u.is_active == True and u.profile_complete == True:
            results.append(u)
    return results""",
        "review_comments": [
            "This is inefficient. Don't loop twice conceptually.",
            "Variable 'u' is a bad name.", 
            "Boolean comparison '== True' is redundant."
        ]
    }
    
    try:
        reviewer = EmpatheticCodeReviewer()
        logger.info("Processing code review...")
        
        report = reviewer.process_review(example_input)
        print("\n" + report)
        
        # Save report to file
        with open("empathetic_review_output.md", "w", encoding="utf-8") as f:
            f.write(report)
        
        print("\n✅ Report saved to empathetic_review_output.md")
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__": main()
import os
from typing import Dict, Any

class NotesAgent:
    """
    NotesAgent:
    Dynamically recommends study or preparation materials based on the event subject/title.
    """
    def __init__(self, secrets_loader):
        self.secrets = secrets_loader

    def recommend_notes(self, subject: str, event_title: str) -> Dict[str, Any]:
        """
        Return recommended note files and key review topics based on the subject or title.
        """
        term = (subject or event_title or "General").strip()
        term_lower = term.lower()

        if "ai" in term_lower or "artificial intelligence" in term_lower or "neural" in term_lower:
            files = ["AI_Course_Summary.pdf", "Viva_Prep_Questions.md"]
            topics = ["Neural Networks", "Search Algorithms", "Machine Learning"]
        elif "data mining" in term_lower or "mining" in term_lower or "dm" in term_lower:
            files = ["Data_Mining_Course_Summary.pdf", "Data_Mining_Prep_Questions.md"]
            topics = ["Association Rules", "Clustering", "Decision Trees"]
        elif "math" in term_lower or "calculus" in term_lower or "algebra" in term_lower:
            files = ["Math_Formula_Sheet.pdf", "Calculus_Prep_Questions.md"]
            topics = ["Derivatives", "Integrals", "Linear Algebra"]
        elif "physics" in term_lower:
            files = ["Physics_Equations_Guide.pdf", "Physics_Lab_Manual.md"]
            topics = ["Classical Mechanics", "Electromagnetism", "Thermodynamics"]
        elif "coding" in term_lower or "programming" in term_lower or "software" in term_lower:
            files = ["Coding_Interview_Cheat_Sheet.pdf", "Algorithms_Questions.md"]
            topics = ["Data Structures", "Big O Notation", "System Design"]
        else:
            # Generate filenames dynamically to generalize to any subject name
            safe_name = term.replace(" ", "_")
            files = [f"{safe_name}_Summary.pdf", f"{safe_name}_Prep_Guide.md"]
            topics = [f"Core concepts of {term}", "Important terms", "Review exercises"]

        return {
            "files": files,
            "topics": topics,
            "message": f"Found {', '.join([f'\'{f}\'' for f in files])} in your files. Recommended reviewing {', '.join([f'\'{t}\'' for t in topics])}."
        }

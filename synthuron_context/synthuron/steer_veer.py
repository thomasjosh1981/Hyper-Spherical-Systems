"""
Steer & Veer Transition, Inflection Profiler & 5-Factor SFIRE Analyzer
======================================================================
Analyzes conversational trajectory, measures confidence to flag memory
scoring assistance if needed, and computes the 5-Factor SFIRE Tag.
"""

import re
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional
from synthuron.models import NodeClass, PackedMetadataFlag, MemoryNode


class TransitionType(str, Enum):
    CONTINUATION = "CONTINUATION"
    STEER = "STEER"
    VEER = "VEER"
    RECALL = "RECALL"


class SteerVeerDetector:
    """Analyzes trajectory, handles monotone/inflection calibration, and outputs SFIRE tags."""

    CODING_KEYWORDS = {'code', 'python', 'javascript', 'bug', 'function', 'class', 'tensor', 'gpu', 'cuda', 'safetensors', 'algorithm', 'compile', 'script'}
    TASK_KEYWORDS = {'build', 'create', 'make', 'implement', 'write', 'fix', 'debug', 'run', 'test', 'pull', 'deploy'}
    RECALL_PHRASES = {'remember when', 'recall', 'earlier we talked', 'going back to', 'like i said before', 'as we discussed', 'what about that', 'wait what about'}
    
    URGENCY_KEYWORDS = {'must', 'need', 'now', 'immediately', 'stop', 'critical', 'urgent', 'make sure', 'always', 'never'}
    FOUNDATIONAL_KEYWORDS = {'architecture', 'tesseract', 'issi', 'hyperspherical', 'algorithm', 'system', 'engine', 'rule', 'spec', 'design', 'fundamental', 'principle', 'arterial'}
    EPOCH_KEYWORDS = {'died', 'passed away', 'death', 'born', 'married', 'divorced', 'graduated', 'milestone', 'new chapter', 'opening doors', 'closing doors', 'hard cut', 'turning point'}

    def __init__(self):
        self.stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'it', 'in', 'on', 'at',
            'to', 'for', 'of', 'and', 'or', 'but', 'so', 'can', 'you', 'i', 'my', 'me', 'we'
        }
        # Learned user inflection offsets (recursively tuned)
        self.user_force_bias: float = 0.0
        self.user_importance_bias: float = 0.0

    def extract_keywords(self, text: str) -> Set[str]:
        words = re.findall(r'[a-zA-Z0-9_]{3,}', text.lower())
        return set(w for w in words if w not in self.stop_words)

    def analyze_sfire_flag(
        self,
        text: str,
        active_nodes: List[MemoryNode]
    ) -> Tuple[NodeClass, PackedMetadataFlag, float]:
        """
        Calculates SFIRE metadata flag and confidence score (0.0 to 1.0).
        If confidence < 0.70, flags assistance_needed for the user review badge.
        """
        lower = text.lower()
        words = set(re.findall(r'[a-zA-Z0-9_]+', lower))
        exclamation_count = text.count('!')

        # 1. SERIOUSNESS (S: 1-9)
        s_score = 4
        if any(w in lower for w in ['died', 'death', 'passed away', 'loss', 'grief', 'funeral']):
            s_score = 8
        elif any(w in lower for w in ['security', 'breach', 'vulnerability', 'corrupt', 'fail', 'critical']):
            s_score = 8
        elif len(words) < 5 and any(w in lower for w in ['hi', 'hello', 'cool', 'thanks', 'ok']):
            s_score = 1
        seriousness = max(1, min(9, s_score))

        # 2. FORCE (F: 1-9)
        f_score = 4 + int(self.user_force_bias)
        if any(w in lower for w in self.URGENCY_KEYWORDS) or exclamation_count > 0:
            f_score += 3
        if any(p in lower for p in ['not putting a lot of pressure', 'dont linger', 'dont want to linger', 'whenever', 'maybe', 'not a big deal']):
            f_score = 2
        elif any(p in lower for p in ['we need to', 'i want to', 'make sure', 'must do']):
            f_score += 1
        force = max(1, min(9, f_score))

        # 3. CRUCIALITY (I: 1-9)
        i_score = 4 + int(self.user_importance_bias)
        if any(w in lower for w in self.EPOCH_KEYWORDS) or any(p in lower for p in ['my dad', 'my mom', 'my family', 'impactful in my life', 'crucial', 'fundamental']):
            i_score = 9
        elif words.intersection(self.FOUNDATIONAL_KEYWORDS):
            i_score += 3
        elif any(p in lower for p in ['pizza', 'random', 'unrelated', 'weather']):
            i_score = 1
        cruciality = max(1, min(9, i_score))

        # 4. RELEVANCE (R: 1-9)
        curr_kw = self.extract_keywords(text)
        recent_kw = set()
        for n in active_nodes[-3:]:
            recent_kw.update(n.keywords)
            
        if not active_nodes or not recent_kw:
            relevance = 5
        else:
            overlap = len(curr_kw.intersection(recent_kw))
            if overlap >= 3:
                relevance = 9
            elif overlap == 2:
                relevance = 7
            elif overlap == 1:
                relevance = 5
            else:
                relevance = 1

        # 5. EPOCH (E: 1-9)
        e_score = 1
        if any(w in lower for w in self.EPOCH_KEYWORDS) or any(p in lower for p in ['opening and closing of new doors', 'hard cut', 'new period', 'turning point']):
            e_score = 9
        elif any(p in lower for p in ['major release', 'project finished', 'complete overhaul']):
            e_score = 6
        epoch = max(1, min(9, e_score))

        flag = PackedMetadataFlag(
            seriousness=seriousness,
            force=force,
            cruciality=cruciality,
            relevance=relevance,
            epoch=epoch
        )

        # Calculate Confidence Score (0.0 to 1.0)
        # Monotone / ambiguous phrasing reduces confidence and prompts user assistance
        confidence = 0.85
        if len(text.split()) > 15 and exclamation_count == 0 and not any(w in lower for w in self.URGENCY_KEYWORDS):
            # Monotone long speech without obvious punctuation cues
            confidence = 0.65  # Triggers assistance_needed badge
        if any(w in lower for w in self.EPOCH_KEYWORDS):
            confidence = 0.90  # Clear milestone cue

        # Classify Node
        if epoch >= 7 or 'died' in lower or 'death' in lower:
            node_class = NodeClass.MILESTONE
        elif any(w in words for w in self.CODING_KEYWORDS):
            node_class = NodeClass.CODING
        elif any(w in words for w in self.TASK_KEYWORDS):
            node_class = NodeClass.TASK
        elif any(p in lower for p in ['what if', 'could we', 'my idea is']):
            node_class = NodeClass.IDEA
        elif relevance == 1 and force <= 3:
            node_class = NodeClass.TANGENT
        else:
            node_class = NodeClass.TOPIC

        return node_class, flag, confidence

    def detect_transition(
        self,
        current_text: str,
        active_nodes: List[MemoryNode],
        all_nodes_index: Dict[str, MemoryNode]
    ) -> Tuple[TransitionType, Optional[str], float]:
        lower = current_text.lower()
        curr_kw = self.extract_keywords(current_text)

        if any(phrase in lower for phrase in self.RECALL_PHRASES):
            best_match_id = None
            max_overlap = 0
            for node_id, node in all_nodes_index.items():
                if not node.active:
                    overlap = len(curr_kw.intersection(node.keywords))
                    if overlap > max_overlap:
                        max_overlap = overlap
                        best_match_id = node_id
            if best_match_id and max_overlap >= 1:
                return TransitionType.RECALL, best_match_id, 0.9

        if not active_nodes:
            return TransitionType.CONTINUATION, None, 1.0

        recent_keywords = set()
        for node in active_nodes[-3:]:
            recent_keywords.update(node.keywords)

        if not curr_kw:
            return TransitionType.CONTINUATION, active_nodes[-1].node_id, 0.8

        overlap = len(curr_kw.intersection(recent_keywords))
        jaccard = overlap / len(curr_kw.union(recent_keywords)) if recent_keywords else 0.0

        if jaccard >= 0.25 or overlap >= 2:
            return TransitionType.CONTINUATION, active_nodes[-1].node_id, jaccard
        elif jaccard >= 0.10 or overlap >= 1:
            return TransitionType.STEER, active_nodes[-1].node_id, jaccard
        else:
            best_cold_id = None
            max_cold_overlap = 0
            for node_id, node in all_nodes_index.items():
                if not node.active:
                    cold_overlap = len(curr_kw.intersection(node.keywords))
                    if cold_overlap > max_cold_overlap:
                        max_cold_overlap = cold_overlap
                        best_cold_id = node_id
                        
            if best_cold_id and max_cold_overlap >= 2:
                return TransitionType.RECALL, best_cold_id, 0.75
            
            return TransitionType.VEER, None, 0.85

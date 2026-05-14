"""
NLP Analyzer - Uses spaCy for linguistic analysis
Detects: compound nouns, passive voice, vague pronouns, sentence length
"""
import spacy

# Load model once
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = None


class NLPAnalyzer:
    """Linguistic analysis for translation readiness."""

    # Vague/generic verbs that cause translation ambiguity
    VAGUE_VERBS = {"do", "make", "get", "take", "put", "go", "have", "run", "set"}

    # Pronouns that are problematic for German (gender-dependent)
    VAGUE_PRONOUNS = {"this", "it", "that", "these", "those", "which"}

    def __init__(self):
        if nlp is None:
            raise RuntimeError("spaCy model not loaded. Run: python -m spacy download en_core_web_sm")
        self.nlp = nlp

    def analyze(self, text: str) -> dict:
        """
        Full NLP analysis of text.
        
        Returns:
            {
                "compounds": [...],
                "passive_voice": [...],
                "vague_pronouns": [...],
                "vague_verbs": [...],
                "long_sentences": [...],
                "sentence_count": int,
                "word_count": int
            }
        """
        doc = self.nlp(text)

        return {
            "compounds": self._detect_compounds(doc),
            "passive_voice": self._detect_passive(doc),
            "vague_pronouns": self._detect_vague_pronouns(doc),
            "vague_verbs": self._detect_vague_verbs(doc),
            "long_sentences": self._detect_long_sentences(doc),
            "sentence_count": len(list(doc.sents)),
            "word_count": len([t for t in doc if not t.is_punct and not t.is_space])
        }

    def _detect_compounds(self, doc) -> list:
        """
        Detect noun compound chains (3+ consecutive nouns).
        These are problematic because German reverses compound direction.
        """
        compounds = []
        noun_chain = []

        for token in doc:
            if token.pos_ in ("NOUN", "PROPN"):
                noun_chain.append(token)
            else:
                if len(noun_chain) >= 3:
                    compound_text = " ".join(t.text for t in noun_chain)
                    compounds.append({
                        "text": compound_text,
                        "count": len(noun_chain),
                        "start": noun_chain[0].idx,
                    })
                noun_chain = []

        # Check last chain
        if len(noun_chain) >= 3:
            compound_text = " ".join(t.text for t in noun_chain)
            compounds.append({
                "text": compound_text,
                "count": len(noun_chain),
                "start": noun_chain[0].idx,
            })

        return compounds

    def _detect_passive(self, doc) -> list:
        """Detect passive voice constructions."""
        passives = []

        for token in doc:
            if token.dep_ == "nsubjpass" or (token.dep_ == "auxpass"):
                # Find the full passive construction
                verb = token.head
                aux = [t for t in verb.children if t.dep_ == "auxpass"]
                if aux or token.dep_ == "nsubjpass":
                    sent = token.sent
                    passives.append({
                        "text": verb.text,
                        "sentence": sent.text.strip(),
                    })

        # Deduplicate by sentence
        seen = set()
        unique = []
        for p in passives:
            if p["sentence"] not in seen:
                seen.add(p["sentence"])
                unique.append(p)

        return unique

    def _detect_vague_pronouns(self, doc) -> list:
        """
        Detect vague pronouns at sentence start.
        Problem for German: pronouns have gender, need clear antecedent.
        """
        issues = []

        for sent in doc.sents:
            tokens = [t for t in sent if not t.is_space]
            if tokens:
                first_word = tokens[0]
                if first_word.text.lower() in self.VAGUE_PRONOUNS:
                    issues.append({
                        "pronoun": first_word.text,
                        "sentence": sent.text.strip(),
                    })

        return issues

    def _detect_vague_verbs(self, doc) -> list:
        """Detect vague/generic verbs that cause translation ambiguity."""
        issues = []

        for token in doc:
            if token.pos_ == "VERB" and token.lemma_.lower() in self.VAGUE_VERBS:
                # Skip auxiliary uses
                if token.dep_ in ("aux", "auxpass"):
                    continue
                issues.append({
                    "verb": token.text,
                    "lemma": token.lemma_,
                    "sentence": token.sent.text.strip(),
                })

        return issues

    def _detect_long_sentences(self, doc) -> list:
        """Flag sentences over 30 words (German will be even longer)."""
        issues = []

        for sent in doc.sents:
            word_count = len([t for t in sent if not t.is_punct and not t.is_space])
            if word_count > 30:
                issues.append({
                    "sentence": sent.text.strip(),
                    "word_count": word_count,
                })

        return issues

    def check_compound_nouns_short(self, text: str) -> list:
        """
        Quick compound check for short UI labels (no full sentence analysis).
        Just counts consecutive nouns.
        """
        doc = self.nlp(text)
        noun_count = sum(1 for t in doc if t.pos_ in ("NOUN", "PROPN"))
        words = text.split()

        issues = []
        if noun_count >= 3 and len(words) >= 3:
            issues.append({
                "type": "compound_noun",
                "severity": "warning",
                "message": f"Noun compound ({noun_count} nouns): '{text}'",
                "suggestion": "German reverses compound order. Consider adding hyphens or prepositions for clarity.",
                "guideline": "SAP Style: Limit consecutive nouns to 2. Use prepositions for clarity."
            })

        return issues
"""Módulo introductorio público (§6.3, R1): tarjetas y mini-quiz desde `content/intro.json`."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.content.loader import load_intro
from app.core.config import Settings
from app.infra.repositories import lessons as lessons_repo
from app.schemas.intro import IntroCardOut, IntroOptionOut, IntroOut, IntroQuestionOut

DISTRACTORS = 2


class IntroService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def get_intro(self) -> IntroOut:
        spec = load_intro(self.settings.content_dir / "intro.json")
        catalog = lessons_repo.sign_catalog(self.session, {*spec.cards, *spec.quiz})
        cards = [
            IntroCardOut(slug=slug, word=catalog[slug].word, video=catalog[slug].video)
            for slug in spec.cards
        ]
        quiz: list[IntroQuestionOut] = []
        for slug in spec.quiz:
            # Distractores: las tarjetas siguientes a la seña (en ciclo), sin azar.
            others = [card for card in spec.cards if card != slug]
            start = spec.cards.index(slug) if slug in spec.cards else 0
            ordered = others[start:] + others[:start]
            options = [
                IntroOptionOut(word=catalog[other].word, correct=False)
                for other in ordered[:DISTRACTORS]
            ]
            options.append(IntroOptionOut(word=catalog[slug].word, correct=True))
            options.sort(key=lambda option: option.word)
            quiz.append(IntroQuestionOut(slug=slug, video=catalog[slug].video, options=options))
        return IntroOut(cards=cards, quiz=quiz)

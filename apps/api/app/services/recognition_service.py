"""Resultados del reconocimiento por cámara (§8.1, §8.2) y logro «Ojo de colibrí» (§7.9)."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError, unauthorized
from app.domain.dates import Clock
from app.infra.repositories import dictionary as dictionary_repo
from app.infra.repositories import lessons as lessons_repo
from app.schemas.recognition import RecognitionIn, RecognitionOut
from app.services.gamification_service import GamificationService

MIN_CONFIDENCE = 0.7
SAME_SIGN_INTERVAL = timedelta(seconds=10)

# Última vez que cada (usuario, seña) sumó. En memoria, con el Clock (D22): la app corre en un solo
# proceso (§17); si se reinicia, como mucho cuenta una vez más esa seña (D-017).
_last_counted: dict[tuple[uuid.UUID, str], datetime] = {}
_lock = threading.Lock()


def reset_recognition_memory() -> None:
    with _lock:
        _last_counted.clear()


class RecognitionService:
    def __init__(self, session: Session, clock: Clock, settings: Settings) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings

    def register_result(self, user_id: uuid.UUID, data: RecognitionIn) -> RecognitionOut:
        if dictionary_repo.get_sign(self.session, data.sign_id) is None:
            raise AppError(404, "SIGN_NOT_FOUND", "No encontramos esta seña.")
        user = lessons_repo.lock_user(self.session, user_id)
        if user is None:
            raise unauthorized()
        counted = False
        if data.correct and data.confidence >= MIN_CONFIDENCE:
            now = self.clock.now()
            key = (user_id, data.sign_id)
            with _lock:
                last = _last_counted.get(key)
                if last is None or now - last >= SAME_SIGN_INTERVAL:
                    _last_counted[key] = now
                    counted = True
        new = []
        if counted:
            user.recognitions_correct += 1
            self.session.flush()
            gamification = GamificationService(self.session, self.clock, self.settings)
            new = gamification.evaluate_achievements(user)
        return RecognitionOut(
            counted=counted,
            recognitions_correct=user.recognitions_correct,
            new_achievements=new,
        )

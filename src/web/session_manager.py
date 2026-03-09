"""In-memory DraftSession registry.

Each session wraps a DraftController and all its associated components for
one active draft. Sessions are keyed by draft_id and persist across HTTP
requests for the duration of the server process.  On a cache miss (server
restart, first load), the session is reconstructed from StatePersistence.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from src.draft_manager.draft_controller import DraftController
from src.draft_manager.draft_state import DraftState
from src.draft_manager.state_persistence import StatePersistence
from src.simulation_engine.computer_drafter import ComputerDrafter
from src.simulation_engine.monte_carlo import MonteCarloSimulator
from src.simulation_engine.pick_recommender import PickRecommender
from src.simulation_engine.vor_calculator import DynamicVORCalculator

logger = logging.getLogger(__name__)


@dataclass
class DraftSession:
    """All components needed to service a single draft's API requests."""

    draft_state: DraftState
    controller: DraftController
    vor_calculator: DynamicVORCalculator
    computer_drafter: ComputerDrafter
    mc_simulator: MonteCarloSimulator
    recommender: PickRecommender
    persistence: StatePersistence
    # Prevents concurrent pick mutations (human pick HTTP + computer task).
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionManager:
    """Global in-memory registry of active DraftSessions."""

    _sessions: Dict[str, DraftSession] = {}

    @classmethod
    def create_session(cls, draft_state: DraftState) -> DraftSession:
        """Build a DraftSession from a DraftState and register it.

        Mirrors the exact component-init order used in
        ``DraftApp._init_components()`` in the CLI.
        """
        scoring = draft_state.league_config.scoring_format
        league_size = draft_state.league_config.league_size

        controller = DraftController(draft_state)
        vor_calculator = DynamicVORCalculator(scoring, league_size)
        computer_drafter = ComputerDrafter(
            vor_calculator=vor_calculator,
            strategy="balanced",
        )
        mc_simulator = MonteCarloSimulator(
            vor_calculator=vor_calculator,
            scoring_format=scoring,
            league_size=league_size,
        )
        recommender = PickRecommender(
            vor_calculator=vor_calculator,
            mc_simulator=mc_simulator,
        )
        persistence = StatePersistence()

        session = DraftSession(
            draft_state=draft_state,
            controller=controller,
            vor_calculator=vor_calculator,
            computer_drafter=computer_drafter,
            mc_simulator=mc_simulator,
            recommender=recommender,
            persistence=persistence,
        )
        cls._sessions[draft_state.draft_id] = session
        logger.info("Created session for draft %s", draft_state.draft_id)
        return session

    @classmethod
    def get_session(cls, draft_id: str) -> Optional[DraftSession]:
        """Return a cached session, or None if not found."""
        return cls._sessions.get(draft_id)

    @classmethod
    def load_or_create(cls, draft_id: str) -> Optional[DraftSession]:
        """Return cached session or rebuild from persisted JSON on miss.

        Used after a server restart or page refresh — the JSON file still
        exists even if the in-memory session was cleared.
        """
        session = cls._sessions.get(draft_id)
        if session:
            return session

        persistence = StatePersistence()
        draft_state = persistence.load_draft(draft_id)
        if draft_state is None:
            logger.warning("Draft %s not found on disk", draft_id)
            return None

        return cls.create_session(draft_state)

    @classmethod
    def remove_session(cls, draft_id: str) -> None:
        """Remove a session from the registry (e.g. after deletion)."""
        cls._sessions.pop(draft_id, None)

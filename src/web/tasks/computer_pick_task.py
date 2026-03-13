"""Async tasks for computer pick execution.

computer_pick_chain  — animated, runs until the next human turn.
fast_sim_chain       — instant, completes the entire draft (all teams).
"""

import asyncio
import logging

from src.draft_manager.draft_rules import DraftRules, ValidationError
from src.ui.config import reach_label as _reach_label
from src.web.config import COMPUTER_PICK_DELAY_S
from src.web.schemas import PickResponse
from src.web.serializers import draft_state_to_response
from src.web.session_manager import SessionManager
from src.web.websocket.connection_manager import manager
from src.web.websocket.events import (
    build_computer_thinking_event,
    build_draft_complete_event,
    build_error_event,
    build_pick_made_event,
)

logger = logging.getLogger(__name__)


async def computer_pick_chain(draft_id: str) -> None:
    """Execute consecutive computer picks until a human turn or completion.

    Each pick is preceded by a 'computer_thinking' broadcast and followed by
    COMPUTER_PICK_DELAY_S of sleep for the animation window.
    """
    session = SessionManager.get_session(draft_id)
    if session is None:
        logger.warning("computer_pick_chain: session %s not found", draft_id)
        return

    async with session.lock:
        state = session.draft_state

        while not state.is_complete and not state.get_current_team().is_human:
            current_team = state.get_current_team()

            # Announce computer is thinking
            await manager.broadcast(
                draft_id,
                build_computer_thinking_event(
                    current_team.team_id,
                    current_team.team_name,
                    state.current_pick,
                ),
            )

            # Brief pause for animation
            await asyncio.sleep(COMPUTER_PICK_DELAY_S)

            # Get legal picks for this team
            available = session.controller.get_available_players()
            rules = DraftRules(state)
            legal = [
                p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
            ]

            if not legal:
                logger.warning(
                    "No legal picks for team %s in draft %s",
                    current_team.team_name,
                    draft_id,
                )
                await manager.broadcast(
                    draft_id,
                    build_error_event(f"No legal picks available for {current_team.team_name}"),
                )
                break

            # Computer makes its selection
            player_id = session.computer_drafter.make_pick(state, legal, current_team.team_id)

            try:
                pick = session.controller.make_pick(current_team.team_id, player_id)
            except ValidationError as exc:
                logger.error("Computer pick validation error in draft %s: %s", draft_id, exc)
                await manager.broadcast(
                    draft_id,
                    build_error_event(f"Computer pick failed: {exc}"),
                )
                break

            try:
                session.persistence.save_draft(state)
            except OSError as exc:
                logger.warning("Auto-save failed for draft %s: %s", draft_id, exc)

            # Build and broadcast the pick event
            info = state.player_data.get(pick.player_id, {})
            overall_rank = info.get("overall_rank")
            delta = (pick.pick_number - overall_rank) if overall_rank else None

            pick_resp = PickResponse(
                pick_number=pick.pick_number,
                round=pick.round,
                team_id=pick.team_id,
                player_id=pick.player_id,
                player_name=info.get("name", pick.player_id),
                position=info.get("position", ""),
                nfl_team=info.get("team", ""),
                slot=pick.slot,
                timestamp=pick.timestamp,
                reach_delta=delta,
                reach_label=_reach_label(delta) if delta is not None else "",
            )

            await manager.broadcast(
                draft_id,
                build_pick_made_event(pick_resp, draft_state_to_response(state)),
            )

        if state.is_complete:
            await manager.broadcast(
                draft_id,
                build_draft_complete_event(draft_state_to_response(state)),
            )


async def fast_sim_chain(draft_id: str) -> None:
    """Simulate all remaining picks instantly (no delay, all teams including human).

    Mirrors the CLI's 'sim' command: uses ComputerDrafter for every remaining
    turn, broadcasts pick_made after each pick, then draft_complete at the end.
    """
    session = SessionManager.get_session(draft_id)
    if session is None:
        logger.warning("fast_sim_chain: session %s not found", draft_id)
        return

    async with session.lock:
        state = session.draft_state

        while not state.is_complete:
            current_team = state.get_current_team()

            available = session.controller.get_available_players()
            rules = DraftRules(state)
            legal = [
                p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
            ]

            if not legal:
                logger.warning(
                    "fast_sim_chain: no legal picks for team %s in draft %s",
                    current_team.team_name,
                    draft_id,
                )
                await manager.broadcast(
                    draft_id,
                    build_error_event(f"No legal picks available for {current_team.team_name}"),
                )
                break

            player_id = session.computer_drafter.make_pick(state, legal, current_team.team_id)

            try:
                pick = session.controller.make_pick(current_team.team_id, player_id)
            except ValidationError as exc:
                logger.error("fast_sim_chain validation error in draft %s: %s", draft_id, exc)
                await manager.broadcast(
                    draft_id,
                    build_error_event(f"Sim pick failed: {exc}"),
                )
                break

            try:
                session.persistence.save_draft(state)
            except OSError as exc:
                logger.warning("Auto-save failed for draft %s: %s", draft_id, exc)

            info = state.player_data.get(pick.player_id, {})
            overall_rank = info.get("overall_rank")
            delta = (pick.pick_number - overall_rank) if overall_rank else None

            pick_resp = PickResponse(
                pick_number=pick.pick_number,
                round=pick.round,
                team_id=pick.team_id,
                player_id=pick.player_id,
                player_name=info.get("name", pick.player_id),
                position=info.get("position", ""),
                nfl_team=info.get("team", ""),
                slot=pick.slot,
                timestamp=pick.timestamp,
                reach_delta=delta,
                reach_label=_reach_label(delta) if delta is not None else "",
            )

            await manager.broadcast(
                draft_id,
                build_pick_made_event(pick_resp, draft_state_to_response(state)),
            )

            # Yield to the event loop so WS messages are flushed between picks
            await asyncio.sleep(0)

        if state.is_complete:
            await manager.broadcast(
                draft_id,
                build_draft_complete_event(draft_state_to_response(state)),
            )

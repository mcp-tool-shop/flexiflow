"""Fixture states for testing dotted path imports."""

from flexiflow.state_machine import State


class FixtureInitial(State):
    """A simple fixture state for testing custom state loading."""

    async def handle_message(self, message, component):
        # Always stays in same state, just for testing import works
        return False, self


class AnotherFixtureState(State):
    """Another fixture state to test multiple imports."""

    async def handle_message(self, message, component):
        if message.get("type") == "advance":
            return True, FixtureInitial()
        return False, self


# Not a State subclass - for error testing
class NotAState:
    """This is not a State subclass, used for error testing."""
    pass


# StatePack fixture for testing pack loader
class FixturePack:
    """A StatePack implementation for testing dotted path loading."""

    @property
    def name(self) -> str:
        return "fixture"

    def provides(self) -> dict:
        from flexiflow.statepack import StateSpec
        return {
            "FixtureState": StateSpec(FixtureInitial, "A test fixture state"),
        }

    def transitions(self) -> list:
        return []

    def depends_on(self) -> set:
        return set()


# Pre-instantiated pack for testing instance loading
fixture_pack_instance = FixturePack()


# StatePack with transitions for visualization testing
class SessionPack:
    """A StatePack with transitions for visualization testing."""

    @property
    def name(self) -> str:
        return "session"

    def provides(self) -> dict:
        from flexiflow.statepack import StateSpec
        return {
            "SessionIdle": StateSpec(FixtureInitial, "Waiting for user action"),
            "SessionActive": StateSpec(AnotherFixtureState, "Processing request"),
        }

    def transitions(self) -> list:
        from flexiflow.statepack import TransitionSpec
        return [
            TransitionSpec("SessionIdle", "start", "SessionActive"),
            TransitionSpec("SessionActive", "complete", "SessionIdle"),
            TransitionSpec("SessionActive", "timeout", "SessionIdle", guard="is_expired"),
        ]

    def depends_on(self) -> set:
        return set()


session_pack_instance = SessionPack()


# StatePack with transition to unknown state (for testing unknown state handling)
class BrokenTransitionPack:
    """A StatePack with a transition to a non-existent state."""

    @property
    def name(self) -> str:
        return "broken"

    def provides(self) -> dict:
        from flexiflow.statepack import StateSpec
        return {
            "BrokenStart": StateSpec(FixtureInitial, "Start state"),
        }

    def transitions(self) -> list:
        from flexiflow.statepack import TransitionSpec
        return [
            TransitionSpec("BrokenStart", "go", "NonExistentState"),
            TransitionSpec("UnknownSource", "back", "BrokenStart"),
        ]

    def depends_on(self) -> set:
        return set()


broken_pack_instance = BrokenTransitionPack()

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4


class WorkflowState(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


@dataclass(frozen=True)
class Trigger:
    """Declarative workflow trigger matched against a normalized Event."""

    event_type: str

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError("Trigger event_type cannot be empty")

    @classmethod
    def create(cls, event_type: str) -> Trigger:
        return cls(event_type=event_type)


@dataclass(frozen=True)
class Condition:
    """Declarative condition attached to a workflow step."""

    left_operand: str
    operator: str
    right_operand: object

    def __post_init__(self) -> None:
        if not self.left_operand.strip():
            raise ValueError("Condition left_operand cannot be empty")
        if not self.operator.strip():
            raise ValueError("Condition operator cannot be empty")

    @classmethod
    def create(
        cls,
        left_operand: str,
        operator: str,
        right_operand: object,
    ) -> Condition:
        return cls(
            left_operand=left_operand,
            operator=operator,
            right_operand=right_operand,
        )


@dataclass(frozen=True)
class WorkflowParameter:
    name: str
    type: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Workflow parameter name cannot be empty")
        if self.type not in {"string", "integer", "number", "boolean"}:
            raise ValueError("Unsupported workflow parameter type")

    @classmethod
    def create(cls, name: str, type: str) -> WorkflowParameter:
        return cls(name=name.strip(), type=type.strip())


@dataclass(frozen=True)
class WorkflowStep:
    id: UUID
    name: str
    capability: str
    condition: Condition | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("WorkflowStep name cannot be empty")
        if not self.capability.strip():
            raise ValueError("WorkflowStep capability cannot be empty")
        if self.condition is not None and not isinstance(self.condition, Condition):
            raise ValueError("WorkflowStep condition must be a Condition instance")

    @classmethod
    def create(
        cls,
        name: str,
        capability: str,
        condition: Condition | None = None,
    ) -> WorkflowStep:
        return cls(
            id=uuid4(),
            name=name,
            capability=capability,
            condition=condition,
        )


@dataclass
class Workflow:
    id: UUID
    name: str
    _steps: list[WorkflowStep]
    state: WorkflowState
    _triggers: list[Trigger] = field(default_factory=list)
    _supported_goals: tuple[str, ...] = ()
    _required_parameters: tuple[str, ...] = ()
    _parameter_types: tuple[WorkflowParameter, ...] = ()
    _automation_domain: str | None = None
    _discovery_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Workflow name cannot be empty")
        if any(not isinstance(step, WorkflowStep) for step in self._steps):
            raise ValueError("Workflow steps must be WorkflowStep instances")
        if any(not isinstance(trigger, Trigger) for trigger in self._triggers):
            raise ValueError("Workflow triggers must be Trigger instances")
        if any(not isinstance(goal, str) for goal in self._supported_goals):
            raise ValueError("Workflow supported goals must be strings")
        if any(not goal.strip() for goal in self._supported_goals):
            raise ValueError("Workflow supported goals cannot be empty")
        if len(set(self._supported_goals)) != len(self._supported_goals):
            raise ValueError("Workflow supported goals must be unique")
        if any(not isinstance(parameter, str) for parameter in self._required_parameters):
            raise ValueError("Workflow required parameters must be strings")
        if any(not parameter.strip() for parameter in self._required_parameters):
            raise ValueError("Workflow required parameters cannot be empty")
        if len(set(self._required_parameters)) != len(self._required_parameters):
            raise ValueError("Workflow required parameters must be unique")
        if any(not isinstance(parameter, WorkflowParameter) for parameter in self._parameter_types):
            raise ValueError("Workflow parameter types must be WorkflowParameter instances")
        parameter_names = {parameter.name for parameter in self._parameter_types}
        if not parameter_names.issubset(set(self._required_parameters)):
            raise ValueError("Workflow parameter types must reference required parameters")
        if len(parameter_names) != len(self._parameter_types):
            raise ValueError("Workflow parameter types must be unique")
        if self._automation_domain is not None and (not isinstance(self._automation_domain, str) or not self._automation_domain.strip()):
            raise ValueError("Workflow automation domain must be a non-empty string")
        if any(not isinstance(tag, str) or not tag.strip() for tag in self._discovery_tags):
            raise ValueError("Workflow discovery tags must be non-empty strings")
        if len(set(self._discovery_tags)) != len(self._discovery_tags):
            raise ValueError("Workflow discovery tags must be unique")

    @property
    def steps(self) -> tuple[WorkflowStep, ...]:
        return tuple(self._steps)

    @property
    def triggers(self) -> tuple[Trigger, ...]:
        return tuple(self._triggers)

    @property
    def supported_goals(self) -> tuple[str, ...]:
        return self._supported_goals

    @property
    def required_parameters(self) -> tuple[str, ...]:
        return self._required_parameters

    @property
    def parameter_types(self) -> tuple[WorkflowParameter, ...]:
        return self._parameter_types

    @property
    def automation_domain(self) -> str | None:
        return self._automation_domain

    @property
    def discovery_tags(self) -> tuple[str, ...]:
        return self._discovery_tags

    @classmethod
    def create(
        cls,
        name: str,
        steps: list[WorkflowStep],
        triggers: list[Trigger] | None = None,
        supported_goals: list[str] | None = None,
        required_parameters: list[str] | None = None,
        parameter_types: list[WorkflowParameter] | None = None,
        automation_domain: str | None = None,
        discovery_tags: list[str] | None = None,
    ) -> Workflow:
        return cls(
            id=uuid4(),
            name=name,
            _steps=list(steps),
            state=WorkflowState.DRAFT,
            _triggers=list(triggers or []),
            _supported_goals=tuple(supported_goals or []),
            _required_parameters=tuple(required_parameters or []),
            _parameter_types=tuple(parameter_types or []),
            _automation_domain=automation_domain.strip() if automation_domain is not None else None,
            _discovery_tags=tuple(tag.strip() for tag in (discovery_tags or [])),
        )

    def publish(self) -> None:
        if self.state != WorkflowState.DRAFT:
            raise ValueError(
                "Workflow can only be published from DRAFT state"
            )

        if not self._steps:
            raise ValueError(
                "Workflow must have at least one step before publishing"
            )

        self.state = WorkflowState.PUBLISHED

    def add_step(self, step: WorkflowStep) -> None:
        if self.state != WorkflowState.DRAFT:
            raise ValueError(
                "Steps can only be added to a Workflow in DRAFT state"
            )

        self._steps.append(step)

    def add_trigger(self, trigger: Trigger) -> None:
        if self.state != WorkflowState.DRAFT:
            raise ValueError(
                "Triggers can only be added to a Workflow in DRAFT state"
            )

        self._triggers.append(trigger)

_G='sm'
import log
_F='state machine has not been started'
_E='child_sm and parent_sm must be different'
_D='initial state is not set'
_C=False
_B=True
_A=None
class State:
	def __init__(A,name,child_sm=_A):A._name=name;A._entry_callbacks=[];A._exit_callbacks=[];A._child_state_machine=child_sm;A._parent_state_machine=_A
	def __repr__(A):return f"State={A._name}"
	def __eq__(A,other):
		if other.name==A._name:return _B
		else:return _C
	def __ne__(A,other):return not A.__eq__(other)
	def __call__(A,data):0
	def on_entry(A,callback):A._entry_callbacks.append(callback)
	def on_exit(A,callback):A._exit_callbacks.append(callback)
	def set_child_sm(A,child_sm):
		B=child_sm
		if not isinstance(B,StateMachine):raise TypeError('child_sm must be the type of StateMachine')
		if A._parent_state_machine and A._parent_state_machine==B:raise ValueError(_E)
		A._child_state_machine=B
	def set_parent_sm(A,parent_sm):
		B=parent_sm
		if not isinstance(B,StateMachine):raise TypeError('parent_sm must be the type of StateMachine')
		if A._child_state_machine and A._child_state_machine==B:raise ValueError(_E)
		A._parent_state_machine=B
	def start(A,data):
		log.debug(_G,f"Entering {A._name}")
		for B in A._entry_callbacks:B(data)
		if A._child_state_machine is not _A:A._child_state_machine.start(data)
	def stop(A,data):
		log.debug(_G,f"Exiting {A._name}")
		for B in A._exit_callbacks:B(data)
		if A._child_state_machine is not _A:A._child_state_machine.stop(data)
	def has_child_sm(A):return _B if A._child_state_machine else _C
	@property
	def name(self):return self._name
	@property
	def child_sm(self):return self._child_state_machine
	@property
	def parent_sm(self):return self._parent_state_machine
class ExitState(State):
	def __init__(A,status='Normal'):A._name='ExitState';A._status=status;super().__init__(A._status+A._name)
	@property
	def status(self):return self._status
class Event:
	def __init__(A,name):A._name=name
	def __repr__(A):return f"Event={A._name}"
	def __eq__(A,other):
		if other.name==A._name:return _B
		else:return _C
	def __ne__(A,other):return not A.__eq__(other)
	@property
	def name(self):return self._name
class Transition:
	def __init__(A,event,src,dst):A._event=event;A._source_state=src;A._destination_state=dst;A._condition=_A;A._action=_A
	def __call__(A,data):raise NotImplementedError
	def add_condition(A,callback):A._condition=callback
	def add_action(A,callback):A._action=callback
	@property
	def event(self):return self._event
	@property
	def source_state(self):return self._source_state
	@property
	def destination_state(self):return self._destination_state
class NormalTransition(Transition):
	def __init__(A,source_state,destination_state,event):C=destination_state;B=source_state;super().__init__(event,B,C);A._from=B;A._to=C
	def __call__(A,data):
		B=data
		if not A._condition or A._condition(B):
			log.info(_G,f"NormalTransition from {A._from} to {A._to} caused by {A._event}")
			if A._action:A._action(B)
			A._from.stop(B);A._to.start(B)
	def __repr__(A):return f"Transition {A._from} to {A._to} by {A._event}"
class SelfTransition(Transition):
	def __init__(B,source_state,event):A=source_state;super().__init__(event,A,A);B._state=A
	def __call__(A,data):
		B=data
		if not A._condition or A._condition(B):
			log.info(_G,f"SelfTransition {A._state}")
			if A._action:A._action(B)
			A._state.stop(B);A._state.start(B)
	def __repr__(A):return f"SelfTransition on {A._state}"
class NullTransition(Transition):
	def __init__(B,source_state,event):A=source_state;super().__init__(event,A,A);B._state=A
	def __call__(A,data):
		if not A._condition or A._condition(data):
			log.info(_G,f"NullTransition {A._state}")
			if A._action:A._action(data)
	def __repr__(A):return f"NullTransition on {A._state}"
class StateMachine:
	def __init__(A,name):A._name=name;A._states=[];A._events=[];A._transitions=[];A._initial_state=_A;A._current_state=_A;A._exit_callback=_A;A._exit_state=ExitState();A.add_state(A._exit_state);A._exited=_B
	def __eq__(A,other):
		if other.name==A._name:return _B
		else:return _C
	def __ne__(A,other):return not A.__eq__(other)
	def __str__(A):return A._name
	def start(A,data):
		if not A._initial_state:raise ValueError(_D)
		A._current_state=A._initial_state;A._exited=_C;A._current_state.start(data)
	def stop(A,data):
		if not A._initial_state:raise ValueError(_D)
		if A._current_state is _A:raise ValueError(_F)
		A._current_state.stop(data);A._current_state=A._exit_state;A._exited=_B
	def on_exit(A,callback):A._exit_callback=callback
	def is_running(A):
		if A._current_state and A._current_state!=A._exit_state:return _B
		else:return _C
	def add_state(A,state,initial_state=_C):
		B=state
		if B in A._states:raise ValueError('attempting to add same state twice')
		A._states.append(B);B.set_parent_sm(A)
		if not A._initial_state and initial_state:A._initial_state=B
	def add_event(A,event):A._events.append(event)
	def add_transition(A,src,dst,evt):
		B=_A
		if src in A._states and dst in A._states and evt in A._events:B=NormalTransition(src,dst,evt);A._transitions.append(B)
		return B
	def add_self_transition(A,state,evt):
		C=state;B=_A
		if C in A._states and evt in A._events:B=SelfTransition(C,evt);A._transitions.append(B)
		return B
	def add_null_transition(A,state,evt):
		C=state;B=_A
		if C in A._states and evt in A._events:B=NullTransition(C,evt);A._transitions.append(B)
		return B
	def trigger_event(A,evt,data=_A,propagate=_C):
		E=propagate;D=data;B=evt;F=_C
		if not A._initial_state:raise ValueError(_D)
		if A._current_state is _A:raise ValueError(_F)
		if E and A._current_state.has_child_sm():log.debug(_G,f"Propagating evt {B} from {A} to {A._current_state.child_sm}");A._current_state.child_sm.trigger_event(B,D,E)
		else:
			for C in A._transitions:
				if C.source_state==A._current_state and C.event==B:
					A._current_state=C.destination_state;C(D)
					if isinstance(A._current_state,ExitState)and A._exit_callback and not A._exited:A._exited=_B;A._exit_callback(A._current_state,D)
					F=_B;break
			if not F:log.warning(_G,f"Event {B} is not valid in state {A._current_state}")
	@property
	def exit_state(self):return self._exit_state
	@property
	def current_state(self):return self._current_state
	@property
	def name(self):return self._name
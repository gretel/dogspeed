_K='after'
_J='before'
_I='action'
_H='to_state'
_G='from_state'
_F='enter'
_E='exit'
_D='condition'
_C=False
_B=True
_A=None
import log,sys
from collections import defaultdict,deque
if str(type(defaultdict)).find('module')>0:defaultdict=defaultdict.defaultdict
def patch_deque(deque_module):
    class A:
        def __init__(C,iterable=_A,maxlen=0):
            B=maxlen;A=iterable
            if A is _A:A=[]
            if B in[_A,0]:B=float('Inf')
            C.q=deque_module.deque(A);C.maxlen=B
        def pop(A):return A.q.pop()
        def append(A,item):
            if A.maxlen>0 and len(A.q)>=A.maxlen:A.q.popleft()
            A.q.append(item)
        def __getattr__(A,name):return getattr(A.q,name)
        def __bool__(A):return len(A.q)>0
        def __len__(A):return len(A.q)
        def __iter__(A):return iter(A.q)
        def __getitem__(A,key):return A.q[key]
    return A
try:test_deque=deque(maxlen=1)
except TypeError:
    if hasattr(deque,'deque'):deque=patch_deque(deque)
    else:
        class MockDequeModule:deque=deque
        deque=patch_deque(MockDequeModule)
else:del test_deque
class AnyEvent:0
any_event=AnyEvent()
def is_iterable(obj):
    try:iter(obj)
    except TypeError:return _C
    return _B
class StateMachineException(Exception):0
class Event:
    def __init__(A,name,input=_A,**B):A.name=name;A.input=input;A.propagate=_B;A.cargo=B;A.state_machine=_A
    def __repr__(A):return '<Event {0}, input={1}, cargo={2} ({3})>'.format(A.name,A.input,A.cargo,hex(id(A)))
class State:
    def __init__(A,name):A.parent=_A;A.name=name;A.handlers={};A.initial=_C;A.register_handlers()
    def __repr__(A):return '<State {0} ({1})>'.format(A.name,hex(id(A)))
    def register_handlers(A):0
    def is_substate(B,state):
        C=state
        if C is B:return _B
        A=B.parent
        while A:
            if A is C:return _B
            A=A.parent
        return _C
    def _on(B,event):
        A=event
        if A.name in B.handlers:A.propagate=_C;B.handlers[A.name](B,A)
        if B.parent and A.propagate and A.name not in(_E,_F):B.parent._on(A)
    def _nop(A,state,event):del state;del event;return _B
class TransitionsContainer:
    def __init__(A,machine):A._machine=machine;A._transitions=defaultdict(list)
    def add(A,key,transition):A._transitions[key].append(transition)
    def get(B,event):A=event;C=B._machine.state,A.name,A.input;return B._get_transition_matching_condition(C,A)
    def _get_transition_matching_condition(B,key,event):
        D=event;C=key;E=B._machine.leaf_state
        for A in B._transitions[C]:
            if A[_D](E,D)is _B:return A
        C=B._machine.state,any_event,D.input
        for A in B._transitions[C]:
            if A[_D](E,D)is _B:return A
        return _A
class Stack:
    def __init__(A,maxlen=_A):A.deque=deque(maxlen=maxlen)
    def pop(A):return A.deque.pop()
    def push(A,value):A.deque.append(value)
    def peek(A):return A.deque[-1]
    def __repr__(A):return str(list(A.deque))
class StateMachine(State):
    STACK_SIZE=32
    def __init__(A,name):super(StateMachine,A).__init__(name);A.states=set();A.state=_A;A._transitions=TransitionsContainer(A);A.state_stack=Stack(maxlen=StateMachine.STACK_SIZE);A.leaf_state_stack=Stack(maxlen=StateMachine.STACK_SIZE);A.stack=Stack();A._leaf_state=_A
    def add_state(B,state,initial=_C):C=initial;A=state;Validator(B).validate_add_state(A,C);A.initial=C;A.parent=B;B.states.add(A)
    def add_states(A,*B):
        for C in B:A.add_state(C)
    def set_initial_state(B,state):A=state;Validator(B).validate_set_initial(A);A.initial=_B
    @property
    def initial_state(self):
        for A in self.states:
            if A.initial:return A
        return _A
    @property
    def root_machine(self):
        A=self
        while A.parent:A=A.parent
        return A
    def add_transition(A,from_state,to_state,events,input=_A,action=_A,condition=_A,before=_A,after=_A):
        H=events;G=to_state;F=after;E=before;D=condition;C=action;B=from_state
        if input is _A:input=tuple([_A])
        if C is _A:C=A._nop
        if E is _A:E=A._nop
        if F is _A:F=A._nop
        if D is _A:D=A._nop
        Validator(A).validate_add_transition(B,G,H,input)
        for I in input:
            for J in H:K=B,J,I;L={_G:B,_H:G,_I:C,_D:D,_J:E,_K:F};A._transitions.add(K,L)
    def _get_transition(C,event):
        A=C.leaf_state.parent
        while A:
            B=A._transitions.get(event)
            if B:return B
            A=A.parent
        return _A
    @property
    def leaf_state(self):return self.root_machine._leaf_state
    def _get_leaf_state(B,state):
        A=state
        while hasattr(A,'state')and A.state is not _A:A=A.state
        return A
    def initialize(A):
        B=deque();B.append(A)
        while B:
            C=B.popleft();Validator(A).validate_initial_state(C);C.state=C.initial_state
            for D in C.states:
                if isinstance(D,StateMachine):B.append(D)
        A._leaf_state=A._get_leaf_state(A)
    def dispatch(B,event):
        A=event;A.state_machine=B;D=B.leaf_state;D._on(A);C=B._get_transition(A)
        if C is _A:return
        E=C[_H];F=C[_G];C[_J](D,A);G=B._exit_states(A,F,E);C[_I](D,A);B._enter_states(A,G,E);C[_K](B.leaf_state,A)
    def _exit_states(B,event,from_state,to_state):
        D=from_state;C=to_state
        if C is _A:return _A
        A=B.leaf_state;B.leaf_state_stack.push(A)
        while A.parent and not(D.is_substate(A)and C.is_substate(A))or A==D==C:log.debug('exiting %s',A.name);E=Event(_E,propagate=_C,source_event=event);E.state_machine=B;B.root_machine._leaf_state=A;A._on(E);A.parent.state_stack.push(A);A.parent.state=A.parent.initial_state;A=A.parent
        return A
    def _enter_states(B,event,top_state,to_state):
        C=to_state
        if C is _A:return
        D=[];A=B._get_leaf_state(C)
        while A.parent and A!=top_state:D.append(A);A=A.parent
        for A in reversed(D):log.debug('entering %s',A.name);E=Event(_F,propagate=_C,source_event=event);E.state_machine=B;B.root_machine._leaf_state=A;A._on(E);A.parent.state=A
    def set_previous_leaf_state(A,event=_A):
        B=event
        if B is not _A:B.state_machine=A
        D=A.leaf_state
        try:C=A.leaf_state_stack.peek()
        except IndexError:return
        E=A._exit_states(B,D,C);A._enter_states(B,E,C)
    def revert_to_previous_leaf_state(A,event=_A):
        A.set_previous_leaf_state(event)
        try:A.leaf_state_stack.pop();A.leaf_state_stack.pop()
        except IndexError:return
class Validator:
    def __init__(A,state_machine):A.state_machine=state_machine;A.template='Machine "{0}" error: {1}'.format(A.state_machine.name,'{0}')
    def _raise(A,msg):raise StateMachineException(A.template.format(msg))
    def validate_add_state(B,state,initial):
        A=state
        if not isinstance(A,State):C='Unable to add state of type {0}'.format(type(A));B._raise(C)
        B._validate_state_already_added(A)
        if initial is _B:B.validate_set_initial(A)
    def _validate_state_already_added(A,state):
        D=state;F=A.state_machine.root_machine;B=deque();B.append(F)
        while B:
            C=B.popleft()
            if D in C.states and C is not A.state_machine:G='Machine "{0}" error: State "{1}" is already added to machine "{2}"'.format(A.state_machine.name,D.name,C.name);A._raise(G)
            for E in C.states:
                if isinstance(E,StateMachine):B.append(E)
    def validate_set_initial(B,state):
        C=state
        for A in B.state_machine.states:
            if A.initial is _B and A is not C:D='Unable to set initial state to "{0}". Initial state is already set to "{1}"'.format(C.name,A.name);B._raise(D)
    def validate_add_transition(A,from_state,to_state,events,input):A._validate_from_state(from_state);A._validate_to_state(to_state);A._validate_events(events);A._validate_input(input)
    def _validate_from_state(A,from_state):
        B=from_state
        if B not in A.state_machine.states:C='Unable to add transition from unknown state "{0}"'.format(B.name);A._raise(C)
    def _validate_to_state(B,to_state):
        A=to_state;C=B.state_machine.root_machine
        if A is _A:return
        elif A is C:return
        elif not A.is_substate(C):D='Unable to add transition to unknown state "{0}"'.format(A.name);B._raise(D)
    def _validate_events(B,events):
        A=events
        if not is_iterable(A):C='Unable to add transition, events is not iterable: {0}'.format(A);B._raise(C)
    def _validate_input(A,input):
        if not is_iterable(input):B='Unable to add transition, input is not iterable: {0}'.format(input);A._raise(B)
    def validate_initial_state(B,machine):
        A=machine
        if A.states and not A.initial_state:C='Machine "{0}" has no initial state'.format(A.name);B._raise(C)
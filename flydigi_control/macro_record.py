"""Passive native-report recording into bounded, editable macro actions."""
import math
import os
import select
import time
from .macro_bank import Action
from .protocol import BUTTON_NAMES, parse_input, strip_report_id
from .transport import discover

# IDs 0–23 are the raw report's ordinary and extra remappable buttons.
KEYS = {name:index for index,name in enumerate(BUTTON_NAMES[:24])}


def direction(pair):
    """Eight directions above half travel, otherwise Center (macro ID 160)."""
    x,y=pair
    if math.hypot(x,y)<16384:
        return 160
    # Positive Y is up in the native report; vendor IDs run clockwise from Up.
    return 161+int(math.floor(math.atan2(x,y)/(math.pi/4)+.5))%8


class Recorder:
    def __init__(self, max_actions=256):
        if type(max_actions) is not int or not 2<=max_actions<=256:
            raise ValueError('At least two free actions are needed to record')
        self.max_actions=max_actions
        self.actions=[]
        self.buttons=set()
        self.sticks=(160,160)
        self.armed=False
        self.origin=None
        self.last_ms=0
        self.last_time=None
        self.done=False

    def feed(self, state, now):
        if self.done:return
        if not math.isfinite(now) or (self.last_time is not None and now<self.last_time):
            raise ValueError('Recording clock moved backwards or is invalid')
        self.last_time=now
        buttons={KEYS[name] for name in state.buttons if name in KEYS}
        sticks=tuple(direction(pair) for pair in (state.left_stick,state.right_stick))
        if not self.armed:
            # The A press that starts recording must be released first.
            if not buttons and sticks==(160,160):self.armed=True
            return
        events=[]
        events.extend((key,0) for key in sorted(self.buttons-buttons))
        events.extend((key,1) for key in sorted(buttons-self.buttons))
        events.extend((value,side+2) for side,value in enumerate(sticks) if value!=self.sticks[side])
        if not events:return
        close_count=len(buttons)+sum(value!=160 for value in sticks)
        if len(self.actions)+len(events)+close_count>self.max_actions:
            self.finish(now);return
        if self.origin is None:self.origin=now
        timestamp=round((now-self.origin)*1000)
        if timestamp>65535:
            self.finish(now);return
        for key,event in events:
            self.actions.append(Action(timestamp-self.last_ms,key,event))
            self.last_ms=timestamp
        self.buttons,self.sticks=buttons,sticks

    def finish(self, now):
        if self.done:return tuple(self.actions)
        if not math.isfinite(now) or (self.last_time is not None and now<self.last_time):
            raise ValueError('Recording clock moved backwards or is invalid')
        timestamp=min(65535,round((now-self.origin)*1000)) if self.origin is not None else 0
        # Reserve these releases throughout recording so timeout/limit cannot
        # leave the stored macro holding a button or pointing a stick forever.
        for key,event in [(key,0) for key in sorted(self.buttons)]+[(160,side+2) for side,value in enumerate(self.sticks) if value!=160]:
            self.actions.append(Action(timestamp-self.last_ms,key,event));self.last_ms=timestamp
        self.done=True
        return tuple(self.actions)


def record(path, seconds, max_actions, progress):
    if not 0<seconds<=60:
        raise ValueError('Choose a recording duration up to 60 seconds')
    if path not in {d['path'] for d in discover()}:
        raise ValueError('Choose a connected Vader 5 Pro interface')
    recorder=Recorder(max_actions)
    fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_CLOEXEC)
    start=time.monotonic();last_input=start;last_progress=start-1
    try:
        while not recorder.done and (remaining:=start+seconds-time.monotonic())>0:
            if not select.select([fd],[],[],min(remaining,.2))[0]:
                if time.monotonic()-last_input>3:
                    raise RuntimeError('Native reports stopped; recording was not applied')
                continue
            try:raw=os.read(fd,64)
            except BlockingIOError:continue
            if not raw:raise OSError('Controller disconnected; recording was not applied')
            state=parse_input(strip_report_id(raw))
            if state is None:
                if time.monotonic()-last_input>3:
                    raise RuntimeError('Native reports stopped; recording was not applied')
                continue
            now=time.monotonic();last_input=now;recorder.feed(state,now)
            if now-last_progress>=.1:
                progress({'armed':recorder.armed,'remaining':max(0,math.ceil(start+seconds-now)),
                          'actions':len(recorder.actions)})
                last_progress=now
        return recorder.finish(time.monotonic())
    finally:os.close(fd)
